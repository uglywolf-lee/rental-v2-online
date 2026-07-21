import sqlite3
import hashlib
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'building_manager.db')

def init_database():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 1. 사용자 테이블 생성
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_no TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role_name TEXT NOT NULL
        )
    ''')

    # 2. 테스트용 기본 관리자 계정 생성 (예: 사번 EMP-001 / 비밀번호 password123!)
    default_emp = "EMP-001"
    default_pw = "password123!"
    default_role = "super_admin"

    # 비밀번호 SHA256 해시화 (db_app.py의 검증 방식과 일치)
    hashed_pw = hashlib.sha256(default_pw.encode()).hexdigest().lower()

    # 이미 존재하지 않는 경우에만 추가
    cur.execute("SELECT id FROM users WHERE employee_no = ?", (default_emp,))
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO users (employee_no, password, role_name) VALUES (?, ?, ?)",
            (default_emp, hashed_pw, default_role)
        )
        print(f"기본 계정이 생성되었습니다. (사번: {default_emp} / 비밀번호: {default_pw})")
    else:
        print("이미 기본 계치가 존재합니다.")

    conn.commit()
    conn.close()
    print("DB 초기화가 완료되었습니다.")

if __name__ == '__main__':
    init_database()

