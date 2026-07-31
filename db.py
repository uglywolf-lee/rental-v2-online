#!/usr/bin/env python3
"""
db.py - 데이터베이스 관리 모듈
- SQLite DB 연결 (get_db)
- 테이블 생성/동적 마이그레이션 (init_db_schema)
- 마스터 계정(EMP-001) 강제 보장
"""

import sqlite3, os, sys, shutil, glob, datetime, threading, time

# 패키징(exe) 대응: 얼려진 실행파일이면 exe 폴더, 아니면 스크립트 폴더 기준
if getattr(sys, 'frozen', False):
    _APP_DIR = os.path.dirname(sys.executable)
else:
    _APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_APP_DIR, 'building_manager.db')
BACKUP_DIR = os.path.join(_APP_DIR, '_backups', 'auto')
BACKUP_KEEP = 30       # 자동(5분 단위) 최신 N개 롤링 보관
DAILY_DIR = os.path.join(_APP_DIR, '_backups', 'daily')
DAILY_KEEP = 30        # 일자별 최근 N일치 보관
# PC 내장 드라이브(사용자 폴더) 사본 — USB 유실/손상 대비 (앱이 USB에서 돌아도 PC에 사본 유지)
PC_BACKUP_DIR = os.path.join(os.path.expanduser('~'), '부동산백업')
# 첨부파일(계약서 사진·PDF·신분증) 실물 폴더 — DB에는 경로만 들어가므로 이 폴더가 없으면 계약서가 열리지 않는다
UPLOAD_DIR = os.path.join(_APP_DIR, 'uploads')


def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn


def _resolve_drive_dir():
    """구글 드라이브 동기화 폴더 찾기: 설정파일(drive_backup_path.txt) 우선, 없으면 자동탐지."""
    cfg = os.path.join(_APP_DIR, 'drive_backup_path.txt')
    try:
        if os.path.exists(cfg):
            for line in open(cfg, encoding='utf-8'):
                line = line.strip().strip('"')
                if line and not line.startswith('#') and os.path.isdir(line):
                    return line
    except Exception:
        pass
    home = os.path.expanduser('~')
    for c in [os.path.join(home, 'My Drive'), os.path.join(home, 'Google Drive'),
              'G:\\My Drive', 'G:\\내 드라이브', 'H:\\My Drive']:
        try:
            if os.path.isdir(c):
                return c
        except Exception:
            pass
    return None


def _needs_copy(src, dst):
    """대상이 없거나, 원본이 더 새로우면 True. (하루치 백업이 갱신될 때 사본도 따라가게)"""
    try:
        if not os.path.exists(dst):
            return True
        return os.path.getmtime(src) > os.path.getmtime(dst) + 1
    except Exception:
        return True


def backup_to_drive(src_file):
    """일자별 백업 파일을 드라이브 동기화 폴더(<드라이브>/부동산백업)로 복사. 폴더 없으면 조용히 통과."""
    base = _resolve_drive_dir()
    if not base or not src_file or not os.path.exists(src_file):
        return None
    try:
        target = os.path.join(base, '부동산백업')
        os.makedirs(target, exist_ok=True)
        dst = os.path.join(target, os.path.basename(src_file))
        if _needs_copy(src_file, dst):
            shutil.copy2(src_file, dst)
        return dst
    except Exception:
        return None


def backup_to_pc(src_file):
    """USB 유실 대비: 백업 사본을 PC 내장 드라이브(사용자폴더\\부동산백업)에도 보관. 최근 DAILY_KEEP개."""
    if not src_file or not os.path.exists(src_file):
        return None
    try:
        # 앱이 이미 그 폴더 안에서 실행 중이면 중복 불필요 → 스킵
        if os.path.abspath(_APP_DIR) == os.path.abspath(PC_BACKUP_DIR):
            return None
        os.makedirs(PC_BACKUP_DIR, exist_ok=True)
        dst = os.path.join(PC_BACKUP_DIR, os.path.basename(src_file))
        if _needs_copy(src_file, dst):
            shutil.copy2(src_file, dst)
            for old in sorted(glob.glob(os.path.join(PC_BACKUP_DIR, 'db_*.db')))[:-DAILY_KEEP]:
                try: os.remove(old)
                except Exception: pass
        return dst
    except Exception:
        return None


