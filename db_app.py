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

def get_db(): return sqlite3.connect(DB_PATH)

class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        
        # 바이패스
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
        if path == '/api/v1/auth/login': return self.handle_api(path, method='POST')
        self.send_error(404)

    def handle_api(self, path, method):
        if path == '/api/v1/auth/login' and method=='POST':
            length = int(self.headers.get('Content-Length',0))
            body = self.rfile.read(length).decode()
            try: data = json.loads(body); emp=data.get('emp','').strip().lower(); pwd=data.get('password','')
            except: return self.json_response(400,{'error':'JSON parse error'})
            
            if not emp or not pwd: return self.json_response(401,{'error':'사번과 비밀번호를 입력하세요'})
            
            conn=get_db(); cur=conn.execute("SELECT id,employee_no,password_hash,role_name FROM users WHERE LOWER(employee_no)=? LIMIT 1",(emp,)); row=cur.fetchone(); conn.close()
            if not row: return self.json_response(401,{'error':'사번 또는 비밀번호 오류'})
            
            h = hashlib.sha256(pwd.encode()).hexdigest().lower(); stored = row[2].lower()
            if h != stored: return self.json_response(401,{'error':'사번 또는 비밀번호 오류'})
            
            return self.json_response(200,{'emp':row[1],'role':row[3]})

        elif path == '/api/v1/auth/me' and method=='GET':
            emp = self.headers.get('x-emp','').strip().lower()
            if not emp: return self.json_response(403,{'error':'인증되지 않음'})
            conn=get_db(); cur=conn.execute("SELECT employee_no,role_name FROM users WHERE employee_no=?",(emp,)); row=cur.fetchone(); conn.close()
            if not row: return self.json_response(403,{'error':'인증된 사용자가 없습니다'})
            return self.json_response(200,{'emp':row[0],'role':row[1]})

        return self.json_response(404,{'error':'API 없음','path':path})

    def json_response(self, code, obj):
        data = json.dumps(obj).encode()
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

