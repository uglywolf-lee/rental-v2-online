#!/usr/bin/env python3
"""
server.py - 메인 실행 파일 / Entry Point
- 8080포트 멀티스레드 HTTP 서버 구동
- 정적 파일 서빙 + API 라우팅 연결
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn
import json, urllib.parse, hashlib
import urllib as urllib_module

from db import get_db, init_db_schema
from routes import handle_get_api, handle_auth_endpoint, handle_post_api

PORT = 8080
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')

if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR, exist_ok=True)

ext_map = {
    '.html': 'text/html;charset=utf-8',
    '.js':   'application/javascript;charset=utf-8',
    '.css':  'text/css;charset=utf-8',
    '.json': 'application/json;charset=utf-8',
    '.png':  'image/png',
    '.jpg':  'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.pdf':  'application/pdf',
    '.ico':  'image/x-icon'
}


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


def json_response(handler, code, obj):
    data = json.dumps(obj, ensure_ascii=False).encode('utf-8')
    handler.send_response(code)
    handler.send_header('Content-Type', 'application/json;charset=utf-8')
    handler.end_headers()
    handler.wfile.write(data)


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-File-Name')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path

        # API GET 요청 처리
        if path.startswith('/api/v1/'):
            status, body = handle_get_api(path)
            return json_response(self, status, body)

        # 정적 파일 서빙
        if path == '/' or path == '':
            filename = 'g_h_i_dashboard.html'
        else:
            filename = path.lstrip('/')

        if not os.path.extsep in filename:
            filename += '.html'

        if os.path.exists(filename) and os.path.isfile(filename):
            self.send_response(200)
            for ext_type, content_type in ext_map.items():
                if filename.endswith(ext_type):
                    self.send_header('Content-type', content_type)
                    break
            self.end_headers()
            with open(filename, 'rb') as f:
                self.wfile.write(f.read())
        else:
            if os.path.exists('g_h_i_dashboard.html'):
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                with open('g_h_i_dashboard.html', 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404, "File Not Found: {}".format(path))

    def json_response(self, code, obj):
        return json_response(self, code, obj)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # 파일 업로드 API
        if path == '/api/v1/upload':
            try:
                length = int(self.headers.get('Content-Length', 0))
                if length == 0:
                    return json_response(self, 400, {'error': '업로드할 파일 데이터가 없습니다.'})
                raw_filename = self.headers.get('X-File-Name', 'file.dat')
                filename = urllib.parse.unquote(raw_filename)
                import time
                safe_filename = "{}_{}".format(int(time.time()), filename)
                save_path = os.path.join(UPLOAD_DIR, safe_filename)
                file_data = self.rfile.read(length)
                with open(save_path, 'wb') as f:
                    f.write(file_data)
                return json_response(self, 201, {
                    'message': '업로드 성공',
                    'filepath': "uploads/{}".format(safe_filename),
                    'filename': filename
                })
            except Exception as e:
                return json_response(self, 500, {'error': '파일 저장 실패: {}'.format(str(e))})

        # JSON 요청 파싱
        try:
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length).decode('utf-8') if length > 0 else '{}'
            data = json.loads(body)
        except Exception:
            data = {}

        # 로그인/인증 API
        auth_result = handle_auth_endpoint(path, data)
        if auth_result is not None:
            return json_response(self, auth_result[0], auth_result[1])

        # POST CRUD API
        status, body = handle_post_api(path, data)
        return json_response(self, status, body)


def main():
    init_db_schema()
    print("\n🏢 부동산 관리 시스템 포터블 통합 서버 실행 완료 (Port: {})".format(PORT))
    print("🔗 접속 주소: http://localhost:{}".format(PORT))
    print("🔑 마스터 계정: ID 999 (사번: EMP-001) / 비밀번호: admin123\n")
    server = ThreadedHTTPServer(('0.0.0.0', PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n서버를 안전하게 종료합니다.")


if __name__ == '__main__':
    main()
