@echo off
setlocal

REM Change these paths before running.
set GAME_ROOT=E:\XZY\shengtianpc\10046\game
set OUT_DIR=E:\XZY\Models

python xzy_yooasset_extractor.py ^
  --game-root "%GAME_ROOT%" ^
  --packages CharacterMesh,Art3D ^
  --categories models,materials,textures ^
  --out "%OUT_DIR%" ^
  --limit 0 ^
  --execute ^
  --progress-every 20

pause
