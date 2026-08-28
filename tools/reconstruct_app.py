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

    OUTPUT.write_bytes(source)
    py_compile.compile(str(OUTPUT), doraise=True)
    print(
        f"Reconstructed {OUTPUT.relative_to(ROOT)} "
        f"({len(source):,} bytes, SHA-256 {digest})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
