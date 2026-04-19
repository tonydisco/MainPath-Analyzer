@echo off
setlocal enabledelayedexpansion
title MainPath Analysis Tool — Installer
color 0A

echo.
echo  ============================================
echo   MainPath Analysis Tool — Windows Installer
echo  ============================================
echo.

:: Check if running as Administrator
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo  [INFO] Requesting Administrator privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

set "INSTALL_DIR=%ProgramFiles%\MainPath"
set "DESKTOP=%USERPROFILE%\Desktop"
set "START_MENU=%APPDATA%\Microsoft\Windows\Start Menu\Programs\MainPath"

:: ── Step 1: Check Python ──
echo  [1/5] Checking Python installation...
python --version >nul 2>&1
if %errorLevel% neq 0 (
    py --version >nul 2>&1
    if !errorLevel! neq 0 (
        echo.
        echo  [ERROR] Python not found.
        echo  Please install Python 3.9+ from https://www.python.org/downloads/
        echo  IMPORTANT: Check "Add Python to PATH" during installation.
        echo.
        pause
        exit /b 1
    )
    set "PYTHON=py"
) else (
    set "PYTHON=python"
)

for /f "tokens=2" %%v in ('%PYTHON% --version 2^>^&1') do set "PY_VER=%%v"
echo  [OK] Python %PY_VER% found

:: ── Step 2: Create install directory ──
echo.
echo  [2/5] Creating install directory: %INSTALL_DIR%
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

:: Copy app files
xcopy /E /I /Y "%~dp0..\*" "%INSTALL_DIR%\" >nul
echo  [OK] Files copied to %INSTALL_DIR%

:: ── Step 3: Install Python dependencies ──
echo.
echo  [3/5] Installing Python dependencies (this may take a few minutes)...
%PYTHON% -m pip install --upgrade pip --quiet
%PYTHON% -m pip install -r "%INSTALL_DIR%\requirements.txt" --quiet

if %errorLevel% neq 0 (
    echo  [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)
echo  [OK] Dependencies installed

:: ── Step 4: Create launcher script ──
echo.
echo  [4/5] Creating launcher...

:: Write the VBScript launcher (no terminal window)
set "LAUNCHER_VBS=%INSTALL_DIR%\MainPath.vbs"
(
echo Set oShell = CreateObject^("WScript.Shell"^)
echo oShell.Run "python -m streamlit run """ ^& Chr^(34^) ^& "%INSTALL_DIR%\app.py" ^& Chr^(34^) ^& " --server.headless true --browser.gatherUsageStats false", 0, False
echo WScript.Sleep 3000
echo oShell.Run "start http://localhost:8501", 0, False
) > "%LAUNCHER_VBS%"

:: Also write a .bat launcher (backup)
set "LAUNCHER_BAT=%INSTALL_DIR%\MainPath.bat"
(
echo @echo off
echo title MainPath Analysis Tool
echo echo Starting MainPath Analysis Tool...
echo echo Please wait for your browser to open.
echo echo.
echo echo To stop: close this window
echo echo.
echo start /B python -m streamlit run "%INSTALL_DIR%\app.py" --server.headless true --browser.gatherUsageStats false
echo timeout /t 4 /nobreak ^>nul
echo start http://localhost:8501
echo echo.
echo echo Server running at http://localhost:8501
echo echo Press any key to stop the server...
echo pause ^>nul
echo taskkill /f /im python.exe /t ^>nul 2^>^&1
) > "%LAUNCHER_BAT%"

echo  [OK] Launchers created

:: ── Step 5: Create shortcuts ──
echo.
echo  [5/5] Creating shortcuts...

:: Desktop shortcut (PowerShell)
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%DESKTOP%\MainPath Analysis Tool.lnk'); $s.TargetPath = '%INSTALL_DIR%\MainPath.bat'; $s.WorkingDirectory = '%INSTALL_DIR%'; $s.Description = 'MainPath Analysis Tool'; $s.Save()"

:: Start menu shortcut
if not exist "%START_MENU%" mkdir "%START_MENU%"
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%START_MENU%\MainPath Analysis Tool.lnk'); $s.TargetPath = '%INSTALL_DIR%\MainPath.bat'; $s.WorkingDirectory = '%INSTALL_DIR%'; $s.Description = 'MainPath Analysis Tool'; $s.Save()"

echo  [OK] Shortcuts created on Desktop and Start Menu

:: ── Done ──
echo.
echo  ============================================
echo   Installation Complete!
echo  ============================================
echo.
echo   How to use:
echo   - Double-click "MainPath Analysis Tool" on your Desktop
echo   - Your browser will open automatically at http://localhost:8501
echo   - Close the terminal window to stop the server
echo.
echo   Install location: %INSTALL_DIR%
echo.

set /p "LAUNCH=Launch now? (Y/N): "
if /i "%LAUNCH%"=="Y" (
    start "" "%INSTALL_DIR%\MainPath.bat"
)

pause
