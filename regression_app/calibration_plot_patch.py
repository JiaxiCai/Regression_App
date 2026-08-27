"""Calibration-plot diagnostics for Regression App v0.4.7."""

import math
import re


def _numeric_equation(res):
    equation = str(getattr(res, "equation", "") or "")
    names = list(getattr(res, "parameter_names", ()) or ())
    params = list(getattr(res, "params", ()) or ())
    for pname, value in sorted(
        zip(names, params), key=lambda pair: len(str(pair[0])), reverse=True
    ):
        try:
            value_text = f"{float(value):.6g}"
        except Exception:
            value_text = str(value)
        equation = re.sub(
            rf"\b{re.escape(str(pname))}\b", value_text, equation
        )
    return equation


def install(MainWindow):
    if getattr(MainWindow, "_calibration_plot_patch_v047", False):
        return
    MainWindow._calibration_plot_patch_v047 = True

    original_update = MainWindow.update_model_views

    def patched_update_model_views(self, res):
        original_update(self, res)

        try:
            if not hasattr(self, "cal_plot") or not self.cal_plot.figure.axes:
                return

            ax = self.cal_plot.figure.axes[0]
            stats = getattr(res, "stats", {}) or {}
            fit_r2 = float(stats.get("fit_r2", float("nan")))
            weighted_r2 = float(stats.get("weighted_r2", float("nan")))

            lines = []
            equation = _numeric_equation(res)
            if equation:
                lines.append(equation)

            if math.isfinite(fit_r2):
                lines.append(f"Fit R² = {fit_r2:.6f}")

            model_name = str(getattr(res, "name", ""))
            if "1/x" in model_name and math.isfinite(weighted_r2):
                lines.append(f"Weighted R² = {weighted_r2:.6f}")

            if lines:
                ax.text(
                    0.02,
                    0.98,
                    "\n".join(lines),
                    transform=ax.transAxes,
                    ha="left",
                    va="top",
                    fontsize=9,
                    bbox=dict(
                        boxstyle="round,pad=0.35",
                        facecolor="white",
                        alpha=0.82,
                    ),
                )
                self.cal_plot.canvas.draw_idle()
        except Exception:
            # Annotation must never block regression results.
            pass

    MainWindow.update_model_views = patched_update_model_views
