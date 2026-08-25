# Changelog

All notable development changes to Regression App are documented here.

## [0.3.2] - 2026-08-24

### Regression statistics
- Added signed Pearson correlation coefficient `r`.
- Model Comparison now reports both `Pearson r` and `Pearson r²`.
- `Pearson r = corr(X, Y)` and preserves sign; `Pearson r² = r²`.
- Added Pearson r to exported regression summaries.

## [0.3.1] - 2026-08-24

### Build tooling
- macOS builder now detects Python 3.10 through 3.14.
- Detects generic `python3`, common Homebrew locations, and python.org framework installs.
- Continues to reject Apple/Xcode system Python.
- Added Python diagnostics when detection fails.

## [0.3.0] - 2026-08-24

### UI / architecture
- Major workspace usability cleanup using draggable Qt splitters.
- Regression `Data & Model Setup` now provides a large spreadsheet-style data-entry pane and separately resizable model/acceptance settings.
- Method Comparison now has resizable input/results regions and independently resizable result table, plot, and notes.
- ROC now has resizable input/results regions with numerical output beside the plot.
- TargetLynx Converter now has resizable compound/column-selection and configuration/preview regions.
- Removed key fixed-height restrictions and increased default main-window size.
- Added `regression_app/ui_helpers.py` as the start of the UI architecture refactor.

## [0.2.7] - 2026-08-24
- Fixed ROC startup crash by explicitly constructing a Matplotlib `Figure`, wrapping it in `FigureCanvas`, and storing a dedicated axes object.

## [0.2.6] - 2026-08-24
- Fixed ROC startup crash caused by referencing undefined `MplCanvas`.

## [0.2.5] - 2026-08-24
- Added ROC curve plot with sensitivity vs `1 - specificity`, no-discrimination line, AUC label, and Youden-optimal operating point.

## [0.2.4] - 2026-08-24
- Replaced three TargetLynx output-field dropdowns with unrestricted multi-select column selection.
- Added separate Sample metadata and Measurement/result categories.
- Added Select measurement fields, Select all columns, and Clear all controls.
- Wide, long/tidy, and per-compound exports now use the selected column set.

## [0.2.3] - 2026-08-24
- Fixed the v0.2.2 startup crash from an undefined central layout reference.
- Regression input moved into `Input & Model Setup` while other top-level tools use the full workspace.

## [0.2.2] - 2026-08-24
- Reworked the workspace so Regression input is no longer permanently visible beside every top-level module.

## [0.2.1] - 2026-08-24
- Replaced the generic converter with a parser for Waters TargetLynx Quantify Compound Summary Reports.
- Validated the parser against the provided 29-compound / 31-injection example report.
- Added compound filtering, internal-standard detection, sample-type filtering, wide/long output, and per-compound workbook export.
- Reorganized Regression results under nested tabs.

## [0.2.0] - 2026-08-24
- Expanded the application into an analytical/clinical chemistry workbench.
- Added Quick Stats, Precision, LoB/LoD/LoQ, Linearity, Reference Interval, Interference, ROC, and initial TargetLynx conversion tools.

## [0.1.9] - 2026-08-24
- Restored stable MainWindow callback structure after the v0.1.8 startup regression.

## [0.1.8] - 2026-08-24
- Added startup crash diagnostics and `~/RegressionApp_crash.log`.

## [0.1.7] - 2026-08-24
- Added Method Comparison with Deming and Passing–Bablok regression.

## [0.1.6] - 2026-08-24
- Fixed imported X/Y column-selection dropdown behavior.

## [0.1.5] - 2026-08-24
- Added explicit Pearson r², residual Fit R², and Weighted R² reporting.
- Added origin Exclude / Include / Force handling and calculation-transparency views.

## [0.1.4] - 2026-08-24
- Added spreadsheet-style copy/paste and improved Calibrator/QC dropdown rendering.

## [0.1.3] - 2026-08-24
- Added row-level inclusion, Calibrator/QC typing, QC evaluation, and QC summaries.

## [0.1.2] - 2026-08-24
- Fixed macOS build selection of Xcode Python and modernized PySide6 build requirements.

## [0.1.1] - 2026-08-24
- Added macOS and Windows one-click build scripts and GitHub Actions desktop builds.

## [0.1.0] - 2026-08-24
- Initial PySide6 calibration/regression application.
