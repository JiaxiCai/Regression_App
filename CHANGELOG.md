# Changelog

All notable development changes to Regression App are documented here.

## [0.4.6] - 2026-08-27

### Fixed — packaged app startup
- Fixed a macOS startup failure where the packaged executable could not import the `regression_app` package.
- Explicitly adds the project root to the PyInstaller search path and declares the app/weighting modules as hidden imports.
- Corrected the generated GUI loader to import all nine `app_chunk_00` through `app_chunk_08` modules.
- macOS builds now run the packaged executable with `--self-test` before reporting success.
- Windows packaging was hardened with the same explicit source path/import checks.
- Builders now fail early if `main.py` or the `regression_app` package is missing from the source folder.

## [0.4.5] - 2026-08-27

### Weighting transparency
- Added explicit UI definitions for unweighted, 1/x, and 1/x² regression.
- Weighted-model tooltips now show the objective function, variance assumption, SD assumption, and NumPy residual multiplier.
- Added a Weighting Definitions dialog to the regression setup.
- The How Calculated view now appends the exact weighting interpretation for the selected model.
- Clarified that UI labels refer to the statistical weight on squared residuals, while NumPy `polyfit` receives the corresponding residual multiplier.
- No numerical regression behavior changed in this release.

## [0.4.4] - 2026-08-27

### Regression workflow improvements
- Added spreadsheet-style Fill Down for Use, Type, X, and Y using Ctrl+D / Cmd+D and a Fill Down button.
- Calibration plot now supports clicking calibrator points to toggle inclusion/exclusion and immediately refit selected models.
- Excluded calibrators remain visible and can be restored by clicking again.
- Model Comparison now includes individual Cal/QC bias drill-down, including excluded-calibrator diagnostics.
- QC Summary now reports minimum and maximum % bias in addition to mean bias.
- Preserves the selected model during interactive refits.

### Efficiency
- Reuses the existing regression engine for interactive refits.
- Maintains one calibration-plot click callback and disconnects stale callbacks before re-registering.
- Preserves original input-row indices for direct UI updates.
- Removed duplicate Pearson-correlation computation.

## [0.4.3] - 2026-08-27

### Replicate Studies UI and IS recovery
- Reworked Replicate Studies views into full-size peer tabs.
- Added Levey–Jennings-style IS recovery using TargetLynx IS Area versus injection number.
- Added mean and ±1/2/3 SD lines plus IS recovery export.

## [0.4.2] - 2026-08-27

### Fixed — Replicate Studies results rendering
- Fixed `ufunc 'isfinite' not supported for the input types` after calibration rotation.
- The rotation calculations were completing successfully; the error occurred when text fields such as calibration status (`OK`) were passed through the regression-only numeric formatter.
- Replicate Studies calibration-summary and precision/bias tables now use the mixed-type-safe display formatter.

## [0.4.1] - 2026-08-27

### Fixed — Replicate Studies mapping table
- Fixed a crash during mapping-table population caused by sending sample-name text through the regression-only numeric `_fmt()` helper.
- Replicate Studies now uses a mixed-type-safe table formatter for injection number, sample name, nominal concentration, response, replicate set, and level.
- Improved mapping validation to distinguish a missing cell from a genuinely invalid Replicate Set value.
