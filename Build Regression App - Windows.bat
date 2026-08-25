@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo  Regression App v0.3.2 - Windows Builder
echo ==========================================
echo.

set PYTHON=

for %%P in (py python3.14 python3.13 python3.12 python3.11 python3.10 python) do (
    if not defined PYTHON (
        where %%P >nul 2>nul
        if not errorlevel 1 (
            %%P -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
            if not errorlevel 1 set PYTHON=%%P
        )
    )
)

if not defined PYTHON (
    echo Python 3.10 or newer was not found.
    echo Please install a current Python from:
    echo https://www.python.org/downloads/windows/
    echo Select "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo Using Python:
%PYTHON% -c "import sys; print(sys.executable); print(sys.version)"
echo.

echo [1/4] Creating isolated build environment...
if exist .buildenv rmdir /s /q .buildenv
%PYTHON% -m venv .buildenv
call .buildenv\Scripts\activate.bat

echo [2/4] Installing dependencies...
python -m pip install --upgrade pip
python -m pip install --no-compile -r requirements-build.txt

echo [3/4] Building RegressionApp.exe...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist RegressionApp.spec del /q RegressionApp.spec

pyinstaller --noconfirm --clean --windowed --name "RegressionApp" --hidden-import "regression_app.method_comparison" --hidden-import "regression_app.clinical_tools" --hidden-import "regression_app.targetlynx_converter" --hidden-import "regression_app.ui_helpers" --hidden-import "scipy.stats" --collect-all "scipy" --collect-all "matplotlib" main.py
if errorlevel 1 (
    echo Build failed.
    pause
    exit /b 1
)

echo [4/4] Creating distributable ZIP...
powershell -NoProfile -Command "Compress-Archive -Path 'dist\RegressionApp' -DestinationPath 'dist\RegressionApp-Windows.zip' -Force"

echo.
echo SUCCESS
echo Folder app:
echo %cd%\dist\RegressionApp\RegressionApp.exe
echo.
echo Shareable ZIP:
echo %cd%\dist\RegressionApp-Windows.zip
echo.
pause
