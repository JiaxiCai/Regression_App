from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd
import traceback

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QLabel,
    QPushButton, QFileDialog, QComboBox, QDoubleSpinBox, QSpinBox,
    QTableWidget, QTableWidgetItem, QTabWidget, QHeaderView, QMessageBox, QMenu, QCheckBox
)
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar

from .surrogate_is import (
    SurrogateCriteria, load_surrogate_data, load_user_amr, analyze_surrogate_is,
    component_mapping_table, qc_sample_mapping_table, pair_metric_matrix,
    compute_pair_detail, refit_pair_with_exclusions, refresh_matched_sil_dependents,
    sync_pair_amr_to_surrogates, export_surrogate_workbook,
)
from .ui_helpers import SortableTableItem, configure_sortable_table, make_table_filter_bar
from .project_io import save_project, load_project
from .models import ORIGIN_EXCLUDE, ORIGIN_INCLUDE, ORIGIN_FORCE
from . import __version__


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
        self.sis_component_mapping = None
        self.sis_qc_mapping = None
        self.sis_user_amr = None
        self.sis_user_amr_path = None
        self.sis_updating_cal_table = False
        self.sis_rank_hidden_columns = set()
        self.sis_project_path = None
        self.sis_analyte_fit_settings = {}
        _build_tab(self)
    MainWindow.__init__ = wrapped_init


