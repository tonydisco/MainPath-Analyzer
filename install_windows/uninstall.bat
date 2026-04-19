@echo off
title MainPath Analysis Tool — Uninstaller
color 0C

echo.
echo  Uninstalling MainPath Analysis Tool...
echo.

set "INSTALL_DIR=%ProgramFiles%\MainPath"
set "DESKTOP=%USERPROFILE%\Desktop"
set "START_MENU=%APPDATA%\Microsoft\Windows\Start Menu\Programs\MainPath"

:: Stop any running instances
taskkill /f /im python.exe /fi "WINDOWTITLE eq MainPath*" >nul 2>&1

:: Remove files
if exist "%INSTALL_DIR%" (
    rmdir /s /q "%INSTALL_DIR%"
    echo  [OK] Removed %INSTALL_DIR%
)

:: Remove shortcuts
if exist "%DESKTOP%\MainPath Analysis Tool.lnk" (
    del "%DESKTOP%\MainPath Analysis Tool.lnk"
    echo  [OK] Removed Desktop shortcut
)

if exist "%START_MENU%" (
    rmdir /s /q "%START_MENU%"
    echo  [OK] Removed Start Menu shortcut
)

echo.
echo  Uninstall complete.
pause
