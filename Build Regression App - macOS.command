#!/bin/bash
set -u
cd "$(dirname "$0")"

echo "=========================================="
echo " Regression App v0.5.28 - macOS Builder"
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
    [[ "$P" == "/usr/bin/python3" ]] && return 1
    [[ "$P" == *"/Xcode.app/"* ]] && return 1
    "$P" -c 'import sys; raise SystemExit(0 if (3,10) <= sys.version_info[:2] <= (3,14) else 1)' >/dev/null 2>&1
}

[ -f main.py ] || fail "main.py is missing."
[ -f regression_app/__init__.py ] || fail "regression_app package is missing."
[ -f tools/reconstruct_app.py ] || fail "tools/reconstruct_app.py is missing."

PYTHON=""
for CANDIDATE in python3.14 python3.13 python3.12 python3.11 python3.10 python3; do
    FOUND="$(command -v "$CANDIDATE" 2>/dev/null || true)"
    if [ -n "$FOUND" ] && is_supported_python "$FOUND"; then
        PYTHON="$FOUND"
        break
    fi
done
[ -n "$PYTHON" ] || fail "Python 3.10–3.14 was not found."

SELECTED_PY="$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
echo "Using Python $SELECTED_PY."

echo "[0/5] Preparing verified direct application source..."
"$PYTHON" tools/reconstruct_app.py || fail "Could not reconstruct direct application source."

if [ -x .buildenv/bin/python ]; then
    ENV_PY="$(.buildenv/bin/python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || true)"
    if [ "$SELECTED_PY" != "$ENV_PY" ]; then
        echo "Existing .buildenv uses Python $ENV_PY; Python $SELECTED_PY is preferred. Recreating it..."
        rm -rf .buildenv
    fi
fi

NEW_ENV=0
if [ ! -x .buildenv/bin/python ]; then
    echo "[1/5] Creating build environment..."
    "$PYTHON" -m venv .buildenv || fail "Could not create build environment."
    NEW_ENV=1
fi

source .buildenv/bin/activate

DEPS_CHANGED=0
[ "$NEW_ENV" = "1" ] && DEPS_CHANGED=1
[ -f .buildenv/requirements.txt.snapshot ] || DEPS_CHANGED=1
[ -f .buildenv/requirements-build.txt.snapshot ] || DEPS_CHANGED=1

if [ "$DEPS_CHANGED" = "0" ]; then
    cmp -s requirements.txt .buildenv/requirements.txt.snapshot || DEPS_CHANGED=1
    cmp -s requirements-build.txt .buildenv/requirements-build.txt.snapshot || DEPS_CHANGED=1
fi

if [ "$DEPS_CHANGED" = "0" ]; then
    python -c 'import PySide6,numpy,pandas,scipy,matplotlib,openpyxl,PyInstaller' >/dev/null 2>&1 || DEPS_CHANGED=1
fi

if [ "$DEPS_CHANGED" = "1" ]; then
    echo "[1/5] Installing/updating build dependencies..."
    if [ "$NEW_ENV" = "1" ]; then
        python -m pip install --disable-pip-version-check --upgrade pip || fail "pip upgrade failed."
    fi
    python -m pip install --disable-pip-version-check --no-compile -r requirements-build.txt || fail "Dependency installation failed."
    cp requirements.txt .buildenv/requirements.txt.snapshot
    cp requirements-build.txt .buildenv/requirements-build.txt.snapshot
else
    echo "[1/5] Build environment and dependencies are current; skipping pip."
fi

APP_VERSION="$(python -c 'import regression_app; print(regression_app.__version__)')"
CACHE_VERSION="$(cat .buildenv/pyinstaller-app-version.snapshot 2>/dev/null || true)"
if [ "$CACHE_VERSION" != "$APP_VERSION" ]; then
    echo "Application version changed; refreshing PyInstaller analysis cache..."
    rm -rf build/RegressionApp
    printf '%s\n' "$APP_VERSION" > .buildenv/pyinstaller-app-version.snapshot
fi

echo "[2/5] Building RegressionApp.app..."
# Preserve PyInstaller's analysis cache within the same app version.
rm -rf dist
python -m PyInstaller \
  --noconfirm \
  --windowed \
  --onedir \
  --name RegressionApp \
  --paths "$PWD" \
  --hidden-import regression_app \
  --hidden-import regression_app.app \
  --hidden-import regression_app.ui_helpers \
  --hidden-import regression_app.weighting_ui_patch \
  --hidden-import regression_app.calibration_plot_patch \
  --hidden-import regression_app.amr_validation \
  --hidden-import regression_app.amr_ui_patch \
  --hidden-import regression_app.replicate_studies \
  --hidden-import regression_app.replicate_ui_patch \
  --hidden-import regression_app.targetlynx_converter \
  --hidden-import regression_app.method_comparison \
  --hidden-import regression_app.clinical_tools \
  --hidden-import regression_app.surrogate_is \
  --hidden-import regression_app.surrogate_is_ui_patch \
  --hidden-import scipy.stats \
  main.py || fail "PyInstaller build failed."

[ -x dist/RegressionApp.app/Contents/MacOS/RegressionApp ] || fail "Packaged executable was not created."

echo "[3/5] Validating packaged application..."
dist/RegressionApp.app/Contents/MacOS/RegressionApp --self-test || fail "Packaged application self-test failed. Check $HOME/RegressionApp_crash.log."

echo "[4/5] Creating ZIP..."
rm -f RegressionApp-macOS.zip
ditto -c -k --sequesterRsrc --keepParent dist/RegressionApp.app RegressionApp-macOS.zip || fail "Could not create ZIP."

OUTPUT_DIR="$HOME/Desktop/RegressionApp-v0.5.28"
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"
cp -R dist/RegressionApp.app "$OUTPUT_DIR/"
cp RegressionApp-macOS.zip "$OUTPUT_DIR/"

echo "[5/5] Finished."
open "$OUTPUT_DIR"
osascript -e 'display dialog "Regression App v0.5.28 built successfully and passed its packaged self-test." buttons {"OK"} default button "OK"'