def _build_tab(w):
    tabs = _top_tabs(w)
    page = QWidget(); root = QVBoxLayout(page)
    intro = QLabel(
        "Systematically benchmark every analyte × internal-standard pairing. "
        "The starting calibrator set can come from Stage 1 or from the calibrators retained by "
        "TargetLynx Primary Flags. Stage 2 then fits each "
        "analyte/IS response ratio using either exhaustive contiguous-window search or the legacy "
        "greedy removal algorithm. Exhaustive search compares passing contiguous calibration windows "
        "using QC bias/precision and working-range width so strong surrogate curves are not missed."
    )
    intro.setWordWrap(True); root.addWidget(intro)

    row = QHBoxLayout(); btn = QPushButton("Open Surrogate IS Dataset")
    btn.clicked.connect(lambda: _load(w)); row.addWidget(btn)
    open_project = QPushButton("Open Project")
    open_project.clicked.connect(lambda: _open_surrogate_project(w)); row.addWidget(open_project)
    save_project_btn = QPushButton("Save Project")
    save_project_btn.clicked.connect(lambda: _save_surrogate_project(w)); row.addWidget(save_project_btn)
    w.sis_file = QLabel("No file loaded"); w.sis_file.setWordWrap(True); row.addWidget(w.sis_file, 1)
    root.addLayout(row)

    amr_row = QHBoxLayout()
    amr_row.addWidget(QLabel("AMR source"))
    w.sis_amr_status = QLabel("Automatic Stage 1")
    amr_row.addWidget(w.sis_amr_status, 1)
    load_amr = QPushButton("Load User AMR File")
    load_amr.clicked.connect(lambda: _load_user_amr_file(w))
    amr_row.addWidget(load_amr)
    clear_amr = QPushButton("Clear User AMR")
    clear_amr.clicked.connect(lambda: _clear_user_amr(w))
    amr_row.addWidget(clear_amr)
    root.addLayout(amr_row)

    source_row = QHBoxLayout()
    source_row.addWidget(QLabel("Calibrator source"))
    w.sis_calibrator_source = QComboBox()
    w.sis_calibrator_source.addItems([
        "Stage 1",
        "TargetLynx Primary Flags",
    ])
    w.sis_calibrator_source.setToolTip(
        "Stage 1: derive the analyte candidate range automatically or from a user AMR file. "
        "TargetLynx Primary Flags: skip Stage 1 and use the analyte calibrators not marked X or lowercase l as the common starting set."
    )
    source_row.addWidget(w.sis_calibrator_source)
    source_row.addWidget(QLabel("Pair search"))
    w.sis_pair_search = QComboBox()
    w.sis_pair_search.addItems(["Exhaustive contiguous", "Greedy"])
    w.sis_pair_search.setCurrentText("Exhaustive contiguous")
    w.sis_pair_search.setToolTip(
        "Exhaustive contiguous evaluates every contiguous calibration window within the allowed "
        "starting levels and prefers the widest window passing both calibration and QC criteria. "
        "Greedy reproduces the legacy Stage-2 behavior by repeatedly removing the current worst-bias level."
    )
    source_row.addWidget(w.sis_pair_search)
    source_row.addStretch()
    root.addLayout(source_row)

    box = QGroupBox("Acceptance criteria"); g = QGridLayout(box)
    g.addWidget(QLabel("Model"), 0, 0)
    w.sis_model = QComboBox(); w.sis_model.addItems(["Linear", "Linear 1/x", "Linear 1/x²", "Quadratic", "Quadratic 1/x", "Quadratic 1/x²", "Padé [1/1]", "Padé [2/1]"])
    w.sis_model.setCurrentText("Linear 1/x"); g.addWidget(w.sis_model, 0, 1)
    g.addWidget(QLabel("Minimum calibrators"), 0, 2)
    w.sis_min_cal = QSpinBox(); w.sis_min_cal.setRange(3, 30); w.sis_min_cal.setValue(5)
    g.addWidget(w.sis_min_cal, 0, 3)
    g.addWidget(QLabel("Default origin handling"), 0, 4)
    w.sis_origin = QComboBox()
    w.sis_origin.addItems([ORIGIN_EXCLUDE, ORIGIN_INCLUDE, ORIGIN_FORCE])
    w.sis_origin.setCurrentText(ORIGIN_EXCLUDE)
    w.sis_origin.setToolTip(
        "Global default for analytes unless overridden in Analyte Fit Settings. "
        "Exclude estimates a free intercept without adding (0,0); Include adds a synthetic (0,0); "
        "Force constrains the fitted curve through zero."
    )
    g.addWidget(w.sis_origin, 0, 5)
    g.addWidget(QLabel("QC reference"), 1, 4)
    w.sis_qc_reference = QComboBox()
    w.sis_qc_reference.addItems([
        "Nominal concentration",
        "Matched SIL-IS calculated concentration",
    ])
    w.sis_qc_reference.setToolTip(
        "Choose whether QC bias is calculated against the assigned nominal concentration "
        "or against the concentration calculated using the analyte's matched SIL-IS curve."
    )
    g.addWidget(w.sis_qc_reference, 1, 5)

    g.addWidget(QLabel("Matched SIL range"), 2, 4)
    w.sis_sil_range_policy = QComboBox()
    w.sis_sil_range_policy.addItems([
        "Allow extrapolation",
        "Restrict to matched SIL-IS AMR",
    ])
    w.sis_sil_range_policy.setCurrentText("Allow extrapolation")
    w.sis_sil_range_policy.setToolTip(
        "Only applies when QC reference is Matched SIL-IS calculated concentration. "
        "Allow extrapolation uses the matched SIL-IS regression equation outside its retained AMR. "
        "Restrict to matched SIL-IS AMR evaluates bias only where the surrogate and matched SIL-IS "
        "reference ranges overlap."
    )
    g.addWidget(w.sis_sil_range_policy, 2, 5)

    specs = [
        ("Max cal |bias| %", "sis_cal_bias", 15.0), ("Minimum Fit R²", "sis_r2", 0.995),
        ("Max QC mean |bias| %", "sis_qc_mean_bias", 20.0),
        ("Max QC individual |bias| %", "sis_qc_max_bias", 20.0),
        ("Max QC CV %", "sis_qc_cv", 10.0),
    ]
    for i, (label, attr, val) in enumerate(specs):
        r = 1 + i // 2; c = (i % 2) * 2; g.addWidget(QLabel(label), r, c)
        sp = QDoubleSpinBox()
        if attr == "sis_r2":
            sp.setDecimals(6); sp.setRange(0.0, 1.0); sp.setSingleStep(0.0001)
        else:
            sp.setRange(0.0, 100.0); sp.setDecimals(2)
        sp.setValue(val); setattr(w, attr, sp); g.addWidget(sp, r, c + 1)
    run = QPushButton("Run Surrogate IS Analysis"); run.clicked.connect(lambda: _run(w)); g.addWidget(run, 3, 4, 2, 2)
    root.addWidget(box)

    w.sis_note = QLabel(""); w.sis_note.setWordWrap(True); root.addWidget(w.sis_note)
    outtabs = QTabWidget()

    mapping_page = QWidget(); ml = QVBoxLayout(mapping_page)
    mapping_intro = QLabel(
        "Review the automatic compound assignments before analysis. Change Role to "
        "Analyte, Internal Standard, or Ignore; uncheck Include to exclude a component "
        "from the current benchmark. Internal standards can also be classified as SIL-IS or "
        "Surrogate and assigned to their paired analyte."
    )
    mapping_intro.setWordWrap(True); ml.addWidget(mapping_intro)
    mapping_actions = QHBoxLayout()
    reset_map = QPushButton("Reset to Automatic")
    reset_map.clicked.connect(lambda: _reset_mapping(w))
    mapping_actions.addWidget(reset_map)
    include_all = QPushButton("Include All")
    include_all.clicked.connect(lambda: _set_all_mapping_included(w, True))
    mapping_actions.addWidget(include_all)
    exclude_all = QPushButton("Exclude All")
    exclude_all.clicked.connect(lambda: _set_all_mapping_included(w, False))
    mapping_actions.addWidget(exclude_all)
    mapping_actions.addStretch()
    w.sis_pair_estimate = QLabel("Load a dataset to review assignments.")
    mapping_actions.addWidget(w.sis_pair_estimate)
    ml.addLayout(mapping_actions)
    w.sis_mapping_table = QTableWidget(0, 8)
    w.sis_mapping_table.setHorizontalHeaderLabels([
        "Include", "Component", "Automatic Role", "Role",
        "IS Class", "Paired Analyte", "Calibrator Rows", "QC Rows"
    ])
    w.sis_mapping_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    w.sis_mapping_table.horizontalHeader().setStretchLastSection(True)
    ml.addWidget(w.sis_mapping_table, 1)
    outtabs.addTab(mapping_page, "Component Mapping")

    fit_page = QWidget(); afl = QVBoxLayout(fit_page)
    fit_intro = QLabel(
        "Override regression model and origin handling independently for each analyte. "
        "Use Global Default to inherit the settings above; analyte-specific choices are applied "
        "consistently to candidate-range fitting, iterative Stage 2, matched SIL-IS reference fits, "
        "and manual pair refits."
    )
    fit_intro.setWordWrap(True); afl.addWidget(fit_intro)
    fit_actions = QHBoxLayout()
    reset_fit = QPushButton("Reset All to Global Defaults")
    reset_fit.clicked.connect(lambda: _reset_analyte_fit_settings(w))
    fit_actions.addWidget(reset_fit)
    fit_actions.addStretch()
    afl.addLayout(fit_actions)
    w.sis_analyte_fit_table = QTableWidget(0, 3)
    w.sis_analyte_fit_table.setHorizontalHeaderLabels([
        "Analyte", "Regression Model", "Origin Handling"
    ])
    w.sis_analyte_fit_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    w.sis_analyte_fit_table.horizontalHeader().setStretchLastSection(True)
    afl.addWidget(w.sis_analyte_fit_table, 1)
    outtabs.addTab(fit_page, "Analyte Fit Settings")

    qcmap_page = QWidget(); qml = QVBoxLayout(qcmap_page)
    qcmap_intro = QLabel(
        "Choose which QC samples are used for surrogate-IS bias and precision calculations. "
        "Unchecked samples are ignored for QC pass/fail and ranking; calibration fitting is unchanged."
    )
    qcmap_intro.setWordWrap(True); qml.addWidget(qcmap_intro)
    qma = QHBoxLayout()
    reset_qc = QPushButton("Reset to Automatic")
    reset_qc.clicked.connect(lambda: _reset_qc_mapping(w)); qma.addWidget(reset_qc)
    include_qc = QPushButton("Include All")
    include_qc.clicked.connect(lambda: _set_all_qc_included(w, True)); qma.addWidget(include_qc)
    exclude_qc = QPushButton("Exclude All")
    exclude_qc.clicked.connect(lambda: _set_all_qc_included(w, False)); qma.addWidget(exclude_qc)
    qma.addStretch()
    w.sis_qc_mapping_summary = QLabel("Load a dataset to review QC samples.")
    qma.addWidget(w.sis_qc_mapping_summary)
    qml.addLayout(qma)
    w.sis_qc_mapping_table = QTableWidget(0, 7)
    w.sis_qc_mapping_table.setHorizontalHeaderLabels([
        "Include", "Name", "ID", "Sample Text", "Type", "Automatic Include", "Sample Key"
    ])
    w.sis_qc_mapping_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    w.sis_qc_mapping_table.horizontalHeader().setStretchLastSection(True)
    qml.addWidget(w.sis_qc_mapping_table, 1)
    outtabs.addTab(qcmap_page, "QC Sample Mapping")

    rank_page = QWidget(); rl = QVBoxLayout(rank_page)
    rank_controls = QHBoxLayout()
    rank_controls.addWidget(QLabel("Filter column"))
    w.sis_rank_filter_column = QComboBox()
    w.sis_rank_filter_column.currentTextChanged.connect(lambda _: _update_ranking_filter_values(w))
    rank_controls.addWidget(w.sis_rank_filter_column)

    rank_controls.addWidget(QLabel("Value"))
    w.sis_rank_filter_value = QComboBox()
    w.sis_rank_filter_value.currentTextChanged.connect(lambda _: _refresh_ranking_view(w))
    rank_controls.addWidget(w.sis_rank_filter_value)

    clear_rank_filter = QPushButton("Clear")
    clear_rank_filter.clicked.connect(lambda: _clear_ranking_filter(w))
    rank_controls.addWidget(clear_rank_filter)

    w.sis_rank_columns_button = QPushButton("Columns")
    w.sis_rank_columns_button.clicked.connect(lambda: _show_ranking_columns_menu(w))
    rank_controls.addWidget(w.sis_rank_columns_button)

    rank_controls.addStretch()
    w.sis_rank_count = QLabel("")
    rank_controls.addWidget(w.sis_rank_count)
    rl.addLayout(rank_controls)
    w.sis_ranking = QTableWidget(); w.sis_ranking.setSelectionBehavior(QTableWidget.SelectRows)
    w.sis_ranking.setSelectionMode(QTableWidget.SingleSelection)
    configure_sortable_table(w.sis_ranking)
    w.sis_ranking.horizontalHeader().setSectionsMovable(True)
    rl.addWidget(make_table_filter_bar(w.sis_ranking, rank_page))
    w.sis_ranking.itemSelectionChanged.connect(lambda: _selection_changed(w))
    rl.addWidget(w.sis_ranking); outtabs.addTab(rank_page, "Pair Ranking")

    heat_page = QWidget(); heat_root = QHBoxLayout(heat_page)

    heat_controls_panel = QWidget(); hcp = QVBoxLayout(heat_controls_panel)
    hcp.addWidget(QLabel("Heatmap value"))
    w.sis_heat_metric = QComboBox()
    w.sis_heat_metric.addItems([
        "Fit R2", "Weighted R2",
        "Min Cal Bias %", "Max Cal Bias %",
        "Min Cal |Bias| %", "Mean Cal |Bias| %", "Max Cal |Bias| %",
        "QC Min Bias %", "QC Max Bias %",
        "QC Min |Bias| %", "QC Mean |Bias| %", "QC Max |Bias| %",
        "QC Min CV %", "QC Mean CV %", "QC Max CV %",
        "LLOQ", "ULOQ", "Span Ratio", "n Cal", "QC Levels",
        "Stage 2 Iterations", "Stage 2 Removed",
    ])
    w.sis_heat_metric.currentTextChanged.connect(lambda _: _draw_heatmap(w))
    hcp.addWidget(w.sis_heat_metric)

    hcp.addWidget(QLabel("Order"))
    w.sis_heat_order = QComboBox()
    w.sis_heat_order.addItems(["Retention time", "Alphabetical"])
    w.sis_heat_order.setCurrentText("Retention time")
    w.sis_heat_order.setToolTip(
        "Retention time sorts analytes and internal standards independently by median calibrator RT; "
        "components without a finite RT are placed last."
    )
    w.sis_heat_order.currentTextChanged.connect(lambda _: _draw_heatmap(w))
    hcp.addWidget(w.sis_heat_order)

    w.sis_heat_annotate = QCheckBox("Annotate values")
    w.sis_heat_annotate.toggled.connect(lambda _: _draw_heatmap(w))
    hcp.addWidget(w.sis_heat_annotate)

    w.sis_heat_grey_fail = QCheckBox("Grey out failed pairs")
    w.sis_heat_grey_fail.setChecked(False)
    w.sis_heat_grey_fail.setToolTip(
        "Display pairs whose final Pass status is false in grey while preserving metric values "
        "and optional annotations."
    )
    w.sis_heat_grey_fail.toggled.connect(lambda _: _draw_heatmap(w))
    hcp.addWidget(w.sis_heat_grey_fail)

    export_png = QPushButton("Export PNG")
    export_png.clicked.connect(lambda: _export_heatmap(w, "png"))
    hcp.addWidget(export_png)
    export_svg = QPushButton("Export SVG")
    export_svg.clicked.connect(lambda: _export_heatmap(w, "svg"))
    hcp.addWidget(export_svg)
    hcp.addStretch()

    heat_plot_panel = QWidget(); hpp = QVBoxLayout(heat_plot_panel)
    w.sis_heat_fig = Figure(figsize=(12, 8), dpi=100)
    w.sis_heat_canvas = FigureCanvas(w.sis_heat_fig)
    hpp.addWidget(NavigationToolbar(w.sis_heat_canvas, heat_plot_panel))
    hpp.addWidget(w.sis_heat_canvas, 1)

    heat_root.addWidget(heat_controls_panel, 0)
    heat_root.addWidget(heat_plot_panel, 1)
    outtabs.addTab(heat_page, "Heatmap")

    detail_page = QWidget(); dl = QVBoxLayout(detail_page)
    w.sis_detail_label = QLabel("Select a pair from Pair Ranking."); w.sis_detail_label.setWordWrap(True)
    dl.addWidget(w.sis_detail_label)
    detail_split = QHBoxLayout()
    plot_panel = QWidget(); ppl = QVBoxLayout(plot_panel)
    w.sis_detail_fig = Figure(figsize=(7, 6), dpi=100); w.sis_detail_canvas = FigureCanvas(w.sis_detail_fig)
    ppl.addWidget(NavigationToolbar(w.sis_detail_canvas, plot_panel))
    ppl.addWidget(w.sis_detail_canvas, 1)

    table_panel = QWidget(); tpl = QVBoxLayout(table_panel)
    cal_label = QLabel(
        "Calibrators — automatic Stage 2 levels start checked. Levels removed by iterative Stage 2, "
        "plus usable levels outside Stage 1, remain visible unchecked. Check or uncheck any level to "
        "manually expand or shrink this pair's AMR and refit. Manual edits are pair-specific."
    )
    cal_label.setWordWrap(True); tpl.addWidget(cal_label)
    sync_amr = QPushButton("Sync AMR to Other Surrogates")
    sync_amr.setToolTip(
        "Apply this pair's current calibrator inclusion/exclusion pattern to all other internal standards for the same analyte."
    )
    sync_amr.clicked.connect(lambda: _sync_amr_to_surrogates(w))
    tpl.addWidget(sync_amr)
    w.sis_cal_detail = QTableWidget()
    configure_sortable_table(w.sis_cal_detail)
    w.sis_cal_detail.itemChanged.connect(lambda item: _calibrator_use_changed(w, item))
    tpl.addWidget(w.sis_cal_detail, 1)

    detail_split.addWidget(plot_panel, 3)
    detail_split.addWidget(table_panel, 2)
    dl.addLayout(detail_split, 1)
    outtabs.addTab(detail_page, "Pair Detail")

    qc_detail_page = QWidget(); qdl = QVBoxLayout(qc_detail_page)
    w.sis_qc_detail_label = QLabel("Select a pair from Pair Ranking.")
    w.sis_qc_detail_label.setWordWrap(True); qdl.addWidget(w.sis_qc_detail_label)
    w.sis_qc_detail = QTableWidget()
    configure_sortable_table(w.sis_qc_detail)
    qdl.addWidget(make_table_filter_bar(w.sis_qc_detail, qc_detail_page))
    qdl.addWidget(w.sis_qc_detail, 1)
    outtabs.addTab(qc_detail_page, "QC Individual Bias")

    stage_page = QWidget(); sl = QVBoxLayout(stage_page); w.sis_stage1 = QTableWidget()
    configure_sortable_table(w.sis_stage1)
    sl.addWidget(make_table_filter_bar(w.sis_stage1, stage_page))
    sl.addWidget(w.sis_stage1); outtabs.addTab(stage_page, "Stage 1")
    root.addWidget(outtabs, 1)

    er = QHBoxLayout(); export = QPushButton("Export Surrogate IS Workbook")
    export.clicked.connect(lambda: _export(w)); er.addWidget(export); er.addStretch(); root.addLayout(er)
    insert = next((i for i in range(tabs.count()) if tabs.tabText(i) == "AMR Validation"), tabs.count())
    tabs.insertTab(insert, page, "Surrogate IS Analysis")


