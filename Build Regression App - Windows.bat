@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

echo ==========================================
echo  Regression App v0.5.17 - Windows Builder
echo ==========================================
echo.

if not exist "main.py" (
    echo ERROR: main.py is missing from the builder folder.
    goto :build_fail
)
if not exist "regression_app\__init__.py" (
    echo ERROR: regression_app package is missing from the builder folder.
    goto :build_fail
)
if not exist "tools\reconstruct_app.py" (
    echo ERROR: tools\reconstruct_app.py is missing.
    goto :build_fail
)

set "PYTHON_CMD="
py -3.14 -c "import sys" >nul 2>nul && set "PYTHON_CMD=py -3.14"
if not defined PYTHON_CMD py -3.13 -c "import sys" >nul 2>nul && set "PYTHON_CMD=py -3.13"
if not defined PYTHON_CMD py -3.12 -c "import sys" >nul 2>nul && set "PYTHON_CMD=py -3.12"
if not defined PYTHON_CMD py -3.11 -c "import sys" >nul 2>nul && set "PYTHON_CMD=py -3.11"
if not defined PYTHON_CMD py -3.10 -c "import sys" >nul 2>nul && set "PYTHON_CMD=py -3.10"
if not defined PYTHON_CMD python -c "import sys; raise SystemExit(0 if (3,10) <= sys.version_info[:2] <= (3,14) else 1)" >nul 2>nul && set "PYTHON_CMD=python"

if not defined PYTHON_CMD (
    echo ERROR: Python 3.10 through 3.14 was not found.
    echo Install a current 64-bit Python release from python.org.
    pause
    exit /b 1
)

for /f %%V in ('%PYTHON_CMD% -c "import sys; print(str(sys.version_info.major)+'.'+str(sys.version_info.minor))"') do set "SELECTED_PY=%%V"
echo Using Python !SELECTED_PY!.

echo [0/5] Preparing verified direct application source...
%PYTHON_CMD% tools\reconstruct_app.py
if errorlevel 1 goto :build_fail

if exist ".buildenv\Scripts\python.exe" (
    for /f %%V in ('.buildenv\Scripts\python.exe -c "import sys; print(str(sys.version_info.major)+'.'+str(sys.version_info.minor))"') do set "ENV_PY=%%V"
    if not "!SELECTED_PY!"=="!ENV_PY!" (
        echo Existing .buildenv uses Python !ENV_PY!; Python !SELECTED_PY! is preferred. Recreating it...
        rmdir /s /q .buildenv
    )
)

set "NEW_ENV=0"
if not exist ".buildenv\Scripts\python.exe" (
    echo [1/5] Creating build environment...
    %PYTHON_CMD% -m venv .buildenv
    if errorlevel 1 goto :build_fail
    set "NEW_ENV=1"
)

call .buildenv\Scripts\activate.bat

set "DEPS_CHANGED=0"
if "!NEW_ENV!"=="1" set "DEPS_CHANGED=1"
if not exist ".buildenv\requirements.txt.snapshot" set "DEPS_CHANGED=1"
if not exist ".buildenv\requirements-build.txt.snapshot" set "DEPS_CHANGED=1"

if exist ".buildenv\requirements.txt.snapshot" (
    fc /b requirements.txt ".buildenv\requirements.txt.snapshot" >nul 2>nul
    if errorlevel 1 set "DEPS_CHANGED=1"
)
if exist ".buildenv\requirements-build.txt.snapshot" (
    fc /b requirements-build.txt ".buildenv\requirements-build.txt.snapshot" >nul 2>nul
    if errorlevel 1 set "DEPS_CHANGED=1"
)

if "!DEPS_CHANGED!"=="0" (
    python -c "import PySide6,numpy,pandas,scipy,matplotlib,openpyxl,PyInstaller" >nul 2>nul
    if errorlevel 1 set "DEPS_CHANGED=1"
)

if "!DEPS_CHANGED!"=="1" (
    echo [1/5] Installing/updating build dependencies...
    if "!NEW_ENV!"=="1" (
        python -m pip install --disable-pip-version-check --upgrade pip
        if errorlevel 1 goto :build_fail
    )
    python -m pip install --disable-pip-version-check --no-compile -r requirements-build.txt
    if errorlevel 1 goto :build_fail
    copy /y requirements.txt ".buildenv\requirements.txt.snapshot" >nul
    copy /y requirements-build.txt ".buildenv\requirements-build.txt.snapshot" >nul
) else (
    echo [1/5] Build environment and dependencies are current; skipping pip.
)

