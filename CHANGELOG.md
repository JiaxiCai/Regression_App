# Changelog

All notable development changes to Regression App are documented here.

## [0.4.18] - 2026-08-27

### Version display consistency
- The application window title is now derived from the single `regression_app.__version__` source during direct-source reconstruction.
- Removed stale title overrides from the weighting, replicate-studies, and AMR UI patches.
- Fixes packaged builds that were functionally current but displayed older labels such as v0.4.9.
- Future version bumps no longer require editing multiple UI modules.

## [0.4.17] - 2026-08-27

### Windows validation cleanup
- Removed the redundant recursive `python*.dll` presence check from the Windows builder.
- The packaged `RegressionApp.exe --self-test` is now the authoritative runtime validation.
- This avoids false failures when PyInstaller changes the internal DLL layout while still guaranteeing that the bundled Python runtime and imports are loadable.
- EXE existence is still checked explicitly before the self-test.

## [0.4.16] - 2026-08-27

### Fixed — Windows output path validation
- Enabled delayed variable expansion so `!DIST_DIR!` resolves correctly in the Windows builder.
- PyInstaller now receives `--distpath "!DIST_DIR!"`, matching the validation and ZIP paths.
- Fixes false `RegressionApp.exe was not created` errors after otherwise successful builds.
- Keeps the locked-output fallback introduced in v0.4.15.

## [0.4.15] - 2026-08-27

### Windows rebuild reliability
- Windows builder now terminates any running `RegressionApp.exe` before replacing the packaged output.
- Retries deletion of the previous `dist` directory to allow Windows file handles and antivirus/indexing processes to release DLLs.
- If the old output remains locked, the build automatically switches to a fresh versioned `dist-v0.4.15-<id>` directory instead of failing.
- PyInstaller's `build` analysis cache is still preserved for faster incremental rebuilds.
- The final self-test, ZIP creation, and Explorer launch follow whichever output directory was actually used.

## [0.4.14] - 2026-08-27

### Direct-source packaging and build efficiency
- GitHub/local builders now reconstruct and checksum-verify the confirmed working direct `regression_app/app.py` before packaging; the executable no longer depends on the historical runtime Base64/zlib chunk loader.
- Windows and macOS builders prefer Python 3.14 and support Python 3.10–3.14.
- Local builders skip dependency installation when the build environment is healthy and the requirements files are unchanged.
- Existing virtual environments are recreated only when their Python major/minor does not match the preferred interpreter.
- PyInstaller's analysis cache is retained for faster incremental builds; only the final `dist` output is replaced.
- Broad `--collect-submodules regression_app` packaging was removed in favor of explicit application-module imports.
- GitHub Actions now builds and self-tests both Windows and macOS using Python 3.14.

## [0.4.11] - 2026-08-27

### Fixed — correct compressed GUI payload sequence
- Corrected the generated GUI loader to use chunks 00–04 followed by 06–08.
- `app_chunk_05` is a stale tail from the older compressed GUI payload and must not be inserted into the current stream.
- This addresses both prior zlib failure modes: checksum mismatch and truncated stream.
- Newer feature modules continue to load after the base GUI payload.

## [0.4.10] - 2026-08-27

### Fixed — Windows/macOS startup zlib error
- Fixed `zlib.error: incorrect data check` during packaged startup/self-test.
- Restored the generated GUI loader to the original complete compressed payload in `app_chunk_00` through `app_chunk_05`.
- Chunks 06–08 were from a later incompatible re-chunking attempt and must not be concatenated with the original payload.
- Newer features remain loaded through normal patch modules after the base GUI is reconstructed.
- GitHub Actions packaging retains explicit module discovery and packaged-app self-tests.

## [0.4.9] - 2026-08-27

### Replicate Studies — unlabeled ladder inference
- Added support for calibration-rotation studies where Sample Text does not contain "Cal" and study rows are exported as QC.
- When explicit Cal labels are absent, the parser now segments repeated nominal-concentration ladders by injection order.
- It then selects the repeated full-length ladder family, preventing shorter interleaved QC sequences from being misclassified as calibration sets.
- Verified on `20260827_16x6.csv`: six 16-level Vancomycin ladders are detected correctly while the intervening 9-level QC sequences are excluded.
- All six detected Vancomycin ladders fit successfully with the current Linear 1/x rotation model.

## [0.4.8] - 2026-08-27

### Replicate Studies — incomplete ladder handling
- Calibration rotation now uses the largest calibration-level range shared by all replicate sets instead of requiring every set to contain every nominal level observed anywhere in the study.
- This fixes Doxycycline in the milk 5×5 dataset, where blank/No Peak responses at several low calibrators caused only 2 of 6 sets to be treated as complete.
- Doxycycline now rotates all 6 sets over the common Cal 3–10 range.
- The common range must still contain at least the configured minimum number of calibrators, preserving a fair like-for-like comparison across replicate sets.

## [0.4.7] - 2026-08-27

### Calibration plot diagnostics
- Displays the fitted numerical equation directly on the Calibration plot.
- Displays Fit R² on the plot for all models.
- Weighted models also display Weighted R².
- Plot annotations update automatically after each interactive calibrator inclusion/exclusion and refit.

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
