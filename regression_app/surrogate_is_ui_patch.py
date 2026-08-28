from __future__ import annotations

from pathlib import Path
import numpy as np

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QLabel,
    QPushButton, QFileDialog, QComboBox, QDoubleSpinBox, QSpinBox,
    QTableWidget, QTableWidgetItem, QTabWidget, QHeaderView, QMessageBox
)
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar

from .surrogate_is import (
    SurrogateCriteria, load_surrogate_data, analyze_surrogate_is,
    pair_metric_matrix, export_surrogate_workbook,
)


def _fmt(v):
    if v is None: return ""
    if isinstance(v, (bool, np.bool_)): return "PASS" if bool(v) else "FAIL"
    if isinstance(v, str): return v
    try:
        if not np.isfinite(v): return ""
    except Exception:
        return str(v)
    return f"{float(v):.6g}" if isinstance(v, (float, np.floating)) else str(v)


def _top_tabs(window):
    for tabs in window.centralWidget().findChildren(QTabWidget):
        if "Clinical Tools" in [tabs.tabText(i) for i in range(tabs.count())]:
            return tabs
    raise RuntimeError("Could not locate the main application tab widget.")


def install(MainWindow):
    if getattr(MainWindow, "_surrogate_is_installed", False): return
    MainWindow._surrogate_is_installed = True
    original_init = MainWindow.__init__
    def wrapped_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self.sis_data = None; self.sis_result = None; self.sis_path = None
        _build_tab(self)
    MainWindow.__init__ = wrapped_init