def _ranking_column_order(w):
    table = w.sis_ranking
    header = table.horizontalHeader()
    order = []
    for visual in range(header.count()):
        logical = header.logicalIndex(visual)
        item = table.horizontalHeaderItem(logical)
        if item is not None:
            order.append(item.text())
    return order


def _json_scalar(value):
    if isinstance(value, np.generic):
        return value.item()
    return value


def _save_surrogate_project(w):
    if w.sis_data is None:
        QMessageBox.information(w, "No dataset", "Load a surrogate-IS dataset before saving a project.")
        return

    default_name = "surrogate_is_project.regproj"
    if w.sis_project_path:
        default_name = str(w.sis_project_path)
    path, _ = QFileDialog.getSaveFileName(
        w, "Save Regression App Project", default_name,
        "Regression App Project (*.regproj)"
    )
    if not path:
        return

    try:
        mapping = _mapping_from_ui(w)
        current_analytes = sorted(
            mapping.loc[
                mapping["Include"].astype(bool) & mapping["Role"].astype(str).eq("Analyte"),
                "Component",
            ].astype(str).unique().tolist()
        )
        table_analytes = [
            w.sis_analyte_fit_table.item(r, 0).text()
            for r in range(w.sis_analyte_fit_table.rowCount())
            if w.sis_analyte_fit_table.item(r, 0) is not None
        ]
        if current_analytes != table_analytes:
            existing = _analyte_fit_settings_from_ui(w)
            w.sis_analyte_fit_settings = existing
            _populate_analyte_fit_settings(w)
        qc_mapping = _qc_mapping_from_ui(w)
        selected = _selected_pair(w)

        exclusions = []
        if w.sis_result:
            for (analyte, is_name), values in w.sis_result.get("manual_exclusions", {}).items():
                exclusions.append({
                    "analyte": str(analyte),
                    "internal_standard": str(is_name),
                    "excluded_nominals": [float(v) for v in values],
                })

        filter_col = w.sis_rank_filter_column.currentText() if hasattr(w, "sis_rank_filter_column") else ""
        filter_value = w.sis_rank_filter_value.currentText() if hasattr(w, "sis_rank_filter_value") else "All"

        state = {
            "workspace": "Surrogate IS Analysis",
            "source_path": str(w.sis_path or ""),
            "analysis_was_run": bool(w.sis_result is not None),
            "criteria": {
                "model_name": w.sis_model.currentText(),
                "min_calibrators": int(w.sis_min_cal.value()),
                "max_calibrator_bias": float(w.sis_cal_bias.value()),
                "min_r2": float(w.sis_r2.value()),
                "max_qc_mean_abs_bias": float(w.sis_qc_mean_bias.value()),
                "max_qc_abs_bias": float(w.sis_qc_max_bias.value()),
                "max_qc_cv": float(w.sis_qc_cv.value()),
                "qc_reference_basis": w.sis_qc_reference.currentText(),
                "matched_sil_range_policy": w.sis_sil_range_policy.currentText(),
                "origin_mode": w.sis_origin.currentText(),
            },
            "analyte_fit_settings": _analyte_fit_settings_from_ui(w),
            "calibrator_source": w.sis_calibrator_source.currentText(),
            "pair_search_mode": w.sis_pair_search.currentText(),
            "manual_exclusions": exclusions,
            "ranking": {
                "filter_column": filter_col,
                "filter_value": filter_value,
                "hidden_columns": sorted(str(c) for c in w.sis_rank_hidden_columns),
                "column_order": _ranking_column_order(w),
                "selected_pair": list(selected) if selected else None,
            },
            "heatmap": {
                "metric": w.sis_heat_metric.currentText(),
                "order": w.sis_heat_order.currentText(),
                "annotate": bool(w.sis_heat_annotate.isChecked()),
                "grey_failed_pairs": bool(w.sis_heat_grey_fail.isChecked()),
            },
        }

        saved = save_project(
            path,
            app_version=__version__,
            module="surrogate_is",
            state=state,
            tables={
                "normalized_data": w.sis_data,
                "component_mapping": mapping,
                "qc_mapping": qc_mapping,
                "user_amr": w.sis_user_amr,
            },
        )
        w.sis_project_path = saved
        QMessageBox.information(w, "Project saved", f"Saved:\n{saved}")
    except Exception as exc:
        QMessageBox.critical(w, "Project save failed", str(exc))


def _restore_combo_text(combo, text):
    idx = combo.findText(str(text))
    if idx >= 0:
        combo.setCurrentIndex(idx)


