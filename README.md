# Regression App v0.1.3

Cross-platform desktop regression prototype for analytical and clinical laboratory data.

## For collaborators

Collaborators should receive the **already-built app**, not this source-code folder.

### macOS
Send them `RegressionApp-macOS.zip`. They unzip it and double-click `RegressionApp.app`.

Because development builds are not yet Apple-signed/notarized, macOS may block the first launch.
If that happens, Control-click the app, choose **Open**, then choose **Open** again.

### Windows
Send them `RegressionApp-Windows.zip`. They unzip it and double-click `RegressionApp.exe`.

Because development builds are not yet digitally signed, Windows SmartScreen may warn about an
unrecognized app. This can be addressed later with production code signing.

Collaborators do **not** need Python installed.

---

## Building the app once

A standalone app must be built on the operating system it will run on.

### Build on macOS — easiest route

1. Install Python 3.11 or 3.12 once.
2. Unzip this project.
3. Double-click `Build Regression App - macOS.command`.

The script creates `dist/RegressionApp.app` and `dist/RegressionApp-macOS.zip`.

### Build on Windows — easiest route

1. Install Python 3.11 or 3.12 once.
2. Unzip this project.
3. Double-click `Build Regression App - Windows.bat`.

The script creates `dist/RegressionApp/RegressionApp.exe` and `dist/RegressionApp-Windows.zip`.

### Automatic builds with GitHub

The included `.github/workflows/build-desktop.yml` can build both macOS and Windows versions using GitHub Actions.

## Current v0.1.3 analysis features

### Input
- Manual X/Y entry
- CSV import
- Excel import
- Select imported X and Y columns
- Row-level include/exclude control
- Calibrator/QC row typing
- QC replicate summaries

### Candidate calibration models
- Linear
- Linear 1/x
- Linear 1/x²
- Quadratic
- Quadratic 1/x
- Quadratic 1/x²
- Padé [1/1]
- Padé [2/1]

### Outputs
- R²
- Adjusted R²
- RMSE
- AIC
- AICc
- BIC
- Back-calculated concentration
- Calibration % bias
- QC % bias and replicate summaries
- Passing-point count
- Widest contiguous passing calibration range
- Calibration curve
- Residual plot
- Parameter table
- Excel export

### Acceptance settings
- User-defined calibrator bias limit
- User-defined QC bias limit
- User-defined minimum number of passing calibrators

## Scientific scope

v0.1.3 is currently a **calibration-regression prototype**. X is interpreted as nominal concentration and Y as analytical response. QC rows are evaluated against the fitted calibration model but do not influence the fit.

Planned later modules include separate LLOQ criteria, improved AMR validation rules, Deming regression, weighted Deming, Passing–Bablok, Bland–Altman, bootstrap confidence intervals, 4PL/5PL, and method-comparison reporting.

## Validation warning

This is research software and has not been validated for clinical use. Regression results should be compared with independent reference implementations and verified datasets before being used for regulated or clinical decision-making.
