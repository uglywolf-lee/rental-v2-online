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

from db import get_db, init_db_schema, backup_db, start_auto_backup
from routes import handle_get_api, handle_auth_endpoint, handle_post_api

PORT = 8080
# 패키징(exe) 대응: 얼려진 실행파일이면 exe 폴더, 아니면 스크립트 폴더 기준
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)   # 정적 파일 서빙을 앱 폴더 기준으로 고정
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

        # API GET 요청 처리 (쿼리스트링 포함 전체 경로 전달 → category 등 필터 유지)
        if path.startswith('/api/v1/'):
            status, body = handle_get_api(self.path)
            return json_response(self, status, body)

        # 정적 파일 서빙
        if path == '/' or path == '':
            filename = 'index.html'
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
            if os.path.exists('index.html'):
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                with open('index.html', 'rb') as f:
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

                # 파일 종류별 저장 구역(subdir) 분류
                ext = os.path.splitext(filename)[1].lower()
                IMAGE_EXTS = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')
                if ext in IMAGE_EXTS:
                    subdir = 'photos'        # 사진 저장 구역
                elif ext == '.pdf':
                    subdir = 'documents'     # PDF 문서 저장 구역
                else:
                    subdir = 'etc'           # 기타 파일 저장 구역

                target_dir = os.path.join(UPLOAD_DIR, subdir)
                os.makedirs(target_dir, exist_ok=True)

                safe_filename = "{}_{}".format(int(time.time()), filename)
                save_path = os.path.join(target_dir, safe_filename)
                file_data = self.rfile.read(length)
                with open(save_path, 'wb') as f:
                    f.write(file_data)
                return json_response(self, 201, {
                    'message': '업로드 성공',
                    'filepath': "uploads/{}/{}".format(subdir, safe_filename),
                    'filename': filename,
                    'category': subdir
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

        # OCR API: 업로드된 계약서/신분증/여권에서 필드 추정 (사람 검토 전제)
        if path == '/api/v1/ocr':
            try:
                import ocr_engine
            except Exception as e:
                return json_response(self, 500, {'error': 'OCR 모듈 로드 실패: {}'.format(e)})
            rel = (data.get('filepath') or '').lstrip('/')
            doc_type = data.get('doc_type', 'lease')
            if not rel:
                return json_response(self, 400, {'error': 'filepath 가 필요합니다.'})
            # 경로 탈출 방지: BASE_DIR 하위만 허용
            target = os.path.normpath(os.path.join(BASE_DIR, rel))
            if not target.startswith(BASE_DIR):
                return json_response(self, 400, {'error': '허용되지 않은 경로입니다.'})
            if not os.path.isfile(target):
                return json_response(self, 404, {'error': '파일을 찾을 수 없습니다: {}'.format(rel)})
            try:
                result = ocr_engine.run_ocr(target, doc_type)
                return json_response(self, 200, result)
            except Exception as e:
                return json_response(self, 500, {'error': 'OCR 처리 오류: {}'.format(e)})

        # 로그인/인증 API
        auth_result = handle_auth_endpoint(path, data)
        if auth_result is not None:
            return json_response(self, auth_result[0], auth_result[1])

        # POST CRUD API
        status, body = handle_post_api(path, data)
        return json_response(self, status, body)


def main():
    init_db_schema()
    bpath = backup_db('startup')      # 실행 시 복원지점 1개 자동 생성
    start_auto_backup(300)            # 저장/수정 감지되면 5분마다 자동 백업
    if bpath:
        print("🛟 시작 백업 생성: {}".format(os.path.relpath(bpath, BASE_DIR)))
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