def _restore_ranking_layout(w, state):
    ranking_state = state.get("ranking", {})
    w.sis_rank_hidden_columns = set(str(c) for c in ranking_state.get("hidden_columns", []))

    col = ranking_state.get("filter_column", "")
    if col:
        _restore_combo_text(w.sis_rank_filter_column, col)
        _update_ranking_filter_values(w)
        value = ranking_state.get("filter_value", "All")
        _restore_combo_text(w.sis_rank_filter_value, value)
        _refresh_ranking_view(w)

    desired = [str(c) for c in ranking_state.get("column_order", [])]
    header = w.sis_ranking.horizontalHeader()
    for target_visual, name in enumerate(desired):
        logical = next(
            (c for c in range(w.sis_ranking.columnCount())
             if w.sis_ranking.horizontalHeaderItem(c) is not None
             and w.sis_ranking.horizontalHeaderItem(c).text() == name),
            None,
        )
        if logical is not None:
            current_visual = header.visualIndex(logical)
            if current_visual != target_visual:
                header.moveSection(current_visual, target_visual)
    _apply_ranking_column_visibility(w)

    pair = ranking_state.get("selected_pair")
    if pair and len(pair) == 2:
        _refresh_ranking_view(w, preferred_pair=(str(pair[0]), str(pair[1])))


def _open_surrogate_project(w):
    path, _ = QFileDialog.getOpenFileName(
        w, "Open Regression App Project", "",
        "Regression App Project (*.regproj)"
    )
    if not path:
        return

    try:
        project = load_project(path)
        if project.get("module") != "surrogate_is":
            raise ValueError(
                f"This project belongs to module '{project.get('module', '')}', "
                "not Surrogate IS Analysis."
            )

        state = project.get("state", {})
        tables = project.get("tables", {})
        data = tables.get("normalized_data")
        if data is None or data.empty:
            raise ValueError("The project does not contain its normalized surrogate-IS dataset.")

        w.sis_data = data
        w.sis_path = state.get("source_path") or None
        w.sis_project_path = Path(path)
        w.sis_component_mapping = tables.get("component_mapping")
        if w.sis_component_mapping is None:
            w.sis_component_mapping = component_mapping_table(data)
        w.sis_qc_mapping = tables.get("qc_mapping")
        if w.sis_qc_mapping is None:
            w.sis_qc_mapping = qc_sample_mapping_table(data)
        w.sis_user_amr = tables.get("user_amr")
        w.sis_user_amr_path = None

        _populate_mapping(w)
        _populate_analyte_fit_settings(w)
        _populate_qc_mapping(w)
        w.sis_file.setText(f"{Path(path).name} (project)")

        criteria = state.get("criteria", {})
        _restore_combo_text(w.sis_model, criteria.get("model_name", "Linear 1/x"))
        if "min_calibrators" in criteria: w.sis_min_cal.setValue(int(criteria["min_calibrators"]))
        if "max_calibrator_bias" in criteria: w.sis_cal_bias.setValue(float(criteria["max_calibrator_bias"]))
        if "min_r2" in criteria: w.sis_r2.setValue(float(criteria["min_r2"]))
        if "max_qc_mean_abs_bias" in criteria: w.sis_qc_mean_bias.setValue(float(criteria["max_qc_mean_abs_bias"]))
        if "max_qc_abs_bias" in criteria: w.sis_qc_max_bias.setValue(float(criteria["max_qc_abs_bias"]))
        if "max_qc_cv" in criteria: w.sis_qc_cv.setValue(float(criteria["max_qc_cv"]))
        _restore_combo_text(
            w.sis_qc_reference,
            criteria.get("qc_reference_basis", "Nominal concentration"),
        )
        _restore_combo_text(
            w.sis_sil_range_policy,
            criteria.get("matched_sil_range_policy", "Allow extrapolation"),
        )
        _restore_combo_text(w.sis_origin, criteria.get("origin_mode", ORIGIN_EXCLUDE))
        w.sis_analyte_fit_settings = {
            str(k): dict(v) for k, v in state.get("analyte_fit_settings", {}).items()
        }
        _populate_analyte_fit_settings(w)
        _restore_combo_text(w.sis_calibrator_source, state.get("calibrator_source", "Stage 1"))
        _restore_combo_text(w.sis_pair_search, state.get("pair_search_mode", "Exhaustive contiguous"))

        heat = state.get("heatmap", {})
        _restore_combo_text(w.sis_heat_metric, heat.get("metric", "Fit R2"))
        _restore_combo_text(w.sis_heat_order, heat.get("order", "Retention time"))
        w.sis_heat_annotate.setChecked(bool(heat.get("annotate", False)))
        w.sis_heat_grey_fail.setChecked(bool(heat.get("grey_failed_pairs", False)))

        if w.sis_user_amr is not None and len(w.sis_user_amr):
            w.sis_amr_status.setText(
                f"Project user-defined AMR for {len(w.sis_user_amr)} analyte(s)"
            )
        else:
            w.sis_amr_status.setText("Automatic Stage 1")

        w.sis_result = None
        if state.get("analysis_was_run", False):
            _run(w, suppress_large_warning=True)
            if w.sis_result is not None:
                for rec in state.get("manual_exclusions", []):
                    try:
                        refit_pair_with_exclusions(
                            w.sis_result,
                            str(rec.get("analyte", "")),
                            str(rec.get("internal_standard", "")),
                            rec.get("excluded_nominals", []),
                        )
                    except Exception:
                        pass
                _refresh_ranking_view(w)
                _draw_heatmap(w)
                _restore_ranking_layout(w, state)

        w.sis_note.setText(
            f"Opened project {Path(path).name} created with Regression App "
            f"{project.get('app_version', '')}. Embedded data and analysis settings restored."
        )
    except Exception as exc:
        QMessageBox.critical(w, "Project open failed", str(exc))


def _load_user_amr_file(w):
    path, _ = QFileDialog.getOpenFileName(
        w, "Open User-defined AMR File", "",
        "AMR files (*.csv *.xlsx *.xls);;All files (*)"
    )
    if not path:
        return
    try:
        table = load_user_amr(path)
        w.sis_user_amr = table
        w.sis_user_amr_path = path
        w.sis_amr_status.setText(
            f"User-defined for {len(table)} analyte(s): {Path(path).name}; "
            "automatic fallback for unmatched analytes"
        )
    except Exception as exc:
        QMessageBox.critical(w, "AMR import failed", str(exc))


def _clear_user_amr(w):
    w.sis_user_amr = None
    w.sis_user_amr_path = None
    w.sis_amr_status.setText("Automatic Stage 1")


def _current_analytes_from_mapping(w):
    mapping = _mapping_from_ui(w) if w.sis_mapping_table.rowCount() else w.sis_component_mapping
    if mapping is None or len(mapping) == 0:
        return []
    x = mapping[
        mapping["Include"].astype(bool)
        & mapping["Role"].astype(str).eq("Analyte")
    ]
    return sorted(x["Component"].astype(str).unique().tolist())


def _refresh_analyte_fit_settings_from_mapping(w):
    """Refresh analyte rows after mapping edits without losing existing overrides."""
    if not hasattr(w, "sis_analyte_fit_table"):
        return
    existing = {}
    table = w.sis_analyte_fit_table
    for r in range(table.rowCount()):
        item = table.item(r, 0)
        if item is None:
            continue
        analyte = item.text()
        model_widget = table.cellWidget(r, 1)
        origin_widget = table.cellWidget(r, 2)
        model_display = model_widget.currentText() if model_widget else "Global Default"
        origin_display = origin_widget.currentText() if origin_widget else "Global Default"
        existing[analyte] = {
            "model_display": model_display,
            "origin_display": origin_display,
            "model_name": (
                w.sis_model.currentText()
                if model_display == "Global Default" else model_display
            ),
            "origin_mode": (
                w.sis_origin.currentText()
                if origin_display == "Global Default" else origin_display
            ),
        }
    if existing:
        w.sis_analyte_fit_settings.update(existing)

    desired = _current_analytes_from_mapping(w)
    current = [
        table.item(r, 0).text()
        for r in range(table.rowCount())
        if table.item(r, 0) is not None
    ]
    if desired != current:
        _populate_analyte_fit_settings(w)


def _populate_analyte_fit_settings(w):
    if not hasattr(w, "sis_analyte_fit_table"):
        return
    analytes = _current_analytes_from_mapping(w)
    table = w.sis_analyte_fit_table
    table.setRowCount(len(analytes))
    for r, analyte in enumerate(analytes):
        item = QTableWidgetItem(str(analyte))
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        table.setItem(r, 0, item)

        saved = w.sis_analyte_fit_settings.get(str(analyte), {})
        model = QComboBox()
        model.addItems(["Global Default", "Linear", "Linear 1/x", "Linear 1/x²", "Quadratic", "Quadratic 1/x", "Quadratic 1/x²", "Padé [1/1]", "Padé [2/1]"])
        model.setCurrentText(str(saved.get("model_display", "Global Default")))
        table.setCellWidget(r, 1, model)

        origin = QComboBox()
        origin.addItems(["Global Default", ORIGIN_EXCLUDE, ORIGIN_INCLUDE, ORIGIN_FORCE])
        origin.setCurrentText(str(saved.get("origin_display", "Global Default")))
        table.setCellWidget(r, 2, origin)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    table.horizontalHeader().setStretchLastSection(True)


