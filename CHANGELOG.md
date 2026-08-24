# Changelog

All notable development changes to Regression App are documented here.

## [0.2.0] - 2026-08-24

### Added
- Clinical chemistry toolbox: descriptive statistics, Shapiro–Wilk, precision summaries and simple variance components, LoB/LoD/LoQ, quick linearity screening, reference intervals, interference/recovery, and ROC analysis.
- TargetLynx converter with CSV/TXT/Excel import, automatic and manual Sample/Analyte/Value mapping, tidy long conversion, one-analyte-per-sheet 1D export, and sample × analyte wide export.
- Method comparison module retained with Deming and Passing–Bablok regression.
- Calibration module retained with linear, weighted linear, quadratic, weighted quadratic, Padé, QC evaluation, origin handling, spreadsheet paste, and transparent fit statistics.

### Changed
- Application metadata updated to v0.2.0.
- macOS, Windows, and GitHub Actions packaging explicitly collect method-comparison, clinical-tool, TargetLynx, SciPy, and Matplotlib dependencies.
- Documentation reorganized around the all-in-one clinical chemistry workbench scope.

### Scope
- Clinical modules are quick-check implementations and are not yet complete reproductions of every CLSI workflow/decision rule.
- TargetLynx export layouts vary; mappings should be checked against representative assay exports.

## [0.1.9] - 2026-08-24
- Fixed startup crash caused by Method Comparison callbacks being inserted at the wrong class indentation level.
- Added structural callback validation before packaging.

## [0.1.8] - 2026-08-24
- Added startup crash logging and visible startup-error diagnostics.
- Strengthened standalone packaging for method-comparison/SciPy dependencies.

## [0.1.7] - 2026-08-24
- Added separate Method Comparison tab with Deming and Passing–Bablok regression, confidence intervals, and identity-line visualization.

## [0.1.6] - 2026-08-24
- Fixed imported X/Y column assignment dropdowns and stable header mapping.

## [0.1.5] - 2026-08-24
- Added Pearson r², Fit R², and Weighted R² as separate statistics.
- Added How Calculated explanations and Exclude/Include/Force origin options.

## [0.1.4] - 2026-08-24
- Added spreadsheet-style copy/paste for manual X/Y entry.

## [0.1.3] - 2026-08-24
- Added calibrator/QC row typing, row inclusion controls, QC back-calculation, and QC replicate summaries.

## [0.1.2] - 2026-08-24
- Fixed macOS build environment selection and PySide6 installation issues; rejected Xcode Python 3.9 and required Python 3.10+.

## [0.1.1] - 2026-08-24
- Added standalone macOS/Windows build scripts and GitHub Actions workflow.

## [0.1.0] - 2026-08-24
- Initial PySide6 desktop interface with manual/file X/Y input and linear, weighted linear, quadratic, weighted quadratic, and Padé calibration models.
