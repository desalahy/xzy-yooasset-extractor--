@echo off
setlocal EnableExtensions

cd /d "%~dp0"

where uv >nul 2>nul
if not %ERRORLEVEL%==0 (
  echo uv is required. Install uv first, then run this script again.
  echo https://docs.astral.sh/uv/
  pause
  exit /b 1
)

echo Syncing Python dependencies with uv...
set "UV_CACHE_DIR=%CD%\.uv-cache"
uv sync
if not %ERRORLEVEL%==0 (
  where py >nul 2>nul
  if %ERRORLEVEL%==0 (
    for /f "usebackq delims=" %%I in (`py -3 -c "import sys; print(sys.executable)"`) do set "UV_PYTHON=%%I"
    echo Retrying uv sync with UV_PYTHON=%UV_PYTHON%
    uv sync
  )
)
if not %ERRORLEVEL%==0 (
  echo uv sync failed.
  echo If uv cannot discover Python on this machine, set UV_PYTHON to a Python 3.10+ executable and retry.
  pause
  exit /b 1
)

set "PYTHON_CMD=uv run python"

echo XZY YooAsset Extractor Windows Wizard
echo.
echo Choose the game root folder. Usually it is the folder that contains XzyLauncher_Data.
echo The wizard scans both XzyLauncher_Data\yoo and XzyLauncher_Data\StreamingAssets\yoo when present.

for /f "usebackq delims=" %%I in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "Add-Type -AssemblyName System.Windows.Forms; $d = New-Object System.Windows.Forms.FolderBrowserDialog; $d.Description = 'Choose game root folder, for example E:\XZY\shengtianpc\10046\game'; if ($d.ShowDialog() -eq 'OK') { $d.SelectedPath }"`) do set "GAME_ROOT=%%I"

if not defined GAME_ROOT (
  echo No game root selected.
  pause
  exit /b 1
)

echo.
echo Choose output folder.

for /f "usebackq delims=" %%I in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "Add-Type -AssemblyName System.Windows.Forms; $d = New-Object System.Windows.Forms.FolderBrowserDialog; $d.Description = 'Choose output folder'; if ($d.ShowDialog() -eq 'OK') { $d.SelectedPath }"`) do set "OUT_DIR=%%I"

if not defined OUT_DIR (
  echo No output folder selected.
  pause
  exit /b 1
)

echo.
echo Select export mode:
echo   1. UI images
echo   2. BGM
echo   3. Audio and voice
echo   4. Models/materials/textures
echo   5. Effects/animation/materials/textures/prefabs
echo   6. All local packages (export only)
echo   7. Bundle index only, no Unity object export
echo   8. Full pipeline (export + Packet/table/bin/text/organize)
echo   9. Full pipeline from existing export cache (skip export stage)
echo.
echo Modes 1-7 stop after the Unity export stage. Modes 8 and 9 run the full chain.
echo.
set /p MODE=Mode number:

echo.
set /p WORKERS=Worker processes [default 4]:
if not defined WORKERS set "WORKERS=4"

set "KEY_TEXT="
set "KEY_HEX="
set "IV_HEX="
set "PACKET_NAME="
set "DUMP_CS="
set "PACKET_INPUT="
set "EXTRA_ARGS="
if "%MODE%"=="1" set "EXTRA_ARGS=--packages Icon,Main,Spine --categories ui --types Texture2D,Sprite"
if "%MODE%"=="2" set "EXTRA_ARGS=--packages Bgm --categories bgm --types AudioClip"
if "%MODE%"=="3" set "EXTRA_ARGS=--packages Se,Voice --categories audio --types AudioClip"
if "%MODE%"=="4" set "EXTRA_ARGS=--packages CharacterMesh,Art3D --categories models,materials,textures"
if "%MODE%"=="5" set "EXTRA_ARGS=--packages BattlePacket,AnimationPacket,CharacterPerformance --categories effects,animation,materials,textures,prefabs,raw --copy-rawfiles"
if "%MODE%"=="6" set "EXTRA_ARGS=--copy-rawfiles"
if "%MODE%"=="7" set "EXTRA_ARGS=--no-export"

