# Regression App v0.5.23

A cross-platform PySide6 desktop workbench for analytical and clinical laboratory data analysis, with emphasis on calibration, method validation, LC-MS/MS workflows, and transparent statistical reporting.

## Current modules

### Regression / Calibration
- Spreadsheet-style manual X/Y entry and CSV/Excel import
- Calibrator vs QC typing with row-level inclusion/exclusion
- Linear, 1/x, 1/x², quadratic, weighted quadratic, Padé [1/1], and Padé [2/1] models
- Origin handling: Exclude, Include, Force
- Interactive calibrator exclusion directly from the calibration plot
- Back-calculated concentrations, individual bias, residuals, RMSE, AIC/AICc/BIC
- Signed Pearson r, Pearson r², residual-based Fit R², and Weighted R² reported separately
- Contiguous passing calibration-range screening and QC summaries
- Calibration equation and fit statistics displayed directly on the plot
- Spreadsheet-style Fill Down support
- Excel export

### Method Comparison
- Deming regression with configurable variance ratio λ
- Passing–Bablok regression
- Slope/intercept confidence intervals
- Comparison plots and supporting statistics

### Clinical Chemistry Tools
- Descriptive statistics and Shapiro–Wilk
- Precision summaries and simple variance components
- LoB / LoD / LoQ quick checks
- Linearity quick screen
- Nonparametric reference intervals with bootstrap confidence intervals
- Interference/recovery bias
- ROC analysis with AUC, Youden-optimal threshold, and ROC plot

### Replicate Studies / Calibration Rotation
- Repeated calibration-ladder workflows such as 5×5, 3×3, and larger repeated ladders
- Detects repeated ladders from TargetLynx sequence order and nominal-level resets
- Supports unlabeled repeated ladders when explicit Cal labels are absent
- Uses the largest calibration-level range shared across replicate sets
- Manual replicate-set reassignment before analysis
- Rotates each complete ladder through the calibrator role using the regression engine
- Recalculates remaining ladders from raw response
- Precision/CV and bias by level
- Calibration-set × evaluation-set mean absolute bias matrix
- Sequence-associated bias view
- Levey–Jennings-style IS recovery
- Excel export of mapping, fits, recalculated values, precision summaries, matrix, sequence trends, and IS recovery

### AMR Validation
- Exhaustive contiguous analytical measurement range screening
- Configurable calibration and QC acceptance criteria
- Supports repeated calibration-rotation datasets
- Reports the widest contiguous range meeting the configured requirements

### Surrogate Internal Standard Analysis
Systematic analyte × internal-standard benchmarking for LC-MS/MS workflows.

#### Data setup
- Supports Waters TargetLynx compound-summary reports and generic long-format datasets
- Component Mapping for Analyte, Internal Standard, or Ignore assignments
- Global regression-model and origin defaults with per-analyte overrides for multiplexed panels
- Origin handling supports Exclude, Include, or Force; analytes can independently choose any supported linear, quadratic, or Padé calibration model
- Included origin uses the lowest calibrator's reciprocal weight for 1/x and 1/x² fits, matching TargetLynx/QuanLynx behavior
- Automatic qualifier exclusion for generic TargetLynx-style exports
- Editable analyte ↔ stable-isotope-labeled internal standard assignments
- Tracks internal-standard identity separately from pair-level role
- Pair Type is reported as:
  - **Own SIL-IS** when the IS is the analyte's matched stable-isotope-labeled analog
  - **Surrogate** for every other analyte × IS combination
- QC Sample Mapping with Include/Exclude controls
- QC sample identification includes Name, ID, Sample Text, and Type
- Obvious Low IS challenge samples are auto-excluded by default but remain user-editable

#### Calibration and AMR
- Calibrator Source can use either Stage 1 or TargetLynx Primary Flags
- Stage 1 automatically establishes an analyte-only contiguous candidate calibration range
- TargetLynx Primary Flags mode skips Stage 1 and uses analyte calibrators not marked X or lowercase l as the common candidate set
- Exhaustive contiguous pair search evaluates all contiguous candidate windows and uses calibration + QC performance to select the best working range; legacy greedy search remains available
- Stage 2 iteratively fits each analyte/IS pair within the Stage-1 levels; if calibration criteria fail, the worst absolute-bias concentration level is removed and the pair is refit until it passes or reaches the minimum calibrator count
- Optional user-defined AMR import from CSV/Excel using analyte/component, LLOQ, and ULOQ columns
- User AMRs can be partial; unmatched analytes fall back to automatic Stage 1 selection
- Pair Detail shows every usable calibrator level for the pair, including levels outside the Stage 1 AMR
- Automatic Stage-2 levels start included; levels removed during iterative Stage 2 and additional usable levels outside Stage 1 remain visible unchecked and can be manually restored
- Individual calibrator nominal concentration, analyte/IS ratio, back-calculated concentration, signed bias, and absolute bias are shown
- Manual pair-specific calibrator inclusion/exclusion with immediate refitting
- Excluded calibrators remain visible in the table and plot
- **Sync AMR to Other Surrogates** applies the selected pair's calibrator pattern to all IS candidates for the same analyte
- AMR provenance is tracked as Automatic, User-defined, or Manual edited

