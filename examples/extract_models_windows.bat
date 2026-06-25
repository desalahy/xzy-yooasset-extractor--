@echo off
setlocal

cd /d "%~dp0.."

set "PYTHON_CMD=python"
where py >nul 2>nul
if %ERRORLEVEL%==0 set "PYTHON_CMD=py -3"

REM Change these paths before running.
set GAME_ROOT=E:\XZY\shengtianpc\10046\game
set OUT_DIR=E:\XZY\Models

%PYTHON_CMD% xzy_yooasset_extractor.py ^
  --game-root "%GAME_ROOT%" ^
  --packages CharacterMesh,Art3D ^
  --categories models,materials,textures ^
  --out "%OUT_DIR%" ^
  --limit 0 ^
  --execute ^
  --progress-every 1 ^
  --progress-style bar

pause
