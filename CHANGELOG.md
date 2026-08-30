# Changelog

All notable development changes to Regression App are documented here.

## [0.5.8] - 2026-08-29

### Pair Detail layout
- Reworked Surrogate IS Pair Detail into a side-by-side layout.
- Calibration plot and toolbar are shown on the left.
- Individual calibrator table and manual Include controls are shown on the right.
- Removed the fixed-height calibrator table so both views can use the available vertical space more effectively.

## [0.5.7] - 2026-08-29

### Surrogate IS user-defined AMR and calibrator editing
- Added optional user-defined AMR import from CSV/Excel using analyte/component, LLOQ, and ULOQ columns with flexible header recognition.
- User-defined AMRs override automatic Stage-1 AMR discovery only for matching analytes; unmatched analytes continue to use automatic AMR selection.
- Pair Ranking and Pair Detail now report AMR Source as Automatic, User-defined, or Manual edited.
- Added an individual calibrator table to Pair Detail with nominal concentration, analyte/IS ratio, back-calculated concentration, signed bias, and absolute bias.
- Added pair-specific calibrator Include controls; unchecking a calibrator immediately refits that analyte × IS pair and refreshes calibration/QC metrics.
- Manual exclusions never change the AMR or calibrator set used by other IS candidates for the same analyte.
- Prevents manual editing below the configured minimum calibrator count.
- Excluded calibrators remain visible in the Pair Detail table and plot for auditability.

## [0.5.6] - 2026-08-29

### Surrogate IS QC sample mapping and individual bias drill-down
- Added a QC Sample Mapping tab with one Include/Exclude control per detected QC sample.
- Calibration fitting is unaffected by QC exclusions; unchecked samples are omitted only from QC bias, precision, pass/fail, and ranking calculations.
- QC sample names containing `Low IS` are conservatively auto-excluded, while all assignments remain visible and user-editable.
- Added Reset to Automatic, Include All, and Exclude All controls for QC sample selection.
- Added a QC Individual Bias tab that updates with the selected analyte × IS pair.
- Individual QC output includes sample key/name, nominal concentration, analyte/IS ratio, calculated concentration, signed bias, absolute bias, and individual pass/fail against the configured QC individual-bias limit.
- Pair-level QC summaries and Excel export continue to use only the currently included QC samples.

## [0.5.5] - 2026-08-27

### Surrogate IS performance and safer auto-mapping
- Linear regression back-calculation is now vectorized algebraically instead of invoking the generic polynomial root solver for each value.
- This substantially reduces CPU cost for large surrogate-IS pair matrices and other linear-model workflows.
- Generic long-format component mapping now defaults Quantifiers to Analyte, Internal Standards to IS, and Qualifiers to Ignore.
- Automatically ignored qualifier transitions remain visible in Component Mapping and can be enabled manually.
- Components mapped to Ignore start excluded from the current benchmark.
- Added a confirmation warning before running more than 2,000 analyte × IS pairs.
- Verified the computational shape of `20260110_Round4_Input.csv`: 75 quantifiers, 84 qualifiers, 68 internal standards; the safer default is 75 × 68 = 5,100 pairs rather than 159 × 68 = 10,812.

## [0.5.4] - 2026-08-27

### Surrogate IS component mapping and pair selection
- Added a visible Component Mapping setup tab before surrogate-IS analysis.
- Automatic analyte/internal-standard recognition remains enabled and is shown explicitly for every detected component.
- Users can override each component as Analyte, Internal Standard, or Ignore.
- Added an independent Include toggle so components can be excluded from the current benchmark without changing their assigned role.
- Added Reset to Automatic, Include All, and Exclude All controls.
- Displays the estimated analyte × IS pair count before analysis, making unexpectedly large benchmark matrices visible before execution.
- Surrogate analysis now runs only the user-selected analytes and internal standards.

## [0.5.3] - 2026-08-27

### Surrogate IS scalability
- Bulk surrogate-IS analysis now stores only compact pair summary metrics instead of full fit objects and QC sample DataFrames for every analyte × IS pair.
- Pair Detail is reconstructed on demand only for the currently selected analyte/IS combination.
- Workbook export regenerates detailed QC rows one pair at a time and writes them incrementally, avoiding a large in-memory concatenation.
- Retains the same calibration-range, fit, QC bias, and QC precision criteria while substantially reducing memory growth for large pair matrices.

## [0.5.2] - 2026-08-27

### Packaging cache reliability
- Local builders now associate the PyInstaller analysis cache with the application version.
- When the app version changes, only `build/RegressionApp` is invalidated so newly added modules cannot be omitted by a stale import graph.
- Rebuilding the same version still reuses the PyInstaller analysis cache for speed.
- Explicitly packages the `regression_app` package root and shared `ui_helpers` module in Windows, macOS, and GitHub Actions builds.
- Updated stale macOS and Windows output/version labels to the current release.
- Keeps the packaged executable self-test as the final distribution gate.

## [0.5.0] - 2026-08-27

### Surrogate Internal Standard Analysis
- Added a new Surrogate IS Analysis workspace for systematic analyte × internal-standard benchmarking.
- Supports Waters TargetLynx compound-summary reports and the generic long-format data structure used by the original surrogate-IS scripts.
- Stage 1 performs analyte-only contiguous calibration-range selection using the app's existing regression engine and conventional statistical weighting definitions.
- Stage 2 evaluates every analyte/IS area-ratio calibration on the Stage 1 concentration levels.
- Independent QC samples are back-calculated for each pair and summarized by mean absolute bias, maximum absolute bias, and maximum CV.
- Added configurable acceptance criteria for calibrator bias, Fit R², QC bias, QC individual bias, QC CV, and minimum calibrator count.
- Added Pair Ranking, analyte × IS heatmap, Pair Detail, Stage 1 diagnostics, and Excel export.
- Pair ranking exposes underlying metrics rather than using an opaque composite score.
- Default model is Linear 1/x with contiguous-range selection; Linear and Linear 1/x² are also available.

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
