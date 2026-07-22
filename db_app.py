#!/usr/bin/env python3
"""db_app.py - 부동산관리시스템 온라인 서버 (USB 배포용, Python 내장 sqlite3)"""
import sys
sys.path.insert(0, '.')
from http.server import HTTPServer, SimpleHTTPRequestHandler
import json, hashlib, os, sqlite3
from urllib.parse import urlparse, parse_qs

PORT = 8080
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, 'building_manager.db')

ext_map = {'.html':'text/html;utf-8','.js':'application/javascript;charset=utf-8','.css':'text/css;charset=utf-8','.json':'application/json;charset=utf-8'}

def get_db():
    try:
        return sqlite3.connect(DB_PATH)
    except Exception as e:
        print(f"[DB ERROR] {e}")
        return None

class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        
        # 바이패스 체크
        if 'access' in query and 'master_sys_884621' in query['access']:
            return self.json_response(200, {'bypass':'true'})

        # API 라우팅
        if path.startswith('/api/'):
            return self.handle_api(path, method='GET')
        
        # 정적 파일 serve
        if path == '/': path = '/index.html'
        fp = os.path.join(BASE_DIR, path.lstrip('/'))
        if not os.path.isfile(fp): return self.send_error(404)
        mime = ext_map.get(os.path.splitext(fp)[1],'application/octet-stream')
        with open(fp,'rb') as f: data = f.read()
        self.send_response(200)
        self.send_header('Content-Type',mime)
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        # API 라우팅으로 POST 처리 위임
        if path.startswith('/api/'):
            return self.handle_api(path, method='POST')
        
        self.send_error(404)

    def handle_api(self, path, method):
        # === login ===
        if path == '/api/v1/auth/login' and method=='POST':
            try:
                length = int(self.headers.get('Content-Length',0))
                body = self.rfile.read(length).decode()
                data = json.loads(body)
            except: return self.json_response(400,{'error':'JSON parse error'})
            
            emp = data.get('emp','').strip().lower()
            pwd = data.get('password','')
            if not emp or not pwd: return self.json_response(401,{'error':'사번과 비밀번호를 입력하세요'})
            
            conn = get_db()
            cur = conn.execute("SELECT id,employee_no,password_hash,role_name FROM users WHERE LOWER(employee_no)=? LIMIT 1",(emp,))
            row = cur.fetchone(); conn.close()
            if not row: return self.json_response(401,{'error':'사번 또는 비밀번호 오류'})
            
            h = hashlib.sha256(pwd.encode()).hexdigest().lower()
            stored = row[2].lower()
            if h != stored: return self.json_response(401,{'error':'사번 또는 비밀번호 오류'})
            
            return self.json_response(200,{'emp':row[1],'role':row[3]})

        # === /api/v1/auth/me ===
        elif path == '/api/v1/auth/me' and method=='GET':
            emp = self.headers.get('x-emp','').strip().lower()
            if not emp: return self.json_response(403,{'error':'인증되지 않음'})
            conn=get_db(); cur=conn.execute("SELECT employee_no,role_name FROM users WHERE employee_no=?",(emp,)); row=cur.fetchone(); conn.close()
            if not row: return self.json_response(403,{'error':'인증된 사용자가 없습니다'})
            return self.json_response(200,{'emp':row[0],'role':row[1]})

        # === /api/v1/buildings (GET) ===
        elif path == '/api/v1/buildings' and method=='GET':
            conn=get_db()
            rows = conn.execute("SELECT id,name,address,floors,rooms_count,is_active FROM buildings ORDER BY id").fetchall()
            conn.close()
            return self.json_response(200,[{'id':r[0],'name':r[1],'address':r[2],'floors':r[3],'rooms_count':r[4],'is_active':bool(r[5])} for r in rows])

        # === /api/v1/buildings (POST - 등록) ===
        elif path == '/api/v1/buildings' and method=='POST':
            try:
                length = int(self.headers.get('Content-Length',0))
                body = self.rfile.read(length).decode()
                data = json.loads(body)
            except: return self.json_response(400,{'error':'JSON parsing failed'})
            
            name = data.get('name','')
            addr = data.get('address','')
            fl   = data.get('floors',1) if data.get('floors') else 1
            rc   = data.get('rooms_count',0) if data.get('rooms_count') else 0
            
            if not name or not addr: return self.json_response(400,{'error':'건물명과 주소 필수'})
            
            conn=get_db()
            cur=conn.execute("INSERT INTO buildings(name,address,floors,rooms_count,is_active) VALUES(?,?,?,?,1)",(name,addr,fl,rc))
            bid = cur.lastrowid; conn.commit(); conn.close()
            return self.json_response(201,{'id':bid,'name':name,'address':addr,'floors':fl,'rooms_count':rc,'message':'건물 등록 완료'})

        # === /api/v1/rooms (GET) ===
        elif path == '/api/v1/rooms' and method=='GET':
            q = urlparse(self.path).query
            building_id = parse_qs(q).get('building_id',[None])[0] or 'all'
            
            conn=get_db()
            if building_id and building_id != 'all':
                query_str = "SELECT r.id, b.name, b.address, r.floor_no, r.room_no, r.area_sqm, r.current_room_status FROM rooms r JOIN buildings b ON r.building_id=b.id WHERE r.building_id=? ORDER BY r.building_id,r.floor_no,r.room_no"
                rows = conn.execute(query_str,(building_id,)).fetchall()
            else:
                query_str = "SELECT r.id, b.name, b.address, r.floor_no, r.room_no, r.area_sqm, r.current_room_status FROM rooms r JOIN buildings b ON r.building_id=b.id ORDER BY r.building_id,r.floor_no,r.room_no"
                rows = conn.execute(query_str).fetchall()
            conn.close()
            
            result = [{'id':r[0],'building_name':r[1],'building_address':r[2],'floor':r[3],'room':r[4],'area':r[5],'status':r[6]} for r in rows]
            return self.json_response(200, result if result else [])

        # === /api/v1/rooms (POST - 등록) ===
        elif path == '/api/v1/rooms' and method=='POST':
            try:
                length = int(self.headers.get('Content-Length',0))
                body = self.rfile.read(length).decode()
                data = json.loads(body)
            except: return self.json_response(400,{'error':'JSON parsing failed'})
            
            bid  = data.get('building_id')
            fl   = data.get('floor_no')
            rn   = data.get('room_no','')
            area = data.get('area_sqm',0) or 0
            status = data.get('current_room_status','비어있다')
            
            if not bid or not fl: return self.json_response(400,{'error':'건물ID와 층수 필수'})
            
            conn=get_db()
            cur=conn.execute("INSERT INTO rooms(building_id,floor_no,room_no,area_sqm,current_room_status,is_active) VALUES(?,?,?,?,?,1)",(int(bid),fl,rn,float(area),status))
            rid = cur.lastrowid; conn.commit(); conn.close()
            return self.json_response(201,{'id':rid,'message':'호실 등록 완료'})

        # === /api/v1/contacts (GET) ===
        elif path == '/api/v1/contacts' and method=='GET':
            conn=get_db()
            rows = conn.execute("SELECT id,category,company_or_name,representative_name,contact_info,email FROM contacts ORDER BY id").fetchall()
            conn.close()
            return self.json_response(200,[{'id':r[0],'category':r[1],'name':r[2],'rep':r[3],'phone':r[4],'email':r[5]} for r in rows])

        # === /api/v1/contacts (POST) ===
        elif path == '/api/v1/contacts' and method=='POST':
            try:
                length = int(self.headers.get('Content-Length',0))
                body = self.rfile.read(length).decode()
                data = json.loads(body)
            except: return self.json_response(400,{'error':'JSON parsing failed'})
            
            cat  = data.get('category','tenant')
            name = data.get('company_or_name','') or data.get('name','')
            rep  = data.get('representative_name','')
            phone= data.get('contact_info','').replace('-','').strip()
            email= data.get('email','')
            
            if not name: return self.json_response(400,{'error':'이름 필수'})
            
            conn=get_db()
            cur=conn.execute("INSERT INTO contacts(category,company_or_name,representative_name,contact_info,email) VALUES(?,?,?,?,?)",(cat,name,rep,phone,email))
            cid = cur.lastrowid; conn.commit(); conn.close()
            return self.json_response(201,{'id':cid,'message':'연계자 등록 완료'})

        # === /api/v1/contracts (GET) ===
        elif path == '/api/v1/contracts' and method=='GET':
            conn=get_db()
            rows = conn.execute("""
                SELECT c.id, c.room_id, c.host_address_full, c.lease_type,
                       c.deposit_amount, c.monthly_rent, c.maintenance_fee, c.commission_fee,
                       c.start_date, c.end_date, c.documents_json, c.broker_id,
                       r.floor_no, r.room_no, s.company_or_name, b.name AS building_name, b.address AS building_address
                FROM contracts c 
                LEFT JOIN rooms r ON c.room_id=r.id 
                LEFT JOIN buildings b ON r.building_id=b.id
                LEFT JOIN contacts s ON c.tenant_contact_id=s.id
                ORDER BY c.id DESC
            """).fetchall()
            conn.close()
            result = []
            for r in rows:
                result.append({
                    'id':r[0],'room_id':r[1],'host_address_full':r[2],
                    'lease_type':r[3],'deposit_amount':r[4] if r[4] else 0,
                    'monthly_rent':r[5] if r[5] else 0,'maintenance_fee':r[6] if r[6] else 0,
                    'commission_fee':r[7] if r[7] else 0,'start_date':r[8],'end_date':r[9],
                    'documents_json':r[10] if r[10] else '[]','broker_id':r[11],
                    'floor_no':r[12],'room_no':r[13],'tenant_name':r[14],
                    'building_name':r[15] if r[15] else '','building_address':r[16] if r[16] else ''
                })
            return self.json_response(200, result)

        # === /api/v1/contracts (POST - 등록) ===
        elif path == '/api/v1/contracts' and method=='POST':
            try:
                length = int(self.headers.get('Content-Length',0))
                body = self.rfile.read(length).decode()
                data = json.loads(body)
            except: return self.json_response(400,{'error':'JSON parsing failed'})

            # 안전한 정수형 변환 (예외 발생 차단)
            try: room_id = int(data.get('room_id') or 0)
            except: room_id = 0
            
            try: owner_cid = int(data.get('owner_contact_id', 1) or 1)
            except: owner_cid = 1
            
            try: tenant_cid = int(data.get('tenant_contact_id', 0) or 0)
            except: tenant_cid = 0
            
            try: broker_id = int(data.get('broker_id', 0) or 0)
            except: broker_id = 0

            room_no     = str(data.get('room_no','') or '')
            host_addr   = data.get('host_address_full','')
            lease_type  = str(data.get('lease_type','월세'))
            deposit     = int(data.get('deposit_amount',0) or 0)
            monthly     = int(data.get('monthly_rent',0) or 0)
            maint_fee   = int(data.get('maintenance_fee',0) or 0)
            comm_fee    = int(data.get('commission_fee',0) or 0)
            s_date      = str(data.get('start_date',''))
            e_date      = str(data.get('end_date',''))
            docs_json   = data.get('documents_json') or '[]'

            if not lease_type: return self.json_response(400,{'error':'계약 종류 필수'})
            if not s_date:     return self.json_response(400,{'error':'계약 시작일 필수'})
            ok = deposit > 0 or monthly > 0
            if not ok:         return self.json_response(400,{'error':'보증금 또는 월세 중 하나 이상 필수'})

            conn = get_db()
            cur = conn.execute("""
                INSERT INTO contracts(room_id,host_address_full,owner_contact_id,tenant_contact_id,broker_id,room_no,
                                      lease_type,deposit_amount,monthly_rent,maintenance_fee,commission_fee,
                                      start_date,end_date,documents_json,is_active)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)""",(room_id, host_addr, owner_cid, tenant_cid, broker_id, room_no,
                        lease_type, deposit, monthly, maint_fee, comm_fee, s_date, e_date, docs_json))
            cid = cur.lastrowid; conn.commit(); conn.close()
            return self.json_response(201,{'id':cid,'message':'계약서 등록 완료'})

        # === fallback ===
        return self.json_response(404,{'error':'API 없음','path':path})

    def json_response(self, code, obj):
        data = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type','application/json;charset=utf-8')
        self.end_headers()
        self.wfile.write(data)

def main():
    print(f"\n🏢 부동산관리시스템 온라인 server PID:{os.getpid()}")
    print(f"🌐 http://localhost:{PORT}")
    print(f"✅ 바이패스: http://localhost:{PORT}/?access=master_sys_884621")
    HTTPServer(('',PORT),Handler).serve_forever()

if __name__ == '__main__': main()