@echo off
chcp 65001 >nul
REM ==================================================
REM  부동산 관리시스템 - 윈도우 EXE 패키징 빌드
REM  (이 빌드 PC에만 파이썬 필요. 배포 대상 PC엔 불필요)
REM ==================================================

echo [1/4] PyInstaller 설치/업데이트...
python -m pip install --upgrade pyinstaller
if errorlevel 1 goto :err

echo [2/4] EXE 빌드 (onedir)...
python -m PyInstaller --noconfirm --clean --console --onedir --name "부동산관리시스템" run_portable.py
if errorlevel 1 goto :err

echo [3/4] 실행에 필요한 화면 파일만 복사 (설계문서/구버전 자동 제외)...
set "OUT=dist\부동산관리시스템"
REM --- 실제 앱 화면(HTML) ---
for %%F in (index.html main.html interface-a.html contract_master.html contractor_roster.html utility_bills.html monthly_rent_collection.html incidents_maintenance.html g_h_i_dashboard.html auditlog.html team_management.html partner_roster.html daily_report.html) do copy /Y "%%F" "%OUT%\" >nul
REM --- 공용 스크립트 (인증/게이트/날짜) ---
for %%F in (auth.js guard.js date8.js) do copy /Y "%%F" "%OUT%\" >nul
REM --- 초기 DB (빈 상태로 배포하려면 아래 한 줄을 삭제) ---
copy /Y building_manager.db "%OUT%\" >nul 2>nul
REM (설계문서 spec_data.js/*.md, 구버전 server.js/api_auth*.js 등은 의도적으로 복사하지 않음)

echo [4/4] 완료!
echo.
echo   배포: dist\부동산관리시스템\ 폴더를 통째로 USB에 복사하세요.
echo   실행: 그 폴더 안 "부동산관리시스템.exe" 더블클릭.
echo   ( 처음부터 빈 데이터로 시작하려면 그 폴더의
echo     building_manager.db 를 삭제 후 배포하세요 )
echo.
pause
goto :eof

:err
echo.
echo [오류] 빌드 실패. 위 메시지를 확인하세요. (파이썬 설치/PATH 여부 등)
pause
