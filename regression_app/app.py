# Generated loader for Regression App v0.4.5.
# The release GUI source is embedded across small chunk modules for reliable connector sync.
import base64 as _b64, zlib as _zlib
from importlib import import_module as _import_module

_parts = []
for _i in range(8):
    _m = _import_module(f".app_chunk_{_i:02d}", __package__)
    _parts.append(_m.CHUNK)

_src = _zlib.decompress(_b64.b64decode("".join(_parts)))
exec(compile(_src, __file__, "exec"))

from .weighting_ui_patch import install as _install_weighting_ui
_install_weighting_ui(MainWindow)
