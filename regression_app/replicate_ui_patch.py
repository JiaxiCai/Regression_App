import numpy as np
import pandas as pd
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton,
    QFileDialog, QComboBox, QDoubleSpinBox, QSpinBox, QTableWidget,
    QTableWidgetItem, QTabWidget, QSplitter, QHeaderView, QMessageBox
)
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

from .models import MODEL_SPECS
from .targetlynx_converter import parse_targetlynx_compound_summary
from .replicate_studies import infer_replicate_sets, rotate_calibration

def _fmt(value):
    if value is None:
        return ""
    try:
        if np.isnan(value):
            return ""
    except Exception:
        pass
    if isinstance(value, (float, np.floating)):
        return f"{value:.6g}"
    return str(value)

def _top_tabs(window):
    for tabs in window.centralWidget().findChildren(QTabWidget):
        names = [tabs.tabText(i) for i in range(tabs.count())]
        if "Clinical Tools" in names and "TargetLynx Converter" in names:
            return tabs
    raise RuntimeError("Could not locate the main application tab widget.")

def install(MainWindow):
    if getattr(MainWindow, "_replicate_studies_installed", False):
        return
    MainWindow._replicate_studies_installed = True
    original_init = MainWindow.__init__
    def wrapped_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self.repstudy_df = None
        self.repstudy_rows = None
        self.repstudy_results = None
        self.repstudy_path = None
        _build_tab(self)
    MainWindow.__init__ = wrapped_init

