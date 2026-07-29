@echo off
REM =====================================================
REM  Real Estate Manager - setup (firewall + auto start)
REM  Just double-click. It will ask for admin rights.
REM  Safe to run many times.
REM =====================================================

REM ---- auto elevate to administrator ----
net session >nul 2>&1
if errorlevel 1 (
  echo Requesting administrator rights...
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

setlocal
set "PORT=8899"
set "APPDIR=%~dp0"
set "EXE=%APPDIR%RealEstate.exe"

echo.
echo ============================================
echo   Real Estate Manager - Setup
echo   Folder : %APPDIR%
echo   Port   : %PORT%
echo ============================================
echo.

echo [1/4] Removing OLD firewall rules (wrong profile / popup-created) ...
REM rules made by our script
netsh advfirewall firewall delete rule name="RealEstate %PORT%" >nul 2>&1
netsh advfirewall firewall delete rule name="RealEstate App" >nul 2>&1
REM rules auto-created by the Windows popup (named after the program)
netsh advfirewall firewall delete rule name="RealEstate" >nul 2>&1
netsh advfirewall firewall delete rule name="RealEstate.exe" >nul 2>&1
REM any rule pointing at our exe path (covers popup rules with odd names)
if exist "%EXE%" netsh advfirewall firewall delete rule program="%EXE%" >nul 2>&1
echo       done.

echo [2/4] Adding firewall rules for ALL profiles (private+public+domain) ...
netsh advfirewall firewall add rule name="RealEstate %PORT%" dir=in action=allow protocol=TCP localport=%PORT% profile=any
if exist "%EXE%" netsh advfirewall firewall add rule name="RealEstate App" dir=in action=allow program="%EXE%" enable=yes profile=any
echo       done.

echo [3/4] Registering auto-start at logon ...
if not exist "%EXE%" (
  echo       [SKIP] RealEstate.exe not found in this folder.
) else (
  set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
  powershell -NoProfile -Command ^
    "$s=(New-Object -ComObject WScript.Shell).CreateShortcut(\"$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\RealEstate.lnk\");" ^
    "$s.TargetPath='%EXE%'; $s.WorkingDirectory='%APPDIR%'; $s.Save()" >nul 2>&1
  echo       done.
)

echo [4/5] Preventing sleep (server must stay reachable) ...
REM never sleep / never hibernate  (plugged in and on battery)
powercfg /change standby-timeout-ac 0
powercfg /change standby-timeout-dc 0
powercfg /change hibernate-timeout-ac 0
powercfg /change hibernate-timeout-dc 0
REM keep network alive; screen may still turn off (that is fine)
powercfg /change monitor-timeout-ac 30
powercfg /hibernate off >nul 2>&1
echo       sleep/hibernate disabled (monitor off after 30 min is OK).

echo [5/5] Current rules for this app:
netsh advfirewall firewall show rule name="RealEstate %PORT%" | findstr /i "Rule Name Profiles Enabled Action LocalPort"
echo.
echo ============================================
echo  SETUP COMPLETE
echo.
echo  Other PCs connect to:  http://[this PC IP]:%PORT%
echo  (exact address is shown on the login screen)
echo.
echo  Sleep is OFF so other PCs can always connect.
echo  (Do not shut down this PC while others are using it.)
echo.
echo  If it still fails, check the network profile:
echo   Settings ^> Network ^& Internet ^> (your network) ^> Private
echo ============================================
echo.
pause
