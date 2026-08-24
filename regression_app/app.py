import sys
from pathlib import Path

import numpy as np
import pandas as pd

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QFileDialog, QTableWidget, QTableWidgetItem, QLabel, QComboBox,
    QMessageBox, QCheckBox, QGroupBox, QDoubleSpinBox, QSpinBox, QTabWidget,
    QSplitter, QHeaderView
)

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

from .models import MODEL_SPECS


TYPE_CAL = "Calibrator"
TYPE_QC = "QC"


class PlotPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.figure = Figure(figsize=(6, 4))
        self.canvas = FigureCanvas(self.figure)
        self.toolbar = NavigationToolbar(self.canvas, self)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)

    def clear(self):
        self.figure.clear()
        self.canvas.draw()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Regression App v0.1.3")
        self.resize(1500, 920)

        self.import_df = None
        self.results = {}
        self.cal_df = None
        self.qc_df = None

        self._build_ui()
        self._initialize_manual_rows()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer = QHBoxLayout(central)

        splitter = QSplitter(Qt.Horizontal)
        outer.addWidget(splitter)

        left = QWidget()
        left_layout = QVBoxLayout(left)

        input_group = QGroupBox("Input")
        input_layout = QVBoxLayout(input_group)

        button_row = QHBoxLayout()
        self.btn_import = QPushButton("Import CSV / Excel")
        self.btn_import.clicked.connect(self.import_file)
        self.btn_clear = QPushButton("Clear")
        self.btn_clear.clicked.connect(self.clear_all)
        button_row.addWidget(self.btn_import)
        button_row.addWidget(self.btn_clear)
        input_layout.addLayout(button_row)

        self.file_label = QLabel("Manual entry mode")
        self.file_label.setWordWrap(True)
        input_layout.addWidget(self.file_label)

        col_row = QGridLayout()
        col_row.addWidget(QLabel("X column"), 0, 0)
        self.x_combo = QComboBox()
        self.x_combo.currentIndexChanged.connect(self.load_selected_columns)
        col_row.addWidget(self.x_combo, 0, 1)
        col_row.addWidget(QLabel("Y column"), 1, 0)
        self.y_combo = QComboBox()
        self.y_combo.currentIndexChanged.connect(self.load_selected_columns)
        col_row.addWidget(self.y_combo, 1, 1)
        input_layout.addLayout(col_row)

        self.data_table = QTableWidget(20, 4)
        self.data_table.setHorizontalHeaderLabels(["Use", "Type", "X nominal", "Y response"])
        header = self.data_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        input_layout.addWidget(self.data_table)

        hint = QLabel("Tip: imported/manual rows default to included Calibrators. Change Type to QC for independent QC evaluation.")
        hint.setWordWrap(True)
        input_layout.addWidget(hint)

        row_controls = QHBoxLayout()
        add_row = QPushButton("+ Row")
        add_row.clicked.connect(self.add_row)
        del_row = QPushButton("− Row")
        del_row.clicked.connect(self.delete_selected_rows)
        row_controls.addWidget(add_row)
        row_controls.addWidget(del_row)
        input_layout.addLayout(row_controls)
        left_layout.addWidget(input_group)

        crit = QGroupBox("Acceptance Criteria")
        crit_layout = QGridLayout(crit)
        crit_layout.addWidget(QLabel("Calibrator bias ± (%)"), 0, 0)
        self.bias_spin = QDoubleSpinBox()
        self.bias_spin.setRange(0.1, 100.0)
        self.bias_spin.setValue(15.0)
        self.bias_spin.setDecimals(1)
        crit_layout.addWidget(self.bias_spin, 0, 1)

        crit_layout.addWidget(QLabel("QC bias ± (%)"), 1, 0)
        self.qc_bias_spin = QDoubleSpinBox()
        self.qc_bias_spin.setRange(0.1, 100.0)
        self.qc_bias_spin.setValue(15.0)
        self.qc_bias_spin.setDecimals(1)
        crit_layout.addWidget(self.qc_bias_spin, 1, 1)

        crit_layout.addWidget(QLabel("Minimum passing calibrators"), 2, 0)
        self.min_points_spin = QSpinBox()
        self.min_points_spin.setRange(2, 50)
        self.min_points_spin.setValue(6)
        crit_layout.addWidget(self.min_points_spin, 2, 1)
        left_layout.addWidget(crit)

        models = QGroupBox("Candidate Models")
        model_layout = QVBoxLayout(models)
        self.model_checks = {}
        for name, _ in MODEL_SPECS:
            cb = QCheckBox(name)
            cb.setChecked(True)
            self.model_checks[name] = cb
            model_layout.addWidget(cb)
        left_layout.addWidget(models)

        self.btn_run = QPushButton("Run Analysis")
        self.btn_run.setMinimumHeight(42)
        self.btn_run.clicked.connect(self.run_analysis)
        left_layout.addWidget(self.btn_run)

        self.btn_export = QPushButton("Export Results to Excel")
        self.btn_export.clicked.connect(self.export_excel)
        self.btn_export.setEnabled(False)
        left_layout.addWidget(self.btn_export)
        left_layout.addStretch()

        splitter.addWidget(left)

        right_tabs = QTabWidget()

        summary = QWidget()
        summary_layout = QVBoxLayout(summary)
        self.summary_table = QTableWidget(0, 12)
        self.summary_table.setHorizontalHeaderLabels([
            "Model", "R²", "Adj R²", "RMSE", "AIC", "AICc", "BIC",
            "Max Cal |Bias| %", "Cal Passing", "Contiguous AMR",
            "Max QC |Bias| %", "QC Passing"
        ])
        self.summary_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.summary_table.setSelectionMode(QTableWidget.SingleSelection)
        self.summary_table.itemSelectionChanged.connect(self.summary_selection_changed)
        self.summary_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        summary_layout.addWidget(self.summary_table)
        right_tabs.addTab(summary, "Model Comparison")

        self.cal_plot = PlotPanel()
        right_tabs.addTab(self.cal_plot, "Calibration Curve")

        self.resid_plot = PlotPanel()
        right_tabs.addTab(self.resid_plot, "Residuals")

        back = QWidget()
        back_layout = QVBoxLayout(back)
        self.back_table = QTableWidget(0, 7)
        self.back_table.setHorizontalHeaderLabels(
            ["Type", "X nominal", "Y observed", "Y fitted", "Back-calculated X", "% Bias", "Pass"]
        )
        self.back_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        back_layout.addWidget(self.back_table)
        right_tabs.addTab(back, "Back-calculation")

        qc = QWidget()
        qc_layout = QVBoxLayout(qc)
        self.qc_summary_table = QTableWidget(0, 7)
        self.qc_summary_table.setHorizontalHeaderLabels(
            ["Nominal X", "n", "Mean back-calc X", "SD", "CV %", "Mean bias %", "All pass?"]
        )
        self.qc_summary_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        qc_layout.addWidget(self.qc_summary_table)
        right_tabs.addTab(qc, "QC Summary")

        params = QWidget()
        params_layout = QVBoxLayout(params)
        self.param_table = QTableWidget(0, 2)
        self.param_table.setHorizontalHeaderLabels(["Parameter", "Value"])
        self.param_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        params_layout.addWidget(self.param_table)
        self.notes_label = QLabel("")
        self.notes_label.setWordWrap(True)
        params_layout.addWidget(self.notes_label)
        right_tabs.addTab(params, "Parameters")

        splitter.addWidget(right_tabs)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([430, 1070])

    def _make_use_item(self, checked=True):
        item = QTableWidgetItem()
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable)
        item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
        return item

    def _make_type_combo(self, value=TYPE_CAL):
        combo = QComboBox()
        combo.addItems([TYPE_CAL, TYPE_QC])
        combo.setCurrentText(value)
        return combo

    def _set_row_defaults(self, row, x_text="", y_text="", sample_type=TYPE_CAL, use=True):
        self.data_table.setItem(row, 0, self._make_use_item(use))
        self.data_table.setCellWidget(row, 1, self._make_type_combo(sample_type))
        self.data_table.setItem(row, 2, QTableWidgetItem(str(x_text)))
        self.data_table.setItem(row, 3, QTableWidgetItem(str(y_text)))

    def _initialize_manual_rows(self):
        for r in range(self.data_table.rowCount()):
            self._set_row_defaults(r)

    def add_row(self):
        r = self.data_table.rowCount()
        self.data_table.insertRow(r)
        self._set_row_defaults(r)

    def delete_selected_rows(self):
        rows = sorted({idx.row() for idx in self.data_table.selectedIndexes()}, reverse=True)
        for r in rows:
            self.data_table.removeRow(r)

    def import_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import data", "", "Data files (*.csv *.xlsx *.xlsm);;CSV (*.csv);;Excel (*.xlsx *.xlsm)"
        )
        if not path:
            return
        try:
            p = Path(path)
            if p.suffix.lower() == ".csv":
                df = pd.read_csv(path)
            else:
                df = pd.read_excel(path)
            self.import_df = df
            self.file_label.setText(str(path))
            columns = [str(c) for c in df.columns]
            self._column_mapping = {str(c): c for c in df.columns}

            self.x_combo.blockSignals(True)
            self.y_combo.blockSignals(True)
            self.x_combo.clear()
            self.y_combo.clear()
            self.x_combo.addItems(columns)
            self.y_combo.addItems(columns)
            if len(columns) >= 2:
                self.x_combo.setCurrentIndex(0)
                self.y_combo.setCurrentIndex(1)
            self.x_combo.blockSignals(False)
            self.y_combo.blockSignals(False)
            self.load_selected_columns()
        except Exception as e:
            QMessageBox.critical(self, "Import error", str(e))

    def load_selected_columns(self):
        if self.import_df is None or not self.x_combo.count() or not self.y_combo.count():
            return
        xcol = self.x_combo.currentText()
        ycol = self.y_combo.currentText()
        mapping = getattr(self, "_column_mapping", {str(c): c for c in self.import_df.columns})
        if xcol not in mapping or ycol not in mapping:
            return

        xseries = pd.to_numeric(self.import_df[mapping[xcol]], errors="coerce")
        yseries = pd.to_numeric(self.import_df[mapping[ycol]], errors="coerce")
        tmp = pd.DataFrame({"X": xseries, "Y": yseries}).dropna()

        self.data_table.setRowCount(max(20, len(tmp)))
        for r in range(self.data_table.rowCount()):
            self._set_row_defaults(r)
        for r, (_, row) in enumerate(tmp.iterrows()):
            self._set_row_defaults(r, f"{row['X']:.12g}", f"{row['Y']:.12g}")

    def _read_rows(self):
        records = []
        for r in range(self.data_table.rowCount()):
            use_item = self.data_table.item(r, 0)
            type_widget = self.data_table.cellWidget(r, 1)
            xi = self.data_table.item(r, 2)
            yi = self.data_table.item(r, 3)

            sx = xi.text().strip() if xi else ""
            sy = yi.text().strip() if yi else ""
            if not sx and not sy:
                continue
            if not sx or not sy:
                raise ValueError(f"Row {r+1} has only one of X/Y filled.")

            try:
                x = float(sx)
                y = float(sy)
            except ValueError:
                raise ValueError(f"Row {r+1} contains a non-numeric X or Y.")
            if not np.isfinite(x) or not np.isfinite(y):
                raise ValueError(f"Row {r+1} contains a non-finite value.")

            use = use_item is None or use_item.checkState() == Qt.Checked
            sample_type = type_widget.currentText() if type_widget else TYPE_CAL
            records.append({"row": r + 1, "use": use, "type": sample_type, "x": x, "y": y})

        if not records:
            raise ValueError("Enter at least one complete X/Y pair.")
        return pd.DataFrame(records)

    def run_analysis(self):
        try:
            df = self._read_rows()
        except Exception as e:
            QMessageBox.warning(self, "Input problem", str(e))
            return

        cal = df[(df["use"]) & (df["type"] == TYPE_CAL)].copy()
        qc = df[(df["use"]) & (df["type"] == TYPE_QC)].copy()

        if len(cal) < 3:
            QMessageBox.warning(self, "Not enough calibrators", "At least 3 included calibrator rows are required.")
            return

        selected = [(n, fn) for n, fn in MODEL_SPECS if self.model_checks[n].isChecked()]
        if not selected:
            QMessageBox.warning(self, "No models", "Select at least one model.")
            return

        x = cal["x"].to_numpy(float)
        y = cal["y"].to_numpy(float)
        self.cal_df = cal
        self.qc_df = qc
        self.results = {}
        failures = []

        for name, fn in selected:
            try:
                res = fn(x, y, self.bias_spin.value(), self.min_points_spin.value())
                if len(qc):
                    qy = qc["y"].to_numpy(float)
                    qx = qc["x"].to_numpy(float)
                    q_back = res.invert(qy)
                    q_bias = np.full_like(qx, np.nan, dtype=float)
                    nz = qx != 0
                    q_bias[nz] = (q_back[nz] - qx[nz]) / qx[nz] * 100.0
                    q_pass = np.isfinite(q_bias) & (np.abs(q_bias) <= self.qc_bias_spin.value())
                    res.qc_backcalc = q_back
                    res.qc_bias_pct = q_bias
                    res.qc_pass_mask = q_pass
                else:
                    res.qc_backcalc = np.array([], float)
                    res.qc_bias_pct = np.array([], float)
                    res.qc_pass_mask = np.array([], bool)
                self.results[name] = res
            except Exception as e:
                failures.append(f"{name}: {e}")

        if not self.results:
            QMessageBox.critical(self, "Analysis failed", "\n".join(failures))
            return

        self.populate_summary()
        self.btn_export.setEnabled(True)
        self.summary_table.selectRow(0)
        self.summary_selection_changed()

        if failures:
            QMessageBox.information(self, "Some models were not fit", "The following candidate models were skipped:\n\n" + "\n".join(failures))

    def populate_summary(self):
        self.summary_table.setRowCount(0)
        for row, (name, res) in enumerate(self.results.items()):
            self.summary_table.insertRow(row)
            s = res.stats
            maxbias = np.nanmax(np.abs(res.bias_pct)) if np.any(np.isfinite(res.bias_pct)) else np.nan
            passing = int(np.sum(res.pass_mask))
            amr = "—"
            if res.contiguous_range is not None:
                amr = f"{res.contiguous_range[0]:.6g} – {res.contiguous_range[1]:.6g}"

            qbias = getattr(res, "qc_bias_pct", np.array([]))
            qpass = getattr(res, "qc_pass_mask", np.array([], bool))
            max_qc_bias = np.nanmax(np.abs(qbias)) if np.any(np.isfinite(qbias)) else np.nan
            qc_passing = f"{int(np.sum(qpass))}/{len(qpass)}" if len(qpass) else "—"

            vals = [name, self._fmt(s["r2"]), self._fmt(s["adj_r2"]), self._fmt(s["rmse"]),
                    self._fmt(s["aic"]), self._fmt(s["aicc"]), self._fmt(s["bic"]),
                    self._fmt(maxbias), f"{passing}/{len(res.pass_mask)}", amr,
                    self._fmt(max_qc_bias), qc_passing]
            for c, v in enumerate(vals):
                self.summary_table.setItem(row, c, QTableWidgetItem(v))

    @staticmethod
    def _fmt(v):
        if v is None or not np.isfinite(v):
            return "—"
        return f"{v:.6g}"

    def summary_selection_changed(self):
        rows = self.summary_table.selectionModel().selectedRows() if self.summary_table.selectionModel() else []
        if not rows:
            return
        item = self.summary_table.item(rows[0].row(), 0)
        if item is None:
            return
        res = self.results.get(item.text())
        if res is not None:
            self.update_model_views(res)

    def update_model_views(self, res):
        cal = self.cal_df
        qc = self.qc_df
        x = cal["x"].to_numpy(float)
        y = cal["y"].to_numpy(float)

        self.cal_plot.figure.clear()
        ax = self.cal_plot.figure.add_subplot(111)
        ax.scatter(x, y, label="Calibrators")
        if len(qc):
            ax.scatter(qc["x"].to_numpy(float), qc["y"].to_numpy(float), marker="s", label="QC")
        grid = np.linspace(np.min(x), np.max(x), 400)
        try:
            pred = res.predict(grid)
            finite = np.isfinite(pred)
            ax.plot(grid[finite], pred[finite], label=res.name)
        except Exception:
            pass
        ax.set_xlabel("Nominal X")
        ax.set_ylabel("Response Y")
        ax.set_title(res.name)
        ax.legend()
        ax.grid(True, alpha=0.25)
        self.cal_plot.figure.tight_layout()
        self.cal_plot.canvas.draw()

        self.resid_plot.figure.clear()
        ax = self.resid_plot.figure.add_subplot(111)
        ax.axhline(0, linewidth=1)
        ax.scatter(x, res.residuals)
        ax.set_xlabel("Nominal X")
        ax.set_ylabel("Residual (Y observed − Y fitted)")
        ax.set_title(f"Calibrator residuals — {res.name}")
        ax.grid(True, alpha=0.25)
        self.resid_plot.figure.tight_layout()
        self.resid_plot.canvas.draw()

        rows = []
        for i in range(len(cal)):
            rows.append([TYPE_CAL, x[i], y[i], res.yhat[i], res.backcalc_x[i], res.bias_pct[i], "Pass" if res.pass_mask[i] else "Fail"])
        if len(qc):
            qx = qc["x"].to_numpy(float)
            qy = qc["y"].to_numpy(float)
            qfit = res.predict(qx)
            for i in range(len(qc)):
                rows.append([TYPE_QC, qx[i], qy[i], qfit[i], res.qc_backcalc[i], res.qc_bias_pct[i], "Pass" if res.qc_pass_mask[i] else "Fail"])

        self.back_table.setRowCount(len(rows))
        for r, vals in enumerate(rows):
            for c, v in enumerate(vals):
                self.back_table.setItem(r, c, QTableWidgetItem(v if isinstance(v, str) else self._fmt(v)))

        self.populate_qc_summary(res)

        self.param_table.setRowCount(len(res.params))
        for i, p in enumerate(res.params):
            self.param_table.setItem(i, 0, QTableWidgetItem(f"p{i}"))
            self.param_table.setItem(i, 1, QTableWidgetItem(self._fmt(p)))
        self.notes_label.setText(res.notes)

    def populate_qc_summary(self, res):
        qc = self.qc_df
        if qc is None or qc.empty:
            self.qc_summary_table.setRowCount(0)
            return

        work = qc.copy()
        work["backcalc"] = res.qc_backcalc
        work["bias"] = res.qc_bias_pct
        work["pass"] = res.qc_pass_mask

        groups = []
        for nominal, g in work.groupby("x", sort=True):
            vals = g["backcalc"].to_numpy(float)
            n = len(vals)
            mean = np.nanmean(vals)
            sd = np.nanstd(vals, ddof=1) if n > 1 else np.nan
            cv = (sd / mean * 100.0) if n > 1 and np.isfinite(mean) and mean != 0 else np.nan
            mean_bias = np.nanmean(g["bias"].to_numpy(float))
            all_pass = bool(g["pass"].all())
            groups.append([nominal, n, mean, sd, cv, mean_bias, "Yes" if all_pass else "No"])

        self.qc_summary_table.setRowCount(len(groups))
        for r, vals in enumerate(groups):
            for c, v in enumerate(vals):
                self.qc_summary_table.setItem(r, c, QTableWidgetItem(v if isinstance(v, str) else self._fmt(v)))

    def export_excel(self):
        if not self.results:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export results", "regression_results.xlsx", "Excel workbook (*.xlsx)")
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"

        try:
            summary_rows = []
            for name, res in self.results.items():
                s = res.stats
                maxbias = np.nanmax(np.abs(res.bias_pct)) if np.any(np.isfinite(res.bias_pct)) else np.nan
                qbias = getattr(res, "qc_bias_pct", np.array([]))
                qpass = getattr(res, "qc_pass_mask", np.array([], bool))
                summary_rows.append({
                    "Model": name,
                    "R2": s["r2"], "Adjusted R2": s["adj_r2"], "RMSE": s["rmse"],
                    "AIC": s["aic"], "AICc": s["aicc"], "BIC": s["bic"],
                    "Max calibrator absolute bias (%)": maxbias,
                    "Passing calibrators": int(np.sum(res.pass_mask)),
                    "Total calibrators": len(res.pass_mask),
                    "Contiguous range low": res.contiguous_range[0] if res.contiguous_range else np.nan,
                    "Contiguous range high": res.contiguous_range[1] if res.contiguous_range else np.nan,
                    "Max QC absolute bias (%)": np.nanmax(np.abs(qbias)) if np.any(np.isfinite(qbias)) else np.nan,
                    "Passing QC": int(np.sum(qpass)) if len(qpass) else np.nan,
                    "Total QC": len(qpass) if len(qpass) else np.nan,
                    "Parameters": ", ".join(f"{p:.12g}" for p in res.params),
                })

            with pd.ExcelWriter(path, engine="openpyxl") as writer:
                pd.DataFrame(summary_rows).to_excel(writer, sheet_name="Model comparison", index=False)
                self._read_rows().to_excel(writer, sheet_name="Input data", index=False)

                for idx, (name, res) in enumerate(self.results.items(), start=1):
                    safe = "".join(ch for ch in name if ch not in r'[]:*?/\\')[:24]
                    cal = self.cal_df
                    cal_df = pd.DataFrame({
                        "Type": TYPE_CAL,
                        "X nominal": cal["x"].to_numpy(float),
                        "Y observed": cal["y"].to_numpy(float),
                        "Y fitted": res.yhat,
                        "Residual": res.residuals,
                        "Back-calculated X": res.backcalc_x,
                        "Bias (%)": res.bias_pct,
                        "Pass": res.pass_mask,
                        "Weight": res.weights,
                    })
                    if self.qc_df is not None and len(self.qc_df):
                        qc = self.qc_df
                        qx = qc["x"].to_numpy(float)
                        qy = qc["y"].to_numpy(float)
                        qc_df = pd.DataFrame({
                            "Type": TYPE_QC,
                            "X nominal": qx,
                            "Y observed": qy,
                            "Y fitted": res.predict(qx),
                            "Residual": qy - res.predict(qx),
                            "Back-calculated X": res.qc_backcalc,
                            "Bias (%)": res.qc_bias_pct,
                            "Pass": res.qc_pass_mask,
                            "Weight": np.nan,
                        })
                        out = pd.concat([cal_df, qc_df], ignore_index=True)
                    else:
                        out = cal_df
                    out.to_excel(writer, sheet_name=f"{idx:02d}_{safe}"[:31], index=False)

            QMessageBox.information(self, "Export complete", f"Saved:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Export error", str(e))

    def clear_all(self):
        self.import_df = None
        self.file_label.setText("Manual entry mode")
        self.x_combo.clear()
        self.y_combo.clear()
        self.data_table.setRowCount(20)
        self._initialize_manual_rows()
        self.results = {}
        self.cal_df = None
        self.qc_df = None
        self.summary_table.setRowCount(0)
        self.back_table.setRowCount(0)
        self.qc_summary_table.setRowCount(0)
        self.param_table.setRowCount(0)
        self.notes_label.setText("")
        self.cal_plot.clear()
        self.resid_plot.clear()
        self.btn_export.setEnabled(False)


def run():
    app = QApplication(sys.argv)
    app.setApplicationName("Regression App")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
