# Changelog

All notable development changes to Regression App are documented here.

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
