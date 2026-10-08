@echo off
setlocal
cd /d "%~dp0"

set LAB=%1
if "%LAB%"=="" (
    echo ======================================================
    echo  ADLabs WireGuard CLI Disconnector
    echo ======================================================
    echo.
    echo  Active / Available Labs:
    for /f "delims=" %%l in ('python "%~dp0adlabs.py" --list-labs') do echo   %%l
    for /f %%c in ('python "%~dp0adlabs.py" --count-labs') do set TOTAL=%%c
    echo.
    set /p LAB="Enter lab number (1-%TOTAL%) or name to disconnect: "
)

if "%LAB%"=="" (
    echo [x] No lab specified. Exiting...
    pause
    exit /b 1
)

:: Check for Administrator privileges
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [*] Administrator privileges required to remove Windows VPN network service.
    echo [*] Requesting UAC elevation...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -ArgumentList '%LAB%' -WorkingDirectory '%~dp0' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"
python "%~dp0adlabs.py" --disconnect "%LAB%"
echo.
pause
