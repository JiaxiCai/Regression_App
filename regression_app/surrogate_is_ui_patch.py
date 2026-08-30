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
    SurrogateCriteria, load_surrogate_data, load_user_amr, analyze_surrogate_is,
    component_mapping_table, qc_sample_mapping_table, pair_metric_matrix,
    compute_pair_detail, refit_pair_with_exclusions, export_surrogate_workbook,
)
from .ui_helpers import SortableTableItem, configure_sortable_table, make_table_filter_bar


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

    mapping_page = QWidget(); ml = QVBoxLayout(mapping_page)
    mapping_intro = QLabel(
        "Review the automatic compound assignments before analysis. Change Role to "
        "Analyte, Internal Standard, or Ignore; uncheck Include to exclude a component "
        "from the current benchmark without changing its assignment."
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
    w.sis_mapping_table = QTableWidget(0, 6)
    w.sis_mapping_table.setHorizontalHeaderLabels([
        "Include", "Component", "Automatic Role", "Role", "Calibrator Rows", "QC Rows"
    ])
    w.sis_mapping_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    w.sis_mapping_table.horizontalHeader().setStretchLastSection(True)
    ml.addWidget(w.sis_mapping_table, 1)
    outtabs.addTab(mapping_page, "Component Mapping")

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
    w.sis_qc_mapping_table = QTableWidget(0, 5)
    w.sis_qc_mapping_table.setHorizontalHeaderLabels([
        "Include", "Sample Name", "Sample Type", "Automatic Include", "Sample Key"
    ])
    w.sis_qc_mapping_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    w.sis_qc_mapping_table.horizontalHeader().setStretchLastSection(True)
    qml.addWidget(w.sis_qc_mapping_table, 1)
    outtabs.addTab(qcmap_page, "QC Sample Mapping")

    rank_page = QWidget(); rl = QVBoxLayout(rank_page)
    w.sis_ranking = QTableWidget(); w.sis_ranking.setSelectionBehavior(QTableWidget.SelectRows)
    w.sis_ranking.setSelectionMode(QTableWidget.SingleSelection)
    configure_sortable_table(w.sis_ranking)
    rl.addWidget(make_table_filter_bar(w.sis_ranking, rank_page))
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
    w.sis_detail_fig = Figure(figsize=(10, 5), dpi=100); w.sis_detail_canvas = FigureCanvas(w.sis_detail_fig)
    dl.addWidget(NavigationToolbar(w.sis_detail_canvas, detail_page)); dl.addWidget(w.sis_detail_canvas, 1)
    cal_label = QLabel(
        "Calibrators — uncheck Use to exclude that concentration for this pair and refit. "
        "Manual edits are pair-specific and are labeled as Manual edited."
    )
    cal_label.setWordWrap(True); dl.addWidget(cal_label)
    w.sis_cal_detail = QTableWidget()
    configure_sortable_table(w.sis_cal_detail)
    w.sis_cal_detail.setMaximumHeight(240)
    w.sis_cal_detail.itemChanged.connect(lambda item: _calibrator_use_changed(w, item))
    dl.addWidget(w.sis_cal_detail)
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
        w.sis_component_mapping = component_mapping_table(data)
        w.sis_qc_mapping = qc_sample_mapping_table(data)
        w.sis_file.setText(Path(path).name)
        _populate_mapping(w)
        _populate_qc_mapping(w)
        n_an = data.loc[data["Component Role"] == "Analyte", "Component"].nunique()
        n_is = data.loc[data["Component Role"] == "IS", "Component"].nunique()
        w.sis_note.setText(
            f"Loaded {meta.get('format', 'data')}: {len(data):,} component rows; "
            f"{n_an} analyte component(s), {n_is} internal standard(s)."
        )
    except Exception as exc:
        QMessageBox.critical(w, "Surrogate IS import failed", str(exc))


def _populate_mapping(w):
    mapping = w.sis_component_mapping
    if mapping is None:
        return
    table = w.sis_mapping_table
    table.blockSignals(True)
    table.setRowCount(len(mapping))
    for r, (_, rec) in enumerate(mapping.iterrows()):
        include = QTableWidgetItem("")
        include.setFlags(include.flags() | Qt.ItemIsUserCheckable)
        include.setCheckState(Qt.Checked if bool(rec["Include"]) else Qt.Unchecked)
        table.setItem(r, 0, include)

        for c, key in [(1, "Component"), (2, "Automatic Role"), (4, "Calibrator Rows"), (5, "QC Rows")]:
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
        rows.append({
            "Component": component,
            "Automatic Role": auto,
            "Role": role,
            "Include": include,
            "Calibrator Rows": int(float(table.item(r, 4).text() or 0)),
            "QC Rows": int(float(table.item(r, 5).text() or 0)),
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
        for c, key in [(1, "Sample Name"), (2, "Sample Type"), (4, "Sample Key")]:
            item = QTableWidgetItem(str(rec[key]))
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            table.setItem(r, c, item)
        auto = QTableWidgetItem("YES" if bool(rec["Automatic Include"]) else "NO")
        auto.setFlags(auto.flags() & ~Qt.ItemIsEditable)
        table.setItem(r, 3, auto)
    table.blockSignals(False)
    try:
        table.itemChanged.disconnect()
    except Exception:
        pass
    table.itemChanged.connect(lambda item: _update_qc_mapping_summary(w) if item.column() == 0 else None)
    _update_qc_mapping_summary(w)


def _qc_mapping_from_ui(w):
    import pandas as pd
    rows = []
    table = w.sis_qc_mapping_table
    for r in range(table.rowCount()):
        rows.append({
            "Sample Key": table.item(r, 4).text(),
            "Sample Name": table.item(r, 1).text(),
            "Sample Type": table.item(r, 2).text(),
            "Automatic Include": table.item(r, 3).text() == "YES",
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


def _run(w):
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
        if pair_count > 2000:
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
            qc_sample_mapping=qc_mapping, user_amr=w.sis_user_amr
        ); rank = w.sis_result["ranking"]
        _fill_table(w.sis_ranking, rank); _fill_table(w.sis_stage1, w.sis_result["stage1"])
        passed = int(rank["Pass"].sum()) if not rank.empty else 0
        w.sis_note.setText(f"Evaluated {len(rank)} analyte–IS pairs; {passed} met all current calibration and QC criteria.")
        _draw_heatmap(w)
        if len(rank): w.sis_ranking.selectRow(0); _selection_changed(w)
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
    cols = ["Use", "Nominal", "Ratio", "Back-calculated", "Bias %", "|Bias| %"]
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
        _refresh_selected_pair(w, pair, detail, refresh_ranking=True)
    except Exception as exc:
        QMessageBox.critical(w, "Pair refit failed", str(exc))
        _selection_changed(w)


def _refresh_selected_pair(w, pair, detail, refresh_ranking=False):
    if refresh_ranking:
        _fill_table(w.sis_ranking, w.sis_result["ranking"])
        headers = {
            w.sis_ranking.horizontalHeaderItem(c).text(): c
            for c in range(w.sis_ranking.columnCount())
            if w.sis_ranking.horizontalHeaderItem(c) is not None
        }
        ac = headers.get("Analyte"); ic = headers.get("Internal Standard")
        if ac is not None and ic is not None:
            for r in range(w.sis_ranking.rowCount()):
                ai = w.sis_ranking.item(r, ac); ii = w.sis_ranking.item(r, ic)
                if ai and ii and ai.text() == pair[0] and ii.text() == pair[1]:
                    w.sis_ranking.selectRow(r)
                    break

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
        f"AMR {s.get('LLOQ', np.nan):g}–{s.get('ULOQ', np.nan):g} ({source}); "
        f"max cal |bias| {s.get('Max Cal |Bias| %', np.nan):.2f}%; "
        f"Fit R² {s.get('Fit R2', np.nan):.6f}; "
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
        export_surrogate_workbook(w.sis_result, path); QMessageBox.information(w, "Export complete", f"Saved:\n{path}")
    except Exception as exc:
        QMessageBox.critical(w, "Export failed", str(exc))
