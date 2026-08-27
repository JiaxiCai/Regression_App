#!/bin/bash
set -u
cd "$(dirname "$0")"

echo "=========================================="
echo " Regression App macOS Builder v0.4.0"
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
for CANDIDATE in python3.12 python3.13 python3.14 python3.11 python3.10 python3; do
    FOUND="$(command -v "$CANDIDATE" 2>/dev/null || true)"
    if [ -n "$FOUND" ] && is_supported_python "$FOUND"; then
        PYTHON="$FOUND"
        break
    fi
done

[ -n "$PYTHON" ] || fail "Supported Python installation not found."

if [ ! -x ".buildenv/bin/python" ]; then
    echo "[1/4] Creating build environment..."
    "$PYTHON" -m venv .buildenv || fail "Could not create virtual environment."
    source .buildenv/bin/activate
    python -m pip install --upgrade pip || fail "pip upgrade failed."
    python -m pip install --no-compile -r requirements-build.txt || fail "Dependency installation failed."
else
    echo "[1/4] Reusing existing build environment..."
    source .buildenv/bin/activate
    python -m pip install --no-compile -r requirements-build.txt || fail "Dependency check failed."
fi

echo "[2/4] Building RegressionApp.app..."
rm -rf build dist RegressionApp.spec
python -m PyInstaller --noconfirm --windowed --onedir --name RegressionApp --collect-submodules regression_app --hidden-import scipy.stats main.py || fail "PyInstaller build failed."

[ -d "dist/RegressionApp.app" ] || fail "dist/RegressionApp.app was not created."

echo "[3/4] Creating ZIP..."
rm -f RegressionApp-macOS.zip
ditto -c -k --sequesterRsrc --keepParent "dist/RegressionApp.app" "RegressionApp-macOS.zip" || fail "Could not create output ZIP."

OUTPUT_DIR="$HOME/Desktop/RegressionApp-v0.4.0"
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"
cp -R "dist/RegressionApp.app" "$OUTPUT_DIR/"
cp "RegressionApp-macOS.zip" "$OUTPUT_DIR/"

echo "[4/4] Finished."
open "$OUTPUT_DIR"
osascript -e 'display dialog "Regression App v0.4.0 finished building. The output folder has been opened on your Desktop." buttons {"OK"} default button "OK"'
read -n 1 -s -r -p "Press any key to close..."
echo
