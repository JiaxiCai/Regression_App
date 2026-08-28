import numpy as np
import pandas as pd
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QLabel,
    QPushButton, QFileDialog, QComboBox, QDoubleSpinBox, QSpinBox,
    QTableWidget, QTableWidgetItem, QTabWidget, QHeaderView, QMessageBox
)
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar

from .models import MODEL_SPECS
from .targetlynx_converter import parse_targetlynx_compound_summary
from .amr_validation import infer_study_sets, systematic_amr_search, level_diagnostics


def _fmt(v):
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    try:
        if not np.isfinite(v):
            return ""
    except Exception:
        return str(v)
    if isinstance(v, (float, np.floating)):
        return f"{float(v):.6g}"
    return str(v)


def _top_tabs(window):
    for tabs in window.centralWidget().findChildren(QTabWidget):
        names = [tabs.tabText(i) for i in range(tabs.count())]
        if "Clinical Tools" in names and "Replicate Studies" in names:
            return tabs
    raise RuntimeError("Could not locate the main application tab widget.")


def install(MainWindow):
    if getattr(MainWindow, "_amr_validation_installed", False):
        return
    MainWindow._amr_validation_installed = True
    original_init = MainWindow.__init__

    def wrapped_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self.amr_df = None
        self.amr_rows = None
        self.amr_summary_sets = None
        self.amr_analysis_sets = []
        self.amr_common_levels = []
        self.amr_result = None
        self.amr_path = None
        self._amr_updating_levels = False
        _build_tab(self)
        self.setWindowTitle("Regression App v0.4.9")

    MainWindow.__init__ = wrapped_init


