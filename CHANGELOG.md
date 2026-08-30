# Changelog

All notable development changes to Regression App are documented here.

## [0.5.32] - 2026-08-30

### More robust Surrogate IS workbook export
- Surrogate IS Excel export now writes the full workbook to a local temporary `.xlsx` file first, closes it, and then moves the completed workbook to the user-selected destination.
- This avoids keeping a long-lived open Excel file handle on cloud-synced/network destinations and reduces low-level file descriptor failures such as `[Errno 9] Bad file descriptor`.
- Export failures now include an expandable full Python traceback in the error dialog so data-specific or filesystem-specific failures can be diagnosed precisely.

## [0.5.31] - 2026-08-30

### Automatic matched-SIL dependency refresh
- When QC reference is `Matched SIL-IS calculated concentration`, manually editing an analyte's matched SIL-IS calibration curve now triggers recalculation of all analyte–IS pairs for that analyte.
- Each surrogate retains its own current calibrator selection/range; only the dependent QC reference concentrations, QC bias metrics, QC pass/fail, overall pass/fail, and ranking/heatmap values are refreshed.
- The edited matched SIL-IS pair itself is recomputed first, then its updated calculated QC concentrations become the shared reference for all surrogate comparisons.
- Pair Ranking and Heatmap are refreshed immediately so they remain consistent with Pair Detail after a matched SIL-IS edit.

## [0.5.30] - 2026-08-30

### Surrogate heatmap pandas import fix
- Fixed the remaining `name 'pd' is not defined` error by moving `import pandas as pd` to module scope in `surrogate_is_ui_patch.py`.
- Removed the heatmap's `pd.DataFrame()` fallback dependency and verified the final `main` source contains the top-level pandas import.

## [0.5.29] - 2026-08-30

### Heatmap import fix
- Fixed `name 'pd' is not defined` when drawing Surrogate IS heatmaps.
- Added the missing pandas import required by the pair-status masking code introduced in v0.5.28.

## [0.5.28] - 2026-08-30

### Robust heatmap masking
- Replaced failed-pair rectangle overlays with an aligned boolean status mask rendered directly by Matplotlib.
- When `Grey out failed pairs` is enabled, pairs with final `Pass = False` are masked and rendered grey by the heatmap colormap itself.
- Missing/unavailable metric values are always rendered grey instead of appearing as unexplained white/transparent cells.
- When value annotations are enabled, unavailable cells are labeled `N/A`.
- Passing cells retain the normal metric color scale and colorbar.

## [0.5.27] - 2026-08-30

### Matched SIL-IS reference range policy
- Added a `Matched SIL range` option when QC reference is `Matched SIL-IS calculated concentration`.
- `Allow extrapolation` (default) uses the matched SIL-IS regression equation for QC concentrations outside the matched SIL-IS retained AMR, preserving the assumption that the matched SIL-IS remains the best correction reference across concentrations.
- `Restrict to matched SIL-IS AMR` calculates matched-SIL bias only for QC levels inside both the surrogate AMR and matched SIL-IS AMR; out-of-reference-range levels are excluded from matched-SIL bias/CV acceptance calculations rather than extrapolated.
- The selected policy is applied consistently during exhaustive contiguous pair search, final ranking metrics, and Pair Detail recalculation.
- Pair Ranking records the matched-SIL range policy, and project files preserve the selected option.

## [0.5.26] - 2026-08-30

### Heatmap layout, failed-pair rendering, and matched-SIL reference consistency
- Reworked the Surrogate IS Heatmap tab into a narrow control panel on the left and a larger plot panel on the right to reduce vertical compression.
- Increased the heatmap figure's default working size for improved readability.
- Replaced the prior RGBA failed-pair rendering path with explicit grey cell overlays, fixing cases where `Grey out failed pairs` did not visibly change the heatmap.
- Failed cells retain their underlying metric values and optional annotations; the colorbar continues to describe the original metric scale.
- Corrected matched SIL-IS reference handling so one canonical matched-SIL curve is selected per analyte and reused as the analyte's own SIL-IS pair when matched-SIL reference mode is active.
- The matched-SIL reference curve's range is selected using calibration criteria plus its QC performance against nominal concentrations; its calculated QC concentrations then serve as the reference for surrogate pairs.
- For an analyte paired with its own matched SIL-IS, calculated concentration and matched-SIL reference concentration are now identical by construction, so QC bias versus matched SIL-IS is exactly zero. QC precision remains independently measurable.

## [0.5.25] - 2026-08-30