def _build_tab(w):
    right_tabs = _top_tabs(w)
    rs = QWidget()
    rsl = QVBoxLayout(rs)
    intro = QLabel(
        "Analyze repeated calibration-ladder studies such as 5×5 or 3×3. "
        "Each complete ladder is rotated through the calibrator role and the "
        "remaining ladders are recalculated from raw TargetLynx Response."
    )
    intro.setWordWrap(True)
    rsl.addWidget(intro)

    row = QHBoxLayout()
    b = QPushButton("Open TargetLynx Report")
    b.clicked.connect(lambda: _load(w))
    row.addWidget(b)
    w.rs_file_label = QLabel("No file loaded")
    w.rs_file_label.setWordWrap(True)
    row.addWidget(w.rs_file_label, 1)
    rsl.addLayout(row)

    setup = QHBoxLayout()
    setup.addWidget(QLabel("Analyte"))
    w.rs_analyte_combo = QComboBox()
    w.rs_analyte_combo.currentIndexChanged.connect(lambda: _refresh(w))
    setup.addWidget(w.rs_analyte_combo, 2)

    setup.addWidget(QLabel("Model"))
    w.rs_model_combo = QComboBox()
    w.rs_model_combo.addItems([name for name, _ in MODEL_SPECS])
    w.rs_model_combo.setCurrentText("Linear 1/x")
    setup.addWidget(w.rs_model_combo, 2)

    setup.addWidget(QLabel("Cal bias ±%"))
    w.rs_bias_spin = QDoubleSpinBox()
    w.rs_bias_spin.setRange(0.1, 100.0)
    w.rs_bias_spin.setValue(15.0)
    setup.addWidget(w.rs_bias_spin)

    setup.addWidget(QLabel("Min calibrators"))
    w.rs_min_cal_spin = QSpinBox()
    w.rs_min_cal_spin.setRange(3, 30)
    w.rs_min_cal_spin.setValue(6)
    setup.addWidget(w.rs_min_cal_spin)

    run = QPushButton("Run Calibration Rotation")
    run.clicked.connect(lambda: _run(w))
    setup.addWidget(run)
    rsl.addLayout(setup)

    splitter = QSplitter(Qt.Vertical)
    splitter.setChildrenCollapsible(False)

    map_box = QGroupBox("Detected replicate mapping — edit Replicate Set if needed")
    ml = QVBoxLayout(map_box)
    w.rs_mapping_table = QTableWidget(0, 6)
    w.rs_mapping_table.setHorizontalHeaderLabels(
        ["Injection", "Sample", "Nominal", "Response", "Replicate Set", "Level"]
    )
    w.rs_mapping_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
    w.rs_mapping_table.setMinimumHeight(240)
    ml.addWidget(w.rs_mapping_table)
    w.rs_mapping_note = QLabel("")
    w.rs_mapping_note.setWordWrap(True)
    ml.addWidget(w.rs_mapping_note)
    splitter.addWidget(map_box)

    result_widget = QWidget()
    rl = QVBoxLayout(result_widget)
    tabs = QTabWidget()

    fit_tab = QWidget()
    fl = QVBoxLayout(fit_tab)
    w.rs_fit_table = QTableWidget(0, 7)
    w.rs_fit_table.setHorizontalHeaderLabels([
        "Cal Set", "Status", "Pearson r", "Fit R²", "Weighted R²",
        "RMSE", "Bias slope / 100 injections"
    ])
    w.rs_fit_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    w.rs_fit_table.horizontalHeader().setStretchLastSection(True)
    fl.addWidget(w.rs_fit_table)
    tabs.addTab(fit_tab, "Calibration Summary")

    level_tab = QWidget()
    ll = QVBoxLayout(level_tab)
    w.rs_level_table = QTableWidget(0, 8)
    w.rs_level_table.setHorizontalHeaderLabels([
        "Cal Set", "Level", "Nominal", "n", "Mean Calc.", "CV %",
        "Mean Bias %", "Max |Bias| %"
    ])
    w.rs_level_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    w.rs_level_table.horizontalHeader().setStretchLastSection(True)
    ll.addWidget(w.rs_level_table)
    tabs.addTab(level_tab, "Precision / Bias by Level")

    matrix_tab = QWidget()
    xl = QVBoxLayout(matrix_tab)
    w.rs_matrix_figure = Figure(figsize=(7, 5), dpi=100)
    w.rs_matrix_canvas = FigureCanvas(w.rs_matrix_figure)
    xl.addWidget(w.rs_matrix_canvas)
    tabs.addTab(matrix_tab, "Calibration Dependence")

    drift_tab = QWidget()
    dl = QVBoxLayout(drift_tab)
    w.rs_drift_figure = Figure(figsize=(7, 5), dpi=100)
    w.rs_drift_canvas = FigureCanvas(w.rs_drift_figure)
    dl.addWidget(w.rs_drift_canvas)
    tabs.addTab(drift_tab, "Sequence View")

    export_row = QHBoxLayout()
    exp = QPushButton("Export Replicate Study Workbook")
    exp.clicked.connect(lambda: _export(w))
    export_row.addWidget(exp)
    export_row.addStretch()
    rl.addLayout(export_row)
    rl.addWidget(tabs)
    splitter.addWidget(result_widget)
    splitter.setStretchFactor(0, 2)
    splitter.setStretchFactor(1, 3)
    splitter.setSizes([350, 550])
    rsl.addWidget(splitter)

    target_index = next(
        (i for i in range(right_tabs.count())
         if right_tabs.tabText(i) == "TargetLynx Converter"),
        right_tabs.count()
    )
    right_tabs.insertTab(target_index, rs, "Replicate Studies")

