#!/bin/bash

set -u
cd "$(dirname "$0")"

echo "=========================================="
echo " Regression App macOS Builder v0.3.2"
echo "=========================================="
echo

fail() {
    echo
    echo "ERROR: $1"
    echo
    read -n 1 -s -r -p "Press any key to close..."
    exit 1
}

is_supported_python() {
    local P="$1"
    [ -x "$P" ] || return 1
    if [[ "$P" == "/usr/bin/python3" ]] || [[ "$P" == *"/Xcode.app/"* ]]; then
        return 1
    fi
    "$P" - <<'PY' >/dev/null 2>&1
import sys
major, minor = sys.version_info[:2]
raise SystemExit(0 if major == 3 and 10 <= minor <= 14 else 1)
PY
}

PYTHON=""
for CANDIDATE in python3.14 python3.13 python3.12 python3.11 python3.10 python3; do
    FOUND="$(command -v "$CANDIDATE" 2>/dev/null || true)"
    if [ -n "$FOUND" ] && is_supported_python "$FOUND"; then
        PYTHON="$FOUND"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    for FOUND in \
        /opt/homebrew/bin/python3 \
        /usr/local/bin/python3 \
        /Library/Frameworks/Python.framework/Versions/3.14/bin/python3 \
        /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 \
        /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 \
        /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 \
        /Library/Frameworks/Python.framework/Versions/3.10/bin/python3
    do
        if is_supported_python "$FOUND"; then
            PYTHON="$FOUND"
            break
        fi
    done
fi

if [ -z "$PYTHON" ]; then
    echo "No supported standalone Python installation was detected."
    echo
    echo "Supported versions: Python 3.10 through 3.14."
    echo "Apple/Xcode's system Python is intentionally excluded."
    echo
    echo "Diagnostic information:"
    echo "  python3 --version:"
    python3 --version 2>&1 || true
    echo
    echo "  which python3:"
    which python3 2>&1 || true
    echo
    fail "Supported Python installation not found."
fi

echo "Using Python:"
"$PYTHON" --version
echo "$PYTHON"
echo

rm -rf .buildenv build dist RegressionApp.spec

echo "Creating build environment..."
"$PYTHON" -m venv .buildenv || fail "Could not create virtual environment."
source .buildenv/bin/activate

echo
echo "Installing dependencies..."
python -m pip install --upgrade pip || fail "pip upgrade failed."
python -m pip install --no-compile -r requirements-build.txt || fail "Dependency installation failed."

echo
echo "Building RegressionApp.app..."
pyinstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name RegressionApp \
  --hidden-import regression_app.method_comparison \
  --hidden-import regression_app.clinical_tools \
  --hidden-import regression_app.targetlynx_converter \
  --hidden-import regression_app.ui_helpers \
  --hidden-import scipy.stats \
  --collect-all scipy \
  --collect-all matplotlib \
  main.py || fail "PyInstaller build failed."

[ -d "dist/RegressionApp.app" ] || fail "dist/RegressionApp.app was not created."

rm -f RegressionApp-macOS.zip
ditto -c -k --sequesterRsrc --keepParent "dist/RegressionApp.app" "RegressionApp-macOS.zip" \
  || fail "Could not create output ZIP."

OUTPUT_DIR="$HOME/Desktop/RegressionApp-v0.3.2"
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"
cp -R "dist/RegressionApp.app" "$OUTPUT_DIR/"
cp "RegressionApp-macOS.zip" "$OUTPUT_DIR/"

echo
echo "=========================================="
echo " BUILD COMPLETE"
echo "=========================================="
echo
echo "Output:"
echo "$OUTPUT_DIR"
echo

open "$OUTPUT_DIR"
osascript -e 'display dialog "Regression App v0.3.2 finished building. The output folder has been opened on your Desktop." buttons {"OK"} default button "OK"'
echo
read -n 1 -s -r -p "Press any key to close..."
echo
