@echo off
title MainPath Analysis Tool
color 0B

echo.
echo  =========================================
echo    MainPath Analysis Tool
echo    Starting server, please wait...
echo  =========================================
echo.

:: Find Python
where python >nul 2>&1
if %errorLevel% equ 0 (
    set "PYTHON=python"
) else (
    where py >nul 2>&1
    if %errorLevel% equ 0 (
        set "PYTHON=py"
    ) else (
        echo  [ERROR] Python not found!
        echo  Please run install_windows\install.bat first.
        pause
        exit /b 1
    )
)

:: Change to app directory
cd /d "%~dp0"

:: Check if streamlit is installed
%PYTHON% -c "import streamlit" >nul 2>&1
if %errorLevel% neq 0 (
    echo  Installing dependencies...
    %PYTHON% -m pip install -r requirements.txt --quiet
)

:: Start Streamlit in background
echo  Starting server at http://localhost:8501
echo  Your browser will open automatically.
echo.
echo  Press Ctrl+C or close this window to stop.
echo.

start /B %PYTHON% -m streamlit run app.py --server.headless true --browser.gatherUsageStats false --server.port 8501

:: Wait for server to start
timeout /t 4 /nobreak >nul

:: Open browser
start http://localhost:8501

:: Keep window open so user can see status / stop server
echo  Server is running. Close this window to stop.
echo.
:LOOP
timeout /t 5 /nobreak >nul
goto LOOP
