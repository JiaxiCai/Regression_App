# Regression App v0.4.5

A cross-platform PySide6 desktop workbench for analytical and clinical laboratory data.

## Current modules

### Regression / calibration
- Manual spreadsheet-style X/Y entry and CSV/Excel import
- Calibrator vs QC typing and row-level inclusion/exclusion
- Linear, 1/x, 1/x², quadratic, weighted quadratic, Padé [1/1], and Padé [2/1]
- Origin handling: Exclude, Include, Force
- Back-calculated concentrations, bias, residuals, RMSE, AIC/AICc/BIC
- Signed Pearson r, Pearson r², residual-based Fit R², and Weighted R² reported separately
- Contiguous passing calibration-range screen and QC summaries
- Excel export
- Explicit weighting definitions for none, 1/x, and 1/x², including objective function, variance/SD assumptions, and NumPy residual multiplier

### Method comparison
- Deming regression with configurable variance ratio λ
- Passing–Bablok regression
- Slope/intercept confidence intervals and comparison plot

### Clinical tools
- Descriptive statistics and Shapiro–Wilk
- Precision summaries and simple variance components
- LoB / LoD / LoQ quick checks
- Linearity quick screen
- Nonparametric reference intervals with bootstrap confidence intervals
- Interference/recovery bias
- ROC analysis with AUC, Youden-optimal threshold, and ROC plot

### Replicate Studies
- Repeated calibration-ladder workflows such as 5×5 and 3×3
- Detects repeated ladders from TargetLynx sequence order and nominal-level resets
- Manual replicate-set reassignment before analysis
- Rotates each complete ladder through the calibrator role using the existing regression engine
- Recalculates all remaining ladders from raw Response
- Precision/CV and bias by level
- Calibration-set × evaluation-set mean absolute bias matrix
- Sequence-associated bias view
- Levey–Jennings-style IS recovery view
- Excel export of mapping, fits, recalculated values, precision summaries, matrix, sequence trends, and IS recovery

### TargetLynx converter
- Parses Waters TargetLynx Quantify Compound Summary Reports as repeated compound blocks
- Compound and sample-type filtering
- Detects analytes vs isotope-labeled internal standards
- Multi-select TargetLynx metadata and measurement/result columns
- Wide, long/tidy, and one-worksheet-per-compound Excel outputs

## Build workflow

- macOS: `Build Regression App - macOS.command`
- Windows: `Build Regression App - Windows.bat`
- GitHub Actions: `.github/workflows/build-desktop.yml`

The Windows distribution is `RegressionApp-Windows.zip`. Extract the entire `RegressionApp` folder before launching `RegressionApp.exe`.

## Statistical transparency

The application deliberately distinguishes Pearson r, Pearson r², ordinary residual-based Fit R², and Weighted R². Calibration models should not be selected from R² alone; back-calculated calibrator bias, QC performance, validated range, and model complexity should also be considered.

### Weighting conventions

The Regression UI now makes the statistical meaning of each weighting explicit:

- None: objective Σe²; constant variance; NumPy residual multiplier 1.
- 1/x: objective Σ(e²/x); σ² ∝ x; σ ∝ √x; NumPy residual multiplier 1/√x.
- 1/x²: objective Σ(e²/x²); σ² ∝ x²; σ ∝ x; approximately constant relative SD/%CV; NumPy residual multiplier 1/x.

These definitions describe the statistical weight on squared residuals while also showing how that objective is implemented with NumPy `polyfit`, whose `w` argument multiplies the residual before squaring.

## Validation status

This is research software and has not been validated for clinical use. Clinical-tool modules are quick-check implementations and are not complete reproductions of all CLSI EP05/EP06/EP07/EP17/EP28 requirements. Results intended for regulated or clinical use should be verified against independent reference implementations and known datasets.

### v0.4.5 weighting UI
- Added hover tooltips to weighted regression models.
- Added a Weighting Definitions dialog.
- Appends the selected model's weighting objective and variance assumptions to How Calculated.
- No numerical regression behavior changed in this release.
