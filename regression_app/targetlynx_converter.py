from pathlib import Path
import csv
import re
import pandas as pd

_COMPOUND_RE = re.compile(r"^Compound\s+\d+:\s*(.+?)\s*$", re.IGNORECASE)
_IS_RE = re.compile(r"(?:-D\d+\b|-\d+C\d+\b|-\d+N\d+\b)", re.IGNORECASE)

DEFAULT_METADATA = [
    "Name", "ID", "Sample Text", "Type", "Std. Conc",
    "Acq.Time", "Acq.Date", "Vial", "Primary Flags"
]

PREFERRED_VALUE_FIELDS = [
    "ng/mL", "Response", "Area", "IS Area", "%Dev", "RT", "S/N",
    "1º Ratio (Actual)", "1º Ratio (Pred)", "RRT",
    "Coeff. Of Determination"
]

def is_internal_standard(compound_name):
    return bool(_IS_RE.search(str(compound_name)))

def parse_targetlynx_compound_summary(path):
    path = Path(path)
    records = []
    compound = None
    header = None
    report_title = ""
    printed_line = ""
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as f:
        reader = csv.reader(f)
        for raw in reader:
            if not raw: continue
            first = (raw[0] or "").strip()
            if not report_title and first: report_title = first
            if first.lower().startswith("printed "): printed_line = first
            m = _COMPOUND_RE.match(first)
            if m:
                compound = m.group(1).strip(); header = None; continue
            if compound and len(raw) > 2:
                second = str(raw[1]).strip(); third = str(raw[2]).strip()
                if second == "#" and third == "Name":
                    header = [str(v).strip() for v in raw[1:]]
                    while header and not header[-1]: header.pop()
                    continue
                if header and second.isdigit():
                    values = list(raw[1:1 + len(header)])
                    values += [""] * max(0, len(header) - len(values))
                    rec = dict(zip(header, values))
                    rec["Compound"] = compound
                    rec["Is Internal Standard"] = is_internal_standard(compound)
                    records.append(rec)
    if not records:
        raise ValueError("No TargetLynx compound blocks were detected. This converter expects a Waters 'Quantify Compound Summary Report' containing lines such as 'Compound 1: Amoxicillin'.")
    df = pd.DataFrame(records)
    front = ["Compound", "Is Internal Standard"]
    df = df[front + [c for c in df.columns if c not in front]]
    sizes = df.groupby("Compound").size()
    metadata = {
        "report_title": report_title,
        "printed_line": printed_line,
        "compound_count": int(df["Compound"].nunique()),
        "sample_count": int(sizes.max()),
        "result_row_count": int(len(df)),
        "balanced_blocks": bool(sizes.nunique() == 1),
    }
    return df, metadata

def available_value_fields(df):
    fields = [c for c in PREFERRED_VALUE_FIELDS if c in df.columns]
    excluded = {"Compound", "Is Internal Standard", "#", "Name", "ID", "Sample Text", "Type", "Acq.Time", "Acq.Date", "Vial"}
    for c in df.columns:
        if c not in excluded and c not in fields: fields.append(c)
    return fields

def filter_results(df, compounds=None, sample_type="All"):
    out = df.copy()
    if compounds: out = out[out["Compound"].astype(str).isin([str(x) for x in compounds])]
    if sample_type and sample_type != "All":
        out = out[out["Type"].astype(str).str.casefold() == str(sample_type).casefold()]
    return out

def build_long_output(df, compounds, value_fields, sample_type="All", include_metadata=True):
    if not compounds: raise ValueError("Select at least one compound.")
    if not value_fields: raise ValueError("Select at least one TargetLynx result field.")
    out = filter_results(df, compounds, sample_type)
    id_cols = ["Compound"]
    if include_metadata: id_cols += [c for c in DEFAULT_METADATA if c in out.columns]
    else: id_cols += [c for c in ("Sample Text", "Type") if c in out.columns]
    keep = list(dict.fromkeys(id_cols + list(value_fields)))
    return out[keep].copy()

def build_wide_output(df, compounds, value_fields, sample_type="All", include_metadata=True):
    if not compounds: raise ValueError("Select at least one compound.")
    if not value_fields: raise ValueError("Select at least one TargetLynx result field.")
    long = filter_results(df, compounds, sample_type)
    if long.empty: return pd.DataFrame()
    sample_key = "Name" if "Name" in long.columns else "Sample Text"
    if include_metadata: meta_cols = [c for c in DEFAULT_METADATA if c in long.columns and c != sample_key]
    else: meta_cols = [c for c in ("Sample Text", "Type") if c in long.columns and c != sample_key]
    meta = long[[sample_key] + meta_cols].drop_duplicates(subset=[sample_key], keep="first").set_index(sample_key)
    pieces = []
    for field in value_fields:
        p = long.pivot_table(index=sample_key, columns="Compound", values=field, aggfunc="first", dropna=False)
        ordered = [c for c in compounds if c in p.columns]
        p = p.reindex(columns=ordered)
        p.columns = [f"{compound}_{field}" for compound in p.columns]
        pieces.append(p)
    return pd.concat([meta] + pieces, axis=1).reset_index()

def export_1d_workbook(df, compounds, value_fields, path, sample_type="All", include_metadata=True):
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        used = set()
        for i, compound in enumerate(compounds):
            one = build_long_output(df, [compound], value_fields, sample_type=sample_type, include_metadata=include_metadata)
            invalid = set('[]:*?/\\')
            sheet = "".join(ch for ch in str(compound) if ch not in invalid)[:28] or f"Compound_{i+1}"
            base = sheet; n = 2
            while sheet in used:
                sheet = (base[:25] + f"_{n}")[:31]; n += 1
            used.add(sheet)
            one.to_excel(writer, sheet_name=sheet, index=False)
