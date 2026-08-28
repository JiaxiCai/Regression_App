"""Reusable Qt UI helpers for Regression App."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QSplitter, QWidget, QHBoxLayout, QLabel, QComboBox, QLineEdit, QPushButton,
    QTableWidgetItem
)


class SortableTableItem(QTableWidgetItem):
    """Table item that sorts numerically when a numeric value is available."""
    def __init__(self, text="", sort_value=None):
        super().__init__(text)
        self._sort_value = sort_value

    def __lt__(self, other):
        if isinstance(other, SortableTableItem):
            a = self._sort_value
            b = other._sort_value
            if a is not None and b is not None:
                try:
                    return float(a) < float(b)
                except Exception:
                    pass
        return super().__lt__(other)


def configure_splitter(splitter: QSplitter, sizes=None, stretch=None):
    splitter.setChildrenCollapsible(False)
    if stretch:
        for index, factor in enumerate(stretch):
            splitter.setStretchFactor(index, factor)
    if sizes:
        splitter.setSizes(list(sizes))
    return splitter


def configure_sortable_table(table):
    """Enable click-to-sort while preserving whole-row selection behavior."""
    table.setSortingEnabled(True)
    table.horizontalHeader().setSortIndicatorShown(True)
    table.horizontalHeader().setSectionsClickable(True)
    return table


def make_table_filter_bar(table, parent=None):
    """Create a compact per-column filter bar for a QTableWidget.

    Text filters use case-insensitive substring matching by default. Numeric
    operators can be entered directly in the filter text, e.g. >=15, <0.995,
    =PASS. Multiple filters are applied one at a time via the selected column.
    """
    bar = QWidget(parent)
    layout = QHBoxLayout(bar)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(QLabel("Filter column"))

    column = QComboBox()
    layout.addWidget(column)

    entry = QLineEdit()
    entry.setPlaceholderText("contains text, or use >=, <=, >, <, =")
    layout.addWidget(entry, 1)

    clear = QPushButton("Clear")
    layout.addWidget(clear)

    state = {"column": column, "entry": entry}
    table._filter_state = state

    def refresh_columns():
        current = column.currentText()
        column.blockSignals(True)
        column.clear()
        for c in range(table.columnCount()):
            item = table.horizontalHeaderItem(c)
            column.addItem(item.text() if item else f"Column {c+1}", c)
        if current:
            i = column.findText(current)
            if i >= 0:
                column.setCurrentIndex(i)
        column.blockSignals(False)

    def parse_numeric(text):
        try:
            return float(text)
        except Exception:
            return None

    def matches(cell_text, query):
        q = query.strip()
        if not q:
            return True
        for op in (">=", "<=", ">", "<", "="):
            if q.startswith(op):
                rhs = q[len(op):].strip()
                if op == "=":
                    left_num = parse_numeric(cell_text)
                    right_num = parse_numeric(rhs)
                    if left_num is not None and right_num is not None:
                        return left_num == right_num
                    return cell_text.strip().casefold() == rhs.casefold()
                left_num = parse_numeric(cell_text)
                right_num = parse_numeric(rhs)
                if left_num is None or right_num is None:
                    return False
                return {
                    ">=": left_num >= right_num,
                    "<=": left_num <= right_num,
                    ">": left_num > right_num,
                    "<": left_num < right_num,
                }[op]
        return q.casefold() in cell_text.casefold()

    def apply_filter():
        if table.columnCount() == 0:
            return
        c = column.currentData()
        if c is None:
            c = 0
        q = entry.text()
        for r in range(table.rowCount()):
            item = table.item(r, int(c))
            text = item.text() if item is not None else ""
            table.setRowHidden(r, not matches(text, q))

    def clear_filter():
        entry.clear()
        for r in range(table.rowCount()):
            table.setRowHidden(r, False)

    entry.textChanged.connect(lambda _: apply_filter())
    column.currentIndexChanged.connect(lambda _: apply_filter())
    clear.clicked.connect(clear_filter)
    table._refresh_filter_columns = refresh_columns
    table._apply_filter = apply_filter
    refresh_columns()
    return bar
