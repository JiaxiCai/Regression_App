# Changelog

All notable development changes to Regression App are documented here.

## [0.1.7] - 2026-08-24

### Added
- Separate **Method Comparison** tab.
- Classical **Deming regression** with user-configurable λ = σy²/σx².
- Deming 95% slope/intercept confidence intervals via paired bootstrap.
- **Passing–Bablok (1983)** regression with shifted-median slope estimator and rank-based 95% confidence intervals.
- Identity line, Deming line, Passing–Bablok line, and paired observations on one plot.
- Spreadsheet-style paste/copy for paired method-comparison data.
- Descriptive constant- and proportional-bias flags based on whether 95% CIs contain 0 and 1.
- In-app method notes and assumptions.

## [0.1.6] - 2026-08-24

### Fixed
- Fixed the **X column** and **Y column** assignment dropdowns used after CSV/Excel import.
- Column selectors are now disabled until a file is loaded, then populated explicitly from imported headers.
- Added stable header-name mapping so the displayed dropdown labels always resolve back to the original pandas columns.
- Duplicate imported column names are disambiguated in the dropdown.
- Increased dropdown popup width so long imported headers remain visible.
- Added a load guard to prevent signal recursion while the column selectors are being repopulated.
- Restored the Calibrator/QC row dropdown behavior from v0.1.4; that control was not the affected UI element.

## [0.1.5] - 2026-08-24

### Fixed
- Corrected weighted-regression statistical reporting; earlier versions fit weighted models correctly but only reported an unweighted residual-based R².

### Added
- Pearson r², ordinary Fit R², and Weighted R² as separately labeled statistics.
- **How Calculated** tab with equations, weighting objective, R² formulas, RMSE, and back-calculation method.
- Human-readable parameter names and fitted equations.
- Origin handling options: **Exclude**, **Include**, and **Force**.
- Excel exports include Pearson r², Fit R², and Weighted R² separately.

## [0.1.4] - 2026-08-24

### Added
- Spreadsheet-style Cmd/Ctrl+V paste into the manual X/Y table.
- Multi-row, multi-column paste from Excel, Numbers, Google Sheets, or tab-delimited text.
- Cmd/Ctrl+C copy from selected cells.
- Automatic row creation for larger pasted blocks.

## [0.1.3] - 2026-08-24

### Added
- Row-level **Use** checkbox for calibrator exclusion without deletion.
- Row-level **Type** selector for Calibrator vs QC.
- Separate QC bias criterion.
- QC back-calculation and pass/fail evaluation.
- QC replicate summary with n, mean back-calculated concentration, SD, CV%, mean bias%, and all-pass status.

## [0.1.2] - 2026-08-24

### Fixed
- macOS build failure caused by Xcode's bundled Python 3.9.
- PySide6 install issue involving byte-compilation of `__init__.tmpl.py`.

### Changed
- Require Python 3.10+ for building.
- macOS builder prefers Python 3.12, 3.11, then 3.10 and refuses Xcode's bundled interpreter.
- Build installation uses `pip --no-compile`.

## [0.1.1] - 2026-08-24

### Added
- One-click macOS and Windows build scripts.
- GitHub Actions workflow for cross-platform builds.

## [0.1.0] - 2026-08-24

### Added
- Initial PySide6 desktop interface.
- Manual X/Y entry and CSV/Excel import.
- Linear, weighted linear, quadratic, weighted quadratic, Padé [1/1], and Padé [2/1] models.
- Back-calculation, bias, fit statistics, plots, contiguous AMR, and Excel export.