### Heatmap failed-pair de-emphasis
- Added a `Grey out failed pairs` option to Surrogate IS heatmaps.
- When enabled, analyte–IS pairs whose final `Pass` status is false are rendered in grey while passing pairs retain the selected metric's heatmap scale.
- Metric values remain unchanged and optional cell annotations are still shown for failed pairs.
- The heatmap colorbar continues to represent the metric scale for passing cells.
- Saved Surrogate IS projects preserve the grey-out setting.

## [0.5.24] - 2026-08-30

### Retention-time ordered surrogate heatmaps
- Heatmap rows (analytes) and columns (internal standards) now default to independent ascending retention-time order.
- Ordering uses the median calibrator RT retained from the input data.
- Components without a finite RT are placed after RT-resolved components and ordered alphabetically.
- Added a heatmap Order selector with `Retention time` and `Alphabetical` options.
- Saved Surrogate IS projects now preserve the selected heatmap ordering mode.

## [0.5.23] - 2026-08-30

### Exhaustive contiguous surrogate-curve search
- Added a Pair Search selector with `Exhaustive contiguous` (new default) and legacy `Greedy` modes.
- Exhaustive mode evaluates every contiguous calibration window within the analyte's allowed starting calibrators instead of repeatedly removing only the current worst-bias level.
- Candidate windows must satisfy the configured calibration criteria; QC bias and precision are then evaluated for the same candidate window.
- Search ranking first prefers windows passing both calibration and QC criteria, then prefers the widest concentration span and more retained calibrator levels; QC CV/bias and calibration quality act as tie-breakers.
- This avoids local-optimum failures where the greedy algorithm reaches an acceptable but substantially poorer surrogate curve.
- Verified on the supplied urine dataset for Penicillin G / Piperacillin-D5: Cal 3-9 is a valid strong contiguous solution under 0.995 Fit R², 15% calibrator absolute bias, 20% QC absolute bias, and 10% QC CV.
- Exhaustive search respects the selected calibrator source. TargetLynx Primary Flags exclusions remain hard starting exclusions unless the user manually re-includes a level.
- Pair Ranking now records the Pair Search mode, and project files preserve the selected search strategy.

## [0.5.22] - 2026-08-30

### TargetLynx-compatible Include Origin weighting
- Corrected reciprocal-weighted Include Origin behavior.
- For 1/x and 1/x² fits, the synthetic (0,0) origin now receives the same weight as the lowest non-zero calibration standard, matching documented TargetLynx/QuanLynx behavior.
- Previously the included origin received a fixed unit weight, which could over-weight the origin and increase low-end back-calculated bias.
- Verified against the Amoxicillin / Amoxicillin-D4 Cal 3–10 example: Cal 3 changes from about -19% bias with the old implementation to about -12.05%, matching the TargetLynx result of -12.0%.

## [0.5.21] - 2026-08-30

### Analyte Fit Settings population fix
- Fixed a v0.5.20 UI regression where the Analyte Fit Settings tab could remain empty after loading a surrogate-IS dataset.
- Normal dataset loading now explicitly populates the analyte fit table after Component Mapping is built.
- Analyte Fit Settings now refresh automatically when component Include status or Role changes.
- Existing per-analyte model/origin overrides are preserved for analytes that remain selected during mapping edits.

## [0.5.20] - 2026-08-30

### Per-analyte regression model and origin handling
- Added a global Origin Handling selector to Surrogate IS Analysis with Exclude, Include, and Force options.
- Exclude estimates a free intercept without adding an origin point; Include adds a synthetic (0,0) point; Force constrains the fitted curve through zero.
- Added an Analyte Fit Settings tab where each analyte can independently inherit the global defaults or override its regression model and origin handling.
- Per-analyte settings are applied consistently to automatic Stage 1 fitting, user-defined AMR fitting, TargetLynx Primary Flags candidate sets, iterative Stage 2 analyte/IS fitting, matched SIL-IS reference fitting, Pair Detail reconstruction, and manual pair refits.
- Expanded Surrogate IS regression choices to the regression engine's current calibration models: Linear, Linear 1/x, Linear 1/x², Quadratic, Quadratic 1/x, Quadratic 1/x², Padé [1/1], and Padé [2/1].
- Pair Ranking and Stage 1 output now report the regression model and origin handling used for each analyte.
- Surrogate IS project files now preserve both global origin handling and analyte-specific model/origin overrides.

## [0.5.19] - 2026-08-30

