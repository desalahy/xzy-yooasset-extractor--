@echo off
setlocal

cd /d "%~dp0.."

set "PYTHON_CMD=python"
where py >nul 2>nul
if %ERRORLEVEL%==0 set "PYTHON_CMD=py -3"

REM Change these two paths before running.
set GAME_ROOT=E:\XZY\shengtianpc\10046\game
set OUT_DIR=E:\XZY\UI
set WORKERS=4

%PYTHON_CMD% xzy_yooasset_extractor.py ^
  --game-root "%GAME_ROOT%" ^
  --packages Icon,Main,Spine ^
  --categories ui ^
  --types Texture2D,Sprite ^
  --out "%OUT_DIR%" ^
  --limit 0 ^
  --execute ^
  --workers %WORKERS% ^
  --progress-every 1 ^
  --progress-style bar

pause