def _build_tab(w):
    tabs = _top_tabs(w)
    page = QWidget()
    root = QVBoxLayout(page)

    intro = QLabel(
        "Quick AMR evaluation from repeated concentration ladders (for example 5×5, "
        "3×3, or 16×6 studies). The app detects replicate ladders, systematically "
        "searches contiguous concentration spans, rotates each study set through the "
        "calibrator role, and checks calibrator fit plus downstream QC precision/bias."
    )
    intro.setWordWrap(True)
    root.addWidget(intro)

    file_row = QHBoxLayout()
    open_btn = QPushButton("Open TargetLynx Report")
    open_btn.clicked.connect(lambda: _load(w))
    file_row.addWidget(open_btn)
    w.amr_file_label = QLabel("No file loaded")
    w.amr_file_label.setWordWrap(True)
    file_row.addWidget(w.amr_file_label, 1)
    root.addLayout(file_row)

    criteria = QGroupBox("AMR acceptance criteria")
    grid = QGridLayout(criteria)

    grid.addWidget(QLabel("Analyte"), 0, 0)
    w.amr_analyte = QComboBox()
    w.amr_analyte.currentIndexChanged.connect(lambda: _refresh_analyte(w))
    grid.addWidget(w.amr_analyte, 0, 1)

    grid.addWidget(QLabel("Model"), 0, 2)
    w.amr_model = QComboBox()
    w.amr_model.addItems([name for name, _ in MODEL_SPECS])
    w.amr_model.setCurrentText("Linear 1/x")
    grid.addWidget(w.amr_model, 0, 3)

    grid.addWidget(QLabel("Max cal |bias| %"), 1, 0)
    w.amr_cal_bias = QDoubleSpinBox()
    w.amr_cal_bias.setRange(0.1, 100.0)
    w.amr_cal_bias.setValue(15.0)
    grid.addWidget(w.amr_cal_bias, 1, 1)

    grid.addWidget(QLabel("Max QC mean |bias| %"), 1, 2)
    w.amr_qc_bias = QDoubleSpinBox()
    w.amr_qc_bias.setRange(0.1, 100.0)
    w.amr_qc_bias.setValue(15.0)
    grid.addWidget(w.amr_qc_bias, 1, 3)

    grid.addWidget(QLabel("Max QC CV %"), 2, 0)
    w.amr_qc_cv = QDoubleSpinBox()
    w.amr_qc_cv.setRange(0.1, 100.0)
    w.amr_qc_cv.setValue(15.0)
    grid.addWidget(w.amr_qc_cv, 2, 1)

    grid.addWidget(QLabel("Minimum Fit R²"), 2, 2)
    w.amr_min_r2 = QDoubleSpinBox()
    w.amr_min_r2.setDecimals(6)
    w.amr_min_r2.setSingleStep(0.0001)
    w.amr_min_r2.setRange(0.0, 1.0)
    w.amr_min_r2.setValue(0.995)
    grid.addWidget(w.amr_min_r2, 2, 3)

    grid.addWidget(QLabel("Minimum calibrators"), 3, 0)
    w.amr_min_cal = QSpinBox()
    w.amr_min_cal.setRange(3, 40)
    w.amr_min_cal.setValue(6)
    grid.addWidget(w.amr_min_cal, 3, 1)

    grid.addWidget(QLabel("Required rotations"), 3, 2)
    w.amr_required_rotations = QSpinBox()
    w.amr_required_rotations.setRange(0, 40)
    w.amr_required_rotations.setValue(0)
    w.amr_required_rotations.setSpecialValueText("All")
    grid.addWidget(w.amr_required_rotations, 3, 3)

    run = QPushButton("Find AMR")
    run.clicked.connect(lambda: _run(w))
    grid.addWidget(run, 0, 4, 2, 1)

    reset = QPushButton("Reset Level Exclusions")
    reset.clicked.connect(lambda: _reset_levels(w))
    grid.addWidget(reset, 2, 4, 2, 1)

    root.addWidget(criteria)

    w.amr_detection_note = QLabel("")
    w.amr_detection_note.setWordWrap(True)
    root.addWidget(w.amr_detection_note)

    outtabs = QTabWidget()

    summary_tab = QWidget()
    sl = QVBoxLayout(summary_tab)
    w.amr_summary_label = QLabel("Load a study and click Find AMR.")
    w.amr_summary_label.setWordWrap(True)
    w.amr_summary_label.setStyleSheet("font-size: 14px; font-weight: 600;")
    sl.addWidget(w.amr_summary_label)

    w.amr_level_table = QTableWidget(0, 8)
    w.amr_level_table.setHorizontalHeaderLabels([
        "Use", "Level", "Nominal", "In AMR span", "Max QC CV %",
        "Max QC |Mean Bias| %", "QC rotations passing", "Status"
    ])
    w.amr_level_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    w.amr_level_table.horizontalHeader().setStretchLastSection(True)
    w.amr_level_table.itemChanged.connect(lambda item: _level_changed(w, item))
    sl.addWidget(w.amr_level_table, 1)
    outtabs.addTab(summary_tab, "AMR / Levels")

    rot_tab = QWidget()
    rl = QVBoxLayout(rot_tab)
    w.amr_rotation_table = QTableWidget(0, 8)
    w.amr_rotation_table.setHorizontalHeaderLabels([
        "Cal Set", "Pass", "Status", "Max Cal |Bias| %", "Fit R²",
        "Weighted R²", "Max QC CV %", "Max QC |Mean Bias| %"
    ])
    w.amr_rotation_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    w.amr_rotation_table.horizontalHeader().setStretchLastSection(True)
    rl.addWidget(w.amr_rotation_table)
    outtabs.addTab(rot_tab, "Rotation Details")

    set_tab = QWidget()
    setl = QVBoxLayout(set_tab)
    w.amr_set_table = QTableWidget(0, 8)
    w.amr_set_table.setHorizontalHeaderLabels([
        "Set", "Rows", "Levels", "First injection", "Last injection",
        "Min nominal", "Max nominal", "Used for AMR"
    ])
    w.amr_set_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    w.amr_set_table.horizontalHeader().setStretchLastSection(True)
    setl.addWidget(w.amr_set_table)
    outtabs.addTab(set_tab, "Detected Sets")

    cand_tab = QWidget()
    cl = QVBoxLayout(cand_tab)
    w.amr_candidate_table = QTableWidget(0, 11)
    w.amr_candidate_table.setHorizontalHeaderLabels([
        "Pass", "LLOQ", "ULOQ", "Span ratio", "Levels span", "Levels fit",
        "Passing rotations", "Max Cal |Bias| %", "Min Fit R²",
        "Max QC CV %", "Max QC |Mean Bias| %"
    ])
    w.amr_candidate_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    cl.addWidget(w.amr_candidate_table)
    outtabs.addTab(cand_tab, "Candidate Ranges")

    plot_tab = QWidget()
    pl = QVBoxLayout(plot_tab)
    w.amr_figure = Figure(figsize=(10, 6.5), dpi=100)
    w.amr_canvas = FigureCanvas(w.amr_figure)
    pl.addWidget(NavigationToolbar(w.amr_canvas, plot_tab))
    pl.addWidget(w.amr_canvas, 1)
    outtabs.addTab(plot_tab, "AMR Diagnostics")

    root.addWidget(outtabs, 1)

    export_row = QHBoxLayout()
    export_btn = QPushButton("Export AMR Evaluation Workbook")
    export_btn.clicked.connect(lambda: _export(w))
    export_row.addWidget(export_btn)
    export_row.addStretch()
    root.addLayout(export_row)

    rep_idx = next(
        (i for i in range(tabs.count()) if tabs.tabText(i) == "Replicate Studies"),
        tabs.count()
    )
    tabs.insertTab(rep_idx, page, "AMR Validation")


