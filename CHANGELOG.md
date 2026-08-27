# Changelog

All notable development changes to Regression App are documented here.

## [0.4.0] - 2026-08-26

### Replicate Studies prototype
- Added a new Replicate Studies workspace for repeated calibration-ladder designs such as 5×5 and 3×3.
- TargetLynx replicate ladders are inferred from actual sequence order and nominal concentration reset rather than sample-name suffix alone.
- Mapping table allows manual replicate-set reassignment before analysis.
- Each complete ladder can be rotated through the calibrator role using the existing regression engine.
- Added calibration-fit summary, precision/CV and bias by level, calibration-dependence matrix, sequence-associated bias view, and Excel export.
- Internal-standard compounds are excluded from the Replicate Studies analyte selector.
- Validated set detection on the provided antibiotic milk 5×5 report, including a mislabeled `Milk Cal 5-3` row within the fourth ladder.

## [0.3.6] - 2026-08-26

### Build efficiency
- Windows now produces one validated `--onedir` build instead of both `--onedir` and `--onefile`.
- Local Windows and macOS builders reuse `.buildenv` instead of recreating the environment on every run.
- Removed repeated pip upgrades on reused environments.
- Removed broad `--collect-all scipy` and `--collect-all matplotlib` flags.
- GitHub Actions now publishes the collaborator-ready Windows ZIP only.
- The packaged GUI self-test remains enabled and `--collect-submodules regression_app` is retained while the chunk loader is still in use.

## [0.3.5] - 2026-08-26

### Fixed — GitHub/Windows chunk packaging
- Windows PyInstaller builds now use `--collect-submodules regression_app` so dynamically loaded `app_chunk_00`…`app_chunk_05` modules are included.
- Bundle self-test now imports `regression_app.app`, catching missing GUI chunks before a build is declared successful.

## [0.3.3] - 2026-08-24

### TargetLynx converter numeric types
- Numeric-looking TargetLynx result cells are now converted to true numeric values during parsing instead of being exported wholesale as Excel text.
- Sample names, IDs, sample text, type, acquisition date/time, vial labels, and primary flags remain text even when they contain only digits.
- Mixed fields preserve vendor annotations such as `<LLOQ` or `No Peak`.
- Typed values propagate through preview, wide output, long/tidy output, and per-compound Excel export.

## [0.3.2] - 2026-08-24
- Added signed Pearson correlation coefficient `r` and exported it alongside `r²`.

## [0.3.1] - 2026-08-24
- Modernized Python detection/build tooling.

## [0.3.0] - 2026-08-24
- Major workspace usability cleanup using draggable Qt splitters.

## [0.2.7] - 2026-08-24
- Fixed ROC startup crash.

## [0.2.5] - 2026-08-24
- Added ROC curve plot.

## [0.2.1] - 2026-08-24
- Added Waters TargetLynx compound-summary parsing.

## [0.2.0] - 2026-08-24
- Expanded the application into an analytical/clinical chemistry workbench.

## [0.1.0] - 2026-08-24
- Initial PySide6 calibration/regression application.
