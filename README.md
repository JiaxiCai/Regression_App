# Regression App v0.2.0

A cross-platform desktop analysis workbench for analytical and clinical laboratory data.

## Current scope

### Calibration regression
- Manual X/Y entry and CSV/Excel import
- Spreadsheet-style copy/paste
- Calibrator/QC row typing and row-level inclusion/exclusion
- Linear, 1/x weighted linear, 1/x² weighted linear
- Quadratic, 1/x weighted quadratic, 1/x² weighted quadratic
- Padé [1/1] and [2/1]
- Origin handling: Exclude, Include, Force
- Back-calculated concentrations, bias, residuals, RMSE, AIC/AICc/BIC
- Pearson r², residual-based Fit R², and Weighted R² shown separately
- Contiguous passing calibration range / AMR screen
- QC back-calculation and replicate summary
- Excel export

### Method comparison
- Deming regression with user-configurable error-variance ratio λ = σy²/σx²
- Passing–Bablok regression
- Slope/intercept confidence intervals
- Identity-line comparison plot
- Descriptive constant- and proportional-bias flags

### Clinical chemistry quick tools
- Descriptive statistics, CV%, IQR, Shapiro–Wilk
- Precision summary and simple within-run / between-run variance components
- LoB / LoD and LoQ estimation from a concentration–CV profile
- Quick linearity screen
- Nonparametric reference intervals with bootstrap confidence intervals
- Interference/recovery bias
- ROC analysis with AUC and Youden-optimal threshold

### TargetLynx converter
- Reads CSV, TargetLynx comma-delimited TXT, tab/semicolon-delimited text, and Excel
- Auto-detects common Sample / Analyte / Value fields
- Manual column mapping for variable report layouts
- Converts long or wide source data to tidy `Sample / Analyte / Value` format
- Exports one-dimensional data with one analyte per worksheet
- Exports sample × analyte wide matrices

## Running from source

Python 3.11 or 3.12 is recommended.

```bash
python -m venv .venv
```

macOS/Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

## Building standalone apps

Standalone applications should be built separately on each operating system. Collaborators do not need Python after the app is packaged.

### macOS
Install Python 3.10+ (3.12 recommended), then double-click:

`Build Regression App - macOS.command`

The build produces `dist/RegressionApp.app` and a shareable ZIP.

### Windows
Install Python 3.10+ (3.12 recommended), then double-click:

`Build Regression App - Windows.bat`

The build produces `dist/RegressionApp/RegressionApp.exe` and a shareable ZIP.

GitHub Actions can build both platforms from `.github/workflows/build-desktop.yml`.

## Startup diagnostics

If the standalone app fails during startup, it writes a diagnostic log to `~/RegressionApp_crash.log` and attempts to display the traceback in an error dialog.

## Statistical transparency

The app includes a **How Calculated** view for calibration models and intentionally distinguishes Pearson r², ordinary residual-based Fit R², and Weighted R². A model should not be selected based on R² alone.

## Validation status

This is research software and has not been validated for clinical use. Current clinical-tool modules are intended for quick checking and are not yet full implementations of every CLSI EP05/EP06/EP17/EP28 decision rule. Results should be verified against independent reference implementations and known datasets before regulated or clinical use.

TargetLynx report layouts can differ by assay and export configuration. Converter field mappings should be checked against representative files from each laboratory workflow.
