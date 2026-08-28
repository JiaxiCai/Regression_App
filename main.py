import sys
import traceback
from pathlib import Path
from datetime import datetime

def _write_crash_log(exc_text):
    try:
        home = Path.home()
        log = home / "RegressionApp_crash.log"
        with log.open("a", encoding="utf-8") as f:
            f.write("\n" + "="*72 + "\n")
            f.write(datetime.now().isoformat() + "\n")
            f.write(exc_text + "\n")
        return str(log)
    except Exception:
        return None

def _bundle_self_test():
    """Import all packaged dependencies, including the GUI module."""
    import numpy
    import pandas
    import scipy
    import matplotlib
    import openpyxl
    import PySide6
    from regression_app import (
        models, method_comparison, clinical_tools, targetlynx_converter,
        surrogate_is, surrogate_is_ui_patch,
    )
    import regression_app.app
    return 0

if "--self-test" in sys.argv:
    try:
        raise SystemExit(_bundle_self_test())
    except Exception:
        text = traceback.format_exc()
        _write_crash_log(text)
        raise

try:
    from regression_app.app import run
    if __name__ == "__main__":
        run()
except Exception:
    text = traceback.format_exc()
    log_path = _write_crash_log(text)

    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
        app = QApplication.instance() or QApplication(sys.argv)
        msg = "Regression App failed to start.\n\n" + text
        if log_path:
            msg += f"\n\nA crash log was written to:\n{log_path}"
        QMessageBox.critical(None, "Regression App Startup Error", msg)
    except Exception:
        print(text, file=sys.stderr)
    raise
