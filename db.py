#!/usr/bin/env python3
"""
db.py - 데이터베이스 관리 모듈
- SQLite DB 연결 (get_db)
- 테이블 생성/동적 마이그레이션 (init_db_schema)
- 마스터 계정(EMP-001) 강제 보장
"""

import sqlite3, os, shutil, glob, datetime, threading, time

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'building_manager.db')
BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_backups', 'auto')
BACKUP_KEEP = 30  # 최신 N개만 롤링 보관


def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn


def backup_db(reason='auto'):
    """building_manager.db를 일관된 스냅샷으로 _backups/auto에 롤링 저장. 반환: 백업 경로 or None"""
    if not os.path.exists(DB_PATH):
        return None
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
    except Exception:
        return None
    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    dst = os.path.join(BACKUP_DIR, 'db_{}_{}.db'.format(ts, reason))
    try:
        s = sqlite3.connect(DB_PATH); d = sqlite3.connect(dst)
        with s, d:
            s.backup(d)                # 쓰기 도중에도 일관된 스냅샷
        d.close(); s.close()
    except Exception:
        try:
            shutil.copy2(DB_PATH, dst)  # 폴백: 단순 복사
        except Exception:
            return None
    try:                               # 롤링: 오래된 것 삭제
        for old in sorted(glob.glob(os.path.join(BACKUP_DIR, 'db_*.db')))[:-BACKUP_KEEP]:
            try: os.remove(old)
            except Exception: pass
    except Exception:
        pass
    return dst


def start_auto_backup(interval=300):
    """DB 파일이 바뀌면(=저장/수정 발생) interval초마다 자동 백업하는 데몬 스레드."""
    def _loop():
        last = os.path.getmtime(DB_PATH) if os.path.exists(DB_PATH) else 0
        while True:
            time.sleep(interval)
            try:
                m = os.path.getmtime(DB_PATH) if os.path.exists(DB_PATH) else 0
                if m and m != last:
                    backup_db('auto'); last = m
            except Exception:
                pass
    threading.Thread(target=_loop, daemon=True).start()


def init_db_schema():
    """DB 초기화 및 동적 ALTER TABLE 자동 마이그레이션 (데이터 영구 보존)"""
    conn = get_db()
    try:
        cur = conn.cursor()

        # 1. contacts (팀원, 세입자, 임대인, 중개사, 협력사)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT DEFAULT 'staff',
            company_or_name TEXT,
            representative_name TEXT,
            contact_info TEXT,
            email TEXT,
            password_hash TEXT,
            role TEXT DEFAULT 'office_worker',
            role_name TEXT DEFAULT 'office_worker',
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")

        # 2. buildings (건물)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS buildings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            address TEXT,
            floors INTEGER DEFAULT 1,
            rooms_count INTEGER DEFAULT 1,
            is_active INTEGER DEFAULT 1
        )""")

        # 3. rooms (호실)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            building_id INTEGER,
            floor_no INTEGER DEFAULT 1,
            room_no TEXT,
            area_sqm REAL DEFAULT 0.0,
            current_room_status TEXT DEFAULT '공실',
            is_active INTEGER DEFAULT 1
        )""")

        # 4. contracts (계약)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS contracts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER,
            host_address_full TEXT,
            owner_contact_id INTEGER DEFAULT 1,
            tenant_contact_id INTEGER DEFAULT 0,
            broker_id INTEGER DEFAULT 0,
            lease_type TEXT DEFAULT '월세',
            deposit_amount INTEGER DEFAULT 0,
            monthly_rent INTEGER DEFAULT 0,
            maintenance_fee INTEGER DEFAULT 0,
            commission_fee INTEGER DEFAULT 0,
            start_date TEXT,
            end_date TEXT,
            documents_json TEXT,
            special_terms TEXT,
            is_active INTEGER DEFAULT 1
        )""")

        # 5. bills (공과금)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS bills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER,
            contact_id INTEGER DEFAULT 0,
            bill_type TEXT,
            elec_usage INTEGER DEFAULT 0,
            water_cost INTEGER DEFAULT 0,
            gas_cost INTEGER DEFAULT 0,
            net_cost INTEGER DEFAULT 0,
            due_date TEXT,
            status TEXT DEFAULT '미납(고지대기)',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")

        # 6. incidents (유지보수/파손신고)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER,
            category TEXT,
            reported_at TEXT,
            completed_at TEXT,
            description TEXT,
            reported_by_name TEXT,
            estimated_cost INTEGER DEFAULT 0,
            status TEXT DEFAULT '접수중',
            photos_json TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")

        # 기존 DB 스키마 꼬임 대비 동적 컬럼 마이그레이션 (데이터 손실 없음)
        migrations = [
            ("contacts", "category", "TEXT DEFAULT 'staff'"),
            ("contacts", "role_name", "TEXT DEFAULT 'office_worker'"),
            ("contacts", "password_hash", "TEXT"),
            ("contacts", "role", "TEXT DEFAULT 'office_worker'"),
            ("contacts", "is_active", "INTEGER DEFAULT 1"),
            ("contacts", "documents_json", "TEXT"),
            ("contracts", "special_terms", "TEXT"),
            ("contracts", "tenant_contact_id", "INTEGER DEFAULT 0"),
            ("contracts", "owner_contact_id", "INTEGER DEFAULT 1"),
            ("contracts", "broker_id", "INTEGER DEFAULT 0"),
            ("bills", "elec_usage", "INTEGER DEFAULT 0"),
            ("bills", "water_cost", "INTEGER DEFAULT 0"),
            ("bills", "gas_cost", "INTEGER DEFAULT 0"),
            ("bills", "net_cost", "INTEGER DEFAULT 0"),
            ("bills", "due_date", "TEXT"),
            ("bills", "status", "TEXT DEFAULT '미납(고지대기)'"),
            ("incidents", "reported_by_name", "TEXT"),
            ("incidents", "estimated_cost", "INTEGER DEFAULT 0"),
            ("incidents", "photos_json", "TEXT")
        ]
        for table, col, col_def in migrations:
            try:
                cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}")
            except sqlite3.OperationalError:
                pass

        # 마스터 계정 (id=999 / EMP-001 / admin123) 강제 보장
        cur.execute("SELECT id FROM contacts WHERE id = 999 OR representative_name = 'EMP-001'")
        if not cur.fetchone():
            cur.execute("""
                INSERT INTO contacts (id, category, company_or_name, representative_name, contact_info, password_hash, role, role_name, is_active)
                VALUES (999, 'staff', '김자산(최상위관리자)', 'EMP-001', '010-0000-0000', 'admin123', 'super_admin', 'super_admin', 1)
            """)
        else:
            cur.execute("""
                UPDATE contacts 
                SET password_hash = 'admin123', role = 'super_admin', role_name = 'super_admin', is_active = 1 
                WHERE id = 999 OR representative_name = 'EMP-001'
            """)
        conn.commit()
    finally:
        conn.close()
