# Changelog

All notable development changes to Regression App are documented here.

## [0.1.5] - 2026-08-24

### Fixed
- Replaced the unreliable embedded Type combo-box widgets with a delegate-based editor. `Calibrator` / `QC` is now always rendered as normal cell text; clicking the cell opens the dropdown.
- Corrected the statistical reporting for weighted regressions. Earlier versions fit weighted models correctly but reported only an unweighted residual-based R².

### Added
- Three explicitly labeled linearity/goodness-of-fit statistics:
  - Pearson r² = corr(x,y)²
  - ordinary residual-based Fit R²
  - weighted residual-based Weighted R²
- **How Calculated** tab describing the equation, weighting objective, R² formulas, RMSE, and back-calculation method for the selected model.
- Human-readable parameter names and fitted equation in the Parameters tab.
- Origin handling options:
  - **Exclude** origin
  - **Include** synthetic (0,0) as a regression point
  - **Force** curve through (0,0)
- Origin handling is applied to linear, quadratic, and Padé models.
- Excel exports now include Pearson r², Fit R², and Weighted R² separately.

### Note
- For `Include` with 1/x or 1/x² weighting, reciprocal weighting is undefined at x=0. v0.1.5 transparently assigns the synthetic origin unit weight and applies reciprocal weights to non-zero calibrators. This convention is documented in the app and may not exactly reproduce every vendor implementation.

## [0.1.4] - 2026-08-24

### Fixed
- Fixed the manual-entry **Type** dropdown rendering blank on some macOS configurations.
- Increased row height and dropdown sizing so `Calibrator` / `QC` remain visible.

### Added
- Spreadsheet-style **Cmd/Ctrl+V paste** into the manual X/Y table.
- Multi-row, multi-column paste directly from Excel, Numbers, Google Sheets, or tab-delimited text.
- **Cmd/Ctrl+C copy** from selected table cells.
- Pasting automatically adds rows when the pasted block is larger than the current table.
- If paste focus is on the Use/Type columns, pasted numeric data is redirected to `X nominal` to avoid overwriting row controls.

## [0.1.3] - 2026-08-24

### Added
- Row-level **Use** checkbox so individual points can be excluded from fitting without deleting them.
- Row-level **Type** selector for Calibrator vs QC.
- Separate QC bias acceptance criterion.
- QC back-calculation and pass/fail evaluation for every fitted model.
- QC replicate summary grouped by nominal concentration with n, mean back-calculated concentration, SD, CV%, mean bias%, and all-pass status.
- QC points displayed separately on the calibration plot.
- Calibrator and QC results exported together while preserving point type.

### Changed
- Manual and imported rows now default to included Calibrators for fast entry.
- Model fitting uses only included Calibrator rows.
- QC rows are evaluated against the fitted calibration curve and never influence the fit.

## [0.1.2] - 2026-08-24

### Fixed
- macOS build failure caused by the builder selecting Xcode's bundled Python 3.9.
- PySide6 installation failure involving byte-compilation of `__init__.tmpl.py`.

### Changed
- Require Python 3.10 or newer for building the desktop application.
- macOS builder now prefers Python 3.12, 3.11, then 3.10 and refuses Xcode's bundled interpreter.
- Build dependency installation now uses `pip --no-compile`.
- Added `.gitignore` and dedicated troubleshooting documentation.

## [0.1.1] - 2026-08-24

### Added
- One-click macOS build script producing `RegressionApp.app` and a shareable ZIP.
- One-click Windows build script producing `RegressionApp.exe` and a shareable ZIP.
- GitHub Actions workflow for cross-platform desktop builds.
- Collaborator-focused distribution instructions.

## [0.1.0] - 2026-08-24

### Added
- Initial PySide6 desktop interface.
- Manual X/Y data entry.
- CSV and Excel import with selectable X/Y columns.
- Linear, weighted linear (1/x, 1/x²), quadratic, weighted quadratic (1/x, 1/x²), Padé [1/1], and Padé [2/1] regression models.
- Back-calculated concentrations and calibration bias.
- R², adjusted R², RMSE, AIC, AICc, and BIC summaries.
- User-configurable calibration bias limit and minimum passing point count.
- Widest contiguous passing calibration range calculation.
- Calibration and residual plots.
- Excel results export.
