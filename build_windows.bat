@echo off
setlocal
REM ==================================================
REM  Real Estate Manager - Windows EXE packaging
REM  (Python needed on THIS build PC only; not on end-user PC)
REM ==================================================

REM Prefer Python 3.13 (stable for PyInstaller). If missing, run first:  py install 3.13
set "PY=py -3.13"
py -3.13 --version >nul 2>&1 || set "PY=py"
%PY% --version >nul 2>&1 || set "PY=python"
%PY% --version >nul 2>&1 || goto :nopy
echo Using Python:
%PY% --version

echo [1/3] Installing PyInstaller...
%PY% -m pip install --upgrade pyinstaller
if errorlevel 1 goto :err

echo [2/3] Building EXE (onedir)...
%PY% -m PyInstaller --noconfirm --clean --console --onedir --name "RealEstate" run_portable.py
if errorlevel 1 goto :err

echo [3/3] Copying app files (HTML / JS / DB)...
set "OUT=dist\RealEstate"
for %%F in (index.html main.html interface-a.html contract_master.html contractor_roster.html utility_bills.html monthly_rent_collection.html incidents_maintenance.html g_h_i_dashboard.html auditlog.html team_management.html partner_roster.html daily_report.html) do copy /Y "%%F" "%OUT%\" >nul
for %%F in (auth.js guard.js date8.js) do copy /Y "%%F" "%OUT%\" >nul
REM DB is NOT shipped by default (protects live data on site).
REM The app creates a new empty DB on first run.
REM For a brand-new install, uncomment the next line:
REM copy /Y building_manager.db "%OUT%\" >nul 2>nul
REM one-time setup script (firewall + auto-start) shipped with the app
copy /Y install_service.bat "%OUT%\" >nul 2>nul
copy /Y drive_backup_path.txt "%OUT%\" >nul 2>nul
REM user guide (copy any .txt guide in this folder)
copy /Y *.txt "%OUT%\" >nul 2>nul

REM Ensure Python DLL is bundled (some installs miss it -> pythonXXX.dll not found)
set "DLLDST=%OUT%"
if exist "%OUT%\_internal\" set "DLLDST=%OUT%\_internal"
for /f "delims=" %%B in ('%PY% -c "import sys;print(sys.base_prefix)"') do set "PYBASE=%%B"
if exist "%PYBASE%\python313.dll" copy /Y "%PYBASE%\python313.dll" "%DLLDST%\" >nul
if exist "%PYBASE%\python314.dll" copy /Y "%PYBASE%\python314.dll" "%DLLDST%\" >nul

echo.
echo ============================================
echo  DONE.
echo  Copy the folder   dist\RealEstate   to a USB.
echo  Run:  RealEstate.exe  (double click)
echo  (You may rename RealEstate.exe in Explorer if you want.)
echo ============================================
echo.
pause
goto :eof

:err
echo.
echo [ERROR] Build failed. Read the messages above.
pause
goto :eof

:nopy
echo.
echo [ERROR] Python not found. Open a NEW terminal and check:  py --version
pause
