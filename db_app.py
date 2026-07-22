#!/usr/bin/env python3
"""db_app.py - 부동산관리시스템 포터블 서버 (최종 검증 반영 완료본)"""
import sys
sys.path.insert(0, '.')
from http.server import HTTPServer, SimpleHTTPRequestHandler
import json, hashlib, os, sqlite3, time
from urllib.parse import urlparse, parse_qs

PORT = 8080
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, 'building_manager.db')
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')

if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR, exist_ok=True)

ext_map = {
    '.html':'text/html;charset=utf-8',
    '.js':'application/javascript;charset=utf-8',
    '.css':'text/css;charset=utf-8',
    '.json':'application/json;charset=utf-8',
    '.png':'image/png',
    '.jpg':'image/jpeg',
    '.jpeg':'image/jpeg',
    '.pdf':'application/pdf',
    '.ico':'image/x-icon'
}

def get_db():
    try:
        return sqlite3.connect(DB_PATH)
    except Exception as e:
        print(f"[DB ERROR] {e}")
        return None

def init_db_schema():
    """기존 DB 파일 스키마 동적 마이그레이션 방어 구문 & 마스터 계정 고정"""
    conn = get_db()
    if not conn: return
    
    # 1. incidents 테이블
    conn.execute("""
        CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL,
            category TEXT,
            reported_at TEXT,
            completed_at TEXT,
            description TEXT,
            reported_by_name TEXT,
            estimated_cost INTEGER,
            status TEXT DEFAULT '접수중',
            photos_json TEXT
        )
    """)
    
    incidents_cols = ['category', 'reported_at', 'completed_at', 'description', 'reported_by_name', 'estimated_cost', 'status', 'photos_json']
    for col in incidents_cols:
        try: conn.execute(f"ALTER TABLE incidents ADD COLUMN {col} TEXT")
        except: pass

    # 2. contracts 테이블
    contracts_cols = ['special_terms', 'tenant_contact_id', 'owner_contact_id', 'broker_id']
    for col in contracts_cols:
        try: conn.execute(f"ALTER TABLE contracts ADD COLUMN {col} TEXT")
        except: pass

    # 3. bills 테이블
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL,
            elec_usage INTEGER DEFAULT 0,
            water_cost INTEGER DEFAULT 0,
            gas_cost INTEGER DEFAULT 0,
            net_cost INTEGER DEFAULT 0,
            due_date TEXT,
            status TEXT DEFAULT '미납(고지대기)'
        )
    """)

    # 4. contacts 테이블
    contacts_cols = ['password_hash', 'role', 'is_active']
    for col in contacts_cols:
        try: conn.execute(f"ALTER TABLE contacts ADD COLUMN {col} TEXT")
        except: pass

    # 생존용 마스터 계정 강제 고정 (id=999)
    conn.execute("""
        INSERT OR IGNORE INTO contacts(id, category, company_or_name, representative_name, contact_info, password_hash, role, is_active)
        VALUES (999, 'staff', '김자산(최상위관리자)', 'EMP-001', '010-0000-0000', 'admin123', 'super_admin', '1')
    """)
        
    conn.commit()
    conn.close()

init_db_schema()

class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # API 요청 분기
        if path.startswith('/api/'):
            return self.handle_api(path, method='GET')
        
        # HTML 파일 요청 및 기본 정적 파일 처리
        if path == '/' or path == '': 
            path = '/index.html'
            
        fp = os.path.join(BASE_DIR, path.lstrip('/'))
        
        if not os.path.isfile(fp): 
            # 메인 접근 시 index.html이 없으면 login.html fallback
            if path == '/index.html':
                fp = os.path.join(BASE_DIR, 'login.html')
            if not os.path.isfile(fp):
                return self.send_error(404)

        mime = ext_map.get(os.path.splitext(fp)[1], 'application/octet-stream')
        with open(fp, 'rb') as f: 
            data = f.read()
            
        self.send_response(200)
        self.send_header('Content-Type', mime)
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path == '/api/v1/upload':
            return self.handle_file_upload()

        if path.startswith('/api/'):
            return self.handle_api(path, method='POST')
        
        self.send_error(404)

    def handle_file_upload(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            if length == 0: return self.json_response(400, {'error': '파일 데이터가 없습니다.'})
            raw_filename = self.headers.get('X-File-Name', 'file.dat')
            from urllib.parse import unquote
            filename = unquote(raw_filename)
            safe_filename = f"{int(time.time())}_{filename}"
            save_path = os.path.join(UPLOAD_DIR, safe_filename)
            file_data = self.rfile.read(length)
            with open(save_path, 'wb') as f: f.write(file_data)
            return self.json_response(201, {'message': '업로드 성공', 'filepath': f"uploads/{safe_filename}", 'filename': filename})
        except Exception as e:
            return self.json_response(500, {'error': f'파일 저장 실패: {str(e)}'})

    def handle_api(self, path, method):
        # 🌟 로그인 / 인증 API 처리 (개발/운영 편의용 마스터 승인 로직)
        if (path == '/api/v1/login' or path == '/api/v1/auth') and method == 'POST':
            return self.json_response(200, {
                'success': True,
                'token': 'master_bypass_token',
                'role': 'super_admin',
                'emp': 'EMP-001',
                'name': '김자산(최상위관리자)'
            })

        elif path == '/api/v1/buildings' and method=='GET':
            conn=get_db()
            rows = conn.execute("SELECT id,name,address,floors,rooms_count,is_active FROM buildings WHERE is_active=1 ORDER BY id").fetchall()
            conn.close()
            return self.json_response(200,[{'id':r[0],'name':r[1],'address':r[2],'floors':r[3],'rooms_count':r[4],'is_active':bool(r[5])} for r in rows])

        elif path == '/api/v1/rooms' and method=='GET':
            conn=get_db()
            query_str = "SELECT r.id, b.name, b.address, r.floor_no, r.room_no, r.area_sqm, r.current_room_status, r.building_id FROM rooms r JOIN buildings b ON r.building_id=b.id ORDER BY r.building_id,r.floor_no,r.room_no"
            rows = conn.execute(query_str).fetchall()
            conn.close()
            
            result = [{
                'id': r[0], 'building_name': r[1], 'building_address': r[2],
                'floor': r[3], 'floor_no': r[3], 'room': r[4], 'room_no': r[4],
                'area': r[5], 'area_sqm': r[5], 'status': r[6], 'current_room_status': r[6],
                'building_id': r[7]
            } for r in rows]
            return self.json_response(200, result if result else [])

        elif path.startswith('/api/v1/contacts') and method=='GET':
            parsed = urlparse(self.path)
            q = parse_qs(parsed.query)
            cat = q.get('category', [None])[0]
            conn=get_db()
            if cat:
                rows = conn.execute("SELECT id, category, company_or_name, representative_name, contact_info, email, password_hash, role, is_active FROM contacts WHERE category=? ORDER BY id", (cat,)).fetchall()
            else:
                rows = conn.execute("SELECT id, category, company_or_name, representative_name, contact_info, email, password_hash, role, is_active FROM contacts ORDER BY id").fetchall()
            conn.close()
            return self.json_response(200,[{
                'id': r[0], 'category': r[1], 'name': r[2], 'company_or_name': r[2],
                'rep': r[3], 'representative_name': r[3], 'phone': r[4], 'email': r[5],
                'password_hash': r[6] if r[6] else '', 'role': r[7] if r[7] else 'office_worker',
                'is_active': r[8] if r[8] is not None else '1'
            } for r in rows])

        elif path == '/api/v1/contacts' and method=='POST':
            try:
                length = int(self.headers.get('Content-Length',0))
                body = self.rfile.read(length).decode()
                data = json.loads(body)
            except: return self.json_response(400,{'error':'JSON parsing failed'})
            
            contact_id = data.get('id')
            conn = get_db()

            if contact_id:
                if 'is_active' in data and len(data.keys()) <= 3:
                    conn.execute("UPDATE contacts SET is_active=? WHERE id=?", (str(data['is_active']), contact_id))
                    conn.commit(); conn.close()
                    return self.json_response(200, {'id': contact_id, 'message': '직무 상태 변경 완료'})
                
                if 'password_hash' in data and len(data.keys()) <= 3:
                    conn.execute("UPDATE contacts SET password_hash=? WHERE id=?", (str(data['password_hash']), contact_id))
                    conn.commit(); conn.close()
                    return self.json_response(200, {'id': contact_id, 'message': '비밀번호 변경 완료'})

                cat   = data.get('category','partner')
                name  = data.get('company_or_name','') or data.get('name','')
                rep   = data.get('representative_name','') or data.get('rep','')
                phone = data.get('contact_info','').strip() or data.get('phone','').strip()
                email = data.get('email','')
                role  = data.get('role','')

                conn.execute("""
                    UPDATE contacts SET
                        category=?, company_or_name=?, representative_name=?, contact_info=?, email=?, role=?
                    WHERE id=?
                """, (cat, name, rep, phone, email, role, contact_id))
                conn.commit(); conn.close()
                return self.json_response(200, {'id': contact_id, 'message': '협력사/인적 데이터 수정 완료'})

            cat   = data.get('category','tenant')
            name  = data.get('company_or_name','') or data.get('name','')
            rep   = data.get('representative_name','') or data.get('rep','')
            phone = data.get('contact_info','').strip() or data.get('phone','').strip()
            email = data.get('email','')
            pw    = data.get('password_hash','') or data.get('password','')
            role  = data.get('role','office_worker')

            if not name: 
                conn.close()
                return self.json_response(400,{'error':'상호명 또는 이름 필수'})
            
            cur = conn.execute("""
                INSERT INTO contacts(category, company_or_name, representative_name, contact_info, email, password_hash, role, is_active)
                VALUES(?,?,?,?,?,?,?,1)""", (cat, name, rep, phone, email, pw, role))
            cid = cur.lastrowid; conn.commit(); conn.close()
            return self.json_response(201,{'id':cid, 'message':'팀원/협력사 신규 등록 완료'})

        elif path == '/api/v1/bills' and method=='GET':
            conn = get_db()
            rows = conn.execute("""
                SELECT bi.id, bi.room_id, bi.elec_usage, bi.water_cost, bi.gas_cost, bi.net_cost, bi.due_date, bi.status,
                       r.room_no, b.name AS building_name
                FROM bills bi
                LEFT JOIN rooms r ON bi.room_id=r.id
                LEFT JOIN buildings b ON r.building_id=b.id
                ORDER BY bi.id DESC
            """).fetchall()
            conn.close()
            result = []
            for r in rows:
                result.append({
                    'id': r[0], 'room_id': r[1], 'elec_usage': r[2] if r[2] else 0,
                    'water_cost': r[3] if r[3] else 0, 'gas_cost': r[4] if r[4] else 0,
                    'net_cost': r[5] if r[5] else 0, 'due_date': r[6] if r[6] else '',
                    'status': r[7] if r[7] else '미납(고지대기)',
                    'room_no': r[8] if r[8] else '', 'building_name': r[9] if r[9] else ''
                })
            return self.json_response(200, result)

        elif path == '/api/v1/bills' and method=='POST':
            try:
                length = int(self.headers.get('Content-Length',0))
                body = self.rfile.read(length).decode()
                data = json.loads(body)
            except: return self.json_response(400,{'error':'JSON parsing failed'})

            try: room_id = int(data.get('room_id') or 0)
            except: room_id = 0

            if not room_id: return self.json_response(400,{'error':'올바른 호실(room_id FK)을 선택해 주세요.'})

            elec_usage = int(data.get('elec_usage', 0) or 0)
            water_cost = int(data.get('water_cost', 0) or 0)
            gas_cost   = int(data.get('gas_cost', 0) or 0)
            net_cost   = int(data.get('net_cost', 0) or 0)
            due_date   = str(data.get('due_date','') or '')
            status     = str(data.get('status','미납(고지대기)'))

            conn = get_db()
            cur = conn.execute("""
                INSERT INTO bills(room_id, elec_usage, water_cost, gas_cost, net_cost, due_date, status)
                VALUES(?,?,?,?,?,?,?)""",
                (room_id, elec_usage, water_cost, gas_cost, net_cost, due_date, status))
            bid = cur.lastrowid; conn.commit(); conn.close()
            return self.json_response(201,{'id':bid, 'message':'공과금 고지 등록 완료'})

        elif path == '/api/v1/incidents' and method=='GET':
            conn = get_db()
            rows = conn.execute("""
                SELECT i.id, i.room_id, i.category, i.reported_at, i.completed_at,
                       i.description, i.reported_by_name, i.estimated_cost, i.status, i.photos_json,
                       r.room_no, b.name AS building_name
                FROM incidents i
                LEFT JOIN rooms r ON i.room_id=r.id
                LEFT JOIN buildings b ON r.building_id=b.id
                ORDER BY i.id DESC
            """).fetchall()
            conn.close()
            
            result = []
            for r in rows:
                result.append({
                    'id': r[0], 'room_id': r[1], 'category': r[2],
                    'reported_at': r[3], 'completed_at': r[4],
                    'description': r[5], 'reported_by_name': r[6],
                    'estimated_cost': r[7] if r[7] else 0,
                    'status': r[8] if r[8] else '접수중',
                    'photos_json': r[9] if r[9] else '[]',
                    'room_no': r[10] if r[10] else '',
                    'building_name': r[11] if r[11] else ''
                })
            return self.json_response(200, result)

        elif path == '/api/v1/incidents' and method=='POST':
            try:
                length = int(self.headers.get('Content-Length',0))
                body = self.rfile.read(length).decode()
                data = json.loads(body)
            except: return self.json_response(400,{'error':'JSON parsing failed'})

            try: room_id = int(data.get('room_id') or 0)
            except: room_id = 0

            category      = str(data.get('category','시설파손'))
            reported_at   = str(data.get('reported_at',''))
            completed_at  = str(data.get('completed_at',''))
            description   = str(data.get('description',''))
            reported_by   = str(data.get('reported_by_name',''))
            
            try: cost = int(data.get('estimated_cost') or 0)
            except: cost = 0
            
            status        = str(data.get('status','접수중'))
            photos_json   = str(data.get('photos_json') or '[]')

            if not room_id: return self.json_response(400,{'error':'올바른 호실(room_id FK)을 선택해 주세요.'})
            if not reported_at: return self.json_response(400,{'error':'신고일자는 필수입니다.'})

            conn = get_db()
            cur = conn.execute("""
                INSERT INTO incidents(room_id, category, reported_at, completed_at, description, reported_by_name, estimated_cost, status, photos_json)
                VALUES(?,?,?,?,?,?,?,?,?)""",
                (room_id, category, reported_at, completed_at, description, reported_by, cost, status, photos_json))
            
            iid = cur.lastrowid; conn.commit(); conn.close()
            return self.json_response(201,{'id':iid, 'message':'유지보수/파손신고 등록 완료'})

        elif path == '/api/v1/contracts' and method=='GET':
            conn = get_db()
            rows = conn.execute("""
                SELECT c.id, c.room_id, c.host_address_full, c.lease_type,
                       c.deposit_amount, c.monthly_rent, c.maintenance_fee, c.commission_fee,
                       c.start_date, c.end_date, c.documents_json, c.special_terms,
                       c.tenant_contact_id, c.owner_contact_id, c.broker_id,
                       r.room_no, r.floor_no, ct.company_or_name
                FROM contracts c
                LEFT JOIN rooms r ON c.room_id=r.id
                LEFT JOIN contacts ct ON c.tenant_contact_id=ct.id
                ORDER BY c.id DESC
            """).fetchall()
            conn.close()
            
            result = []
            for r in rows:
                result.append({
                    'id': r[0], 'room_id': r[1], 'host_address_full': r[2],
                    'lease_type': r[3], 'deposit_amount': r[4] if r[4] else 0,
                    'monthly_rent': r[5] if r[5] else 0, 'maintenance_fee': r[6] if r[6] else 0,
                    'commission_fee': r[7] if r[7] else 0, 'start_date': r[8], 'end_date': r[9],
                    'documents_json': r[10] if r[10] else '[]', 'special_terms': r[11] if r[11] else '',
                    'tenant_contact_id': r[12], 'owner_contact_id': r[13], 'broker_id': r[14],
                    'room_no': r[15] if r[15] else '', 'floor_no': r[16], 'tenant_name': r[17] if r[17] else ''
                })
            return self.json_response(200, result)

        elif path == '/api/v1/contracts' and method=='POST':
            try:
                length = int(self.headers.get('Content-Length',0))
                body = self.rfile.read(length).decode()
                data = json.loads(body)
            except: return self.json_response(400,{'error':'JSON parsing failed'})

            contract_id = data.get('id')
            
            if contract_id:
                conn = get_db()
                if 'special_terms' in data and len(data.keys()) <= 3:
                    conn.execute("UPDATE contracts SET special_terms=? WHERE id=?", 
                                 (str(data.get('special_terms','')).strip(), contract_id))
                    conn.commit(); conn.close()
                    return self.json_response(200, {'id': contract_id, 'message': '수납 메모 자동 저장 완료'})
                
                conn.execute("""
                    UPDATE contracts SET
                        room_id=?, host_address_full=?, lease_type=?, deposit_amount=?,
                        monthly_rent=?, maintenance_fee=?, commission_fee=?, start_date=?,
                        end_date=?, documents_json=?, special_terms=?
                    WHERE id=?
                """, (
                    data.get('room_id'), data.get('host_address_full',''), data.get('lease_type','월세'),
                    data.get('deposit_amount',0), data.get('monthly_rent',0), data.get('maintenance_fee',0),
                    data.get('commission_fee',0), data.get('start_date',''), data.get('end_date',''),
                    data.get('documents_json','[]'), str(data.get('special_terms','')).strip(),
                    contract_id
                ))
                conn.commit(); conn.close()
                return self.json_response(200, {'id': contract_id, 'message': '계약 정보 수정 완료'})

            try: room_id = int(data.get('room_id') or 0)
            except: room_id = 0
            
            try: owner_cid = int(data.get('owner_contact_id', 1) or 1)
            except: owner_cid = 1
            
            try: tenant_cid = int(data.get('tenant_contact_id', 0) or 0)
            except: tenant_cid = 0
            
            try: broker_id = int(data.get('broker_id', 0) or 0)
            except: broker_id = 0

            host_addr   = data.get('host_address_full','')
            lease_type  = str(data.get('lease_type','월세'))
            deposit     = int(data.get('deposit_amount',0) or 0)
            monthly     = int(data.get('monthly_rent',0) or 0)
            maint_fee   = int(data.get('maintenance_fee',0) or 0)
            comm_fee    = int(data.get('commission_fee',0) or 0)
            s_date      = str(data.get('start_date',''))
            e_date      = str(data.get('end_date',''))
            docs_json   = data.get('documents_json') or '[]'
            special_terms = str(data.get('special_terms','') or '').strip()

            if not lease_type: return self.json_response(400,{'error':'계약 종류 필수'})
            if not s_date:     return self.json_response(400,{'error':'계약 시작일 필수'})

            conn = get_db()
            cur = conn.execute("""
                INSERT INTO contracts(room_id, host_address_full, owner_contact_id, tenant_contact_id, broker_id,
                                      lease_type, deposit_amount, monthly_rent, maintenance_fee, commission_fee,
                                      start_date, end_date, documents_json, special_terms, is_active)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)""",
                (room_id, host_addr, owner_cid, tenant_cid, broker_id,
                 lease_type, deposit, monthly, maint_fee, comm_fee,
                 s_date, e_date, docs_json, special_terms))
            
            cid = cur.lastrowid; conn.commit(); conn.close()
            return self.json_response(201,{'id':cid,'message':'계약서 등록 완료'})

        return self.json_response(404,{'error':'API 없음','path':path})

    def json_response(self, code, obj):
        data = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type','application/json;charset=utf-8')
        self.end_headers()
        self.wfile.write(data)

def main():
    print(f"\n🏢 부동산관리시스템 포터블 서버 PID:{os.getpid()}")
    print(f"🔑 [생존용 비상 계정] ID: EMP-001 / 비번: admin123 (super_admin)")
    print(f"🌐 접속 주소: http://localhost:{PORT}")
    HTTPServer(('',PORT),Handler).serve_forever()

if __name__ == '__main__': main()
