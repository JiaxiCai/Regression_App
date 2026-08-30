from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pandas as pd


PROJECT_FORMAT = "RegressionApp Project"
PROJECT_SCHEMA_VERSION = 1


def _table_to_json(df):
    if df is None:
        return None
    buf = io.StringIO()
    df.to_json(buf, orient="table", index=False, date_format="iso")
    return buf.getvalue()


def _table_from_json(text):
    if text is None:
        return None
    return pd.read_json(io.StringIO(text), orient="table")


def save_project(path, *, app_version, module, state, tables=None):
    """Write a portable, versioned Regression App project archive.

    Project files are ZIP containers containing JSON only; no pickle/code objects
    are stored, so reopening a project does not execute serialized Python.
    """
    path = Path(path)
    if path.suffix.lower() != ".regproj":
        path = path.with_suffix(".regproj")

    manifest = {
        "format": PROJECT_FORMAT,
        "schema_version": PROJECT_SCHEMA_VERSION,
        "app_version": str(app_version),
        "module": str(module),
        "state": state or {},
        "tables": {},
    }

    tables = tables or {}
    encoded = {}
    for name, df in tables.items():
        if df is None:
            continue
        filename = f"tables/{name}.json"
        manifest["tables"][name] = filename
        encoded[filename] = _table_to_json(df)

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
        for filename, text in encoded.items():
            zf.writestr(filename, text)

    return path


def load_project(path):
    """Read a Regression App project archive and return manifest/state/tables."""
    path = Path(path)
    with zipfile.ZipFile(path, "r") as zf:
        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        if manifest.get("format") != PROJECT_FORMAT:
            raise ValueError("This file is not a Regression App project.")
        schema = int(manifest.get("schema_version", 0))
        if schema > PROJECT_SCHEMA_VERSION:
            raise ValueError(
                f"Project schema {schema} is newer than this app supports "
                f"(maximum {PROJECT_SCHEMA_VERSION})."
            )

        tables = {}
        for name, filename in manifest.get("tables", {}).items():
            tables[name] = _table_from_json(zf.read(filename).decode("utf-8"))

    return {
        "path": path,
        "schema_version": schema,
        "app_version": manifest.get("app_version", ""),
        "module": manifest.get("module", ""),
        "state": manifest.get("state", {}),
        "tables": tables,
    }