def sync_uploads(base_dir):
    """계약서 사진·PDF 원본을 base_dir/uploads 로 증분 복사. 반환: (새로 복사한 개수, 전체 개수)

    uploads/ 안의 파일은 한번 저장되면 바뀌지 않으므로 '대상에 없는 것만' 복사하면 된다.
    → 매일 GB를 다시 복사하지 않고, 새 계약서만 몇 개 넘어간다.
    DB 백업만으로는 복구가 안 된다(DB엔 경로만 있고 실물은 여기 있음)."""
    if not base_dir or not os.path.isdir(UPLOAD_DIR):
        return (0, 0)
    copied = 0
    total = 0
    try:
        target_root = os.path.join(base_dir, 'uploads')
        for root, _dirs, files in os.walk(UPLOAD_DIR):
            rel = os.path.relpath(root, UPLOAD_DIR)
            tdir = target_root if rel == '.' else os.path.join(target_root, rel)
            for fn in files:
                if fn.startswith('.'):
                    continue
                total += 1
                src = os.path.join(root, fn)
                dst = os.path.join(tdir, fn)
                try:
                    if os.path.exists(dst) and os.path.getsize(dst) == os.path.getsize(src):
                        continue          # 이미 사본이 있고 크기도 같음 → 건너뜀
                    os.makedirs(tdir, exist_ok=True)
                    shutil.copy2(src, dst)
                    copied += 1
                except Exception:
                    pass                  # 한 파일이 실패해도 나머지는 계속 복사
    except Exception:
        pass
    return (copied, total)


