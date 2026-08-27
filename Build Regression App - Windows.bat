@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ==========================================
echo  Regression App v0.3.5 - Windows Builder
echo ==========================================
echo.

set "PYTHON_CMD="

py -3.12 -c "import sys; print(sys.executable)" >nul 2>nul && set "PYTHON_CMD=py -3.12"
if not defined PYTHON_CMD py -3.13 -c "import sys; print(sys.executable)" >nul 2>nul && set "PYTHON_CMD=py -3.13"
if not defined PYTHON_CMD py -3.14 -c "import sys; print(sys.executable)" >nul 2>nul && set "PYTHON_CMD=py -3.14"
if not defined PYTHON_CMD python3.12 -c "import sys" >nul 2>nul && set "PYTHON_CMD=python3.12"
if not defined PYTHON_CMD python3.13 -c "import sys" >nul 2>nul && set "PYTHON_CMD=python3.13"
if not defined PYTHON_CMD python3.14 -c "import sys" >nul 2>nul && set "PYTHON_CMD=python3.14"
if not defined PYTHON_CMD python -c "import sys; raise SystemExit(0 if (3,10) <= sys.version_info[:2] < (3,15) else 1)" >nul 2>nul && set "PYTHON_CMD=python"

if not defined PYTHON_CMD (
    echo ERROR: A supported Python installation was not found.
    echo Recommended: 64-bit Python 3.12 from python.org.
    pause
    exit /b 1
)

echo Using Python:
%PYTHON_CMD% -c "import sys, platform; print(sys.executable); print(sys.version); print(platform.architecture())"
echo.

echo [1/7] Creating isolated build environment...
if exist .buildenv rmdir /s /q .buildenv
%PYTHON_CMD% -m venv .buildenv
if errorlevel 1 goto :build_fail
call .buildenv\Scripts\activate.bat

echo [2/7] Installing dependencies...
python -m pip install --upgrade pip
if errorlevel 1 goto :build_fail
python -m pip install --no-compile -r requirements-build.txt
if errorlevel 1 goto :build_fail
python -m PyInstaller --version

echo [3/7] Building normal folder application...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist RegressionApp.spec del /q RegressionApp.spec
if exist RegressionApp-Portable.spec del /q RegressionApp-Portable.spec

python -m PyInstaller --noconfirm --clean --windowed --onedir --name "RegressionApp" --collect-submodules "regression_app" --hidden-import "scipy.stats" --collect-all "scipy" --collect-all "matplotlib" main.py
if errorlevel 1 goto :build_fail

echo [4/7] Verifying folder bundle...
if not exist "dist\RegressionApp\RegressionApp.exe" goto :build_fail
set "PYDLL="
for /r "dist\RegressionApp" %%F in (python*.dll) do (
    if not defined PYDLL set "PYDLL=%%F"
)
if not defined PYDLL (
    echo ERROR: The bundled Python DLL is missing.
    goto :build_fail
)
echo Found bundled Python DLL:
echo %PYDLL%
"dist\RegressionApp\RegressionApp.exe" --self-test
if errorlevel 1 (
    echo ERROR: Folder bundle self-test failed.
    echo Check %%USERPROFILE%%\RegressionApp_crash.log.
    goto :build_fail
)
echo Folder bundle self-test passed.

echo [5/7] Building single-file portable application...
python -m PyInstaller --noconfirm --clean --windowed --onefile --name "RegressionApp-Portable" --collect-submodules "regression_app" --hidden-import "scipy.stats" --collect-all "scipy" --collect-all "matplotlib" main.py
if errorlevel 1 goto :build_fail
if not exist "dist\RegressionApp-Portable.exe" goto :build_fail

echo Testing portable application...
"dist\RegressionApp-Portable.exe" --self-test
if errorlevel 1 (
    echo ERROR: Portable bundle self-test failed.
    echo Check %%USERPROFILE%%\RegressionApp_crash.log.
    goto :build_fail
)
echo Portable bundle self-test passed.

echo [6/7] Creating distributable ZIP and instructions...
> "dist\README-WINDOWS.txt" (
    echo Regression App v0.3.5 - Windows
    echo.
    echo EASIEST OPTION:
    echo   Run RegressionApp-Portable.exe.
    echo.
    echo FOLDER OPTION:
    echo   Extract RegressionApp-Windows.zip completely first.
    echo   Then open RegressionApp\RegressionApp.exe.
    echo.
    echo IMPORTANT:
    echo   Do NOT run RegressionApp.exe from inside the ZIP.
    echo   Do NOT copy RegressionApp.exe by itself.
    echo.
    echo This build also validates the dynamically loaded Regression App GUI
    echo modules before reporting success.
)
powershell -NoProfile -Command "Compress-Archive -Path 'dist\RegressionApp' -DestinationPath 'dist\RegressionApp-Windows.zip' -Force"
if errorlevel 1 goto :build_fail

echo [7/7] Finished.
echo.
echo SUCCESS
echo Recommended file to share:
echo   %cd%\dist\RegressionApp-Portable.exe
echo Alternative:
echo   %cd%\dist\RegressionApp-Windows.zip
explorer "%cd%\dist"
pause
exit /b 0

:build_fail
echo.
echo BUILD / PACKAGE VALIDATION FAILED
pause
exit /b 1