def _load(w):
    path, _ = QFileDialog.getOpenFileName(
        w, "Open TargetLynx Report", "",
        "TargetLynx / CSV files (*.csv *.txt);;All files (*)"
    )
    if not path:
        return
    try:
        df, _ = parse_targetlynx_compound_summary(path)
        w.repstudy_df = df
        w.repstudy_path = path
        w.rs_file_label.setText(Path(path).name)
        analytes = []
        for compound in df["Compound"].astype(str).drop_duplicates():
            cr = df[df["Compound"].astype(str) == str(compound)]
            if "Is Internal Standard" in cr.columns:
                if bool(cr["Is Internal Standard"].fillna(False).astype(bool).any()):
                    continue
            try:
                _, summary = infer_replicate_sets(df, compound)
                if int(summary["Complete"].sum()) >= 2:
                    analytes.append(compound)
            except Exception:
                pass
        w.rs_analyte_combo.blockSignals(True)
        w.rs_analyte_combo.clear()
        w.rs_analyte_combo.addItems(analytes)
        w.rs_analyte_combo.blockSignals(False)
        if analytes:
            _refresh(w)
        else:
            w.rs_mapping_note.setText("No repeated calibration ladders were detected.")
    except Exception as exc:
        QMessageBox.critical(w, "Replicate study import failed", str(exc))

def _refresh(w):
    if w.repstudy_df is None or not w.rs_analyte_combo.currentText():
        return
    try:
        analyte = w.rs_analyte_combo.currentText()
        rows, summary = infer_replicate_sets(w.repstudy_df, analyte)
        w.repstudy_rows = rows.copy()
        w.rs_mapping_table.setRowCount(len(rows))
        for r, rec in rows.iterrows():
            vals = [
                rec["Injection"], rec.get("Sample Text", ""), rec["Nominal"],
                rec["Response_numeric"], int(rec["Replicate Set"]), int(rec["Level"])
            ]
            for c, value in enumerate(vals):
                item = QTableWidgetItem(_fmt(value))
                if c != 4:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                w.rs_mapping_table.setItem(r, c, item)
        complete = int(summary["Complete"].sum())
        sizes = ", ".join(
            f"Set {int(x['Replicate Set'])}: {int(x['n'])} rows"
            for _, x in summary.iterrows()
        )
        w.rs_mapping_note.setText(
            f"Detected {len(summary)} sets; {complete} complete ladders. {sizes}. "
            "Grouping uses actual sequence position and nominal-level reset, not suffix alone."
        )
    except Exception as exc:
        w.rs_mapping_note.setText(str(exc))

def _mapped_rows(w):
    if w.repstudy_rows is None:
        raise ValueError("Load a replicate-study file first.")
    rows = w.repstudy_rows.copy()
    set_ids = []
    for r in range(w.rs_mapping_table.rowCount()):
        item = w.rs_mapping_table.item(r, 4)
        if item is None or not item.text().strip():
            raise ValueError(
                f"Row {r+1} is missing a Replicate Set. Reload the analyte mapping."
            )
        try:
            set_id = int(float(item.text().strip()))
        except Exception:
            raise ValueError(
                f"Row {r+1} has an invalid Replicate Set value: {item.text()!r}."
            )
        if set_id < 1:
            raise ValueError("Replicate Set values must be positive integers.")
        set_ids.append(set_id)
    rows["Replicate Set"] = set_ids
    levels = sorted(rows["Nominal"].dropna().unique())
    level_map = {v: i + 1 for i, v in enumerate(levels)}
    rows["Level"] = rows["Nominal"].map(level_map)
    return rows

def _run(w):
    try:
        result = rotate_calibration(
            _mapped_rows(w),
            model_name=w.rs_model_combo.currentText(),
            calibrator_bias=w.rs_bias_spin.value(),
            min_calibrators=w.rs_min_cal_spin.value(),
        )
        w.repstudy_results = result
        _render(w)
    except Exception as exc:
        QMessageBox.critical(w, "Replicate study analysis failed", str(exc))

