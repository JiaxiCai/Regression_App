#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "=========================================="
echo " Regression App v0.2.0 - macOS Builder"
echo "=========================================="
echo

# Prefer a normal standalone Python installation. Do not use Xcode's bundled Python.
PYTHON=""

for candidate in python3.12 python3.11 python3.10; do
    if command -v "$candidate" >/dev/null 2>&1; then
        PYTHON="$(command -v "$candidate")"
        break
    fi
done

# Fall back to python3 only when it is >= 3.10 and is not Xcode's bundled interpreter.
if [ -z "$PYTHON" ] && command -v python3 >/dev/null 2>&1; then
    CANDIDATE="$(command -v python3)"
    VERSION="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || true)"
    MAJOR="$(echo "$VERSION" | cut -d. -f1)"
    MINOR="$(echo "$VERSION" | cut -d. -f2)"

    if [[ "$CANDIDATE" != *"/Applications/Xcode.app/"* ]] && \
       [ "${MAJOR:-0}" -ge 3 ] && [ "${MINOR:-0}" -ge 10 ]; then
        PYTHON="$CANDIDATE"
    fi
fi

if [ -z "$PYTHON" ]; then
    echo "A suitable Python installation was not found."
    echo
    echo "Regression App requires Python 3.10 or newer to BUILD."
    echo "Your Mac appears to be using Apple's/Xcode's bundled Python 3.9,"
    echo "which should not be used for this build."
    echo
    echo "Please install Python 3.12 from:"
    echo "https://www.python.org/downloads/macos/"
    echo
    echo "After installation, double-click this builder again."
    echo
    read -n 1 -s -r -p "Press any key to close..."
    exit 1
fi

echo "Using Python:"
"$PYTHON" -c 'import sys; print(sys.executable); print(sys.version)'
echo

echo "[1/4] Creating isolated build environment..."
rm -rf .buildenv
"$PYTHON" -m venv .buildenv
source .buildenv/bin/activate

echo "[2/4] Installing dependencies..."
python -m pip install --upgrade pip
# --no-compile avoids a known pip/PySide6 interaction where template .py files
# are incorrectly byte-compiled during installation.
python -m pip install --no-compile -r requirements-build.txt

echo "[3/4] Building RegressionApp.app..."
rm -rf build dist RegressionApp.spec
pyinstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name "RegressionApp" \
  --osx-bundle-identifier "org.regressionapp.desktop" \
  --hidden-import "regression_app.method_comparison" \
  --hidden-import "regression_app.clinical_tools" \
  --hidden-import "regression_app.targetlynx_converter" \
  --hidden-import "scipy.stats" \
  --collect-all "scipy" \
  --collect-all "matplotlib" \
  main.py

echo "[4/4] Creating distributable ZIP..."
cd dist
rm -f RegressionApp-macOS.zip
ditto -c -k --sequesterRsrc --keepParent "RegressionApp.app" "RegressionApp-macOS.zip"
cd ..

echo
echo "SUCCESS"
echo
echo "App:"
echo "$(pwd)/dist/RegressionApp.app"
echo
echo "Shareable ZIP:"
echo "$(pwd)/dist/RegressionApp-macOS.zip"
echo
echo "Development builds are not yet Apple-signed/notarized."
echo "On another Mac, Control-click > Open may be required the first time."
echo
read -n 1 -s -r -p "Press any key to close..."
