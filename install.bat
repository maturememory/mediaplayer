@echo off
title Nova Media Player — Installer
color 0B
echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║          Nova Media Player — Setup                   ║
echo  ╚══════════════════════════════════════════════════════╝
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python not found. Download from https://www.python.org
    pause
    exit /b 1
)
echo  [OK] Python found

:: Check pip
pip --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] pip not found. Reinstall Python with pip option enabled.
    pause
    exit /b 1
)

echo.
echo  Installing Python packages ...
echo  (This may take a few minutes — torch + whisper are large downloads)
echo.

pip install PyQt6 python-vlc Pillow

echo.
echo  Installing OpenAI Whisper (AI subtitle engine) ...
pip install openai-whisper

echo.
echo  ══════════════════════════════════════════════════════
echo.
echo  IMPORTANT — Two more manual installs required:
echo.
echo  1. VLC Media Player (for video/audio playback)
echo     https://www.videolan.org/vlc/download-windows.html
echo     Install the 64-bit version.
echo.
echo  2. FFmpeg (required by Whisper for audio processing)
echo     https://github.com/BtbN/FFmpeg-Builds/releases
echo     Download ffmpeg-master-latest-win64-gpl.zip,
echo     extract it, and add the /bin folder to your PATH.
echo     (Or use: winget install ffmpeg)
echo.
echo  ══════════════════════════════════════════════════════
echo.
echo  Setup complete! Run the player with:  run.bat
echo.
pause