def _analyte_fit_settings_from_ui(w):
    settings = {}
    table = w.sis_analyte_fit_table
    for r in range(table.rowCount()):
        item = table.item(r, 0)
        if item is None:
            continue
        analyte = item.text()
        model_widget = table.cellWidget(r, 1)
        origin_widget = table.cellWidget(r, 2)
        model_display = model_widget.currentText() if model_widget else "Global Default"
        origin_display = origin_widget.currentText() if origin_widget else "Global Default"
        settings[analyte] = {
            "model_name": w.sis_model.currentText() if model_display == "Global Default" else model_display,
            "origin_mode": w.sis_origin.currentText() if origin_display == "Global Default" else origin_display,
            "model_display": model_display,
            "origin_display": origin_display,
        }
    w.sis_analyte_fit_settings = settings
    return settings


def _reset_analyte_fit_settings(w):
    w.sis_analyte_fit_settings = {}
    _populate_analyte_fit_settings(w)


def _criteria(w):
    return SurrogateCriteria(
        model_name=w.sis_model.currentText(), min_calibrators=w.sis_min_cal.value(),
        max_calibrator_bias=w.sis_cal_bias.value(), min_r2=w.sis_r2.value(),
        max_qc_mean_abs_bias=w.sis_qc_mean_bias.value(), max_qc_abs_bias=w.sis_qc_max_bias.value(),
        max_qc_cv=w.sis_qc_cv.value(), qc_reference_basis=w.sis_qc_reference.currentText(),
        matched_sil_range_policy=w.sis_sil_range_policy.currentText(),
        origin_mode=w.sis_origin.currentText(),
    )


def _load(w):
    path, _ = QFileDialog.getOpenFileName(
        w, "Open Surrogate IS Dataset", "", "Data files (*.csv *.txt *.xlsx *.xls);;All files (*)"
    )
    if not path: return
    try:
        data, meta = load_surrogate_data(path); w.sis_data = data; w.sis_path = path
        w.sis_component_mapping = component_mapping_table(data)
        w.sis_qc_mapping = qc_sample_mapping_table(data)
        w.sis_file.setText(Path(path).name)
        _populate_mapping(w)
        _populate_analyte_fit_settings(w)
        _populate_qc_mapping(w)
        n_an = data.loc[data["Component Role"] == "Analyte", "Component"].nunique()
        n_is = data.loc[data["Component Role"] == "IS", "Component"].nunique()
        flag_note = ""
        if "Primary Flags" in data.columns:
            flags = data["Primary Flags"].fillna("").astype(str)
            flagged = int((flags.str.contains("X", regex=False) | flags.str.contains("l", regex=False)).sum())
            if flagged:
                flag_note = f" {flagged:,} row(s) carry TargetLynx X/l Primary Flags."
        w.sis_note.setText(
            f"Loaded {meta.get('format', 'data')}: {len(data):,} component rows; "
            f"{n_an} analyte component(s), {n_is} internal standard(s).{flag_note}"
        )
    except Exception as exc:
        QMessageBox.critical(w, "Surrogate IS import failed", str(exc))


def _populate_mapping(w):
    mapping = w.sis_component_mapping
    if mapping is None:
        return
    table = w.sis_mapping_table
    analytes = sorted(
        mapping.loc[mapping["Role"].astype(str).eq("Analyte"), "Component"].astype(str).unique().tolist()
    )
    table.blockSignals(True)
    table.setRowCount(len(mapping))
    for r, (_, rec) in enumerate(mapping.iterrows()):
        include = QTableWidgetItem("")
        include.setFlags(include.flags() | Qt.ItemIsUserCheckable)
        include.setCheckState(Qt.Checked if bool(rec["Include"]) else Qt.Unchecked)
        table.setItem(r, 0, include)

        for c, key in [
            (1, "Component"), (2, "Automatic Role"), (6, "Calibrator Rows"), (7, "QC Rows")
        ]:
            item = QTableWidgetItem(_fmt(rec[key]))
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            table.setItem(r, c, item)

        role = QComboBox()
        role.addItems(["Analyte", "Internal Standard", "Ignore"])
        role_value = str(rec["Role"])
        if role_value == "IS":
            role_value = "Internal Standard"
        role.setCurrentText(role_value)
        role.currentTextChanged.connect(lambda _=None: _update_mapping_summary(w))
        table.setCellWidget(r, 3, role)

        is_class = QComboBox()
        is_class.addItems(["", "SIL-IS", "Surrogate"])
        is_class.setCurrentText(str(rec.get("IS Class", "")))
        table.setCellWidget(r, 4, is_class)

        paired = QComboBox()
        paired.addItem("")
        paired.addItems(analytes)
        paired.setCurrentText(str(rec.get("Paired Analyte", "")))
        table.setCellWidget(r, 5, paired)

        def update_is_controls(_=None, role_widget=role, class_widget=is_class, paired_widget=paired):
            enabled = role_widget.currentText() == "Internal Standard"
            class_widget.setEnabled(enabled)
            paired_widget.setEnabled(enabled)
            if not enabled:
                class_widget.setCurrentText("")
                paired_widget.setCurrentText("")
            elif class_widget.currentText() == "":
                class_widget.setCurrentText("Surrogate")

        role.currentTextChanged.connect(update_is_controls)
        update_is_controls()

    table.blockSignals(False)
    try:
        table.itemChanged.disconnect()
    except Exception:
        pass
    table.itemChanged.connect(lambda item: _update_mapping_summary(w) if item.column() == 0 else None)
    _update_mapping_summary(w)

def _mapping_from_ui(w):
    rows = []
    table = w.sis_mapping_table
    for r in range(table.rowCount()):
        component = table.item(r, 1).text()
        auto = table.item(r, 2).text()
        include = table.item(r, 0).checkState() == Qt.Checked
        role_widget = table.cellWidget(r, 3)
        role = role_widget.currentText() if role_widget is not None else auto
        if role == "Internal Standard":
            role = "IS"
        class_widget = table.cellWidget(r, 4)
        paired_widget = table.cellWidget(r, 5)
        is_class = class_widget.currentText() if class_widget is not None else ""
        paired = paired_widget.currentText() if paired_widget is not None else ""
        if role != "IS":
            is_class = ""
            paired = ""
        rows.append({
            "Component": component,
            "Automatic Role": auto,
            "Role": role,
            "IS Class": is_class,
            "Paired Analyte": paired,
            "Include": include,
            "Calibrator Rows": int(float(table.item(r, 6).text() or 0)),
            "QC Rows": int(float(table.item(r, 7).text() or 0)),
        })
    import pandas as pd
    return pd.DataFrame(rows)

def _update_mapping_summary(w):
    if not hasattr(w, "sis_mapping_table") or w.sis_mapping_table.rowCount() == 0:
        return
    mapping = _mapping_from_ui(w)
    inc = mapping[mapping["Include"].astype(bool)]
    n_an = int((inc["Role"] == "Analyte").sum())
    n_is = int((inc["Role"] == "IS").sum())
    ignored = int((inc["Role"] == "Ignore").sum())
    w.sis_pair_estimate.setText(
        f"{n_an} analyte(s) × {n_is} IS = {n_an * n_is:,} pair(s)"
        + (f"; {ignored} included component(s) ignored" if ignored else "")
    )
    if hasattr(w, "sis_analyte_fit_table"):
        _refresh_analyte_fit_settings_from_mapping(w)


def _reset_mapping(w):
    if w.sis_component_mapping is None:
        return
    _populate_mapping(w)


def _set_all_mapping_included(w, included):
    table = w.sis_mapping_table
    table.blockSignals(True)
    for r in range(table.rowCount()):
        item = table.item(r, 0)
        if item is not None:
            item.setCheckState(Qt.Checked if included else Qt.Unchecked)
    table.blockSignals(False)
    _update_mapping_summary(w)


def _populate_qc_mapping(w):
    mapping = w.sis_qc_mapping
    if mapping is None:
        return
    table = w.sis_qc_mapping_table
    table.blockSignals(True)
    table.setRowCount(len(mapping))
    for r, (_, rec) in enumerate(mapping.iterrows()):
        include = QTableWidgetItem("")
        include.setFlags(include.flags() | Qt.ItemIsUserCheckable)
        include.setCheckState(Qt.Checked if bool(rec["Include"]) else Qt.Unchecked)
        table.setItem(r, 0, include)

        for c, key in [
            (1, "Name"), (2, "ID"), (3, "Sample Text"), (4, "Type"), (6, "Sample Key")
        ]:
            item = QTableWidgetItem(str(rec.get(key, "")))
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            table.setItem(r, c, item)

        auto = QTableWidgetItem("YES" if bool(rec["Automatic Include"]) else "NO")
        auto.setFlags(auto.flags() & ~Qt.ItemIsEditable)
        table.setItem(r, 5, auto)

    table.blockSignals(False)
    try:
        table.itemChanged.disconnect()
    except Exception:
        pass
    table.itemChanged.connect(
        lambda item: _update_qc_mapping_summary(w) if item.column() == 0 else None
    )
    _update_qc_mapping_summary(w)

