@echo off
REM =====================================================
REM  Real Estate Manager - SAFE UPDATE
REM  Replaces program files ONLY.
REM  Your data (building_manager.db), backups and uploads
REM  are NEVER touched.
REM
REM  HOW TO USE
REM   1) Put this file inside the NEW version folder
REM      (the folder you just built: dist\RealEstate)
REM   2) Double-click it
REM   3) Choose the installed folder on this PC
REM =====================================================
setlocal EnableDelayedExpansion
chcp 65001 >nul

set "SRC=%~dp0"
echo.
echo ============================================
echo   Real Estate Manager - SAFE UPDATE
echo ============================================
echo.
echo  NEW version folder : %SRC%
echo.
set /p "DST=Installed folder path (drag the folder here, then Enter): "
if "%DST%"=="" goto :cancel
if "%DST:~-1%"=="\" set "DST=%DST:~0,-1%"

if not exist "%DST%\RealEstate.exe" (
  echo.
  echo  [ERROR] RealEstate.exe not found in:
  echo          %DST%
  echo  Please check the folder and try again.
  pause
  exit /b 1
)

echo.
echo  Target : %DST%
echo.
echo  This will REPLACE program files.
echo  Your data will be kept:
echo    - building_manager.db   (all your records)
echo    - _backups\             (automatic backups)
echo    - uploads\              (contract / ID scans)
echo.
set /p "OK=Continue? (Y/N): "
if /i not "%OK%"=="Y" goto :cancel

REM --- 1) safety copy of the data before touching anything ---
set "TS=%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%"
set "TS=%TS: =0%"
if exist "%DST%\building_manager.db" (
  if not exist "%DST%\_backups\manual" mkdir "%DST%\_backups\manual" >nul 2>nul
  copy /Y "%DST%\building_manager.db" "%DST%\_backups\manual\before_update_%TS%.db" >nul
  echo  [1/3] Data backed up: _backups\manual\before_update_%TS%.db
) else (
  echo  [1/3] No existing data found - skipping backup.
)

REM --- 2) stop the running program (so files are not locked) ---
taskkill /IM RealEstate.exe /F >nul 2>&1
echo  [2/3] Stopped running program (if any).

REM --- 3) copy program files only ---
robocopy "%SRC%." "%DST%" /E /XF building_manager.db drive_backup_path.txt /XD _backups uploads dist build >nul
echo  [3/3] Program files updated.

echo.
echo ============================================
echo  UPDATE COMPLETE
echo.
echo  Data kept as-is. Start the program:
echo    %DST%\RealEstate.exe
echo ============================================
echo.
pause
exit /b 0

:cancel
echo.
echo  Cancelled. Nothing was changed.
pause