#### QC evaluation
- QC evaluation is restricted to samples whose nominal concentration falls within the fitted AMR
- QC Individual Bias view shows each included QC replicate
- Displays nominal concentration, calculated concentration, signed/absolute bias, and individual pass/fail
- QC bias reference can be selected as:
  - **Nominal concentration**
  - **Matched SIL-IS calculated concentration**
- SIL-derived reference mode compares surrogate results against the concentration calculated from the analyte's own SIL-IS curve for the same QC sample
- Missing or unusable matched SIL-IS references are reported as unavailable rather than silently reverting to nominal
- QC CV remains grouped by nominal QC level even when SIL-derived concentrations are used as the bias reference

#### Retention time
- Preserves RT from supported input files
- Pair Ranking reports median absolute analyte–IS retention-time difference
- Pair Detail and QC Individual Bias report analyte RT, IS RT, and ΔRT when available

#### Pair Ranking and visualization
- Pair-level summary includes calibration pass, QC pass, overall pass, AMR, calibrator bias, Fit R², QC bias/CV, RT metrics, and Pair Type
- Generic two-dropdown filtering:
  - choose any ranking column
  - choose one of its available values
- Ranking columns can be reordered by dragging the header and shown/hidden from the Columns menu
- Example: **Pair Type → Surrogate** displays all analyte–surrogate combinations
- Heatmaps can display R², calibration bias, QC bias, QC CV, AMR, retained-level, and Stage-2 iteration metrics
- Optional cell-value annotations
- Direct PNG and SVG heatmap export
- Full ranking remains available for export while the UI renders only the filtered subset for improved stability
- Pair Detail plot and calibrator table are displayed side-by-side

#### Performance
- Bulk analysis stores compact pair summaries instead of full fit/QC objects for every pair
- Detailed pair information is reconstructed on demand
- Calibration, QC, and RT wide tables are aligned once and cached as NumPy arrays
- Bulk QC metrics use lightweight NumPy calculations instead of thousands of DataFrame/groupby operations
- Pair Ranking renders only the filtered subset instead of thousands of Qt rows at once
- Linear back-calculation is vectorized algebraically

### TargetLynx Converter
- Parses Waters TargetLynx Quantify Compound Summary Reports as repeated compound blocks
- Compound and sample-type filtering
- Detects analytes and isotope-labeled internal standards
- Multi-select TargetLynx metadata and measurement/result columns
- Preserves numeric data types while retaining values such as `<LLOQ` and `No Peak` as text
- Wide, long/tidy, and one-worksheet-per-compound Excel outputs

### Project sessions
- Save and reopen portable `.regproj` analysis projects
- Project files embed normalized source data and versioned analysis settings rather than unsafe Python pickle objects
- Surrogate IS projects currently restore component/QC mappings, user AMRs, acceptance criteria, calibrator source, manual pair edits, ranking layout/filter state, selected pair, and heatmap settings
- Completed analyses are reconstructed from saved state when reopened so calculations remain compatible with the current application code
- The project format is designed for additional Regression App modules to adopt progressively

## Statistical transparency

Regression App deliberately distinguishes Pearson r, Pearson r², ordinary residual-based Fit R², and Weighted R². Calibration models should not be selected from R² alone; back-calculated calibrator bias, QC performance, validated range, and model complexity should also be considered.

### Weighting conventions

- **None:** objective Σe²; constant variance; NumPy residual multiplier 1
- **1/x:** objective Σ(e²/x); σ² ∝ x; σ ∝ √x; NumPy residual multiplier 1/√x
- **1/x²:** objective Σ(e²/x²); σ² ∝ x²; σ ∝ x; approximately constant relative SD/%CV; NumPy residual multiplier 1/x

These labels describe the statistical weight applied to squared residuals. NumPy `polyfit` receives the square-root residual multiplier required to produce the intended objective.

## Build workflow

- macOS: `Build Regression App - macOS.command`
- Windows: `Build Regression App - Windows.bat`
- GitHub Actions: `.github/workflows/build-desktop.yml`

Current desktop builds use Python 3.14. Local builders support Python 3.10–3.14, prefer Python 3.14 when available, cache reusable build state, and invalidate PyInstaller analysis when the application version changes.

The repository uses build-time reconstruction of the verified direct `regression_app/app.py` source. Packaged applications do not depend on the historical runtime Base64/zlib loader.

GitHub Actions builds both Windows and macOS distributions and runs packaged-app self-tests before artifacts are uploaded.

### Windows distribution

Download the `RegressionApp-Windows` artifact, extract the outer artifact ZIP and then `RegressionApp-Windows.zip`, and run `RegressionApp.exe` from the complete extracted `RegressionApp` folder.

## Validation status

Regression App is research software and has not been validated for clinical use. Clinical-tool modules are quick-check implementations and are not complete reproductions of all CLSI requirements.

Results intended for regulated or clinical use should be verified against independent reference implementations, known datasets, and the laboratory's applicable validation procedures.

## Version history

See [CHANGELOG.md](CHANGELOG.md) for detailed release history.
