# Regression App v0.3.6

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

### TargetLynx converter
- Parses Waters TargetLynx Quantify Compound Summary Reports as repeated compound blocks
- Compound and sample-type filtering
- Detects analytes vs isotope-labeled internal standards
- Multi-select TargetLynx metadata and measurement/result columns
- Wide, long/tidy, and one-worksheet-per-compound Excel outputs

## v0.3 workspace redesign

The main analytical workspaces use draggable Qt splitters instead of rigid stacked layouts. Regression provides a wide spreadsheet-style data-entry pane with independently resizable model settings. Method Comparison, ROC, and TargetLynx likewise expose resizable input, results, plot, configuration, and preview regions.

The UI architecture cleanup has begun with reusable layout infrastructure in `regression_app/ui_helpers.py`. The large `app.py` source is stored through small generated chunk modules in the repository because the connected GitHub synchronization interface has a per-transfer size limitation; runtime behavior corresponds to the v0.3.2 release source.

## Running from source

Use a standalone Python 3.10–3.14 installation rather than Apple's/Xcode Python.

```bash
python -m venv .venv
source .venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
python main.py
```

On Windows, activate `.venv\Scripts\Activate.ps1` instead.

## Building standalone apps

- macOS: `Build Regression App - macOS.command`
- Windows: `Build Regression App - Windows.bat`
- GitHub Actions: `.github/workflows/build-desktop.yml`

The macOS builder detects Python 3.10–3.14, checks common Homebrew/python.org locations, rejects Apple/Xcode Python, and produces `RegressionApp.app` plus a distributable ZIP.

## Statistical transparency

The application deliberately distinguishes Pearson r, Pearson r², ordinary residual-based Fit R², and Weighted R². Calibration models should not be selected from R² alone; back-calculated calibrator bias, QC performance, validated range, and model complexity should also be considered.

## Validation status

This is research software and has not been validated for clinical use. Clinical-tool modules are quick-check implementations and are not complete reproductions of all CLSI EP05/EP06/EP07/EP17/EP28 requirements. Results intended for regulated or clinical use should be verified against independent reference implementations and known datasets.


## Windows distribution note

The Windows distribution is `RegressionApp-Windows.zip`. Extract the entire `RegressionApp` folder before launching `RegressionApp.exe`; the executable depends on runtime files in its adjacent `_internal` directory. Collaborators do not need Python or a local build environment.


### v0.3.6 Windows build note

GitHub-sourced builds explicitly collect all `regression_app` submodules so the generated `app_chunk_XX` modules used by the repository loader are packaged by PyInstaller. The folder build imports the GUI module during self-test before the builder reports success.


## v0.3.6 build workflow

The Windows builder now creates one validated PyInstaller folder build and packages it as `RegressionApp-Windows.zip`. Local builders reuse `.buildenv` instead of recreating the environment on every run, and broad `--collect-all scipy` / `--collect-all matplotlib` flags have been removed to reduce build overhead.