if "%MODE%"=="8" goto FULL_PIPELINE
if "%MODE%"=="9" goto FULL_PIPELINE_SKIP
if defined EXTRA_ARGS goto EXPORT_ONLY

echo Invalid mode.
pause
exit /b 1

:FULL_PIPELINE
echo.
set /p KEY_TEXT=Packet AES key text [optional, press Enter to skip]:
echo.
set /p KEY_HEX=Packet AES key hex [optional, press Enter to skip]:
echo.
set /p IV_HEX=Packet AES IV hex [optional, press Enter to skip]:
echo.
set /p PACKET_NAME=Packet logical name [optional, press Enter to skip]:
echo.
set /p DUMP_CS=Il2CppDumper dump.cs full path [optional, press Enter to skip]:
echo.
set /p PACKET_INPUT=Existing decoded packet tree [optional, press Enter to skip]:

echo.
echo Game root: %GAME_ROOT%
echo Output:    %OUT_DIR%
echo Workers:   %WORKERS%
echo Pipeline:  full chain
echo.

%PYTHON_CMD% tools\run_full_pipeline.py ^
  --game-root "%GAME_ROOT%" ^
  --out "%OUT_DIR%" ^
  --workers %WORKERS% ^
  --progress-every 1 ^
  --progress-style bar ^
  --key-text "%KEY_TEXT%" ^
  --key-hex "%KEY_HEX%" ^
  --iv-hex "%IV_HEX%" ^
  --packet-name "%PACKET_NAME%" ^
  --packet-input "%PACKET_INPUT%" ^
  --dump-cs "%DUMP_CS%"

echo.
echo Done. Check pipeline_summary.json, table_texts_activity, table_texts_all, bin_probe, and organized in the output folder.
pause
exit /b 0

:FULL_PIPELINE_SKIP
echo.
set /p KEY_TEXT=Packet AES key text [optional, press Enter to skip]:
echo.
set /p KEY_HEX=Packet AES key hex [optional, press Enter to skip]:
echo.
set /p IV_HEX=Packet AES IV hex [optional, press Enter to skip]:
echo.
set /p PACKET_NAME=Packet logical name [optional, press Enter to skip]:
echo.
set /p DUMP_CS=Il2CppDumper dump.cs full path [optional, press Enter to skip]:
echo.
set /p PACKET_INPUT=Existing decoded packet tree [optional, press Enter to skip]:

echo.
echo Game root: %GAME_ROOT%
echo Output:    %OUT_DIR%
echo Workers:   %WORKERS%
echo Pipeline:  full chain, reuse existing export cache
echo.

%PYTHON_CMD% tools\run_full_pipeline.py ^
  --game-root "%GAME_ROOT%" ^
  --out "%OUT_DIR%" ^
  --workers %WORKERS% ^
  --progress-every 1 ^
  --progress-style bar ^
  --skip-export ^
  --key-text "%KEY_TEXT%" ^
  --key-hex "%KEY_HEX%" ^
  --iv-hex "%IV_HEX%" ^
  --packet-name "%PACKET_NAME%" ^
  --packet-input "%PACKET_INPUT%" ^
  --dump-cs "%DUMP_CS%"

echo.
echo Done. Check pipeline_summary.json, table_texts_activity, table_texts_all, bin_probe, and organized in the output folder.
pause
exit /b 0

:EXPORT_ONLY
echo.
echo Game root: %GAME_ROOT%
echo Output:    %OUT_DIR%
echo Workers:   %WORKERS%
echo Args:      %EXTRA_ARGS%
echo.

%PYTHON_CMD% xzy_yooasset_extractor.py ^
  --game-root "%GAME_ROOT%" ^
  --out "%OUT_DIR%" ^
  --limit 0 ^
  --execute ^
  --workers %WORKERS% ^
  --progress-every 1 ^
  --progress-style bar ^
  %EXTRA_ARGS%

echo.
echo Done. Check summary.json, package_report.csv, bundles.csv, assets.csv, and manifest_refs.csv in the output folder.
pause
