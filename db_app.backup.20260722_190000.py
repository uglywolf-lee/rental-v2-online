#!/usr/bin/env python3
"""
db_app.py - 부동산 관리 시스템 포터블 통합 서버 (최종 안정화 버전)
- 멀티스레딩 지원 (ThreadingHTTPServer): 동시 요청 시 500 에러 및 속도 지연 완전 해결
- DB Connection Leak 방지 (try...finally 구문 적용)
- 스키마 완벽 지원: contacts(role, category), buildings, rooms, contracts, bills, incidents
- id=999 (EMP-001 / admin123) 마스터 계정 보장 및 바이패스 인증 연동
"""

import sys
sys.path.insert(0, '.')
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn
import json, os, sqlite3
from urllib.parse import urlparse, parse_qs

PORT = 8080
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, 'building_manager.db')
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')

if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR, exist_ok=True)

# 🌟 멀티스레드 서버 클래스 (속도 지연 및 블로킹 완벽 해결)
class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10.0) # DB Lock 방지 타임아웃
    conn.row_factory = sqlite3.Row
    return conn

def init_db_schema():
    conn = get_db()
    try:
        cur = conn.cursor()
        
        # 1. contacts (팀원, 세입자, 임대인, 중개사, 협력사)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_no TEXT,
            password_hash TEXT,
            role TEXT DEFAULT 'office_worker',
            role_name TEXT DEFAULT 'office_worker',
            company_or_name TEXT,
            representative_name TEXT,
            contact_info TEXT,
            phone TEXT,
            email TEXT,
            category TEXT DEFAULT 'staff',
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
            building_name TEXT,
            floor INTEGER,
            room TEXT,
            area REAL DEFAULT 0.0,
            status TEXT DEFAULT '공실',
            is_active INTEGER DEFAULT 1
        )""")
        
        # 4. contracts (계약)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS contracts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER,
            host_address_full TEXT,
            owner_contact_id INTEGER,
            tenant_contact_id INTEGER,
            broker_id INTEGER,
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
            contact_id INTEGER,
            bill_type TEXT,
            elec_usage INTEGER DEFAULT 0,
            water_cost INTEGER DEFAULT 0,
            gas_cost INTEGER DEFAULT 0,
            net_cost INTEGER DEFAULT 0,
            due_date TEXT,
            status TEXT DEFAULT '미납(고지대기)',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        
        # 6. incidents (시설유지보수/파손신고)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER,
            building_name TEXT,
            room_no TEXT,
            category TEXT,
            description TEXT,
            estimated_cost INTEGER DEFAULT 0,
            reported_by_name TEXT,
            reported_at TEXT,
            completed_at TEXT,
            status TEXT DEFAULT '접수',
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")

        # 🌟 마스터 계정 (id=999, EMP-001 / admin123) 보장
        cur.execute("SELECT id FROM contacts WHERE id = 999 OR employee_no = 'EMP-001'")
        if not cur.fetchone():
            cur.execute("""
                INSERT INTO contacts (id, employee_no, password_hash, role, role_name, company_or_name, category, is_active)
                VALUES (999, 'EMP-001', 'admin123', 'super_admin', 'super_admin', '최고관리자', 'staff', 1)
            """)
        else:
            cur.execute("""
                UPDATE contacts 
                SET password_hash = 'admin123', role = 'super_admin', role_name = 'super_admin', is_active = 1 
                WHERE id = 999 OR employee_no = 'EMP-001'
            """)
        conn.commit()
    finally:
        conn.close()

class RequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path.startswith('/api/v1/'):
            conn = get_db()
            try:
                cur = conn.cursor()

                if path == '/api/v1/buildings':
                    cur.execute("SELECT * FROM buildings WHERE is_active=1")
                    return self.json_response(200, [dict(r) for r in cur.fetchall()])

                elif path == '/api/v1/rooms':
                    cur.execute("SELECT * FROM rooms WHERE is_active=1")
                    return self.json_response(200, [dict(r) for r in cur.fetchall()])

                elif path == '/api/v1/contacts':
                    cat = query.get('category', [None])[0]
                    if cat:
                        cur.execute("SELECT * FROM contacts WHERE category=? AND is_active=1", (cat,))
                    else:
                        cur.execute("SELECT * FROM contacts WHERE is_active=1")
                    return self.json_response(200, [dict(r) for r in cur.fetchall()])

                elif path == '/api/v1/contracts':
                    cur.execute("""
                        SELECT c.*, r.room as room_no, cnt.company_or_name as tenant_name, cnt.phone as tenant_phone
                        FROM contracts c
                        LEFT JOIN rooms r ON c.room_id = r.id
                        LEFT JOIN contacts cnt ON c.tenant_contact_id = cnt.id
                        WHERE c.is_active=1 ORDER BY c.id DESC
                    """)
                    return self.json_response(200, [dict(r) for r in cur.fetchall()])

                elif path == '/api/v1/bills':
                    cur.execute("SELECT * FROM bills ORDER BY id DESC")
                    return self.json_response(200, [dict(r) for r in cur.fetchall()])

                elif path == '/api/v1/incidents':
                    cur.execute("SELECT * FROM incidents WHERE is_active=1 ORDER BY id DESC")
                    return self.json_response(200, [dict(r) for r in cur.fetchall()])

                return self.json_response(404, {'error': '엔드포인트가 없습니다.'})
            except Exception as e:
                return self.json_response(500, {'error': str(e)})
            finally:
                conn.close()

        # 정적 HTML/JS 파일 서빙
        if path == '/' or path == '':
            path = '/g_h_i_dashboard.html'

        file_path = os.path.join(BASE_DIR, path.lstrip('/'))
        if os.path.exists(file_path) and os.path.isfile(file_path):
            self.send_response(200)
            self.end_headers()
            with open(file_path, 'rb') as f:
                self.wfile.write(f.read())
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        try:
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length) if length > 0 else b'{}'
            data = json.loads(body.decode('utf-8'))
        except Exception:
            data = {}

        # 🌟 1. 로그인 인증 API
        if path in ['/api/v1/login', '/api/v1/auth']:
            username = data.get('username') or data.get('employee_no') or data.get('emp')
            password = data.get('password') or ''

            # 마스터 우회 접속
            if path == '/api/v1/auth' and not username:
                return self.json_response(200, {
                    'success': True,
                    'token': 'master_bypass_token',
                    'emp': 'EMP-001',
                    'role': 'super_admin',
                    'message': '마스터 세션 성공'
                })

            if username and password:
                conn = get_db()
                try:
                    cur = conn.cursor()
                    cur.execute("""
                        SELECT * FROM contacts 
                        WHERE (LOWER(employee_no) = LOWER(?) OR id = ?) 
                          AND password_hash = ? 
                          AND is_active = 1
                    """, (username, username, password))
                    user = cur.fetchone()
                    if user:
                        u = dict(user)
                        return self.json_response(200, {
                            'success': True,
                            'token': f"token_{u.get('employee_no') or u.get('id')}",
                            'emp': u.get('employee_no', 'EMP-001'),
                            'role': u.get('role', 'super_admin')
                        })
                    return self.json_response(401, {'success': False, 'error': '사번 또는 비밀번호 오류'})
                finally:
                    conn.close()

            return self.json_response(400, {'success': False, 'error': '인증 파라미터 부족'})

        # 2. CRUD POST API
        conn = get_db()
        try:
            cur = conn.cursor()

            if path == '/api/v1/contacts':
                cid = data.get('id')
                if cid:
                    fields = []
                    vals = []
                    for k in ['password_hash', 'role', 'role_name', 'company_or_name', 'representative_name', 'phone', 'contact_info', 'email', 'category', 'is_active']:
                        if k in data:
                            fields.append(f"{k}=?")
                            vals.append(data[k])
                    if fields:
                        vals.append(cid)
                        cur.execute(f"UPDATE contacts SET {','.join(fields)} WHERE id=?", vals)
                        conn.commit()
                    return self.json_response(200, {'success': True, 'message': '연락처 수정 완료'})
                else:
                    cur.execute("""
                        INSERT INTO contacts (employee_no, password_hash, role, role_name, company_or_name, representative_name, contact_info, phone, email, category)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        data.get('employee_no'), data.get('password_hash', '1234'), data.get('role', 'office_worker'),
                        data.get('role_name', 'office_worker'), data.get('company_or_name'), data.get('representative_name'),
                        data.get('contact_info'), data.get('phone'), data.get('email'), data.get('category', 'partner')
                    ))
                    conn.commit()
                    return self.json_response(201, {'success': True, 'message': '연락처 등록 완료'})

            elif path == '/api/v1/buildings':
                cur.execute("INSERT INTO buildings (name, address, floors, rooms_count) VALUES (?, ?, ?, ?)",
                            (data.get('name'), data.get('address'), data.get('floors', 1), data.get('rooms_count', 1)))
                conn.commit()
                return self.json_response(201, {'success': True, 'message': '건물 등록 완료'})

            elif path == '/api/v1/rooms':
                cur.execute("INSERT INTO rooms (building_id, building_name, floor, room, area) VALUES (?, ?, ?, ?, ?)",
                            (data.get('building_id'), data.get('building_name'), data.get('floor'), data.get('room'), data.get('area', 0.0)))
                conn.commit()
                return self.json_response(201, {'success': True, 'message': '호실 등록 완료'})

            elif path == '/api/v1/bills':
                cur.execute("""
                    INSERT INTO bills (room_id, contact_id, bill_type, elec_usage, water_cost, gas_cost, net_cost, due_date, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (data.get('room_id'), data.get('contact_id'), data.get('bill_type'), data.get('elec_usage', 0),
                      data.get('water_cost', 0), data.get('gas_cost', 0), data.get('net_cost', 0), data.get('due_date'), data.get('status', '미납(고지대기)')))
                conn.commit()
                return self.json_response(201, {'success': True, 'message': '공과금 고지 등록 완료'})

            elif path == '/api/v1/incidents':
                cur.execute("""
                    INSERT INTO incidents (room_id, building_name, room_no, category, description, estimated_cost, reported_by_name, reported_at, completed_at, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (data.get('room_id'), data.get('building_name'), data.get('room_no'), data.get('category'),
                      data.get('description'), data.get('estimated_cost', 0), data.get('reported_by_name'),
                      data.get('reported_at'), data.get('completed_at'), data.get('status', '접수')))
                conn.commit()
                return self.json_response(201, {'success': True, 'message': '파손/유지보수 신고 등록 완료'})

            elif path == '/api/v1/contracts':
                cid = data.get('id')
                special_terms = data.get('special_terms')
                if cid and special_terms is not None:
                    cur.execute("UPDATE contracts SET special_terms = ? WHERE id = ?", (special_terms, cid))
                    conn.commit()
                    return self.json_response(200, {'success': True, 'message': '특약/메모 업데이트 완료'})

                cur.execute("""
                    INSERT INTO contracts (room_id, lease_type, deposit_amount, monthly_rent, maintenance_fee, start_date, end_date, special_terms)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (data.get('room_id'), data.get('lease_type', '월세'), data.get('deposit_amount', 0),
                      data.get('monthly_rent', 0), data.get('maintenance_fee', 0), data.get('start_date'),
                      data.get('end_date'), special_terms or ''))
                conn.commit()
                return self.json_response(201, {'id': cur.lastrowid, 'success': True, 'message': '계약 등록 완료'})

            return self.json_response(404, {'error': 'API 엔드포인트를 찾을 수 없습니다.'})
        except Exception as e:
            return self.json_response(500, {'error': str(e)})
        finally:
            conn.close()

    def json_response(self, code, obj):
        data = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json;charset=utf-8')
        self.end_headers()
        self.wfile.write(data)

def main():
    init_db_schema()
    print(f"\n🏢 멀티스레딩 최적화 서버가 시작되었습니다. (Port: {PORT})")
    print(f"🔗 접속 주소: http://localhost:{PORT}")
    print(f"🔑 마스터 계정 ID: 999 (사번: EMP-001) / 비밀번호: admin123\n")
    server = ThreadedHTTPServer(('0.0.0.0', PORT), RequestHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n서버를 종료합니다.")

if __name__ == '__main__':
    main()