def _build_tab(w):
    tabs = _top_tabs(w)
    page = QWidget(); root = QVBoxLayout(page)
    intro = QLabel(
        "Systematically benchmark every analyte × internal-standard pairing. "
        "Stage 1 establishes an analyte-only contiguous calibration range; Stage 2 fits "
        "analyte/IS response ratios on those levels and evaluates independent QC bias and precision."
    )
    intro.setWordWrap(True); root.addWidget(intro)

    row = QHBoxLayout(); btn = QPushButton("Open Surrogate IS Dataset")
    btn.clicked.connect(lambda: _load(w)); row.addWidget(btn)
    w.sis_file = QLabel("No file loaded"); w.sis_file.setWordWrap(True); row.addWidget(w.sis_file, 1)
    root.addLayout(row)

    box = QGroupBox("Acceptance criteria"); g = QGridLayout(box)
    g.addWidget(QLabel("Model"), 0, 0)
    w.sis_model = QComboBox(); w.sis_model.addItems(["Linear", "Linear 1/x", "Linear 1/x²"])
    w.sis_model.setCurrentText("Linear 1/x"); g.addWidget(w.sis_model, 0, 1)
    g.addWidget(QLabel("Minimum calibrators"), 0, 2)
    w.sis_min_cal = QSpinBox(); w.sis_min_cal.setRange(3, 30); w.sis_min_cal.setValue(5)
    g.addWidget(w.sis_min_cal, 0, 3)

    specs = [
        ("Max cal |bias| %", "sis_cal_bias", 20.0), ("Minimum Fit R²", "sis_r2", 0.99),
        ("Max QC mean |bias| %", "sis_qc_mean_bias", 20.0),
        ("Max QC individual |bias| %", "sis_qc_max_bias", 30.0),
        ("Max QC CV %", "sis_qc_cv", 20.0),
    ]
    for i, (label, attr, val) in enumerate(specs):
        r = 1 + i // 2; c = (i % 2) * 2; g.addWidget(QLabel(label), r, c)
        sp = QDoubleSpinBox()
        if attr == "sis_r2":
            sp.setDecimals(6); sp.setRange(0.0, 1.0); sp.setSingleStep(0.0001)
        else:
            sp.setRange(0.0, 100.0); sp.setDecimals(2)
        sp.setValue(val); setattr(w, attr, sp); g.addWidget(sp, r, c + 1)
    run = QPushButton("Run Surrogate IS Analysis"); run.clicked.connect(lambda: _run(w)); g.addWidget(run, 0, 4, 2, 1)
    root.addWidget(box)

    w.sis_note = QLabel(""); w.sis_note.setWordWrap(True); root.addWidget(w.sis_note)
    outtabs = QTabWidget()

    rank_page = QWidget(); rl = QVBoxLayout(rank_page)
    w.sis_ranking = QTableWidget(); w.sis_ranking.setSelectionBehavior(QTableWidget.SelectRows)
    w.sis_ranking.setSelectionMode(QTableWidget.SingleSelection)
    w.sis_ranking.itemSelectionChanged.connect(lambda: _selection_changed(w))
    rl.addWidget(w.sis_ranking); outtabs.addTab(rank_page, "Pair Ranking")

    heat_page = QWidget(); hl = QVBoxLayout(heat_page); hc = QHBoxLayout()
    hc.addWidget(QLabel("Heatmap metric")); w.sis_heat_metric = QComboBox()
    w.sis_heat_metric.addItems(["QC Mean |Bias| %", "QC Max |Bias| %", "QC Max CV %", "Max Cal |Bias| %", "Fit R2"])
    w.sis_heat_metric.currentTextChanged.connect(lambda _: _draw_heatmap(w))
    hc.addWidget(w.sis_heat_metric); hc.addStretch(); hl.addLayout(hc)
    w.sis_heat_fig = Figure(figsize=(10, 6), dpi=100); w.sis_heat_canvas = FigureCanvas(w.sis_heat_fig)
    hl.addWidget(NavigationToolbar(w.sis_heat_canvas, heat_page)); hl.addWidget(w.sis_heat_canvas, 1)
    outtabs.addTab(heat_page, "Heatmap")

    detail_page = QWidget(); dl = QVBoxLayout(detail_page)
    w.sis_detail_label = QLabel("Select a pair from Pair Ranking."); w.sis_detail_label.setWordWrap(True)
    dl.addWidget(w.sis_detail_label)
    w.sis_detail_fig = Figure(figsize=(10, 6), dpi=100); w.sis_detail_canvas = FigureCanvas(w.sis_detail_fig)
    dl.addWidget(NavigationToolbar(w.sis_detail_canvas, detail_page)); dl.addWidget(w.sis_detail_canvas, 1)
    outtabs.addTab(detail_page, "Pair Detail")

    stage_page = QWidget(); sl = QVBoxLayout(stage_page); w.sis_stage1 = QTableWidget()
    sl.addWidget(w.sis_stage1); outtabs.addTab(stage_page, "Stage 1")
    root.addWidget(outtabs, 1)

    er = QHBoxLayout(); export = QPushButton("Export Surrogate IS Workbook")
    export.clicked.connect(lambda: _export(w)); er.addWidget(export); er.addStretch(); root.addLayout(er)
    insert = next((i for i in range(tabs.count()) if tabs.tabText(i) == "AMR Validation"), tabs.count())
    tabs.insertTab(insert, page, "Surrogate IS Analysis")


def _criteria(w):
    return SurrogateCriteria(
        model_name=w.sis_model.currentText(), min_calibrators=w.sis_min_cal.value(),
        max_calibrator_bias=w.sis_cal_bias.value(), min_r2=w.sis_r2.value(),
        max_qc_mean_abs_bias=w.sis_qc_mean_bias.value(), max_qc_abs_bias=w.sis_qc_max_bias.value(),
        max_qc_cv=w.sis_qc_cv.value(),
    )


def _load(w):
    path, _ = QFileDialog.getOpenFileName(
        w, "Open Surrogate IS Dataset", "", "Data files (*.csv *.txt *.xlsx *.xls);;All files (*)"
    )
    if not path: return
    try:
        data, meta = load_surrogate_data(path); w.sis_data = data; w.sis_path = path
        w.sis_file.setText(Path(path).name)
        n_an = data.loc[data["Component Role"] == "Analyte", "Component"].nunique()
        n_is = data.loc[data["Component Role"] == "IS", "Component"].nunique()
        w.sis_note.setText(
            f"Loaded {meta.get('format', 'data')}: {len(data):,} component rows; "
            f"{n_an} analyte component(s), {n_is} internal standard(s)."
        )
    except Exception as exc:
        QMessageBox.critical(w, "Surrogate IS import failed", str(exc))