def _qc_mapping_from_ui(w):
    import pandas as pd
    rows = []
    table = w.sis_qc_mapping_table
    for r in range(table.rowCount()):
        rows.append({
            "Sample Key": table.item(r, 6).text(),
            "Name": table.item(r, 1).text(),
            "ID": table.item(r, 2).text(),
            "Sample Text": table.item(r, 3).text(),
            "Type": table.item(r, 4).text(),
            "Automatic Include": table.item(r, 5).text() == "YES",
            "Include": table.item(r, 0).checkState() == Qt.Checked,
        })
    return pd.DataFrame(rows)

def _update_qc_mapping_summary(w):
    if not hasattr(w, "sis_qc_mapping_table"):
        return
    table = w.sis_qc_mapping_table
    total = table.rowCount()
    included = sum(
        1 for r in range(total)
        if table.item(r, 0) is not None and table.item(r, 0).checkState() == Qt.Checked
    )
    w.sis_qc_mapping_summary.setText(
        f"{included:,} of {total:,} QC sample(s) included"
    )


def _reset_qc_mapping(w):
    if w.sis_qc_mapping is not None:
        _populate_qc_mapping(w)


def _set_all_qc_included(w, included):
    table = w.sis_qc_mapping_table
    table.blockSignals(True)
    for r in range(table.rowCount()):
        item = table.item(r, 0)
        if item is not None:
            item.setCheckState(Qt.Checked if included else Qt.Unchecked)
    table.blockSignals(False)
    _update_qc_mapping_summary(w)


def _ranking_display_value(value):
    if isinstance(value, (bool, np.bool_)):
        return "PASS" if bool(value) else "FAIL"
    return _fmt(value)


def _update_ranking_filter_values(w):
    if not w.sis_result:
        return
    rank = w.sis_result.get("ranking")
    if rank is None or rank.empty:
        return
    col = w.sis_rank_filter_column.currentText()
    w.sis_rank_filter_value.blockSignals(True)
    w.sis_rank_filter_value.clear()
    w.sis_rank_filter_value.addItem("All")
    if col and col in rank.columns:
        values = rank[col].drop_duplicates().tolist()
        values = sorted(values, key=lambda v: _ranking_display_value(v).casefold())
        for value in values:
            w.sis_rank_filter_value.addItem(_ranking_display_value(value), value)
    w.sis_rank_filter_value.blockSignals(False)
    w.sis_rank_filter_value.setCurrentIndex(0)
    _refresh_ranking_view(w)


def _clear_ranking_filter(w):
    if hasattr(w, "sis_rank_filter_value"):
        w.sis_rank_filter_value.setCurrentIndex(0)


def _show_ranking_columns_menu(w):
    if not w.sis_result:
        return
    rank = w.sis_result.get("ranking")
    if rank is None or rank.empty:
        return
    menu = QMenu(w.sis_rank_columns_button)
    for col in rank.columns:
        action = menu.addAction(str(col))
        action.setCheckable(True)
        action.setChecked(str(col) not in w.sis_rank_hidden_columns)
        action.toggled.connect(
            lambda checked, name=str(col): _set_ranking_column_visible(w, name, checked)
        )
    menu.addSeparator()
    show_all = menu.addAction("Show All")
    show_all.triggered.connect(lambda: _show_all_ranking_columns(w))
    menu.exec(w.sis_rank_columns_button.mapToGlobal(w.sis_rank_columns_button.rect().bottomLeft()))


def _set_ranking_column_visible(w, column, visible):
    if visible:
        w.sis_rank_hidden_columns.discard(str(column))
    else:
        w.sis_rank_hidden_columns.add(str(column))
    for c in range(w.sis_ranking.columnCount()):
        item = w.sis_ranking.horizontalHeaderItem(c)
        if item is not None and item.text() == str(column):
            w.sis_ranking.setColumnHidden(c, not visible)
            break


def _show_all_ranking_columns(w):
    w.sis_rank_hidden_columns.clear()
    for c in range(w.sis_ranking.columnCount()):
        w.sis_ranking.setColumnHidden(c, False)


def _apply_ranking_column_visibility(w):
    if not hasattr(w, "sis_rank_hidden_columns"):
        return
    for c in range(w.sis_ranking.columnCount()):
        item = w.sis_ranking.horizontalHeaderItem(c)
        if item is not None:
            w.sis_ranking.setColumnHidden(c, item.text() in w.sis_rank_hidden_columns)


def _refresh_ranking_view(w, preferred_pair=None):
    if not w.sis_result:
        return
    header = w.sis_ranking.horizontalHeader()
    prior_order = []
    if w.sis_ranking.columnCount():
        prior_order = [
            w.sis_ranking.horizontalHeaderItem(header.logicalIndex(v)).text()
            for v in range(header.count())
            if w.sis_ranking.horizontalHeaderItem(header.logicalIndex(v)) is not None
        ]
    rank = w.sis_result.get("ranking")
    if rank is None:
        return

    view = rank
    col = w.sis_rank_filter_column.currentText() if hasattr(w, "sis_rank_filter_column") else ""
    value_index = w.sis_rank_filter_value.currentIndex() if hasattr(w, "sis_rank_filter_value") else 0
    if col and col in rank.columns and value_index > 0:
        raw = w.sis_rank_filter_value.currentData()
        series = rank[col]
        if isinstance(raw, (bool, np.bool_)):
            mask = series.astype(bool).eq(bool(raw))
        elif isinstance(raw, (int, float, np.integer, np.floating)) and not isinstance(raw, (bool, np.bool_)):
            vals = pd.to_numeric(series, errors="coerce")
            mask = np.isclose(vals.to_numpy(float), float(raw), rtol=1e-12, atol=1e-12, equal_nan=False)
        else:
            mask = series.astype(str).eq(str(raw))
        view = rank.loc[mask]

    _fill_table(w.sis_ranking, view.reset_index(drop=True))
    header = w.sis_ranking.horizontalHeader()
    header.setSectionsMovable(True)
    if prior_order:
        desired = [name for name in prior_order if name in view.columns] + [
            str(c) for c in view.columns if str(c) not in prior_order
        ]
        for target_visual, name in enumerate(desired):
            logical = next(
                (c for c in range(w.sis_ranking.columnCount())
                 if w.sis_ranking.horizontalHeaderItem(c) is not None
                 and w.sis_ranking.horizontalHeaderItem(c).text() == name),
                None,
            )
            if logical is not None:
                current_visual = header.visualIndex(logical)
                if current_visual != target_visual:
                    header.moveSection(current_visual, target_visual)
    _apply_ranking_column_visibility(w)
    if hasattr(w, "sis_rank_count"):
        w.sis_rank_count.setText(f"{len(view):,} displayed / {len(rank):,} total pair(s)")

    target = preferred_pair
    if target is None and len(view):
        target = (str(view.iloc[0]["Analyte"]), str(view.iloc[0]["Internal Standard"]))

    if target and w.sis_ranking.rowCount():
        headers = {
            w.sis_ranking.horizontalHeaderItem(c).text(): c
            for c in range(w.sis_ranking.columnCount())
            if w.sis_ranking.horizontalHeaderItem(c) is not None
        }
        ac = headers.get("Analyte"); ic = headers.get("Internal Standard")
        if ac is not None and ic is not None:
            for r in range(w.sis_ranking.rowCount()):
                ai = w.sis_ranking.item(r, ac); ii = w.sis_ranking.item(r, ic)
                if ai and ii and ai.text() == target[0] and ii.text() == target[1]:
                    w.sis_ranking.selectRow(r)
                    break

