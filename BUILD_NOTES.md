# Build Notes

## v0.3.6 — 2026-08-26

The build workflow was simplified after auditing repeated work.

- Windows now performs one PyInstaller one-folder build instead of both one-folder and one-file builds.
- Local Windows and macOS builders reuse the existing .buildenv instead of deleting and recreating it each run.
- Broad --collect-all scipy and --collect-all matplotlib flags were removed.
- The packaged GUI self-test remains enabled.
- GitHub Actions now produces the collaborator-ready Windows ZIP directly.
- Collaborators should download, extract, and run the built application; they do not need Python, pip, PyInstaller, or a local build.
- --collect-submodules regression_app remains temporarily necessary because the repository still uses generated app_chunk_XX modules.