def write_backup_status(lines):
    """백업이 조용히 실패하는 것을 막기 위한 사람이 읽는 기록 — _backups/백업상태.txt"""
    try:
        os.makedirs(os.path.join(_APP_DIR, '_backups'), exist_ok=True)
        p = os.path.join(_APP_DIR, '_backups', '백업상태.txt')
        with open(p, 'w', encoding='utf-8') as f:
            f.write('마지막 백업: {}\n\n'.format(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            for ln in lines:
                f.write(ln + '\n')
            f.write('\n※ 이 파일의 시각이 오늘이 아니면 백업이 멈춘 것입니다. 관리자에게 알려주세요.\n')
    except Exception:
        pass


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
    # 일자별 백업: 하루 1개 파일, 그 날의 최신 상태로 갱신 (최근 DAILY_KEEP일치 유지)
    try:
        os.makedirs(DAILY_DIR, exist_ok=True)
        today = datetime.datetime.now().strftime('%Y%m%d')
        daily_dst = os.path.join(DAILY_DIR, 'db_%s.db' % today)
        # 하루치 파일은 '그 날의 최신'으로 계속 갱신한다. 처음 것만 남기면 낮에 데이터가 바뀌어도
        # 다음날까지 낡은 백업이 유지되고, 원격 백업도 낡은 것을 가져간다.
        if os.path.exists(dst):
            shutil.copy2(dst, daily_dst)
            for old in sorted(glob.glob(os.path.join(DAILY_DIR, 'db_*.db')))[:-DAILY_KEEP]:
                try: os.remove(old)
                except Exception: pass
        backup_to_drive(daily_dst)   # 드라이브 동기화 폴더로도 하루 1개(폴더 있을 때만)
        backup_to_pc(daily_dst)      # PC 내장드라이브(사용자폴더)에도 사본 — USB 유실 대비
        # 첨부파일(계약서 원본) 사본 — DB만 백업하면 복구 후 계약서가 열리지 않는다
        status = []
        c1, t1 = sync_uploads(PC_BACKUP_DIR)
        status.append('계약서 원본 {}개 → {} (새로 복사 {}개)'.format(t1, PC_BACKUP_DIR, c1))
        drive_base = _resolve_drive_dir()
        if drive_base:
            dbase = os.path.join(drive_base, '부동산백업')
            c2, t2 = sync_uploads(dbase)
            status.append('계약서 원본 {}개 → {} (새로 복사 {}개)'.format(t2, dbase, c2))
        else:
            status.append('구글드라이브 폴더를 찾지 못했습니다 (drive_backup_path.txt 확인)')
        status.insert(0, 'DB 백업: {}'.format(os.path.basename(dst)))
        write_backup_status(status)
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
            account_no TEXT,
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
            elec_cost INTEGER DEFAULT 0,
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

        # 7. payments (월세 수납 장부) — 수납률/받은금액 집계용
        cur.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            contract_id INTEGER,
            room_id INTEGER,
            period TEXT,
            pay_date TEXT,
            amount INTEGER DEFAULT 0,
            pay_type TEXT DEFAULT '정상완납',
            memo TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")

        # 8-1. audit_logs (작업 기록: 누가·언제·무엇을)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor TEXT,
            action TEXT,
            target TEXT,
            detail TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")

        # 8. system_snapshots (행단위 스냅샷/되돌리기) — 수정 전 원본 JSON 보관
        cur.execute("""
        CREATE TABLE IF NOT EXISTS system_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_type TEXT DEFAULT 'auto_snapshot',
            table_name TEXT,
            target_id INTEGER,
            data_snapshot_json TEXT,
            requested_by_id INTEGER,
            is_restored INTEGER DEFAULT 0,
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
            ("contacts", "account_no", "TEXT"),
            ("bills", "elec_cost", "INTEGER DEFAULT 0"),
            ("bills", "water_usage", "INTEGER DEFAULT 0"),   # 수도 당월 지침(누적) — 다음달 전월지침 자동채움용
            ("bills", "building_id", "INTEGER DEFAULT 0"),      # 공용비용: 건물 단위 귀속
            ("bills", "scope", "TEXT DEFAULT 'room'"),          # 'room'=호실별, 'common'=공용(복도/공동화장실 등)
            ("bills", "common_area", "TEXT"),                   # 공용 구역명(예: 1층 복도, 공동화장실)
            ("incidents", "building_id", "INTEGER DEFAULT 0"),
            ("incidents", "scope", "TEXT DEFAULT 'room'"),
            ("incidents", "common_area", "TEXT"),
            ("audit_logs", "actor", "TEXT"),
            ("audit_logs", "action", "TEXT"),
            ("audit_logs", "target", "TEXT"),
            ("audit_logs", "detail", "TEXT"),
            ("audit_logs", "created_at", "TEXT"),
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

        # 마스터(최고관리자) 계정 강제 보장 — id=999 고정
        # 보안: 비밀번호는 평문 저장 금지 → sha256 해시만 저장(소스에도 평문 없음)
        MASTER_ID = 'uglywolf@gmail.com'
        MASTER_PW_HASH = 'af5a670e2e15d2a37878143e71e6fc2e0d86267406b21d9600bad721156f58b8'  # sha256(마스터 비밀번호) 2026-07-25 변경
        cur.execute("SELECT id FROM contacts WHERE id = 999")
        if not cur.fetchone():
            cur.execute("""
                INSERT INTO contacts (id, category, company_or_name, representative_name, contact_info, password_hash, role, role_name, is_active)
                VALUES (999, 'staff', '최고관리자', ?, '', ?, 'super_admin', 'super_admin', 1)
            """, (MASTER_ID, MASTER_PW_HASH))
        else:
            cur.execute("""
                UPDATE contacts
                SET representative_name = ?, password_hash = ?, role = 'super_admin', role_name = 'super_admin', is_active = 1
                WHERE id = 999
            """, (MASTER_ID, MASTER_PW_HASH))
        conn.commit()
    finally:
        conn.close()
