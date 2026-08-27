"""Explicit weighting definitions for Regression App v0.4.5."""

from PySide6.QtWidgets import (
    QLabel, QPushButton, QDialog, QVBoxLayout, QTextBrowser, QDialogButtonBox
)

_WEIGHTING_TEXT = """WEIGHTING DEFINITIONS

None
  Objective: sum(e_i^2)
  Variance assumption: sigma^2 is constant
  SD assumption: sigma is constant
  NumPy polyfit residual multiplier: 1

1/x
  Objective: sum(e_i^2 / x_i)
  Variance assumption: sigma^2 proportional to x
  SD assumption: sigma proportional to sqrt(x)
  NumPy polyfit residual multiplier: 1/sqrt(x)

1/x^2
  Objective: sum(e_i^2 / x_i^2)
  Variance assumption: sigma^2 proportional to x^2
  SD assumption: sigma proportional to x
  Approximate interpretation: constant relative SD / %CV
  NumPy polyfit residual multiplier: 1/x

Important: NumPy polyfit applies its w argument to the residual before
squaring. Therefore the residual multiplier is the square root of the
statistical weight on the squared residual.
"""

def _tooltip_for_model(name):
    if "1/x²" in name or "1/x2" in name:
        return (
            "1/x² variance weighting\n"
            "Objective: Σ(e²/x²)\n"
            "Variance assumption: σ² ∝ x²\n"
            "SD assumption: σ ∝ x\n"
            "Approx. constant relative SD / %CV\n"
            "NumPy residual multiplier: 1/x"
        )
    if "1/x" in name:
        return (
            "1/x variance weighting\n"
            "Objective: Σ(e²/x)\n"
            "Variance assumption: σ² ∝ x\n"
            "SD assumption: σ ∝ √x\n"
            "NumPy residual multiplier: 1/√x"
        )
    return (
        "Unweighted least squares\n"
        "Objective: Σe²\n"
        "Variance assumption: constant σ²\n"
        "NumPy residual multiplier: 1"
    )

def _show_weighting_dialog(window):
    dlg = QDialog(window)
    dlg.setWindowTitle("Regression weighting definitions")
    dlg.resize(720, 560)
    layout = QVBoxLayout(dlg)
    browser = QTextBrowser()
    browser.setPlainText(_WEIGHTING_TEXT)
    layout.addWidget(browser, 1)
    buttons = QDialogButtonBox(QDialogButtonBox.Close)
    buttons.rejected.connect(dlg.reject)
    buttons.clicked.connect(dlg.accept)
    layout.addWidget(buttons)
    dlg.exec()

def install(MainWindow):
    if getattr(MainWindow, "_weighting_ui_patch_v045", False):
        return
    MainWindow._weighting_ui_patch_v045 = True

    original_init = MainWindow.__init__
    original_update = MainWindow.update_model_views

    def patched_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self.setWindowTitle("Regression App v0.4.5")

        # Make the familiar model labels self-documenting without making them
        # so long that the model selector becomes difficult to scan.
        for name, checkbox in getattr(self, "model_checks", {}).items():
            checkbox.setToolTip(_tooltip_for_model(name))

        checks = list(getattr(self, "model_checks", {}).values())
        if checks:
            parent = checks[0].parentWidget()
            layout = parent.layout() if parent is not None else None
            if layout is not None:
                note = QLabel(
                    "Weighting labels refer to the statistical weight on squared "
                    "residuals. Hover a model or open the definitions for the "
                    "variance/SD assumptions and NumPy implementation."
                )
                note.setWordWrap(True)
                layout.addWidget(note)
                btn = QPushButton("Weighting Definitions…")
                btn.clicked.connect(lambda: _show_weighting_dialog(self))
                layout.addWidget(btn)
                self.weighting_definitions_button = btn

    def patched_update_model_views(self, res):
        original_update(self, res)
        name = getattr(res, "name", "")
        if hasattr(self, "calc_browser"):
            existing = self.calc_browser.toPlainText()
            if "1/x²" in name or "1/x2" in name:
                explicit = (
                    "\n\nWEIGHTING INTERPRETATION\n"
                    "Statistical weighting: 1/x²\n"
                    "Objective: Σ(e_i²/x_i²)\n"
                    "Variance assumption: σ² ∝ x²\n"
                    "SD assumption: σ ∝ x\n"
                    "Approximate constant relative SD / %CV\n"
                    "NumPy polyfit residual multiplier: 1/x"
                )
            elif "1/x" in name:
                explicit = (
                    "\n\nWEIGHTING INTERPRETATION\n"
                    "Statistical weighting: 1/x\n"
                    "Objective: Σ(e_i²/x_i)\n"
                    "Variance assumption: σ² ∝ x\n"
                    "SD assumption: σ ∝ √x\n"
                    "NumPy polyfit residual multiplier: 1/√x"
                )
            else:
                explicit = (
                    "\n\nWEIGHTING INTERPRETATION\n"
                    "Statistical weighting: none\n"
                    "Objective: Σe_i²\n"
                    "Variance assumption: constant σ²\n"
                    "NumPy polyfit residual multiplier: 1"
                )
            self.calc_browser.setPlainText(existing + explicit)

    MainWindow.__init__ = patched_init
    MainWindow.update_model_views = patched_update_model_views
