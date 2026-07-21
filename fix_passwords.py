#!/usr/bin/env python3
"""fix_passwords.py — DB의 pw_hash를 실제 SHA-256로 교체"""
import sqlite3, hashlib, os

DB = '/Users/uglywolf/rental-v2-online/building_manager.db'
conn = sqlite3.connect(DB)

# password_hash 열 있는지 확인
cols = [c[1] for c in conn.execute("PRAGMA table_info(users)").fetchall()]
if 'password_hash' not in cols:
    print('ERROR: users 테이블에 password_hash 없음')
    conn.close()
    exit(1)

# 기존 데이터 확인
users = conn.execute("SELECT id, employee_no, role_name FROM users").fetchall()
for uid, emp, role in users:
    new_pw = {'EMP-001':'admin123', 'EMP-002':'staff123', 'maint-01':'maint123'}.get(emp, None)
    if new_pw:
        h = hashlib.sha256(new_pw.encode()).hexdigest()
        conn.execute("UPDATE users SET password_hash=? WHERE id=?", (h, uid))
        print(f"UPDATE {emp} -> sha256({new_pw}) = {h}")

conn.commit()

# 검증
users = conn.execute("SELECT employee_no, password_hash FROM users").fetchall()
for emp, pw in users:
    calc = hashlib.sha256({'EMP-001':'admin123','EMP-002':'staff123','maint-01':'maint123'}.get(emp,'').encode()).hexdigest()
    match = '✅' if pw == calc else '❌';
    print(f"VERIFY {emp}: stored={pw[:16]}... calc={calc[:16]}... {match}")

conn.close()
