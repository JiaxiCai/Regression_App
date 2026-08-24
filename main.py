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

try:
    from regression_app.app import run
    if __name__ == "__main__":
        run()
except Exception:
    text = traceback.format_exc()
    log_path = _write_crash_log(text)

    # Best-effort visible error instead of silent app exit.
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
