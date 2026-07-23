#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_portable.py - 포터블 실행 런처 (USB/EXE 배포용)
- 서버(server.py)를 띄우고 기본 브라우저로 로그인 화면을 자동으로 엽니다.
- 이 파일을 PyInstaller로 빌드하면 사용자는 EXE 더블클릭만으로 실행됩니다.
"""
import sys, os, threading, time, webbrowser

# 실행 위치(앱 폴더) 잡기 — exe로 얼려진 경우 / 스크립트 실행 경우 모두 대응
if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

import server  # server.py (같은 폴더)


def _open_browser():
    time.sleep(1.5)  # 서버가 뜰 시간을 잠깐 대기
    try:
        webbrowser.open('http://localhost:%d' % server.PORT)
    except Exception:
        pass


if __name__ == '__main__':
    print('=' * 46)
    print('  부동산 관리시스템을 시작합니다')
    print('  잠시 후 브라우저가 자동으로 열립니다.')
    print('  안 열리면 주소창에  http://localhost:%d  입력' % server.PORT)
    print('  이 창을 닫으면 프로그램이 종료됩니다.')
    print('=' * 46)
    threading.Thread(target=_open_browser, daemon=True).start()
    server.main()