def _render(w):
    result = w.repstudy_results
    fits = result["fits"].merge(result["drift"], on="Calibration Set", how="left")
    w.rs_fit_table.setRowCount(len(fits))
    for r, rec in fits.iterrows():
        vals = [
            rec.get("Calibration Set", ""), rec.get("Status", ""),
            rec.get("Pearson r", np.nan), rec.get("Fit R2", np.nan),
            rec.get("Weighted R2", np.nan), rec.get("RMSE", np.nan),
            rec.get("Bias slope per 100 injections", np.nan),
        ]
        for c, value in enumerate(vals):
            w.rs_fit_table.setItem(r, c, QTableWidgetItem(_fmt(value)))

    lvl = result["by_level"]
    w.rs_level_table.setRowCount(len(lvl))
    for r, rec in lvl.iterrows():
        vals = [
            rec["Calibration Set"], rec["Level"], rec["Nominal"], rec["n"],
            rec["mean_calculated"], rec["cv_pct"], rec["mean_bias_pct"],
            rec["max_abs_bias_pct"],
        ]
        for c, value in enumerate(vals):
            w.rs_level_table.setItem(r, c, QTableWidgetItem(_fmt(value)))

    matrix = result["matrix"]
    w.rs_matrix_figure.clear()
    ax = w.rs_matrix_figure.add_subplot(111)
    arr = matrix.to_numpy(float)
    im = ax.imshow(arr, aspect="auto")
    ax.set_xticks(range(len(matrix.columns)), labels=matrix.columns, rotation=45, ha="right")
    ax.set_yticks(range(len(matrix.index)), labels=matrix.index)
    ax.set_title("Mean absolute bias (%) by calibration / evaluation set")
    for i in range(arr.shape[0]):
        for j in range(arr.shape[1]):
            if np.isfinite(arr[i, j]):
                ax.text(j, i, f"{arr[i,j]:.1f}", ha="center", va="center")
    w.rs_matrix_figure.colorbar(im, ax=ax, label="Mean |bias| %")
    w.rs_matrix_figure.tight_layout()
    w.rs_matrix_canvas.draw()

    q = result["quantified"]
    w.rs_drift_figure.clear()
    ax2 = w.rs_drift_figure.add_subplot(111)
    for cal_set, g in q.groupby("Calibration Set"):
        gg = g[np.isfinite(g["Injection"]) & np.isfinite(g["Bias %"])].sort_values("Injection")
        ax2.scatter(
            gg["Injection"], gg["Bias %"], s=12, alpha=0.55,
            label=f"Cal Set {int(cal_set)}"
        )
        if len(gg) >= 3 and np.ptp(gg["Injection"]) > 0:
            slope, intercept = np.polyfit(gg["Injection"], gg["Bias %"], 1)
            xx = np.array([gg["Injection"].min(), gg["Injection"].max()])
            ax2.plot(xx, intercept + slope * xx, linewidth=1)
    ax2.axhline(0, linewidth=1)
    ax2.set_xlabel("TargetLynx injection number")
    ax2.set_ylabel("Bias from nominal (%)")
    ax2.set_title("Sequence-associated bias by calibration choice")
    ax2.legend(ncol=2, fontsize=8)
    w.rs_drift_figure.tight_layout()
    w.rs_drift_canvas.draw()

def _export(w):
    if not w.repstudy_results:
        QMessageBox.information(w, "No results", "Run a replicate study first.")
        return
    path, _ = QFileDialog.getSaveFileName(
        w, "Export Replicate Study Workbook",
        "replicate_study_rotation.xlsx", "Excel Workbook (*.xlsx)"
    )
    if not path:
        return
    try:
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            _mapped_rows(w).to_excel(writer, sheet_name="Mapped Raw Data", index=False)
            w.repstudy_results["fits"].to_excel(writer, sheet_name="Calibration Fits", index=False)
            w.repstudy_results["by_level"].to_excel(writer, sheet_name="Precision by Level", index=False)
            w.repstudy_results["matrix"].to_excel(writer, sheet_name="Calibration Matrix")
            w.repstudy_results["drift"].to_excel(writer, sheet_name="Sequence Trends", index=False)
            w.repstudy_results["quantified"].to_excel(writer, sheet_name="All Recalculated", index=False)
        QMessageBox.information(w, "Export complete", f"Saved:\n{path}")
    except Exception as exc:
        QMessageBox.critical(w, "Export failed", str(exc))
