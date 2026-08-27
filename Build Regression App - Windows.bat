@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ==========================================
echo  Regression App v0.4.7 - Windows Builder
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
if not exist "regression_app\app.py" (
    echo ERROR: regression_app\app.py is missing.
    goto :build_fail
)

set "PYTHON_CMD="
py -3.12 -c "import sys" >nul 2>nul && set "PYTHON_CMD=py -3.12"
if not defined PYTHON_CMD py -3.13 -c "import sys" >nul 2>nul && set "PYTHON_CMD=py -3.13"
if not defined PYTHON_CMD py -3.14 -c "import sys" >nul 2>nul && set "PYTHON_CMD=py -3.14"
if not defined PYTHON_CMD python -c "import sys; raise SystemExit(0 if (3,10) <= sys.version_info[:2] < (3,15) else 1)" >nul 2>nul && set "PYTHON_CMD=python"

if not defined PYTHON_CMD (
    echo ERROR: Supported Python not found. Python 3.12 64-bit is recommended.
    pause
    exit /b 1
)

if not exist ".buildenv\Scripts\python.exe" (
    echo [1/5] Creating build environment...
    %PYTHON_CMD% -m venv .buildenv
    if errorlevel 1 goto :build_fail
    call .buildenv\Scripts\activate.bat
    python -m pip install --upgrade pip
    if errorlevel 1 goto :build_fail
    python -m pip install --no-compile -r requirements-build.txt
    if errorlevel 1 goto :build_fail
) else (
    echo [1/5] Reusing existing build environment...
    call .buildenv\Scripts\activate.bat
    python -m pip install --no-compile -r requirements-build.txt
    if errorlevel 1 goto :build_fail
)

echo [2/5] Building folder application...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist RegressionApp.spec del /q RegressionApp.spec

python -m PyInstaller --noconfirm --windowed --onedir --name "RegressionApp" --paths "%CD%" --collect-submodules "regression_app" --hidden-import "regression_app.app" --hidden-import "regression_app.weighting_ui_patch" --hidden-import "regression_app.calibration_plot_patch" --hidden-import "scipy.stats" main.py
if errorlevel 1 goto :build_fail

echo [3/5] Validating packaged application...
if not exist "dist\RegressionApp\RegressionApp.exe" goto :build_fail
set "PYDLL="
for /r "dist\RegressionApp" %%F in (python*.dll) do if not defined PYDLL set "PYDLL=%%F"
if not defined PYDLL (
    echo ERROR: bundled Python DLL is missing.
    goto :build_fail
)
"dist\RegressionApp\RegressionApp.exe" --self-test
if errorlevel 1 (
    echo ERROR: packaged application self-test failed.
    echo Check %%USERPROFILE%%\RegressionApp_crash.log.
    goto :build_fail
)

echo [4/5] Creating collaborator-ready ZIP...
> "dist\README-WINDOWS.txt" (
    echo Regression App v0.4.7 - Windows
    echo.
    echo 1. Extract RegressionApp-Windows.zip completely.
    echo 2. Open the extracted RegressionApp folder.
    echo 3. Double-click RegressionApp.exe.
    echo.
    echo No Python installation is required on the collaborator's machine.
)
powershell -NoProfile -Command "Compress-Archive -Path 'dist\RegressionApp' -DestinationPath 'dist\RegressionApp-Windows.zip' -Force"
if errorlevel 1 goto :build_fail

echo [5/5] Finished.
echo Share: %cd%\dist\RegressionApp-Windows.zip
explorer "%cd%\dist"
pause
exit /b 0

:build_fail
echo BUILD / PACKAGE VALIDATION FAILED
pause
exit /b 1