def _run(w, suppress_large_warning=False):
    if w.sis_data is None:
        QMessageBox.information(w, "No dataset", "Load a surrogate-IS dataset first."); return
    try:
        mapping = _mapping_from_ui(w)
        qc_mapping = _qc_mapping_from_ui(w)
        included = mapping[mapping["Include"].astype(bool)]
        n_an = int((included["Role"] == "Analyte").sum())
        n_is = int((included["Role"] == "IS").sum())
        if n_an == 0 or n_is == 0:
            QMessageBox.information(
                w, "Component mapping",
                "Select at least one included Analyte and one included Internal Standard."
            )
            return
        pair_count = n_an * n_is
        if pair_count > 2000 and not suppress_large_warning:
            answer = QMessageBox.warning(
                w,
                "Large surrogate-IS benchmark",
                f"This setup will evaluate {n_an} analytes × {n_is} internal standards = "
                f"{pair_count:,} pairs. Large analyses can be CPU-intensive.\n\n"
                "Continue with this selection?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return
        w.sis_result = analyze_surrogate_is(
            w.sis_data, _criteria(w), component_mapping=mapping,
            qc_sample_mapping=qc_mapping, user_amr=w.sis_user_amr,
            calibrator_source_mode=w.sis_calibrator_source.currentText(),
            analyte_fit_settings=_analyte_fit_settings_from_ui(w),
            pair_search_mode=w.sis_pair_search.currentText()
        ); rank = w.sis_result["ranking"]
        w.sis_rank_filter_column.blockSignals(True)
        w.sis_rank_filter_column.clear()
        if not rank.empty:
            w.sis_rank_filter_column.addItems([str(c) for c in rank.columns])
        w.sis_rank_filter_column.blockSignals(False)
        if not rank.empty:
            preferred = "Analyte" if "Analyte" in rank.columns else str(rank.columns[0])
            w.sis_rank_filter_column.setCurrentText(preferred)
            _update_ranking_filter_values(w)
        else:
            _refresh_ranking_view(w)
        _fill_table(w.sis_stage1, w.sis_result["stage1"])
        passed = int(rank["Pass"].sum()) if not rank.empty else 0
        w.sis_note.setText(f"Evaluated {len(rank)} analyte–IS pairs; {passed} met all current calibration and QC criteria.")
        _draw_heatmap(w)
        if len(rank) and w.sis_ranking.rowCount(): w.sis_ranking.selectRow(0); _selection_changed(w)
    except Exception as exc:
        QMessageBox.critical(w, "Surrogate IS analysis failed", str(exc))


def _fill_table(table, df):
    sorting = table.isSortingEnabled()
    table.setSortingEnabled(False)
    table.clear(); table.setRowCount(len(df)); table.setColumnCount(len(df.columns))
    table.setHorizontalHeaderLabels([str(c) for c in df.columns])
    for r, (_, rec) in enumerate(df.iterrows()):
        for c, col in enumerate(df.columns):
            value = rec[col]
            sort_value = None
            if isinstance(value, (bool, np.bool_)):
                sort_value = int(bool(value))
            elif isinstance(value, (int, float, np.integer, np.floating)):
                try:
                    if np.isfinite(value): sort_value = float(value)
                except Exception:
                    pass
            item = SortableTableItem(_fmt(value), sort_value=sort_value)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            table.setItem(r, c, item)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    table.horizontalHeader().setStretchLastSection(True)
    if hasattr(table, "_refresh_filter_columns"):
        table._refresh_filter_columns()
    table.setSortingEnabled(sorting)
    if hasattr(table, "_apply_filter"):
        table._apply_filter()


def _fill_calibrator_table(w, df):
    table = w.sis_cal_detail
    w.sis_updating_cal_table = True
    sorting = table.isSortingEnabled()
    table.setSortingEnabled(False)
    preferred = [
        "Use", "Nominal", "Ratio", "Back-calculated",
        "Analyte RT", "IS RT", "ΔRT", "Bias %", "|Bias| %"
    ]
    cols = [c for c in preferred if c in df.columns or c == "Use"]
    table.clear(); table.setRowCount(len(df)); table.setColumnCount(len(cols))
    table.setHorizontalHeaderLabels(cols)
    for r, (_, rec) in enumerate(df.iterrows()):
        use_item = QTableWidgetItem("")
        use_item.setFlags(use_item.flags() | Qt.ItemIsUserCheckable)
        use_item.setCheckState(Qt.Checked if bool(rec["Use"]) else Qt.Unchecked)
        use_item.setData(Qt.UserRole, float(rec["Nominal"]))
        table.setItem(r, 0, use_item)
        for c, col in enumerate(cols[1:], start=1):
            value = rec[col]
            sort_value = float(value) if isinstance(value, (int, float, np.integer, np.floating)) and np.isfinite(value) else None
            item = SortableTableItem(_fmt(value), sort_value=sort_value)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            table.setItem(r, c, item)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    table.horizontalHeader().setStretchLastSection(True)
    table.setSortingEnabled(sorting)
    w.sis_updating_cal_table = False


def _calibrator_use_changed(w, item):
    if w.sis_updating_cal_table or item.column() != 0 or not w.sis_result:
        return
    pair = _selected_pair(w)
    if pair is None:
        return

    table = w.sis_cal_detail
    included = []
    excluded = []
    for r in range(table.rowCount()):
        it = table.item(r, 0)
        if it is None:
            continue
        nominal = float(it.data(Qt.UserRole))
        if it.checkState() == Qt.Checked:
            included.append(nominal)
        else:
            excluded.append(nominal)

    if len(included) < w.sis_min_cal.value():
        QMessageBox.information(
            w, "Minimum calibrators",
            f"At least {w.sis_min_cal.value()} calibrators must remain included."
        )
        w.sis_updating_cal_table = True
        item.setCheckState(Qt.Checked)
        w.sis_updating_cal_table = False
        return

    try:
        detail = refit_pair_with_exclusions(
            w.sis_result, pair[0], pair[1], excluded
        )

        # If the edited pair is this analyte's matched SIL-IS and matched-SIL
        # reference mode is active, every surrogate QC bias depends on this
        # reference curve. Refresh those dependent pair summaries immediately
        # while preserving each surrogate's own calibrator selection.
        criteria = w.sis_result.get("criteria")
        is_meta = w.sis_result.get("is_metadata")
        is_matched_sil = False
        if (
            criteria is not None
            and getattr(criteria, "qc_reference_basis", "") == "Matched SIL-IS calculated concentration"
            and is_meta is not None
            and len(is_meta)
        ):
            sil = is_meta[
                is_meta["IS Class"].astype(str).eq("SIL-IS")
                & is_meta["Paired Analyte"].astype(str).eq(str(pair[0]))
                & is_meta["Component"].astype(str).eq(str(pair[1]))
            ]
            is_matched_sil = len(sil) > 0

        if is_matched_sil:
            refresh = refresh_matched_sil_dependents(w.sis_result, pair[0])
            detail = compute_pair_detail(w.sis_result, pair[0], pair[1])
            _refresh_ranking_view(w, preferred_pair=pair)
            _draw_heatmap(w)
            failed = refresh.get("failed", [])
            suffix = (
                f"; {len(failed)} dependent pair(s) could not be refreshed"
                if failed else ""
            )
            w.sis_note.setText(
                f"Updated matched SIL-IS reference for {pair[0]}; recalculated "
                f"{refresh.get('updated', 0)} reference-dependent pair(s){suffix}."
            )

        _refresh_selected_pair(w, pair, detail, refresh_ranking=True)
    except Exception as exc:
        QMessageBox.critical(w, "Pair refit failed", str(exc))
        _selection_changed(w)


def _sync_amr_to_surrogates(w):
    if not w.sis_result:
        return
    pair = _selected_pair(w)
    if pair is None:
        return

    table = w.sis_cal_detail
    active_n = sum(
        1 for r in range(table.rowCount())
        if table.item(r, 0) is not None and table.item(r, 0).checkState() == Qt.Checked
    )

    answer = QMessageBox.question(
        w,
        "Sync AMR to other surrogates",
        f"Apply the current {pair[0]} calibrator pattern ({active_n} included level(s)) "
        "to every internal-standard candidate for this analyte?\n\n"
        "Existing pair-specific manual exclusions for those surrogate fits will be replaced.",
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No,
    )
    if answer != QMessageBox.Yes:
        return

    try:
        result = sync_pair_amr_to_surrogates(w.sis_result, pair[0], pair[1])
        _refresh_ranking_view(w, preferred_pair=pair)
        _draw_heatmap(w)

        detail = compute_pair_detail(w.sis_result, pair[0], pair[1])
        _refresh_selected_pair(w, pair, detail, refresh_ranking=True)

        failed = result.get("failed", [])
        if failed:
            names = ", ".join(name for name, _ in failed[:8])
            more = "…" if len(failed) > 8 else ""
            QMessageBox.warning(
                w,
                "AMR sync completed with skips",
                f"Updated {result.get('updated', 0)} surrogate fit(s). "
                f"{len(failed)} could not be refit with this AMR: {names}{more}"
            )
        else:
            QMessageBox.information(
                w,
                "AMR sync complete",
                f"Applied the current {pair[0]} AMR/calibrator pattern to "
                f"{result.get('updated', 0)} surrogate fit(s)."
            )
    except Exception as exc:
        QMessageBox.critical(w, "AMR sync failed", str(exc))


def _refresh_selected_pair(w, pair, detail, refresh_ranking=False):
    if refresh_ranking:
        _refresh_ranking_view(w, preferred_pair=pair)

    s = detail["summary"]
    _fill_calibrator_table(w, detail.get("calibrators", []))
    qc_samples = detail.get("qc_samples")
    if qc_samples is not None:
        _fill_table(w.sis_qc_detail, qc_samples)
        w.sis_qc_detail_label.setText(
            f"{pair[0]} / {pair[1]} — {len(qc_samples)} included QC result(s); "
            f"individual pass criterion: |bias| ≤ {w.sis_qc_max_bias.value():g}%."
        )

    source = s.get("AMR Source", w.sis_result.get("stage1_sources", {}).get(pair[0], "Automatic"))
    w.sis_detail_label.setText(
        f"{pair[0]} / {pair[1]} — {'PASS' if s.get('Pass', False) else 'FAIL'}; "
        f"{s.get('Pair Type', 'Surrogate')}; "
        f"AMR {s.get('LLOQ', np.nan):g}–{s.get('ULOQ', np.nan):g} ({source}); "
        f"median |ΔRT| {_fmt(s.get('Median |ΔRT|', np.nan))}; "
        f"max cal |bias| {s.get('Max Cal |Bias| %', np.nan):.2f}%; "
        f"Fit R² {s.get('Fit R2', np.nan):.6f}; "
        f"QC reference: {s.get('QC Reference', '')}; "
        f"QC mean |bias| {_fmt(s.get('QC Mean |Bias| %', np.nan))}%; "
        f"QC max CV {_fmt(s.get('QC Max CV %', np.nan))}%."
    )
    fig = w.sis_detail_fig; fig.clear(); ax = fig.add_subplot(111)
    x = np.asarray(detail["x_cal"], float); y = np.asarray(detail["ratio_cal"], float); fit = detail["fit"]
    ax.scatter(x, y, label="Included calibrators")
    grid = np.linspace(np.min(x), np.max(x), 200)
    ax.plot(grid, fit.predict(grid), label="Fit")
    cal = detail.get("calibrators")
    if cal is not None and len(cal):
        excluded_rows = cal.loc[~cal["Use"].astype(bool)]
        if len(excluded_rows):
            ax.scatter(
                excluded_rows["Nominal"].to_numpy(float),
                excluded_rows["Ratio"].to_numpy(float),
                marker="x", label="Excluded calibrators"
            )
    ax.set_xlabel("Nominal concentration")
    ax.set_ylabel("Analyte / IS area ratio")
    ax.set_title(f"{pair[0]} using {pair[1]}")
    ax.legend()
    fig.tight_layout(); w.sis_detail_canvas.draw_idle()


def _heatmap_annotation_text(metric, value):
    if not np.isfinite(value):
        return ""
    if "R2" in metric:
        return f"{value:.4f}"
    if "%" in metric:
        return f"{value:.1f}"
    if metric in {"n Cal", "QC Levels", "Stage 2 Iterations", "Stage 2 Removed"}:
        return f"{value:.0f}"
    return f"{value:.3g}"


def _draw_heatmap(w):
    fig = w.sis_heat_fig; fig.clear()
    if not w.sis_result:
        w.sis_heat_canvas.draw_idle(); return
    metric = w.sis_heat_metric.currentText()
    mat = pair_metric_matrix(
        w.sis_result,
        metric,
        order=w.sis_heat_order.currentText() if hasattr(w, "sis_heat_order") else "Retention time",
    )
    if mat.empty:
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, f"No data available for {metric}", ha="center", va="center")
        ax.set_axis_off()
        w.sis_heat_canvas.draw_idle(); return

    values = mat.to_numpy(float)
    ax = fig.add_subplot(111)

    # Build a pair-status matrix aligned exactly to the displayed metric
    # matrix. Missing metric values are always shown in grey. When requested,
    # failed pairs are masked as well so Matplotlib itself renders the cell grey
    # rather than relying on post-hoc rectangle overlays.
    rank = w.sis_result.get("ranking")
    status = np.full(values.shape, False, dtype=bool)
    status_known = np.full(values.shape, False, dtype=bool)
    if rank is not None and hasattr(rank, "empty") and not rank.empty and "Pass" in rank.columns:
        pass_lookup = {}
        for _, rec in rank.iterrows():
            raw_pass = rec["Pass"]
            if isinstance(raw_pass, (bool, np.bool_)):
                passed = bool(raw_pass)
            else:
                passed = str(raw_pass).strip().casefold() in {
                    "true", "pass", "passed", "1", "yes"
                }
            pass_lookup[(str(rec["Analyte"]), str(rec["Internal Standard"]))] = passed

        for r, analyte in enumerate(mat.index):
            for c, is_name in enumerate(mat.columns):
                key = (str(analyte), str(is_name))
                if key in pass_lookup:
                    status_known[r, c] = True
                    status[r, c] = bool(pass_lookup[key])

    missing_metric = ~np.isfinite(values)
    grey_failed = (
        getattr(w, "sis_heat_grey_fail", None) is not None
        and w.sis_heat_grey_fail.isChecked()
    )
    mask = missing_metric.copy()
    if grey_failed:
        mask |= (~status_known) | (~status)

    import matplotlib.pyplot as plt
    cmap = plt.get_cmap().copy()
    cmap.set_bad("0.72")
    display_values = np.ma.array(values, mask=mask)
    im = ax.imshow(display_values, aspect="auto", cmap=cmap)
    colorbar_mappable = im
    ax.set_xticks(range(len(mat.columns)))
    ax.set_xticklabels(mat.columns, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(mat.index)))
    ax.set_yticklabels(mat.index, fontsize=8)
    ax.set_title(metric)

    if getattr(w, "sis_heat_annotate", None) is not None and w.sis_heat_annotate.isChecked():
        for r in range(values.shape[0]):
            for c in range(values.shape[1]):
                text_value = _heatmap_annotation_text(metric, values[r, c])
                if not text_value and not np.isfinite(values[r, c]):
                    text_value = "N/A"
                if text_value:
                    ax.text(c, r, text_value, ha="center", va="center", fontsize=6, zorder=3)

    fig.colorbar(colorbar_mappable, ax=ax, shrink=0.8)
    fig.tight_layout()
    w.sis_heat_canvas.draw_idle()


