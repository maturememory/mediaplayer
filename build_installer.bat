@echo off
setlocal EnableExtensions

title Nova Media Player - Windows Installer Build
cd /d "%~dp0"

echo.
echo  ============================================================
echo    Nova Media Player - Windows Installer Build
echo  ============================================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python was not found. Install 64-bit Python 3.10+ and try again.
    exit /b 1
)

if not exist ".venv-build\Scripts\python.exe" (
    echo [INFO] Creating build virtual environment...
    python -m venv .venv-build
    if errorlevel 1 exit /b 1
)

call ".venv-build\Scripts\activate.bat"
python -m pip install --upgrade pip
if errorlevel 1 exit /b 1

python -m pip install -r requirements.txt pyinstaller
if errorlevel 1 exit /b 1

echo.
echo [INFO] Building application bundle with PyInstaller...
python -m PyInstaller nova_player.spec --noconfirm --clean
if errorlevel 1 exit /b 1

set "ISCC="
for %%I in (ISCC.exe) do set "ISCC=%%~$PATH:I"
if not defined ISCC if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"

if not defined ISCC (
    echo.
    echo [ERROR] Inno Setup 6 was not found.
    echo Install it, then rerun this script:
    echo     winget install JRSoftware.InnoSetup
    exit /b 1
)

echo.
echo [INFO] Creating single-file Windows installer...
"%ISCC%" packaging\windows\nova_player.iss
if errorlevel 1 exit /b 1

echo.
echo [OK] Installer created in: dist\installer\
echo.
endlocal
