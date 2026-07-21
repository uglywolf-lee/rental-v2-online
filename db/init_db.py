#!/usr/bin/env python3
"""db/init_db.py — SQLite building_manager.db init with SHA-256 passwords."""
import sqlite3
import hashlib
import os

DB_PATH = '/Users/uglywolf/rental-v2-online/building_manager.db'

def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()

# 테이블 스키마 목록 (DDL 전체를 VALUES로 전달)
SCHEMAS = {
    'users': """(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  employee_no VARCHAR(20) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  role_name VARCHAR(50) NOT NULL DEFAULT 'office_worker',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)""",
    'buildings': """(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name VARCHAR(255),
  address VARCHAR(500),
  floors INTEGER DEFAULT 1,
  rooms_count INTEGER DEFAULT 0,
  is_active BOOLEAN DEFAULT 1,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
)""",
    'rooms': """(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  building_id INTEGER REFERENCES buildings(id),
  floor_no INTEGER,
  room_no VARCHAR(50),
  area_sqm REAL,
  current_room_status VARCHAR(50) DEFAULT '비어있다',
  is_active BOOLEAN DEFAULT 1,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)""",
    'contacts': """(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  category VARCHAR(50),
  company_or_name VARCHAR(255),
  representative_name VARCHAR(100),
  contact_info VARCHAR(50),
  email VARCHAR(255),
  documents_json TEXT,
  is_active BOOLEAN DEFAULT 1,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)""",
    'contracts': """(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  room_id INTEGER REFERENCES rooms(id),
  host_address_full TEXT,
  owner_contact_id INTEGER REFERENCES contacts(id),
  tenant_contact_id INTEGER REFERENCES contacts(id),
  broker_id INTEGER REFERENCES contacts(id),
  lease_type VARCHAR(50),
  deposit_amount BIGINT,
  monthly_rent BIGINT,
  maintenance_fee BIGINT DEFAULT 0,
  commission_fee BIGINT DEFAULT 0,
  start_date DATE,
  end_date DATE,
  documents_json TEXT,
  is_active BOOLEAN DEFAULT 1,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
)""",
    'bills': """(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  room_id INTEGER REFERENCES rooms(id),
  contact_id INTEGER REFERENCES contacts(id),
  bill_type VARCHAR(50),
  amount BIGINT,
  billing_period_start DATE,
  billing_period_end DATE,
  due_date DATE,
  is_paid BOOLEAN DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)""",
    'meter_readings': """(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  room_id INTEGER REFERENCES rooms(id),
  bill_type VARCHAR(50),
  last_cumulative_reading BIGINT,
  current_cumulative_reading BIGINT,
  usage_amount BIGINT,
  billing_amount_won BIGINT,
  billing_period_start DATE,
  billing_period_end DATE,
  due_date DATE,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)""",
    'incidents': """(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  room_id INTEGER REFERENCES rooms(id),
  category VARCHAR(50),
  description TEXT,
  estimated_cost BIGINT,
  reported_by_name VARCHAR(50),
  status VARCHAR(50) DEFAULT '접수중',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)""",
    'audit_logs': """(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  worker_id INTEGER REFERENCES users(id),
  target_table VARCHAR(50),
  action_type VARCHAR(10),
  detail_log_json TEXT,
  exec_time DATETIME DEFAULT CURRENT_TIMESTAMP
)""",
    'memos': """(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  room_id INTEGER REFERENCES rooms(id),
  contact_id INTEGER REFERENCES contacts(id),
  writer_user_id INTEGER REFERENCES users(id),
  memo_text TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)""",
    'contracts_tenants': """(
  contract_id INTEGER REFERENCES contracts(id),
  tenant_contact_id INTEGER REFERENCES contacts(id),
  PRIMARY KEY (contract_id, tenant_contact_id)
)"""
}

# 초기 사용자 데이터 (비밀번호 평문 → sha256 해싱하여 insert
INITIAL_USERS = [
    ('EMP-001', 'admin123', 'super_admin'),
    ('EMP-002', 'staff123', 'office_worker'),
    ('maint-01', 'maint123', 'maintenance_staff')
]

def main():
    if os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        print(f'[INFO] DB exists: {DB_PATH} ({len(tables)} tables)')
        
        users = conn.execute("SELECT id, employee_no, role_name FROM users").fetchall() if 'users' in [t[0] for t in tables] else []
        print(f'[INFO] Current users: {len(users)}')
        for uid, emp, role in users:
            print(f'  → User: {emp} / {role}')
        
        # 테이블/사용자 있으면 그냥 exit
        if len(tables) > 0 and len(users) > 0:
            print(f'[SKIP] Everything initialized. Nothing to do.')
            conn.close()
            return

    # 새 DB 생성 or 기존 테이블 없음 → 초기화 진행
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 1. 테이블 생성
    print('[INIT] Creating tables...')
    for table, ddl in SCHEMAS.items():
        sql = f"CREATE TABLE IF NOT EXISTS {table} {ddl}"
        cur.execute(sql)
        print(f'  OK: {table}')

    # 2. 초기 사용자 insert (sha256 해싱)
    print('[INIT] Inserting initial users...')
    for emp, pw, role in INITIAL_USERS:
        pw_hash = sha256_hex(pw)
        try:
            cur.execute(
                "INSERT INTO users (employee_no, password_hash, role_name) VALUES (?, ?, ?)",
                (emp, pw_hash, role)
            )
            print(f'  OK: {emp} → {role[:20]}')
        except Exception as e:
            print(f'  WARN: {emp}: {e}')

    conn.commit()

    # 확인
    tables = cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    users = cur.execute("SELECT id, employee_no, role_name FROM users").fetchall()
    print(f'[OK] Done: DB={DB_PATH}, Tables={len(tables)}, Users={len(users)}')
    for uid, emp, role in users:
        print(f'  → User: {emp} / {role}')

if __name__ == '__main__':
    main()