def _export_heatmap(w, file_type):
    if not w.sis_result:
        QMessageBox.information(w, "No results", "Run Surrogate IS Analysis first.")
        return
    metric = w.sis_heat_metric.currentText()
    safe_metric = "".join(ch if ch.isalnum() else "_" for ch in metric).strip("_").lower()
    if file_type == "svg":
        default_name = f"heatmap_{safe_metric}.svg"
        filter_text = "SVG Vector Image (*.svg)"
    else:
        default_name = f"heatmap_{safe_metric}.png"
        filter_text = "PNG Image (*.png)"

    path, _ = QFileDialog.getSaveFileName(w, f"Export {metric} Heatmap", default_name, filter_text)
    if not path:
        return
    suffix = f".{file_type}"
    if not path.lower().endswith(suffix):
        path += suffix
    try:
        w.sis_heat_fig.savefig(path, format=file_type, bbox_inches="tight")
        QMessageBox.information(w, "Heatmap export complete", f"Saved:\n{path}")
    except Exception as exc:
        QMessageBox.critical(w, "Heatmap export failed", str(exc))


def _selected_pair(w):
    if not w.sis_result: return None
    rows = w.sis_ranking.selectionModel().selectedRows()
    if not rows: return None
    r = rows[0].row()

    headers = {
        w.sis_ranking.horizontalHeaderItem(c).text(): c
        for c in range(w.sis_ranking.columnCount())
        if w.sis_ranking.horizontalHeaderItem(c) is not None
    }
    a_col = headers.get("Analyte")
    is_col = headers.get("Internal Standard")
    if a_col is None or is_col is None:
        return None

    a_item = w.sis_ranking.item(r, a_col)
    is_item = w.sis_ranking.item(r, is_col)
    if a_item is None or is_item is None:
        return None
    return a_item.text(), is_item.text()


def _selection_changed(w):
    pair = _selected_pair(w)
    if pair is None: return
    try:
        detail = compute_pair_detail(w.sis_result, pair[0], pair[1])
    except Exception as exc:
        w.sis_detail_label.setText(f"Could not build pair detail: {exc}")
        return
    _refresh_selected_pair(w, pair, detail, refresh_ranking=False)


def _export(w):
    if not w.sis_result:
        QMessageBox.information(w, "No results", "Run Surrogate IS Analysis first."); return
    path, _ = QFileDialog.getSaveFileName(w, "Export Surrogate IS Workbook", "surrogate_is_analysis.xlsx", "Excel Workbook (*.xlsx)")
    if not path: return
    try:
        export_surrogate_workbook(w.sis_result, path)
        QMessageBox.information(w, "Export complete", f"Saved:\n{path}")
    except Exception as exc:
        details = traceback.format_exc()
        box = QMessageBox(w)
        box.setIcon(QMessageBox.Critical)
        box.setWindowTitle("Export failed")
        box.setText(str(exc))
        box.setDetailedText(details)
        box.exec()
