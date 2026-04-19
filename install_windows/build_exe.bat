@echo off
title MainPath — Build Standalone EXE
echo.
echo  Building MainPath.exe with PyInstaller...
echo  (Run this on a Windows machine with Python installed)
echo.

cd /d "%~dp0.."

:: Install PyInstaller if needed
python -m pip install pyinstaller --quiet
if %errorLevel% neq 0 (
    echo [ERROR] Failed to install PyInstaller
    pause
    exit /b 1
)

:: Install all dependencies
python -m pip install -r requirements.txt --quiet

:: Build
python -m PyInstaller mainpath.spec --clean --noconfirm

if %errorLevel% equ 0 (
    echo.
    echo  ============================================
    echo   Build successful!
    echo   Output: dist\MainPath\MainPath.exe
    echo  ============================================
    echo.
    echo  To distribute: zip the entire dist\MainPath\ folder
    echo  Users run: MainPath.exe (no installation needed)
) else (
    echo.
    echo  [ERROR] Build failed. Check output above.
)
pause
