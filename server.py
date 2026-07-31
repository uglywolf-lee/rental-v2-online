#!/usr/bin/env python3
"""
server.py - 메인 실행 파일 / Entry Point
- 8899포트 멀티스레드 HTTP 서버 구동
- 정적 파일 서빙 + API 라우팅 연결
"""

import sys, os, socket
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn
import json, urllib.parse, hashlib
import urllib as urllib_module

from db import get_db, init_db_schema, backup_db, start_auto_backup
from routes import handle_get_api, handle_auth_endpoint, handle_post_api

PORT = 8899
# 패키징(exe) 대응: 얼려진 실행파일이면 exe 폴더, 아니면 스크립트 폴더 기준
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)   # 정적 파일 서빙을 앱 폴더 기준으로 고정
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
MAX_UPLOAD_BYTES = 25 * 1024 * 1024    # 첨부파일 1개 상한 (사진·PDF는 이 안에 들어옴. 동영상 실수 업로드 차단)
_DRAIN_LIMIT = 300 * 1024 * 1024       # 초과분을 버릴 때의 한계 — 메모리에 올리지 않고 조각으로 흘려보냄

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
    allow_reuse_address = True      # 이전 종료 직후에도 같은 포트 즉시 재사용(TIME_WAIT 회피)
    request_queue_size = 50         # 동시 접속 대기열 확대


def json_response(handler, code, obj):
    data = json.dumps(obj, ensure_ascii=False).encode('utf-8')
    handler.send_response(code)
    handler.send_header('Content-Type', 'application/json;charset=utf-8')
    handler.end_headers()
    handler.wfile.write(data)


def get_lan_ip():
    """이 컴퓨터의 LAN(내부망) IP 추정 — 같은 네트워크의 다른 기기가 접속할 주소 안내용."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))   # 실제 전송 없이 나가는 인터페이스 IP만 확인
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'


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

        # 서버 접속 주소 안내 (로그인 화면용)
        if path == '/api/v1/serverinfo':
            return json_response(self, 200, {'ip': get_lan_ip(), 'port': PORT})

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

        # 앱 폴더 기준 절대경로로 해석 (작업디렉터리와 무관하게 uploads/ 등 정상 서빙)
        filename = urllib.parse.unquote(filename)
        filename = os.path.normpath(os.path.join(BASE_DIR, filename))
        if not filename.startswith(BASE_DIR):      # 경로 탈출 방지
            return self.send_error(403, "Forbidden")

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
            _idx = os.path.join(BASE_DIR, 'index.html')
            if os.path.exists(_idx):
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                with open(_idx, 'rb') as f:
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
                if length > MAX_UPLOAD_BYTES:
                    left = min(length, _DRAIN_LIMIT)   # 본문을 조각으로 버림 (메모리 보호 + 브라우저에 이유 전달)
                    while left > 0:
                        chunk = self.rfile.read(min(1048576, left))
                        if not chunk:
                            break
                        left -= len(chunk)
                    return json_response(self, 413, {'error': '파일이 너무 큽니다. 한 개당 25MB까지 올릴 수 있습니다. (지금 파일: {:.1f}MB) 사진을 다시 찍거나 PDF로 저장해서 올려 주세요.'.format(length / 1048576.0)})
                raw_filename = self.headers.get('X-File-Name', 'file.dat')
                filename = urllib.parse.unquote(raw_filename)
                # 경로 탈출 방지: 폴더 구분자를 없애고 파일명만 남긴다 (uploads/ 밖으로 저장 불가)
                filename = os.path.basename(filename.replace('\\', '/').strip())
                if not filename or filename in ('.', '..'):
                    filename = 'file.dat'
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
    # 포트 점유 (이미 사용 중이면 원인을 명확히 알리고 종료)
    try:
        server = ThreadedHTTPServer(('0.0.0.0', PORT), Handler)
    except OSError as e:
        print("\n" + "=" * 52)
        print("  [오류] 포트 {} 를 사용할 수 없습니다.".format(PORT))
        print("  이미 이 프로그램이 실행 중이거나, 다른 프로그램이 포트를 쓰고 있습니다.")
        print("")
        print("  해결: 이미 떠 있는 창이 있으면 그 창을 쓰세요.")
        print("        없다면 작업관리자에서 RealEstate 를 모두 종료 후 다시 실행하세요.")
        print("  (상세: {})".format(e))
        print("=" * 52)
        try:
            input("\n엔터를 누르면 닫힙니다...")
        except Exception:
            pass
        return

    lan = get_lan_ip()
    print("\n🏢 부동산 관리 시스템 실행 완료 (Port: {})".format(PORT))
    print("🔗 이 컴퓨터:  http://localhost:{}".format(PORT))
    print("🌐 다른 기기:  http://{}:{}".format(lan, PORT))
    print("🔑 관리자 계정으로 로그인하세요.")
    print("   (이 창을 닫으면 프로그램이 종료됩니다)\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n서버를 안전하게 종료합니다.")
    finally:
        try:
            server.server_close()   # 포트 확실히 반납
        except Exception:
            pass


if __name__ == '__main__':
    main()