### Project save/open framework
- Added a portable versioned `.regproj` project format for saving analysis sessions.
- Project archives store JSON/table data only; no Python pickle/code objects are serialized.
- Project files embed normalized input data so reopening does not depend on the original CSV/TargetLynx file remaining at the same path.
- Added Save Project and Open Project controls to Surrogate IS Analysis.
- Surrogate IS projects preserve component mapping, QC sample mapping, user-defined AMRs, regression/QC criteria, calibrator-source mode, manual pair calibrator exclusions, ranking filters, visible/hidden columns, ranking column order, selected pair, heatmap metric, and heatmap annotation state.
- When a completed project is reopened, the analysis is reconstructed from the saved inputs/settings and manual pair edits are reapplied rather than restoring stale serialized fit objects.
- Project manifests include schema version and originating app version for forward-compatible evolution.
- The project I/O layer is module-agnostic so additional Regression App workspaces can adopt the same `.regproj` format in future releases.

## [0.5.18] - 2026-08-29

### Heatmap metric selection, annotations, and export
- Expanded Pair Ranking summary metrics with minimum/maximum signed calibrator bias, minimum absolute calibrator bias, minimum/mean/maximum QC CV, and minimum/maximum signed/absolute QC bias.
- Heatmap value selector now supports Fit R², Weighted R², calibration bias metrics, QC bias metrics, QC CV metrics, LLOQ, ULOQ, span ratio, retained calibrator count, QC level count, and Stage 2 iteration/removal counts.
- Added an Annotate values checkbox to display cell values directly on the heatmap.
- Annotation formatting adapts to R², percentages, counts, and general numeric metrics.
- Added direct PNG and SVG heatmap export buttons.
- Export filenames are generated from the selected metric and preserve the current annotation state.

## [0.5.17] - 2026-08-29

### TargetLynx Primary Flags calibrator-source mode
- Preserves the TargetLynx `Primary Flags` field during surrogate-data normalization.
- Added a Calibrator Source selector with `Stage 1` and `TargetLynx Primary Flags` modes.
- In TargetLynx Primary Flags mode, Stage 1 candidate-range selection is bypassed.
- For each analyte, calibrators marked with `X` or lowercase `l` in Primary Flags are treated as excluded; the remaining analyte calibrator levels become the common starting set for all analyte × IS pair fits.
- Iterative Stage 2 fitting still operates from that TargetLynx-defined starting set and can remove additional worst-bias levels as required by the configured calibration criteria.
- Pair Detail continues to expose excluded/unused calibrators for manual re-inclusion or removal.
- Generic long-format imports also preserve Primary Flag/Primary Flags columns when present.
- The load summary reports how many rows contain TargetLynx X/l Primary Flags.

## [0.5.16] - 2026-08-29

### Pair Ranking column customization
- Removed the redundant `Matched SIL-IS` column from Pair Ranking; `Pair Type` already distinguishes Own SIL-IS from Surrogate.
- Pair Ranking columns can now be reordered by dragging the table header.
- Added a Columns menu to show or hide individual ranking fields.
- Added Show All to restore all columns.
- Column visibility and visual order persist during the current app session and survive ranking refreshes/manual refits.
- Filtering and workbook export continue to use the complete underlying ranking dataset regardless of visible columns.

## [0.5.15] - 2026-08-29

### Iterative Stage 2 analyte–IS fitting
- Restored the original greedy iterative analyte/IS fitting concept within the app's two-stage surrogate workflow.
- Stage 1 continues to establish the common analyte-level candidate range.
- For each analyte × IS pair, Stage 2 now starts with all usable Stage-1 levels, fits the configured calibration model, evaluates calibrator bias and Fit R², removes the concentration level containing the worst absolute-bias calibrator when the fit fails, and repeats.
- Iteration stops when the configured calibration criteria pass, the minimum calibrator-level count is reached, or the iteration limit is reached.
- Stage 2 exclusions are stored independently for every analyte × IS pair.
- Pair Ranking reports Stage 2 iteration count and number of automatically removed levels; AMR Source is labeled Stage 2 iterative when trimming occurred.
- Pair Detail starts from the resulting automatic Stage-2 level set while still displaying removed Stage-2 levels and usable out-of-Stage-1 levels unchecked for manual re-inclusion.
- Manual calibrator edits continue to override the automatic pair selection and can expand or shrink the pair AMR.
- AMR synchronization copies the effective current calibrator pattern, including automatic Stage-2 removals and manual changes.
- Matched SIL-IS QC reference calculations use the matched SIL pair's own effective calibration levels.

## [0.5.14] - 2026-08-29

