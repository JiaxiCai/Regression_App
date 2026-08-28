"""Reconstruct the direct-source Regression App GUI before packaging.

The build_source/*.b64 files are repository transport parts only. They are
joined, decoded, decompressed, SHA-256 verified, and written to
regression_app/app.py before PyInstaller runs. The packaged application never
executes a Base64/zlib loader.
"""
from __future__ import annotations

import base64
import hashlib
from pathlib import Path
import py_compile
import zlib

ROOT = Path(__file__).resolve().parents[1]
PART_DIR = ROOT / "build_source"
OUTPUT = ROOT / "regression_app" / "app.py"
EXPECTED_SHA256 = "8e9a599ccb80b616a4c36acbca96014c4ace896438c302f840207980bb3afcdb"
EXPECTED_PARTS = 8


def main() -> int:
    parts = sorted(PART_DIR.glob("app_source_*.b64"))
    if len(parts) != EXPECTED_PARTS:
        raise SystemExit(
            f"Expected {EXPECTED_PARTS} app source parts in {PART_DIR}, found {len(parts)}."
        )

    payload = "".join(p.read_text(encoding="ascii").strip() for p in parts)
    try:
        source = zlib.decompress(base64.b64decode(payload, validate=True))
    except Exception as exc:
        raise SystemExit(f"Could not reconstruct direct app source: {exc}") from exc

    digest = hashlib.sha256(source).hexdigest()
    if digest != EXPECTED_SHA256:
        raise SystemExit(
            "Direct app source checksum mismatch. "
            f"Expected {EXPECTED_SHA256}, got {digest}."
        )

    # Normalize the visible application version after the transport checksum
    # is verified. Read the single package version source so the title cannot
    # drift from the actual release version.
    init_text = (ROOT / "regression_app" / "__init__.py").read_text(encoding="utf-8")
    import re
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', init_text)
    if not match:
        raise SystemExit("Could not determine regression_app.__version__.")
    version = match.group(1)

    text = source.decode("utf-8")
    text = text.replace("Regression App v0.4.12", f"Regression App v{version}")
    text = text.replace("# v0.4.12:", f"# v{version}:")

    # Feature workspaces that live as normal modules are installed onto the
    # confirmed direct-source MainWindow after reconstruction.
    if "_install_surrogate_is_ui" not in text:
        text += (
            "\n\nfrom .surrogate_is_ui_patch import install as _install_surrogate_is_ui\n"
            "_install_surrogate_is_ui(MainWindow)\n"
        )
    output = text.encode("utf-8")
    output_digest = hashlib.sha256(output).hexdigest()

    OUTPUT.write_bytes(output)
    py_compile.compile(str(OUTPUT), doraise=True)
    print(
        f"Reconstructed {OUTPUT.relative_to(ROOT)} "
        f"({len(output):,} bytes, SHA-256 {output_digest})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
