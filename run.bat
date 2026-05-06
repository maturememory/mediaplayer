@echo off
:: Run Nova Media Player
:: Optional: pass a file path as argument to open it immediately
::   run.bat "C:\Videos\mymovie.mkv"

cd /d "%~dp0"
python nova_player.py %*
