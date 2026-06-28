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

echo XZY YooAsset Full Pipeline
echo.
echo Choose the game root folder. Usually it is the folder that contains XzyLauncher_Data.

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
set /p WORKERS=Worker processes [default 4]:
if not defined WORKERS set "WORKERS=4"

echo.
set /p KEY_TEXT=Packet AES key text [optional]:

echo.
set /p DUMP_CS=Il2CppDumper dump.cs path [optional]:

echo.
set /p PACKET_INPUT=Existing decoded packet tree [optional]:

echo.
echo Starting full pipeline...
echo Game root: %GAME_ROOT%
echo Output:    %OUT_DIR%
echo Workers:   %WORKERS%
echo.

%PYTHON_CMD% tools\run_full_pipeline.py ^
  --game-root "%GAME_ROOT%" ^
  --out "%OUT_DIR%" ^
  --workers %WORKERS% ^
  --progress-every 1 ^
  --progress-style bar ^
  --key-text "%KEY_TEXT%" ^
  --packet-input "%PACKET_INPUT%" ^
  --dump-cs "%DUMP_CS%"

echo.
echo Done. Check pipeline_summary.json under the output folder.
pause
