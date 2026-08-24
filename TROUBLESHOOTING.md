# Troubleshooting

## macOS: PySide6 `__init__.tmpl.py` SyntaxError during installation

If the traceback includes:

`PySide6/scripts/deploy_lib/android/recipes/PySide6/__init__.tmpl.py`

and an Xcode Python path such as:

`/Applications/Xcode.app/.../Python3.framework/Versions/3.9/...`

the builder has selected Apple's/Xcode's old bundled Python.

Version 0.1.2 and later fix this by:

1. requiring Python 3.10 or newer;
2. preferring Python 3.12, 3.11, or 3.10;
3. refusing Xcode's bundled Python;
4. using `pip install --no-compile` to avoid byte-compiling PySide6 template files.

Recommended solution: install Python 3.12 from python.org and rerun `Build Regression App - macOS.command`.

The final built `.app` does not require collaborators to install Python.