def _run(w):
    if w.sis_data is None:
        QMessageBox.information(w, "No dataset", "Load a surrogate-IS dataset first."); return
    try:
        w.sis_result = analyze_surrogate_is(w.sis_data, _criteria(w)); rank = w.sis_result["ranking"]
        _fill_table(w.sis_ranking, rank); _fill_table(w.sis_stage1, w.sis_result["stage1"])
        passed = int(rank["Pass"].sum()) if not rank.empty else 0
        w.sis_note.setText(f"Evaluated {len(rank)} analyte–IS pairs; {passed} met all current calibration and QC criteria.")
        _draw_heatmap(w)
        if len(rank): w.sis_ranking.selectRow(0); _selection_changed(w)
    except Exception as exc:
        QMessageBox.critical(w, "Surrogate IS analysis failed", str(exc))


def _fill_table(table, df):
    table.clear(); table.setRowCount(len(df)); table.setColumnCount(len(df.columns))
    table.setHorizontalHeaderLabels([str(c) for c in df.columns])
    for r, (_, rec) in enumerate(df.iterrows()):
        for c, col in enumerate(df.columns):
            item = QTableWidgetItem(_fmt(rec[col])); item.setFlags(item.flags() & ~Qt.ItemIsEditable); table.setItem(r, c, item)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    table.horizontalHeader().setStretchLastSection(True)


def _draw_heatmap(w):
    fig = w.sis_heat_fig; fig.clear()
    if not w.sis_result: w.sis_heat_canvas.draw_idle(); return
    metric = w.sis_heat_metric.currentText(); mat = pair_metric_matrix(w.sis_result, metric)
    if mat.empty: w.sis_heat_canvas.draw_idle(); return
    ax = fig.add_subplot(111); im = ax.imshow(mat.to_numpy(float), aspect="auto")
    ax.set_xticks(range(len(mat.columns))); ax.set_xticklabels(mat.columns, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(mat.index))); ax.set_yticklabels(mat.index, fontsize=8); ax.set_title(metric)
    fig.colorbar(im, ax=ax, shrink=0.8); fig.tight_layout(); w.sis_heat_canvas.draw_idle()


def _selected_pair(w):
    if not w.sis_result: return None
    rows = w.sis_ranking.selectionModel().selectedRows()
    if not rows: return None
    r = rows[0].row(); rank = w.sis_result["ranking"]
    if r >= len(rank): return None
    rec = rank.iloc[r]; return str(rec["Analyte"]), str(rec["Internal Standard"])


def _selection_changed(w):
    pair = _selected_pair(w)
    if pair is None: return
    detail = w.sis_result["detail"].get(pair)
    if not detail: return
    s = detail["summary"]
    w.sis_detail_label.setText(
        f"{pair[0]} / {pair[1]} — {'PASS' if s['Pass'] else 'FAIL'}; "
        f"range {s['LLOQ']:g}–{s['ULOQ']:g}; max cal |bias| {s['Max Cal |Bias| %']:.2f}%; "
        f"Fit R² {s['Fit R2']:.6f}; QC mean |bias| {_fmt(s['QC Mean |Bias| %'])}%; QC max CV {_fmt(s['QC Max CV %'])}%."
    )
    fig = w.sis_detail_fig; fig.clear(); ax = fig.add_subplot(111)
    x = np.asarray(detail["x_cal"], float); y = np.asarray(detail["ratio_cal"], float); fit = detail["fit"]
    ax.scatter(x, y, label="Calibrators"); grid = np.linspace(np.min(x), np.max(x), 200)
    ax.plot(grid, fit.predict(grid), label="Fit"); ax.set_xlabel("Nominal concentration")
    ax.set_ylabel("Analyte / IS area ratio"); ax.set_title(f"{pair[0]} using {pair[1]}"); ax.legend()
    fig.tight_layout(); w.sis_detail_canvas.draw_idle()


def _export(w):
    if not w.sis_result:
        QMessageBox.information(w, "No results", "Run Surrogate IS Analysis first."); return
    path, _ = QFileDialog.getSaveFileName(w, "Export Surrogate IS Workbook", "surrogate_is_analysis.xlsx", "Excel Workbook (*.xlsx)")
    if not path: return
    try:
        export_surrogate_workbook(w.sis_result, path); QMessageBox.information(w, "Export complete", f"Saved:\n{path}")
    except Exception as exc:
        QMessageBox.critical(w, "Export failed", str(exc))