for /f %%V in ('python -c "import regression_app; print(regression_app.__version__)"') do set "APP_VERSION=%%V"
set "CACHE_VERSION="
if exist ".buildenv\pyinstaller-app-version.snapshot" set /p CACHE_VERSION=<".buildenv\pyinstaller-app-version.snapshot"
if not "!CACHE_VERSION!"=="!APP_VERSION!" (
    echo Application version changed from !CACHE_VERSION! to !APP_VERSION!; refreshing PyInstaller analysis cache...
    if exist "build\RegressionApp" rmdir /s /q "build\RegressionApp"
    > ".buildenv\pyinstaller-app-version.snapshot" echo !APP_VERSION!
)

echo [2/5] Preparing output folder...
REM A prior RegressionApp process can keep EXE/DLL files in dist locked on Windows.
REM Close it first, then retry cleanup. If Windows still holds the folder, use
REM a fresh dist directory instead of throwing away the PyInstaller build cache.
taskkill /F /T /IM RegressionApp.exe >nul 2>nul
timeout /t 1 /nobreak >nul

set "DIST_DIR=dist"
if exist "!DIST_DIR!" (
    for /L %%R in (1,1,4) do (
        if exist "!DIST_DIR!" (
            rmdir /s /q "!DIST_DIR!" >nul 2>nul
            if exist "!DIST_DIR!" timeout /t 1 /nobreak >nul
        )
    )
)
if exist "!DIST_DIR!" (
    set "DIST_DIR=dist-v0.5.17-!RANDOM!"
    echo Previous dist folder is still locked; using !DIST_DIR! instead.
)

echo [2/5] Building folder application...
python -m PyInstaller --noconfirm --windowed --onedir --name "RegressionApp" --paths "%CD%" --distpath "!DIST_DIR!" ^
  --hidden-import "regression_app" ^
  --hidden-import "regression_app.app" ^
  --hidden-import "regression_app.ui_helpers" ^
  --hidden-import "regression_app.weighting_ui_patch" ^
  --hidden-import "regression_app.calibration_plot_patch" ^
  --hidden-import "regression_app.amr_validation" ^
  --hidden-import "regression_app.amr_ui_patch" ^
  --hidden-import "regression_app.replicate_studies" ^
  --hidden-import "regression_app.replicate_ui_patch" ^
  --hidden-import "regression_app.targetlynx_converter" ^
  --hidden-import "regression_app.method_comparison" ^
  --hidden-import "regression_app.clinical_tools" ^
  --hidden-import "regression_app.surrogate_is" ^
  --hidden-import "regression_app.surrogate_is_ui_patch" ^
  --hidden-import "scipy.stats" main.py
if errorlevel 1 goto :build_fail

echo [3/5] Validating packaged application...
if not exist "!DIST_DIR!\RegressionApp\RegressionApp.exe" (
    echo ERROR: RegressionApp.exe was not created.
    goto :build_fail
)
REM The packaged executable self-test is the authoritative runtime check.
REM If it launches and imports the app successfully, its bundled Python runtime
REM and dependent DLLs are present and loadable.
"!DIST_DIR!\RegressionApp\RegressionApp.exe" --self-test
if errorlevel 1 (
    echo ERROR: packaged application self-test failed.
    echo Check %%USERPROFILE%%\RegressionApp_crash.log.
    goto :build_fail
)

echo [4/5] Creating collaborator-ready ZIP...
> "!DIST_DIR!\README-WINDOWS.txt" (
    echo Regression App v0.5.17 - Windows
    echo.
    echo 1. Extract RegressionApp-Windows.zip completely.
    echo 2. Open the extracted RegressionApp folder.
    echo 3. Double-click RegressionApp.exe.
    echo.
    echo No Python installation is required on the collaborator's machine.
)
powershell -NoProfile -Command "Compress-Archive -Path '!DIST_DIR!\RegressionApp' -DestinationPath '!DIST_DIR!\RegressionApp-Windows.zip' -Force"
if errorlevel 1 goto :build_fail

echo [5/5] Finished.
echo Share: %cd%\!DIST_DIR!\RegressionApp-Windows.zip
explorer "%cd%\!DIST_DIR!"
pause
exit /b 0

:build_fail
echo BUILD / PACKAGE VALIDATION FAILED
pause
exit /b 1