def _load(w):
    path, _ = QFileDialog.getOpenFileName(
        w, "Open TargetLynx Report", "",
        "TargetLynx / CSV files (*.csv *.txt);;All files (*)"
    )
    if not path:
        return
    try:
        df, _ = parse_targetlynx_compound_summary(path)
        w.amr_df = df
        w.amr_path = path
        w.amr_file_label.setText(Path(path).name)

        analytes = []
        for compound in df["Compound"].astype(str).drop_duplicates():
            cr = df[df["Compound"].astype(str) == str(compound)]
            if "Is Internal Standard" in cr.columns:
                if bool(cr["Is Internal Standard"].fillna(False).astype(bool).any()):
                    continue
            try:
                _, summary, selected, common = infer_study_sets(df, compound)
                if len(selected) >= 2 and len(common) >= 3:
                    analytes.append(compound)
            except Exception:
                pass

        w.amr_analyte.blockSignals(True)
        w.amr_analyte.clear()
        w.amr_analyte.addItems(analytes)
        w.amr_analyte.blockSignals(False)

        if analytes:
            _refresh_analyte(w)
        else:
            w.amr_detection_note.setText(
                "No repeated quantitative concentration ladders were detected."
            )
    except Exception as exc:
        QMessageBox.critical(w, "AMR study import failed", str(exc))


def _refresh_analyte(w):
    if w.amr_df is None or not w.amr_analyte.currentText():
        return
    try:
        rows, summary, selected, common = infer_study_sets(
            w.amr_df, w.amr_analyte.currentText()
        )
        w.amr_rows = rows
        w.amr_summary_sets = summary
        w.amr_analysis_sets = selected
        w.amr_common_levels = list(map(float, common))
        w.amr_required_rotations.setMaximum(max(1, len(selected)))

        w.amr_set_table.setRowCount(len(summary))
        for r, rec in summary.iterrows():
            vals = [
                rec["Replicate Set"], rec["n"], rec["levels"],
                rec["first_injection"], rec["last_injection"],
                rec["min_nominal"], rec["max_nominal"],
                "Yes" if bool(rec["Analysis Set"]) else "No",
            ]
            for c, val in enumerate(vals):
                w.amr_set_table.setItem(r, c, QTableWidgetItem(_fmt(val)))

        _populate_levels(w)
        used = ", ".join(str(x) for x in selected)
        w.amr_detection_note.setText(
            f"Detected {len(summary)} concentration sequences. "
            f"Using {len(selected)} study ladders (sets {used}) based on ≥75% "
            f"coverage of the largest ladder. {len(common)} levels are shared "
            "across those ladders and are available for AMR search."
        )
        w.amr_result = None
        w.amr_summary_label.setText("Click Find AMR for the initial systematic search.")
    except Exception as exc:
        w.amr_detection_note.setText(str(exc))


