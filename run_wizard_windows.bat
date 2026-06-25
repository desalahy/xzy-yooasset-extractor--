@echo off
setlocal EnableExtensions

cd /d "%~dp0"

set "PYTHON_CMD=python"
where py >nul 2>nul
if %ERRORLEVEL%==0 set "PYTHON_CMD=py -3"

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
echo   6. All local packages
echo   7. Bundle index only, no Unity object export
echo.
set /p MODE=Mode number:

echo.
set /p WORKERS=Worker processes [default 4]:
if not defined WORKERS set "WORKERS=4"

set "EXTRA_ARGS="
if "%MODE%"=="1" set "EXTRA_ARGS=--packages Icon,Main,Spine --categories ui --types Texture2D,Sprite"
if "%MODE%"=="2" set "EXTRA_ARGS=--packages Bgm --categories bgm --types AudioClip"
if "%MODE%"=="3" set "EXTRA_ARGS=--packages Se,Voice --categories audio --types AudioClip"
if "%MODE%"=="4" set "EXTRA_ARGS=--packages CharacterMesh,Art3D --categories models,materials,textures"
if "%MODE%"=="5" set "EXTRA_ARGS=--packages BattlePacket,AnimationPacket,CharacterPerformance --categories effects,animation,materials,textures,prefabs,raw --copy-rawfiles"
if "%MODE%"=="6" set "EXTRA_ARGS=--copy-rawfiles"
if "%MODE%"=="7" set "EXTRA_ARGS=--no-export"

if not defined EXTRA_ARGS if not "%MODE%"=="6" (
  echo Invalid mode.
  pause
  exit /b 1
)

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
