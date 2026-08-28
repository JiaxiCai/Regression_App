# Generated loader for Regression App v0.4.11.
# The release GUI source is embedded across small chunk modules for reliable connector sync.
import base64 as _b64, zlib as _zlib
from importlib import import_module as _import_module

_parts = []
# app_chunk_05 is the stale tail from the older compressed GUI payload.
# The current payload reuses chunks 00-04 and continues with 06-08.
for _i in (0, 1, 2, 3, 4, 6, 7, 8):
    _m = _import_module(f".app_chunk_{_i:02d}", __package__)
    _parts.append(_m.CHUNK)

_src = _zlib.decompress(_b64.b64decode("".join(_parts)))
exec(compile(_src, __file__, "exec"))

from .weighting_ui_patch import install as _install_weighting_ui
_install_weighting_ui(MainWindow)

from .calibration_plot_patch import install as _install_calibration_plot_ui
_install_calibration_plot_ui(MainWindow)

from .amr_ui_patch import install as _install_amr_validation_ui
_install_amr_validation_ui(MainWindow)