def _populate_levels(w):
    w._amr_updating_levels = True
    try:
        w.amr_level_table.setRowCount(len(w.amr_common_levels))
        for r, nominal in enumerate(w.amr_common_levels):
            use = QTableWidgetItem("")
            use.setFlags(use.flags() | Qt.ItemIsUserCheckable)
            use.setCheckState(Qt.Checked)
            w.amr_level_table.setItem(r, 0, use)
            for c, val in [(1, r + 1), (2, nominal)]:
                item = QTableWidgetItem(_fmt(val))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                w.amr_level_table.setItem(r, c, item)
            for c in range(3, 8):
                item = QTableWidgetItem("")
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                w.amr_level_table.setItem(r, c, item)
    finally:
        w._amr_updating_levels = False


def _excluded_levels(w):
    excluded = []
    for r, nominal in enumerate(w.amr_common_levels):
        item = w.amr_level_table.item(r, 0)
        if item is not None and item.checkState() != Qt.Checked:
            excluded.append(float(nominal))
    return excluded


def _criteria(w):
    return dict(
        model_name=w.amr_model.currentText(),
        max_calibrator_bias=w.amr_cal_bias.value(),
        max_qc_cv=w.amr_qc_cv.value(),
        max_qc_mean_bias=w.amr_qc_bias.value(),
        min_r2=w.amr_min_r2.value(),
        min_calibrators=w.amr_min_cal.value(),
        required_rotations=w.amr_required_rotations.value(),
    )


def _run(w, quiet=False):
    if w.amr_rows is None:
        if not quiet:
            QMessageBox.information(w, "No study", "Load an AMR/precision study first.")
        return
    try:
        result = systematic_amr_search(
            mapped_rows=w.amr_rows,
            analysis_sets=w.amr_analysis_sets,
            common_levels=w.amr_common_levels,
            excluded_levels=_excluded_levels(w),
            **_criteria(w),
        )
        w.amr_result = result
        _render(w)
    except Exception as exc:
        if not quiet:
            QMessageBox.critical(w, "AMR evaluation failed", str(exc))
        else:
            w.amr_summary_label.setText(f"AMR evaluation failed: {exc}")


def _level_changed(w, item):
    if w._amr_updating_levels or item.column() != 0:
        return
    if w.amr_rows is not None and w.amr_result is not None:
        _run(w, quiet=True)


def _reset_levels(w):
    if not w.amr_common_levels:
        return
    w._amr_updating_levels = True
    try:
        for r in range(w.amr_level_table.rowCount()):
            item = w.amr_level_table.item(r, 0)
            if item is not None:
                item.setCheckState(Qt.Checked)
    finally:
        w._amr_updating_levels = False
    if w.amr_result is not None:
        _run(w, quiet=True)