### Manual AMR expansion beyond Stage 1
- Pair Detail now shows every usable calibrator level for the selected analyte × IS pair, not only levels retained by Stage 1.
- Stage 1 levels are checked by default; usable levels outside Stage 1 are visible unchecked.
- Users can manually check additional calibrators to expand a pair's AMR, or uncheck existing levels to shrink it.
- Any checkbox edit creates an explicit pair-specific manual calibrator set and immediately refits calibration and QC metrics.
- Manual AMR synchronization now copies the effective current calibrator pattern, including manually added levels outside Stage 1.
- Pair ranking continues to label edited ranges as Manual edited.

## [0.5.13] - 2026-08-29

### Generic Pair Ranking filters
- Replaced the analyte-only Pair Ranking selector with two dropdowns: Filter Column and Value.
- Filter Column can use any Pair Ranking field, including Analyte, Internal Standard, Pair Type, Pass, QC Reference, AMR Source, and RT metrics.
- Value is populated dynamically from the unique values available in the selected column.
- Added an All/Clear state to restore the complete ranking view.
- Supports pair-level views such as Pair Type = Surrogate to display all analyte–surrogate combinations across the dataset.
- Retains the full ranking in memory while only rendering the filtered subset in Qt for scalability.

## [0.5.12] - 2026-08-29

### Pair-level SIL-IS versus surrogate classification
- Pair Ranking now classifies each analyte × IS combination by its role for that analyte.
- Pair Type is `Own SIL-IS` only when the selected internal standard is the analyte's matched isotope-labeled analog.
- Every non-matched analyte × IS combination is classified as `Surrogate`, including SIL-labeled standards that belong to a different analyte.
- Retains intrinsic IS identity and paired-analyte metadata separately for traceability.
- Pair Detail now reports the pair-level classification rather than the intrinsic IS classification.

## [0.5.11] - 2026-08-29

### Surrogate IS performance and stability
- Reduced bulk-analysis temporary object creation by converting aligned calibration, QC, and RT wide tables to NumPy arrays once before analyte × IS iteration.
- Replaced per-pair pandas QC DataFrame/groupby work in the bulk ranking path with lightweight NumPy QC metrics.
- Preserves detailed pandas QC tables only for on-demand Pair Detail and export.
- Aligns area, nominal, RT, and metadata tables once before NumPy caching so speed improvements do not change sample matching.
- Pair Ranking now renders one analyte at a time instead of materializing thousands of Qt table rows and >100,000 QTableWidgetItems at once.
- Added an analyte selector and displayed/total pair count; the complete ranking remains available in memory, heatmaps, and workbook export.
- Manual refits and AMR synchronization refresh only the currently displayed analyte ranking.
- Corrected SIL-reference QC precision handling: QC bias can use the matched SIL-derived reference while QC CV remains grouped by nominal QC level.

## [0.5.10] - 2026-08-29

### Surrogate IS retention time, SIL classification, and QC reference basis
- Preserves retention time (RT) from TargetLynx and generic long-format input when available.
- Pair Ranking now tracks internal-standard class, paired analyte, whether the pair is the matched SIL-IS, and median absolute analyte–IS retention-time difference.
- Pair Detail and QC Individual Bias include analyte RT, IS RT, and ΔRT for individual observations when RT is available.
- Component Mapping now allows each internal standard to be classified as SIL-IS or Surrogate and assigned to a paired analyte.
- Stable-isotope naming patterns such as D3, 13C, 15N, 18O, and 34S are used to propose SIL-IS pairings automatically; assignments remain editable.
- Added a QC reference selector with Nominal concentration and Matched SIL-IS calculated concentration options.
- When matched SIL-IS reference is selected, surrogate QC bias is calculated against the concentration obtained from the analyte's paired SIL-IS calibration curve for the same QC sample.
- Missing/unusable matched SIL-IS references are reported as unavailable rather than silently falling back to nominal concentration.
- Manual pair refits and AMR synchronization preserve the selected QC reference basis.

## [0.5.9] - 2026-08-29

### Surrogate IS AMR synchronization and richer QC identification
- Added a Pair Detail button to synchronize the selected pair's current manual calibrator inclusion/exclusion pattern across all surrogate IS candidates for the same analyte.
- AMR synchronization refits each affected analyte × IS pair and refreshes calibration, QC, ranking, and heatmap metrics.
- Existing pair-specific manual exclusions on target surrogate fits are replaced by the synchronized calibrator pattern.
- Preserved original sample metadata fields through surrogate-data normalization: Name, ID, Sample Text, and Type.
- Expanded QC Sample Mapping to show Include, Name, ID, Sample Text, Type, automatic inclusion, and Sample Key.
- Expanded QC Individual Bias output to show Name, ID, Sample Text, and Type alongside nominal concentration, analyte/IS ratio, calculated concentration, signed bias, absolute bias, and individual pass/fail.

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