def _render(w):
    result = w.amr_result
    s = result["summary"]
    status = "PASS" if result["found_passing_amr"] else "NO RANGE MET ALL CRITERIA"
    excluded = f"; excluded levels: {s['Excluded levels']}" if s["Excluded levels"] else ""
    w.amr_summary_label.setText(
        f"{status} — AMR {s['LLOQ']:g}–{s['ULOQ']:g}; "
        f"{s['Levels fitted']}/{s['Levels in span']} levels fitted{excluded}. "
        f"Rotations passing: {s['Passing rotations']}/{s['Total rotations']} "
        f"(required {s['Required rotations']}). "
        f"Max cal |bias| {s['Max Cal |Bias| %']:.2f}%; "
        f"min Fit R² {s['Min Fit R2']:.6f}; "
        f"max QC CV {s['Max QC CV %']:.2f}%; "
        f"max QC |mean bias| {s['Max QC |Mean Bias| %']:.2f}%."
    )

    rot = result["rotations"]
    w.amr_rotation_table.setRowCount(len(rot))
    cols = [
        "Calibration Set", "Pass", "Status", "Max Cal |Bias| %", "Fit R2",
        "Weighted R2", "QC Max CV %", "QC Max |Mean Bias| %"
    ]
    for r, rec in rot.iterrows():
        vals = [rec.get(c, "") for c in cols]
        for c, val in enumerate(vals):
            w.amr_rotation_table.setItem(r, c, QTableWidgetItem(_fmt(val)))

    diag = level_diagnostics(result)
    diag_map = {float(rec["Nominal"]): rec for _, rec in diag.iterrows()} if len(diag) else {}
    span = set(map(float, result["span_levels"]))
    fit = set(map(float, result["fit_levels"]))

    w._amr_updating_levels = True
    try:
        for r, nominal in enumerate(w.amr_common_levels):
            rec = diag_map.get(float(nominal))
            vals = [
                "Yes" if float(nominal) in span else "No",
                rec["max_qc_cv_pct"] if rec is not None else np.nan,
                rec["max_abs_qc_mean_bias_pct"] if rec is not None else np.nan,
                (
                    f"{int(rec['rotations_passing'])}/{int(rec['rotations_evaluated'])}"
                    if rec is not None else ""
                ),
                (
                    "Excluded by user" if float(nominal) in span and float(nominal) not in fit
                    else "In fitted AMR" if float(nominal) in fit
                    else "Outside AMR"
                ),
            ]
            for c, val in enumerate(vals, start=3):
                w.amr_level_table.setItem(r, c, QTableWidgetItem(_fmt(val)))
    finally:
        w._amr_updating_levels = False

    cand = result["candidates"].head(100)
    w.amr_candidate_table.setRowCount(len(cand))
    ccols = [
        "Pass", "LLOQ", "ULOQ", "Span ratio", "Levels in span", "Levels fitted",
        "Passing rotations", "Max Cal |Bias| %", "Min Fit R2",
        "Max QC CV %", "Max QC |Mean Bias| %"
    ]
    for r, rec in cand.iterrows():
        for c, name in enumerate(ccols):
            w.amr_candidate_table.setItem(r, c, QTableWidgetItem(_fmt(rec.get(name, ""))))

    w.amr_figure.clear()
    ax = w.amr_figure.add_subplot(111)
    if len(diag):
        x = diag["Nominal"].to_numpy(float)
        ax.plot(x, diag["max_qc_cv_pct"], marker="o", label="Max QC CV %")
        ax.plot(x, diag["max_abs_qc_mean_bias_pct"], marker="o", label="Max QC |mean bias| %")
        ax.axhline(w.amr_qc_cv.value(), linestyle="--", linewidth=1, label="QC CV limit")
        ax.axhline(w.amr_qc_bias.value(), linestyle=":", linewidth=1, label="QC bias limit")
        if np.all(x > 0):
            ax.set_xscale("log")
        ax.set_xlabel("Nominal concentration")
        ax.set_ylabel("Percent")
        ax.set_title(f"AMR level diagnostics — {w.amr_analyte.currentText()}")
        ax.legend()
        ax.grid(True, axis="y", alpha=0.25)
    else:
        ax.text(0.5, 0.5, "No level diagnostics available.", ha="center", va="center")
    w.amr_figure.tight_layout()
    w.amr_canvas.draw()


def _export(w):
    if not w.amr_result:
        QMessageBox.information(w, "No results", "Run AMR evaluation first.")
        return
    path, _ = QFileDialog.getSaveFileName(
        w, "Export AMR Evaluation Workbook",
        "amr_replicate_validation.xlsx", "Excel Workbook (*.xlsx)"
    )
    if not path:
        return
    try:
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            pd.DataFrame([w.amr_result["summary"]]).to_excel(
                writer, sheet_name="AMR Summary", index=False
            )
            w.amr_summary_sets.to_excel(writer, sheet_name="Detected Sets", index=False)
            w.amr_rows.to_excel(writer, sheet_name="Mapped Study Rows", index=False)
            w.amr_result["rotations"].to_excel(writer, sheet_name="Rotation Results", index=False)
            w.amr_result["by_level"].to_excel(writer, sheet_name="QC by Rotation Level", index=False)
            level_diagnostics(w.amr_result).to_excel(writer, sheet_name="Level Diagnostics", index=False)
            w.amr_result["candidates"].to_excel(writer, sheet_name="Candidate Ranges", index=False)
            w.amr_result["quantified"].to_excel(writer, sheet_name="All Recalculated", index=False)
        QMessageBox.information(w, "Export complete", f"Saved:\n{path}")
    except Exception as exc:
        QMessageBox.critical(w, "Export failed", str(exc))
