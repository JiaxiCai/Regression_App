from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import pandas as pd

from .models import MODEL_SPECS, ORIGIN_EXCLUDE
from .targetlynx_converter import parse_targetlynx_compound_summary


@dataclass
class SurrogateCriteria:
    model_name: str = "Linear 1/x"
    min_calibrators: int = 5
    max_calibrator_bias: float = 20.0
    min_r2: float = 0.99
    max_qc_mean_abs_bias: float = 20.0
    max_qc_abs_bias: float = 30.0
    max_qc_cv: float = 20.0
    qc_reference_basis: str = "Nominal concentration"
    origin_mode: str = ORIGIN_EXCLUDE


def _num(s):
    return pd.to_numeric(s, errors="coerce")


def _first_existing(columns, candidates):
    lower = {str(c).strip().casefold(): c for c in columns}
    for cand in candidates:
        hit = lower.get(cand.casefold())
        if hit is not None:
            return hit
    return None


def load_surrogate_data(path):
    path = Path(path)
    if path.suffix.lower() in {".csv", ".txt"}:
        try:
            df, meta = parse_targetlynx_compound_summary(path)
            return normalize_targetlynx(df), {"format": "TargetLynx", **meta}
        except Exception:
            pass
    raw = pd.read_excel(path) if path.suffix.lower() in {".xlsx", ".xls"} else pd.read_csv(path)
    return normalize_generic_long(raw), {"format": "Long format"}


def load_user_amr(path):
    """Load user-defined analyte AMRs from CSV/Excel.

    Required logical fields are analyte/component name, LLOQ, and ULOQ.
    Common header variants are recognized automatically.
    """
    path = Path(path)
    raw = pd.read_excel(path) if path.suffix.lower() in {".xlsx", ".xls"} else pd.read_csv(path)
    cols = list(raw.columns)
    analyte_col = _first_existing(cols, [
        "Analyte", "Analyte Component", "analyte_component", "Component",
        "Component Name", "Compound",
    ])
    lloq_col = _first_existing(cols, ["LLOQ", "LLoQ", "Lower Limit", "AMR LLOQ", "Lower"])
    uloq_col = _first_existing(cols, ["ULOQ", "ULoQ", "Upper Limit", "AMR ULOQ", "Upper"])
    missing = [
        name for name, col in [("analyte", analyte_col), ("LLOQ", lloq_col), ("ULOQ", uloq_col)]
        if col is None
    ]
    if missing:
        raise ValueError("Could not identify user-AMR columns: " + ", ".join(missing))

    out = pd.DataFrame({
        "Analyte": raw[analyte_col].astype(str).str.strip(),
        "LLOQ": _num(raw[lloq_col]),
        "ULOQ": _num(raw[uloq_col]),
    }).replace([np.inf, -np.inf], np.nan).dropna()
    out = out[(out["LLOQ"] > 0) & (out["ULOQ"] >= out["LLOQ"])]
    if out.empty:
        raise ValueError("No valid positive user-defined AMRs were found.")
    return out.drop_duplicates("Analyte", keep="last").reset_index(drop=True)


def user_amr_lookup(amr_table):
    if amr_table is None or len(amr_table) == 0:
        return {}
    return {
        str(r["Analyte"]): (float(r["LLOQ"]), float(r["ULOQ"]))
        for _, r in amr_table.iterrows()
        if np.isfinite(r["LLOQ"]) and np.isfinite(r["ULOQ"])
    }


def _strip_isotope_label(name):
    """Best-effort base name for common stable-isotope-labelled component names."""
    import re
    text = str(name).strip()
    patterns = [
        r"[-_ ]D\d+\b", r"[-_ ]\d+C\d+\b", r"[-_ ]\d+N\d+\b",
        r"[-_ ]\d+O\d+\b", r"[-_ ]\d+S\d+\b",
    ]
    out = text
    for pat in patterns:
        out = re.sub(pat, "", out, flags=re.IGNORECASE)
    return out.strip(" _-")


def _auto_is_assignment(component, analytes):
    base = _strip_isotope_label(component)
    exact = {str(a).casefold(): str(a) for a in analytes}
    paired = exact.get(base.casefold(), "")
    is_sil = bool(paired) and base.casefold() != str(component).casefold()
    return ("SIL-IS" if is_sil else "Surrogate", paired)


def normalize_targetlynx(df):
    if "Compound" not in df.columns:
        raise ValueError("TargetLynx table does not contain Compound.")
    name_col = "Name" if "Name" in df.columns else "Sample Text"
    id_col = "ID" if "ID" in df.columns else None
    inj_col = "#" if "#" in df.columns else None
    if "Area" not in df.columns:
        raise ValueError("TargetLynx report does not contain Area.")

    out = pd.DataFrame(index=df.index)
    out["Sample Key"] = (
        df[id_col].astype(str) + "|" + df[name_col].astype(str)
        if id_col else df[name_col].astype(str)
    )
    out["Sample Name"] = df[name_col].astype(str)
    out["Sample Type"] = df.get("Type", "").astype(str)
    out["Name"] = df["Name"].astype(str) if "Name" in df.columns else out["Sample Name"]
    out["ID"] = df["ID"].astype(str) if "ID" in df.columns else ""
    out["Sample Text"] = df["Sample Text"].astype(str) if "Sample Text" in df.columns else ""
    out["Type"] = df["Type"].astype(str) if "Type" in df.columns else out["Sample Type"]
    flag_col = _first_existing(df.columns, ["Primary Flags", "Primary Flag"])
    out["Primary Flags"] = df[flag_col].astype(str) if flag_col else ""
    out["Component"] = df["Compound"].astype(str)
    out["Component Group"] = df["Compound"].astype(str)
    is_flag = df.get("Is Internal Standard", False)
    if not isinstance(is_flag, pd.Series):
        is_flag = pd.Series(bool(is_flag), index=df.index)
    out["Component Role"] = np.where(is_flag.astype(bool), "IS", "Analyte")
    out["Auto Role"] = out["Component Role"]
    out["Nominal"] = _num(df.get("Std. Conc", np.nan))
    out["Area"] = _num(df["Area"])
    rt_col = _first_existing(df.columns, ["RT", "Retention Time", "Retention Time (min)"])
    out["RT"] = _num(df[rt_col]) if rt_col else np.nan
    out["Injection"] = _num(df[inj_col]) if inj_col else np.arange(1, len(df) + 1)
    return out.reset_index(drop=True)


def normalize_generic_long(df):
    cols = list(df.columns)
    sample_index = _first_existing(cols, ["Sample Index", "Injection", "#", "ID"])
    sample_name = _first_existing(cols, ["Sample Name", "Name", "Sample Text"])
    sample_type = _first_existing(cols, ["Sample Type", "Type"])
    source_name = _first_existing(cols, ["Name"])
    source_id = _first_existing(cols, ["ID"])
    source_sample_text = _first_existing(cols, ["Sample Text"])
    source_type = _first_existing(cols, ["Type"])
    primary_flags = _first_existing(cols, ["Primary Flags", "Primary Flag"])
    component_type = _first_existing(cols, ["Component Type", "Role"])
    component_name = _first_existing(cols, ["Component Name", "Compound", "Analyte"])
    component_group = _first_existing(cols, ["Component Group Name", "Component Group", "Analyte Group"])
    concentration = _first_existing(cols, ["Actual Concentration", "Std. Conc", "Nominal", "Concentration"])
    area = _first_existing(cols, ["Area", "Peak Area", "Response"])
    rt_col = _first_existing(cols, ["RT", "Retention Time", "Retention Time (min)"])
    injection = _first_existing(cols, ["Sample Index", "Injection", "#"])

    required = {
        "sample name": sample_name, "sample type": sample_type,
        "component name": component_name, "concentration": concentration, "area": area,
    }
    missing = [k for k, v in required.items() if v is None]
    if missing:
        raise ValueError("Could not identify required long-format columns: " + ", ".join(missing))

    out = pd.DataFrame(index=df.index)
    out["Sample Key"] = (
        df[sample_index].astype(str) + "|" + df[sample_name].astype(str)
        if sample_index else df[sample_name].astype(str)
    )
    out["Sample Name"] = df[sample_name].astype(str)
    out["Sample Type"] = df[sample_type].astype(str)
    out["Name"] = df[source_name].astype(str) if source_name else out["Sample Name"]
    out["ID"] = df[source_id].astype(str) if source_id else (
        df[sample_index].astype(str) if sample_index else ""
    )
    out["Sample Text"] = df[source_sample_text].astype(str) if source_sample_text else ""
    out["Type"] = df[source_type].astype(str) if source_type else out["Sample Type"]
    out["Primary Flags"] = df[primary_flags].astype(str) if primary_flags else ""
    out["Component"] = df[component_name].astype(str)
    out["Component Group"] = (
        df[component_group].astype(str) if component_group else df[component_name].astype(str)
    )
    if component_type:
        role_text = df[component_type].astype(str).str.strip().str.casefold()
        out["Component Role"] = np.select(
            [
                role_text.str.contains("internal") | role_text.str.fullmatch(r"is"),
                role_text.str.contains("qualifier"),
            ],
            ["IS", "Ignore"],
            default="Analyte",
        )
        out["Auto Role"] = out["Component Role"]
    else:
        nm = df[component_name].astype(str)
        is_mask = nm.str.contains(r"(?:-D\d+\b|-\d+C\d+\b|-\d+N\d+\b)", regex=True, case=False)
        out["Component Role"] = np.where(is_mask, "IS", "Analyte")
        out["Auto Role"] = out["Component Role"]
    out["Nominal"] = _num(df[concentration])
    out["Area"] = _num(df[area])
    out["RT"] = _num(df[rt_col]) if rt_col else np.nan
    out["Injection"] = _num(df[injection]) if injection else np.arange(1, len(df) + 1)
    return out.reset_index(drop=True)


def component_mapping_table(normalized):
    """Return one editable setup row per detected component."""
    analytes = sorted(
        normalized.loc[normalized["Component Role"] == "Analyte", "Component"].astype(str).unique()
    )
    rows = []
    for component, g in normalized.groupby("Component", sort=True):
        auto = str(g.get("Auto Role", g["Component Role"]).iloc[0])
        role = str(g["Component Role"].iloc[0])
        is_class, paired = _auto_is_assignment(component, analytes) if role == "IS" else ("", "")
        rows.append({
            "Component": str(component),
            "Automatic Role": auto,
            "Role": role,
            "IS Class": is_class,
            "Paired Analyte": paired,
            "Include": role != "Ignore",
            "Calibrator Rows": int(_sample_type_mask(g["Sample Type"], "cal").sum()) if "Sample Type" in g else 0,
            "QC Rows": int(_sample_type_mask(g["Sample Type"], "qc").sum()) if "Sample Type" in g else 0,
        })
    return pd.DataFrame(rows)

def apply_component_mapping(normalized, mapping):
    """Apply user-visible component role/include choices to a copy of the data."""
    data = normalized.copy()
    if mapping is None or len(mapping) == 0:
        return data

    role_map = {}
    include_map = {}
    class_map = {}
    paired_map = {}
    for _, row in mapping.iterrows():
        name = str(row["Component"])
        role = str(row.get("Role", row.get("Automatic Role", "Ignore")))
        include = bool(row.get("Include", True))
        role_map[name] = role
        include_map[name] = include
        class_map[name] = str(row.get("IS Class", ""))
        paired_map[name] = str(row.get("Paired Analyte", ""))

    data["Component Role"] = data["Component"].astype(str).map(role_map).fillna(data["Component Role"])
    data["IS Class"] = data["Component"].astype(str).map(class_map).fillna("")
    data["Paired Analyte"] = data["Component"].astype(str).map(paired_map).fillna("")
    keep = data["Component"].astype(str).map(include_map).fillna(True).astype(bool)
    keep &= data["Component Role"].astype(str).isin(["Analyte", "IS"])
    return data.loc[keep].copy()


def qc_sample_mapping_table(normalized):
    """Return one editable Include/Exclude row per detected QC sample."""
    qc = normalized.loc[_sample_type_mask(normalized["Sample Type"], "qc")].copy()
    cols = [
        "Sample Key", "Name", "ID", "Sample Text", "Type",
        "Automatic Include", "Include",
    ]
    if qc.empty:
        return pd.DataFrame(columns=cols)

    rows = []
    for sample_key, g in qc.groupby("Sample Key", sort=False):
        name = str(g["Name"].iloc[0]) if "Name" in g else str(g["Sample Name"].iloc[0])
        sample_id = str(g["ID"].iloc[0]) if "ID" in g else ""
        sample_text = str(g["Sample Text"].iloc[0]) if "Sample Text" in g else ""
        sample_type = str(g["Type"].iloc[0]) if "Type" in g else str(g["Sample Type"].iloc[0])
        searchable = " ".join([name, sample_id, sample_text, sample_type]).casefold()
        searchable = searchable.replace("_", " ").replace("-", " ")
        auto_include = "low is" not in searchable
        rows.append({
            "Sample Key": str(sample_key),
            "Name": name,
            "ID": sample_id,
            "Sample Text": sample_text,
            "Type": sample_type,
            "Automatic Include": bool(auto_include),
            "Include": bool(auto_include),
        })
    return pd.DataFrame(rows)

def apply_qc_sample_mapping(normalized, mapping):
    """Exclude user-disabled QC samples while leaving calibrators and other rows unchanged."""
    data = normalized.copy()
    if mapping is None or len(mapping) == 0:
        return data

    include_map = {
        str(row["Sample Key"]): bool(row.get("Include", True))
        for _, row in mapping.iterrows()
    }
    qc_mask = _sample_type_mask(data["Sample Type"], "qc")
    qc_keep = data["Sample Key"].astype(str).map(include_map).fillna(True).astype(bool)
    keep = (~qc_mask) | qc_keep
    return data.loc[keep].copy()


def _sample_type_mask(series, kind):
    t = series.astype(str).str.strip().str.casefold()
    if kind == "cal":
        return t.isin({"standard", "calibrator", "cal", "std"})
    if kind == "qc":
        return t.isin({"qc", "quality control", "control"})
    raise ValueError(kind)


def _sample_metadata(normalized, rows):
    """One metadata row per sample, indexed identically to area/nominal pivots."""
    cols = ["Sample Key", "Sample Name", "Name", "ID", "Sample Text", "Type"]
    x = normalized.loc[rows, [c for c in cols if c in normalized.columns]].copy()
    for c in cols:
        if c not in x.columns:
            x[c] = ""
    return (
        x[cols].drop_duplicates(["Sample Key", "Sample Name"])
        .set_index(["Sample Key", "Sample Name"])
    )


def _pivot(normalized, rows):
    return normalized.loc[rows].pivot_table(
        index=["Sample Key", "Sample Name"], columns="Component", values="Area", aggfunc="first"
    )


def _rt_pivot(normalized, rows):
    if "RT" not in normalized.columns:
        return pd.DataFrame()
    return normalized.loc[rows].pivot_table(
        index=["Sample Key", "Sample Name"], columns="Component", values="RT", aggfunc="first"
    )


def _analyte_nominals(normalized, rows):
    x = normalized.loc[rows & (normalized["Component Role"] == "Analyte")]
    return x.pivot_table(
        index=["Sample Key", "Sample Name"], columns="Component", values="Nominal", aggfunc="first"
    )


def _group_lookup(normalized):
    x = normalized[normalized["Component Role"] == "Analyte"]
    return (
        x.drop_duplicates("Component").set_index("Component")["Component Group"].astype(str).to_dict()
        if not x.empty else {}
    )


def _criteria_for_analyte(criteria, analyte, analyte_fit_settings=None):
    """Return a criteria copy with optional analyte-specific model/origin overrides."""
    if analyte_fit_settings is None:
        return criteria
    settings = analyte_fit_settings.get(str(analyte), {})
    model_name = str(settings.get("model_name", criteria.model_name) or criteria.model_name)
    origin_mode = str(settings.get("origin_mode", criteria.origin_mode) or criteria.origin_mode)
    return replace(criteria, model_name=model_name, origin_mode=origin_mode)


def _fit_model(x, y, criteria):
    lookup = dict(MODEL_SPECS)
    if criteria.model_name not in lookup:
        raise ValueError(f"Unknown model: {criteria.model_name}")
    return lookup[criteria.model_name](
        np.asarray(x, float), np.asarray(y, float),
        float(criteria.max_calibrator_bias), int(criteria.min_calibrators), criteria.origin_mode,
    )


def _fit_candidate(x, y, criteria):
    try:
        fit = _fit_model(x, y, criteria)
    except Exception:
        return None
    bias = np.asarray(fit.bias_pct, float)
    finite_bias = bias[np.isfinite(bias)]
    max_bias = float(np.nanmax(np.abs(finite_bias))) if finite_bias.size else np.nan
    min_abs = float(np.nanmin(np.abs(finite_bias))) if finite_bias.size else np.nan
    mean_abs = float(np.nanmean(np.abs(finite_bias))) if finite_bias.size else np.nan
    min_signed = float(np.nanmin(finite_bias)) if finite_bias.size else np.nan
    max_signed = float(np.nanmax(finite_bias)) if finite_bias.size else np.nan
    r2 = float(fit.stats.get("fit_r2", np.nan))
    wr2 = float(fit.stats.get("weighted_r2", np.nan))
    passed = (
        len(x) >= criteria.min_calibrators and np.isfinite(max_bias)
        and max_bias <= criteria.max_calibrator_bias
        and np.isfinite(r2) and r2 >= criteria.min_r2
    )
    return {
        "fit": fit, "n_cal": int(len(x)), "max_cal_abs_bias_pct": max_bias,
        "min_cal_abs_bias_pct": min_abs, "mean_cal_abs_bias_pct": mean_abs,
        "min_cal_bias_pct": min_signed, "max_cal_bias_pct": max_signed,
        "fit_r2": r2, "weighted_r2": wr2,
        "pass_cal": bool(passed), "lloq": float(np.min(x)), "uloq": float(np.max(x)),
    }


def select_stage1_levels(x, y, criteria):
    d = pd.DataFrame({"x": x, "y": y}).replace([np.inf, -np.inf], np.nan).dropna()
    d = d[d["x"] > 0].groupby("x", as_index=False)["y"].mean().sort_values("x")
    if len(d) < criteria.min_calibrators:
        return [], None
    xs = d["x"].to_numpy(float); ys = d["y"].to_numpy(float)
    passing = []
    for i in range(len(xs)):
        for j in range(i + criteria.min_calibrators - 1, len(xs)):
            m = _fit_candidate(xs[i:j+1], ys[i:j+1], criteria)
            if m is not None and m["pass_cal"]:
                passing.append(m)
    if not passing:
        return [], None
    best = max(
        passing,
        key=lambda m: (
            np.log10(max(m["uloq"] / m["lloq"], 1.0)), m["n_cal"],
            -m["max_cal_abs_bias_pct"], m["fit_r2"],
        ),
    )
    levels = xs[(xs >= best["lloq"]) & (xs <= best["uloq"])].tolist()
    return levels, best


def _qc_metrics(calc, reference, group_levels=None):
    """Lightweight QC metrics for bulk pair screening without per-pair DataFrames."""
    calc = np.asarray(calc, float)
    ref = np.asarray(reference, float)
    levels = np.asarray(group_levels if group_levels is not None else reference, float)
    valid = np.isfinite(calc) & np.isfinite(ref) & np.isfinite(levels) & (ref > 0) & (levels > 0)
    if not valid.any():
        return {}
    calc = calc[valid]; ref = ref[valid]; levels = levels[valid]
    bias = (calc - ref) / ref * 100.0
    unique_levels = np.unique(levels)
    cvs = []
    for level in unique_levels:
        vals = calc[levels == level]
        if len(vals) > 1:
            mean = float(np.mean(vals))
            if np.isfinite(mean) and mean != 0:
                cvs.append(float(np.std(vals, ddof=1) / mean * 100.0))
    finite_bias = bias[np.isfinite(bias)]
    return {
        "qc_n": int(len(calc)),
        "qc_levels": int(len(unique_levels)),
        "qc_mean_abs_bias_pct": float(np.mean(np.abs(finite_bias))) if finite_bias.size else np.nan,
        "qc_min_abs_bias_pct": float(np.min(np.abs(finite_bias))) if finite_bias.size else np.nan,
        "qc_max_abs_bias_pct": float(np.max(np.abs(finite_bias))) if finite_bias.size else np.nan,
        "qc_min_bias_pct": float(np.min(finite_bias)) if finite_bias.size else np.nan,
        "qc_max_bias_pct": float(np.max(finite_bias)) if finite_bias.size else np.nan,
        "qc_mean_cv_pct": float(np.nanmean(cvs)) if cvs else np.nan,
        "qc_min_cv_pct": float(np.nanmin(cvs)) if cvs else np.nan,
        "qc_max_cv_pct": float(np.nanmax(cvs)) if cvs else np.nan,
    }


def _qc_summary(calc, reference, group_levels=None):
    calc = np.asarray(calc, float)
    ref = np.asarray(reference, float)
    levels = np.asarray(group_levels if group_levels is not None else reference, float)
    d = pd.DataFrame({"calc": calc, "reference": ref, "level": levels})
    d = d.replace([np.inf, -np.inf], np.nan).dropna()
    d = d[(d["reference"] > 0) & (d["level"] > 0)]
    if d.empty:
        return pd.DataFrame(), {}
    d["bias_pct"] = (d["calc"] - d["reference"]) / d["reference"] * 100.0
    by = d.groupby("level", as_index=False).agg(
        n=("calc", "count"), mean_calc=("calc", "mean"), sd=("calc", "std"),
        mean_bias_pct=("bias_pct", "mean"),
        mean_abs_bias_pct=("bias_pct", lambda x: float(np.nanmean(np.abs(x)))),
        max_abs_bias_pct=("bias_pct", lambda x: float(np.nanmax(np.abs(x)))),
    ).rename(columns={"level": "nominal"})
    by["cv_pct"] = by["sd"] / by["mean_calc"] * 100.0
    return by, {
        "qc_n": int(len(d)), "qc_levels": int(by["nominal"].nunique()),
        "qc_mean_abs_bias_pct": float(np.nanmean(np.abs(d["bias_pct"]))),
        "qc_min_abs_bias_pct": float(np.nanmin(np.abs(d["bias_pct"]))),
        "qc_max_abs_bias_pct": float(np.nanmax(np.abs(d["bias_pct"]))),
        "qc_min_bias_pct": float(np.nanmin(d["bias_pct"])),
        "qc_max_bias_pct": float(np.nanmax(d["bias_pct"])),
        "qc_mean_cv_pct": float(np.nanmean(by["cv_pct"])) if np.isfinite(by["cv_pct"]).any() else np.nan,
        "qc_min_cv_pct": float(np.nanmin(by["cv_pct"])) if np.isfinite(by["cv_pct"]).any() else np.nan,
        "qc_max_cv_pct": float(np.nanmax(by["cv_pct"])) if np.isfinite(by["cv_pct"]).any() else np.nan,
    }


def _matched_sil_name(is_meta, analyte):
    if is_meta is None or len(is_meta) == 0:
        return ""
    x = is_meta[
        is_meta["IS Class"].astype(str).eq("SIL-IS")
        & is_meta["Paired Analyte"].astype(str).eq(str(analyte))
    ]
    return str(x.index[0]) if len(x) else ""


def _fit_pair_from_cache(cal_area, cal_nom, analyte, is_name, levels, criteria):
    if not is_name or is_name not in cal_area.columns:
        return None
    idx = cal_area.index.intersection(cal_nom.index)
    xa = _num(cal_nom.loc[idx, analyte]); aa = _num(cal_area.loc[idx, analyte]); ia = _num(cal_area.loc[idx, is_name])
    valid = np.isfinite(xa) & np.isfinite(aa) & np.isfinite(ia) & (xa > 0) & (ia > 0) & xa.isin(levels)
    if int(valid.sum()) < criteria.min_calibrators:
        return None
    return _fit_candidate(
        xa[valid].to_numpy(float),
        (aa[valid] / ia[valid]).to_numpy(float),
        criteria,
    )


def _fit_pair_contiguous_search(
    x, ratio, criteria, qc_ratio=None, qc_nominal=None, qc_reference=None
):
    """Exhaustively search contiguous calibration windows and prefer the widest QC-passing fit."""
    x = np.asarray(x, float)
    ratio = np.asarray(ratio, float)
    valid = np.isfinite(x) & np.isfinite(ratio) & (x > 0)
    x = x[valid]; ratio = ratio[valid]
    if len(x) == 0:
        return None

    levels = sorted(np.unique(x).astype(float).tolist())
    if len(levels) < int(criteria.min_calibrators):
        return None

    qratio = None if qc_ratio is None else np.asarray(qc_ratio, float)
    qnom = None if qc_nominal is None else np.asarray(qc_nominal, float)
    qref = None if qc_reference is None else np.asarray(qc_reference, float)

    candidates = []
    tested = 0
    for i in range(len(levels)):
        for j in range(i + int(criteria.min_calibrators) - 1, len(levels)):
            active = levels[i:j+1]
            mask = np.isin(x, active)
            metrics = _fit_candidate(x[mask], ratio[mask], criteria)
            tested += 1
            if metrics is None or not metrics["pass_cal"]:
                continue

            qs = {}
            qc_pass = False
            if qratio is not None and qnom is not None and qref is not None:
                qvalid = (
                    np.isfinite(qratio) & np.isfinite(qnom) & np.isfinite(qref)
                    & (qnom >= metrics["lloq"]) & (qnom <= metrics["uloq"])
                    & (qref > 0)
                )
                if qvalid.any():
                    qcalc = metrics["fit"].invert(qratio[qvalid])
                    qs = _qc_metrics(qcalc, qref[qvalid], qnom[qvalid])
                    qc_pass = bool(qs) and (
                        np.isfinite(qs.get("qc_mean_abs_bias_pct", np.nan))
                        and qs["qc_mean_abs_bias_pct"] <= criteria.max_qc_mean_abs_bias
                        and np.isfinite(qs.get("qc_max_abs_bias_pct", np.nan))
                        and qs["qc_max_abs_bias_pct"] <= criteria.max_qc_abs_bias
                        and (
                            not np.isfinite(qs.get("qc_max_cv_pct", np.nan))
                            or qs["qc_max_cv_pct"] <= criteria.max_qc_cv
                        )
                    )

            span = float(metrics["uloq"] / metrics["lloq"]) if metrics["lloq"] > 0 else 0.0
            # Prefer full calibration+QC pass. Then maximize contiguous span and
            # level count. QC precision/bias and calibration quality are tie-breakers.
            score = (
                1 if qc_pass else 0,
                np.log10(max(span, 1.0)),
                len(active),
                -float(qs.get("qc_max_cv_pct", np.inf)) if np.isfinite(qs.get("qc_max_cv_pct", np.nan)) else -np.inf,
                -float(qs.get("qc_mean_abs_bias_pct", np.inf)) if np.isfinite(qs.get("qc_mean_abs_bias_pct", np.nan)) else -np.inf,
                -float(qs.get("qc_max_abs_bias_pct", np.inf)) if np.isfinite(qs.get("qc_max_abs_bias_pct", np.nan)) else -np.inf,
                -float(metrics["max_cal_abs_bias_pct"]),
                float(metrics["fit_r2"]),
            )
            candidates.append({
                "metrics": metrics,
                "active_levels": [float(v) for v in active],
                "qc_metrics": qs,
                "qc_pass": bool(qc_pass),
                "score": score,
            })

    if not candidates:
        return None

    best = max(candidates, key=lambda c: c["score"])
    active_set = set(best["active_levels"])
    return {
        "metrics": best["metrics"],
        "active_levels": best["active_levels"],
        "removed_levels": [float(v) for v in levels if float(v) not in active_set],
        "iterations": int(tested),
        "start_n": int(len(levels)),
        "qc_metrics": best["qc_metrics"],
        "qc_pass": best["qc_pass"],
        "search_mode": "Exhaustive contiguous",
    }


def _fit_pair_iterative(x, ratio, criteria, max_iterations=50):
    """Greedy Stage-2 fit: remove the worst-bias concentration level until calibration criteria pass."""
    x = np.asarray(x, float)
    ratio = np.asarray(ratio, float)
    valid = np.isfinite(x) & np.isfinite(ratio) & (x > 0)
    x = x[valid]; ratio = ratio[valid]
    if len(x) == 0:
        return None

    active_levels = sorted(np.unique(x).astype(float).tolist())
    start_levels = list(active_levels)
    last = None
    iteration = 0

    while len(active_levels) >= int(criteria.min_calibrators) and iteration < int(max_iterations):
        iteration += 1
        mask = np.isin(x, active_levels)
        metrics = _fit_candidate(x[mask], ratio[mask], criteria)
        if metrics is None:
            break
        last = metrics
        if metrics["pass_cal"] or len(active_levels) <= int(criteria.min_calibrators):
            break

        backcalc = metrics["fit"].invert(ratio[mask])
        bias = (backcalc - x[mask]) / x[mask] * 100.0
        finite = np.isfinite(bias)
        if not finite.any():
            break
        active_x = x[mask]
        worst_pos = np.flatnonzero(finite)[int(np.argmax(np.abs(bias[finite])))]
        worst_level = float(active_x[worst_pos])
        active_levels = [lv for lv in active_levels if float(lv) != worst_level]

    final_mask = np.isin(x, active_levels)
    if final_mask.sum() >= int(criteria.min_calibrators):
        final_metrics = _fit_candidate(x[final_mask], ratio[final_mask], criteria)
        if final_metrics is not None:
            last = final_metrics
    if last is None:
        return None

    active_set = set(float(v) for v in active_levels)
    return {
        "metrics": last,
        "active_levels": [float(v) for v in active_levels],
        "removed_levels": [float(v) for v in start_levels if float(v) not in active_set],
        "iterations": int(iteration),
        "start_n": int(len(start_levels)),
    }


def _primary_flag_excluded(series):
    """TargetLynx calibrator exclusion flags: X or lowercase l."""
    text = series.fillna("").astype(str).str.strip()
    return text.str.contains("X", regex=False) | text.str.contains("l", regex=False)


def _targetlynx_candidate_levels(data, analyte):
    """Levels retained by the user's TargetLynx Primary Flags for one analyte."""
    if "Primary Flags" not in data.columns:
        return []
    rows = (
        _sample_type_mask(data["Sample Type"], "cal")
        & data["Component"].astype(str).eq(str(analyte))
    )
    x = data.loc[rows].copy()
    if x.empty:
        return []
    nominal = _num(x["Nominal"])
    area = _num(x["Area"])
    excluded = _primary_flag_excluded(x["Primary Flags"])
    valid = np.isfinite(nominal) & np.isfinite(area) & (nominal > 0) & ~excluded.to_numpy(bool)
    return sorted(np.unique(nominal[valid].to_numpy(float)).tolist())


def analyze_surrogate_is(normalized, criteria=None, component_mapping=None, qc_sample_mapping=None, user_amr=None, calibrator_source_mode="Stage 1", analyte_fit_settings=None, pair_search_mode="Exhaustive contiguous"):
    criteria = criteria or SurrogateCriteria()
    data = apply_component_mapping(normalized, component_mapping)
    data = apply_qc_sample_mapping(data, qc_sample_mapping)
    cal_rows = _sample_type_mask(data["Sample Type"], "cal")
    qc_rows = _sample_type_mask(data["Sample Type"], "qc")
    if not cal_rows.any(): raise ValueError("No calibrator/standard rows were detected.")
    if not qc_rows.any(): raise ValueError("No QC rows were detected.")

    cal_area = _pivot(data, cal_rows); qc_area = _pivot(data, qc_rows)
    cal_rt = _rt_pivot(data, cal_rows); qc_rt = _rt_pivot(data, qc_rows)
    cal_nom = _analyte_nominals(data, cal_rows); qc_nom = _analyte_nominals(data, qc_rows)
    qc_meta = _sample_metadata(data, qc_rows)

    # Align once so all cached NumPy columns refer to identical sample rows.
    cal_index = cal_area.index.intersection(cal_nom.index)
    qc_index = qc_area.index.intersection(qc_nom.index)
    cal_area = cal_area.reindex(cal_index)
    cal_nom = cal_nom.reindex(cal_index)
    if not cal_rt.empty:
        cal_rt = cal_rt.reindex(cal_index)
    qc_area = qc_area.reindex(qc_index)
    qc_nom = qc_nom.reindex(qc_index)
    if not qc_rt.empty:
        qc_rt = qc_rt.reindex(qc_index)
    qc_meta = qc_meta.reindex(qc_index)
    analytes = [c for c in cal_nom.columns if c in cal_area.columns]
    is_names = sorted(data.loc[data["Component Role"] == "IS", "Component"].astype(str).unique())
    if not analytes: raise ValueError("No analyte components with calibration concentrations were detected.")
    if not is_names: raise ValueError("No internal-standard components were detected.")
    groups = _group_lookup(data)
    amr_lookup = user_amr_lookup(user_amr)

    # Convert wide numeric tables once. Repeated pandas coercion inside thousands
    # of analyte × IS loops creates substantial temporary-object churn.
    cal_area_np = {str(c): _num(cal_area[c]).to_numpy(float) for c in cal_area.columns}
    qc_area_np = {str(c): _num(qc_area[c]).to_numpy(float) for c in qc_area.columns}
    cal_nom_np = {str(c): _num(cal_nom[c]).to_numpy(float) for c in cal_nom.columns}
    qc_nom_np = {str(c): _num(qc_nom[c]).to_numpy(float) for c in qc_nom.columns}
    cal_rt_np = {str(c): _num(cal_rt[c]).to_numpy(float) for c in cal_rt.columns} if not cal_rt.empty else {}
    is_meta = (
        data.loc[data["Component Role"] == "IS", ["Component", "IS Class", "Paired Analyte"]]
        .drop_duplicates("Component").set_index("Component")
        if "IS Class" in data.columns else pd.DataFrame()
    )

    rankings = []; stage1_rows = []; stage1_levels = {}; stage1_sources = {}
    auto_pair_exclusions = {}; stage2_iterations = {}
    for analyte in analytes:
        analyte_criteria = _criteria_for_analyte(criteria, analyte, analyte_fit_settings)
        idx = cal_area.index.intersection(cal_nom.index)
        x = _num(cal_nom.loc[idx, analyte]); y = _num(cal_area.loc[idx, analyte])
        valid = np.isfinite(x) & np.isfinite(y) & (x > 0)
        if calibrator_source_mode == "TargetLynx Primary Flags":
            levels = _targetlynx_candidate_levels(data, analyte)
            xd = np.asarray(x[valid], float); yd = np.asarray(y[valid], float)
            level_mask = np.isin(xd, levels)
            s1 = _fit_candidate(xd[level_mask], yd[level_mask], analyte_criteria) if int(level_mask.sum()) >= analyte_criteria.min_calibrators else None
            amr_source = "TargetLynx Primary Flags"
        elif str(analyte) in amr_lookup:
            user_lloq, user_uloq = amr_lookup[str(analyte)]
            xd = np.asarray(x[valid], float); yd = np.asarray(y[valid], float)
            level_mask = (xd >= user_lloq) & (xd <= user_uloq)
            levels = sorted(np.unique(xd[level_mask]).astype(float).tolist())
            s1 = _fit_candidate(xd[level_mask], yd[level_mask], analyte_criteria) if int(level_mask.sum()) >= analyte_criteria.min_calibrators else None
            amr_source = "User-defined"
        else:
            levels, s1 = select_stage1_levels(x[valid], y[valid], analyte_criteria)
            amr_source = "Automatic"
        stage1_rows.append({
            "Analyte": analyte, "Group": groups.get(analyte, analyte),
            "AMR Source": amr_source,
            "Regression Model": analyte_criteria.model_name,
            "Origin Handling": analyte_criteria.origin_mode,
            "Stage 1 Pass": bool(levels), "Stage 1 LLOQ": min(levels) if levels else np.nan,
            "Stage 1 ULOQ": max(levels) if levels else np.nan, "Stage 1 n": len(levels),
            "Stage 1 Max |Bias| %": s1["max_cal_abs_bias_pct"] if s1 else np.nan,
            "Stage 1 Fit R2": s1["fit_r2"] if s1 else np.nan,
        })
        stage1_levels[str(analyte)] = list(map(float, levels))
        stage1_sources[str(analyte)] = amr_source
        if not levels: continue

        matched_sil = _matched_sil_name(is_meta, analyte)
        matched_sil_fit = None
        matched_sil_iter = None
        if matched_sil and str(matched_sil) in cal_area_np:
            xa_sil = cal_nom_np[str(analyte)]
            aa_sil = cal_area_np[str(analyte)]
            ia_sil = cal_area_np[str(matched_sil)]
            sil_valid = (
                np.isfinite(xa_sil) & np.isfinite(aa_sil) & np.isfinite(ia_sil)
                & (xa_sil > 0) & (ia_sil > 0) & np.isin(xa_sil, levels)
            )
            if int(sil_valid.sum()) >= analyte_criteria.min_calibrators:
                sil_x = xa_sil[sil_valid]
                sil_ratio = aa_sil[sil_valid] / ia_sil[sil_valid]

                # Select the matched-SIL reference curve once per analyte.
                # Its own QC performance is assessed against nominal
                # concentration for range selection; once selected, its
                # calculated QC concentrations become the reference values
                # for every surrogate pair.
                sil_qratio = sil_qnom = sil_qref = None
                if (
                    str(analyte) in qc_area_np
                    and str(matched_sil) in qc_area_np
                    and str(analyte) in qc_nom_np
                ):
                    qa_ref = qc_area_np[str(analyte)]
                    qi_ref = qc_area_np[str(matched_sil)]
                    qn_ref = qc_nom_np[str(analyte)]
                    qv_ref = (
                        np.isfinite(qa_ref) & np.isfinite(qi_ref) & np.isfinite(qn_ref)
                        & (qi_ref > 0) & (qn_ref > 0)
                    )
                    sil_qratio = qa_ref[qv_ref] / qi_ref[qv_ref]
                    sil_qnom = qn_ref[qv_ref]
                    sil_qref = sil_qnom.copy()

                if pair_search_mode == "Exhaustive contiguous":
                    matched_sil_iter = _fit_pair_contiguous_search(
                        sil_x, sil_ratio, analyte_criteria,
                        qc_ratio=sil_qratio, qc_nominal=sil_qnom, qc_reference=sil_qref,
                    )
                else:
                    matched_sil_iter = _fit_pair_iterative(
                        sil_x, sil_ratio, analyte_criteria
                    )
                if matched_sil_iter is not None:
                    matched_sil_fit = matched_sil_iter["metrics"]

        for is_name in is_names:
            if is_name not in cal_area.columns: continue
            xa = cal_nom_np[str(analyte)]
            aa = cal_area_np[str(analyte)]
            ia = cal_area_np[str(is_name)]
            valid = np.isfinite(xa) & np.isfinite(aa) & np.isfinite(ia) & (xa > 0) & (ia > 0) & np.isin(xa, levels)
            if int(valid.sum()) < analyte_criteria.min_calibrators: continue
            xstart = xa[valid]; rstart = aa[valid] / ia[valid]

            # Prepare all QC values once so exhaustive contiguous search can
            # compare candidate windows using both calibration and QC performance.
            qa_all = qc_area_np.get(str(analyte))
            qi_all = qc_area_np.get(str(is_name))
            qn_all = qc_nom_np.get(str(analyte))
            qratio_all = qnom_all = qref_all = None
            if qa_all is not None and qi_all is not None and qn_all is not None:
                qbase = (
                    np.isfinite(qa_all) & np.isfinite(qi_all) & np.isfinite(qn_all)
                    & (qi_all > 0) & (qn_all > 0)
                )
                qratio_all = qa_all[qbase] / qi_all[qbase]
                qnom_all = qn_all[qbase]
                qref_all = qnom_all.copy()
                if analyte_criteria.qc_reference_basis == "Matched SIL-IS calculated concentration":
                    if matched_sil_fit is not None and matched_sil in qc_area_np:
                        qsil_all = qc_area_np[str(matched_sil)]
                        qbase = qbase & np.isfinite(qsil_all) & (qsil_all > 0)
                        qratio_all = qa_all[qbase] / qi_all[qbase]
                        qnom_all = qn_all[qbase]
                        sil_ratio_all = qa_all[qbase] / qsil_all[qbase]
                        qref_all = matched_sil_fit["fit"].invert(sil_ratio_all)
                    else:
                        qref_all = np.full_like(qnom_all, np.nan, dtype=float)

            if (
                analyte_criteria.qc_reference_basis == "Matched SIL-IS calculated concentration"
                and matched_sil_iter is not None
                and str(is_name) == str(matched_sil)
            ):
                # Reuse the exact reference fit for the analyte's own SIL-IS
                # pair. This guarantees that own-SIL calculated concentration
                # and matched-SIL reference concentration are identical.
                iterative = matched_sil_iter
            elif pair_search_mode == "Exhaustive contiguous":
                iterative = _fit_pair_contiguous_search(
                    xstart, rstart, analyte_criteria,
                    qc_ratio=qratio_all, qc_nominal=qnom_all, qc_reference=qref_all,
                )
            else:
                iterative = _fit_pair_iterative(xstart, rstart, analyte_criteria)
            if iterative is None: continue
            m = iterative["metrics"]
            fit = m["fit"]
            pair_key = (str(analyte), str(is_name))
            stage1_set = set(float(v) for v in levels)
            kept_set = set(float(v) for v in iterative["active_levels"])
            auto_pair_exclusions[pair_key] = sorted(stage1_set - kept_set)
            stage2_iterations[pair_key] = int(iterative["iterations"])
            reference_basis = criteria.qc_reference_basis

            qidx = qc_area.index.intersection(qc_nom.index)
            if analyte in qc_area.columns and is_name in qc_area.columns and analyte in qc_nom.columns:
                qa = qc_area_np[str(analyte)]
                qi = qc_area_np[str(is_name)]
                qn = qc_nom_np[str(analyte)]
                qvalid = np.isfinite(qa) & np.isfinite(qi) & np.isfinite(qn) & (qi > 0) & (qn >= m["lloq"]) & (qn <= m["uloq"])
                qratio = qa[qvalid] / qi[qvalid]
                qnom = qn[qvalid]; qcalc = fit.invert(qratio)
                qref = qnom.copy()
                reference_basis = "Nominal concentration"
                if criteria.qc_reference_basis == "Matched SIL-IS calculated concentration":
                    if (
                        matched_sil_fit is not None
                        and matched_sil in qc_area.columns
                        and str(is_name) == str(matched_sil)
                    ):
                        # The own SIL-IS pair defines the matched-SIL reference.
                        # Reusing qcalc avoids comparing two independently
                        # selected/fitted versions of the same reference curve.
                        qref = qcalc.copy()
                        reference_basis = "Matched SIL-IS calculated concentration"
                    elif matched_sil_fit is not None and matched_sil in qc_area.columns:
                        qsil = qc_area_np[str(matched_sil)]
                        sil_valid_values = qsil[qvalid]
                        qa_values = qa[qvalid]
                        sil_ratio = qa_values / sil_valid_values
                        qref = matched_sil_fit["fit"].invert(sil_ratio)
                        reference_basis = "Matched SIL-IS calculated concentration"
                    else:
                        qref = np.full_like(qnom, np.nan, dtype=float)
                        reference_basis = "Matched SIL-IS unavailable"
                qs = _qc_metrics(qcalc, qref, qnom)
            else:
                qs = {}

            qc_pass = bool(qs) and (
                np.isfinite(qs.get("qc_mean_abs_bias_pct", np.nan))
                and qs["qc_mean_abs_bias_pct"] <= criteria.max_qc_mean_abs_bias
                and np.isfinite(qs.get("qc_max_abs_bias_pct", np.nan))
                and qs["qc_max_abs_bias_pct"] <= criteria.max_qc_abs_bias
                and (not np.isfinite(qs.get("qc_max_cv_pct", np.nan)) or qs["qc_max_cv_pct"] <= criteria.max_qc_cv)
            )
            is_class = str(is_meta.loc[is_name, "IS Class"]) if len(is_meta) and is_name in is_meta.index else ""
            paired_analyte = str(is_meta.loc[is_name, "Paired Analyte"]) if len(is_meta) and is_name in is_meta.index else ""
            own_sil = bool(is_class == "SIL-IS" and paired_analyte == str(analyte))
            pair_type = "Own SIL-IS" if own_sil else "Surrogate"
            rt_delta = np.nan
            if str(analyte) in cal_rt_np and str(is_name) in cal_rt_np:
                art = cal_rt_np[str(analyte)]; irt = cal_rt_np[str(is_name)]
                rv = np.isfinite(art) & np.isfinite(irt)
                if rv.any():
                    rt_delta = float(np.nanmedian(np.abs(art[rv] - irt[rv])))
            row = {
                "Analyte": analyte, "Group": groups.get(analyte, analyte), "Internal Standard": is_name,
                "Regression Model": analyte_criteria.model_name,
                "Origin Handling": analyte_criteria.origin_mode,
                "Pair Type": pair_type,
                "IS Identity": is_class or "Unclassified",
                "Paired Analyte": paired_analyte,
                "Median |ΔRT|": rt_delta,
                "QC Reference": reference_basis,
                "AMR Source": "Stage 2 iterative" if iterative["removed_levels"] else stage1_sources.get(str(analyte), "Automatic"),
                "Stage 2 Iterations": int(iterative["iterations"]),
                "Stage 2 Removed": int(len(iterative["removed_levels"])),
                "Pass": bool(m["pass_cal"] and qc_pass), "Calibration Pass": bool(m["pass_cal"]), "QC Pass": qc_pass,
                "n Cal": m["n_cal"], "LLOQ": m["lloq"], "ULOQ": m["uloq"], "Span Ratio": m["uloq"] / m["lloq"],
                "Min Cal Bias %": m.get("min_cal_bias_pct", np.nan),
                "Max Cal Bias %": m.get("max_cal_bias_pct", np.nan),
                "Min Cal |Bias| %": m.get("min_cal_abs_bias_pct", np.nan),
                "Max Cal |Bias| %": m["max_cal_abs_bias_pct"],
                "Mean Cal |Bias| %": m["mean_cal_abs_bias_pct"],
                "Fit R2": m["fit_r2"], "Weighted R2": m["weighted_r2"], "QC n": qs.get("qc_n", 0),
                "QC Levels": qs.get("qc_levels", 0),
                "QC Min Bias %": qs.get("qc_min_bias_pct", np.nan),
                "QC Max Bias %": qs.get("qc_max_bias_pct", np.nan),
                "QC Min |Bias| %": qs.get("qc_min_abs_bias_pct", np.nan),
                "QC Mean |Bias| %": qs.get("qc_mean_abs_bias_pct", np.nan),
                "QC Max |Bias| %": qs.get("qc_max_abs_bias_pct", np.nan),
                "QC Min CV %": qs.get("qc_min_cv_pct", np.nan),
                "QC Mean CV %": qs.get("qc_mean_cv_pct", np.nan),
                "QC Max CV %": qs.get("qc_max_cv_pct", np.nan),
            }
            rankings.append(row)

    analyte_rt = {str(a): _median_component_rt(cal_rt, a) for a in analytes}
    is_rt = {str(i): _median_component_rt(cal_rt, i) for i in is_names}

    ranking = pd.DataFrame(rankings)
    if not ranking.empty:
        ranking = ranking.sort_values(
            ["Analyte", "Pass", "QC Mean |Bias| %", "QC Max CV %", "Max Cal |Bias| %"],
            ascending=[True, False, True, True, True], na_position="last"
        ).reset_index(drop=True)
    return {
        "ranking": ranking, "stage1": pd.DataFrame(stage1_rows),
        "criteria": criteria, "analytes": analytes, "internal_standards": is_names,
        "analyte_rt": analyte_rt, "is_rt": is_rt,
        "is_metadata": is_meta.reset_index() if len(is_meta) else pd.DataFrame(),
        "pair_count_requested": int(len(analytes) * len(is_names)),
        "qc_sample_mapping": qc_sample_mapping,
        "user_amr": user_amr,
        "calibrator_source_mode": calibrator_source_mode,
        "analyte_fit_settings": analyte_fit_settings or {},
        "pair_search_mode": pair_search_mode,
        "stage1_levels": stage1_levels,
        "stage1_sources": stage1_sources,
        "auto_pair_exclusions": auto_pair_exclusions,
        "stage2_iterations": stage2_iterations,
        "manual_exclusions": {},
        "_cache": {
            "cal_area": cal_area, "qc_area": qc_area,
            "cal_rt": cal_rt, "qc_rt": qc_rt,
            "cal_nom": cal_nom, "qc_nom": qc_nom, "qc_meta": qc_meta,
        },
    }


def _usable_pair_levels(result, analyte, is_name):
    """Return all positive calibrator levels with usable analyte and IS responses for a pair."""
    cache = result.get("_cache", {})
    cal_area = cache.get("cal_area"); cal_nom = cache.get("cal_nom")
    if cal_area is None or cal_nom is None:
        return []
    if analyte not in cal_area.columns or analyte not in cal_nom.columns or is_name not in cal_area.columns:
        return []
    idx = cal_area.index.intersection(cal_nom.index)
    xa = _num(cal_nom.loc[idx, analyte])
    aa = _num(cal_area.loc[idx, analyte])
    ia = _num(cal_area.loc[idx, is_name])
    valid = np.isfinite(xa) & np.isfinite(aa) & np.isfinite(ia) & (xa > 0) & (ia > 0)
    return sorted(np.unique(xa[valid].to_numpy(float)).tolist())


def _effective_pair_levels(result, analyte, is_name):
    """Return the current effective levels for a pair, honoring manual edits then automatic Stage 2 trimming."""
    all_levels = _usable_pair_levels(result, analyte, is_name)
    if not all_levels:
        return []
    key = (str(analyte), str(is_name))
    manual = result.get("manual_exclusions", {})
    if key in manual:
        excluded = set(float(v) for v in manual.get(key, []))
        return [float(v) for v in all_levels if float(v) not in excluded]

    stage1 = set(float(v) for v in result.get("stage1_levels", {}).get(str(analyte), []))
    auto_removed = set(
        float(v) for v in result.get("auto_pair_exclusions", {}).get(key, [])
    )
    return [
        float(v) for v in all_levels
        if float(v) in stage1 and float(v) not in auto_removed
    ]


def compute_pair_detail(result, analyte, is_name):
    """Recompute detailed calibration/QC data for one selected pair only.

    Bulk analysis intentionally stores only compact pair summaries. This
    function reconstructs the fit and QC sample tables on demand so memory
    usage does not scale with pair_count × QC_rows.
    """
    base_criteria = result["criteria"]
    criteria = _criteria_for_analyte(
        base_criteria, analyte, result.get("analyte_fit_settings", {})
    )
    cache = result.get("_cache", {})
    cal_area = cache.get("cal_area"); qc_area = cache.get("qc_area")
    cal_rt = cache.get("cal_rt"); qc_rt = cache.get("qc_rt")
    cal_nom = cache.get("cal_nom"); qc_nom = cache.get("qc_nom")
    qc_meta = cache.get("qc_meta")
    if any(x is None for x in (cal_area, qc_area, cal_nom, qc_nom)):
        raise ValueError("Detailed pair cache is unavailable.")

    levels = result.get("stage1_levels", {}).get(str(analyte), [])
    if not levels:
        raise ValueError(f"No Stage 1 calibration range is available for {analyte}.")

    all_levels = _usable_pair_levels(result, analyte, is_name)
    if not all_levels:
        raise ValueError("No usable calibrator levels are available for this pair.")

    key = (str(analyte), str(is_name))
    active_levels = _effective_pair_levels(result, analyte, is_name)
    active_set = set(float(v) for v in active_levels)
    excluded = set(float(v) for v in all_levels if float(v) not in active_set)

    idx = cal_area.index.intersection(cal_nom.index)
    xa = _num(cal_nom.loc[idx, analyte]); aa = _num(cal_area.loc[idx, analyte])
    ia = _num(cal_area.loc[idx, is_name])
    valid = np.isfinite(xa) & np.isfinite(aa) & np.isfinite(ia) & (xa > 0) & (ia > 0) & xa.isin(active_levels)
    if int(valid.sum()) < criteria.min_calibrators:
        raise ValueError("Too few usable calibrators for this pair.")

    xfit = xa[valid].to_numpy(float)
    ratio = (aa[valid] / ia[valid]).to_numpy(float)
    metrics = _fit_candidate(xfit, ratio, criteria)
    if metrics is None:
        raise ValueError("The selected pair could not be fitted.")
    fit = metrics["fit"]

    is_meta = result.get("is_metadata", pd.DataFrame())
    matched_sil = ""
    if is_meta is not None and len(is_meta):
        sil = is_meta[
            is_meta["IS Class"].astype(str).eq("SIL-IS")
            & is_meta["Paired Analyte"].astype(str).eq(str(analyte))
        ]
        if len(sil):
            matched_sil = str(sil.iloc[0]["Component"])
    matched_sil_levels = (
        _effective_pair_levels(result, analyte, matched_sil) if matched_sil else []
    )
    matched_sil_metrics = _fit_pair_from_cache(
        cal_area, cal_nom, analyte, matched_sil, matched_sil_levels, criteria
    ) if matched_sil and matched_sil_levels else None

    qidx = qc_area.index.intersection(qc_nom.index)
    sample_detail = pd.DataFrame()
    by_level = pd.DataFrame()
    if analyte in qc_area.columns and is_name in qc_area.columns and analyte in qc_nom.columns:
        qa = _num(qc_area.loc[qidx, analyte]); qi = _num(qc_area.loc[qidx, is_name])
        qn = _num(qc_nom.loc[qidx, analyte])
        qvalid = np.isfinite(qa) & np.isfinite(qi) & np.isfinite(qn) & (qi > 0) & (qn >= metrics["lloq"]) & (qn <= metrics["uloq"])
        qratio = (qa[qvalid] / qi[qvalid]).to_numpy(float)
        qnom = qn[qvalid].to_numpy(float)
        qcalc = fit.invert(qratio)
        qref = qnom.copy()
        reference_basis = "Nominal concentration"
        if criteria.qc_reference_basis == "Matched SIL-IS calculated concentration":
            if matched_sil_metrics is not None and matched_sil in qc_area.columns:
                qsil = _num(qc_area.loc[qidx, matched_sil])
                sil_area = qsil[qvalid].to_numpy(float)
                ana_area = qa[qvalid].to_numpy(float)
                qref = matched_sil_metrics["fit"].invert(ana_area / sil_area)
                reference_basis = "Matched SIL-IS calculated concentration"
            else:
                qref = np.full_like(qnom, np.nan, dtype=float)
                reference_basis = "Matched SIL-IS unavailable"
        by_level, _ = _qc_summary(qcalc, qref, qnom)
        selected_index = qidx[qvalid]
        if qc_meta is not None:
            md = qc_meta.reindex(selected_index)
            sample_detail = pd.DataFrame({
                "Name": md["Name"].fillna("").astype(str).to_numpy(),
                "ID": md["ID"].fillna("").astype(str).to_numpy(),
                "Sample Text": md["Sample Text"].fillna("").astype(str).to_numpy(),
                "Type": md["Type"].fillna("").astype(str).to_numpy(),
                "Sample Key": [i[0] for i in selected_index],
                "Nominal": qnom,
                "Ratio": qratio,
                "Calculated": qcalc,
            })
        else:
            sample_detail = pd.DataFrame({
                "Name": [i[1] for i in selected_index],
                "ID": "",
                "Sample Text": "",
                "Type": "",
                "Sample Key": [i[0] for i in selected_index],
                "Nominal": qnom,
                "Ratio": qratio,
                "Calculated": qcalc,
            })
        sample_detail["Reference concentration"] = qref
        sample_detail["Reference basis"] = reference_basis
        if qc_rt is not None and not qc_rt.empty:
            art = _num(qc_rt.reindex(selected_index)[analyte]) if analyte in qc_rt.columns else pd.Series(np.nan, index=selected_index)
            irt = _num(qc_rt.reindex(selected_index)[is_name]) if is_name in qc_rt.columns else pd.Series(np.nan, index=selected_index)
            sample_detail["Analyte RT"] = art.to_numpy(float)
            sample_detail["IS RT"] = irt.to_numpy(float)
            sample_detail["ΔRT"] = sample_detail["Analyte RT"] - sample_detail["IS RT"]
        sample_detail["Bias %"] = (
            (sample_detail["Calculated"] - sample_detail["Reference concentration"])
            / sample_detail["Reference concentration"] * 100.0
        )
        sample_detail["|Bias| %"] = np.abs(sample_detail["Bias %"])
        sample_detail["Individual Pass"] = (
            sample_detail["|Bias| %"] <= float(criteria.max_qc_abs_bias)
        )

    ranking = result.get("ranking", pd.DataFrame())
    match = ranking[
        (ranking["Analyte"].astype(str) == str(analyte))
        & (ranking["Internal Standard"].astype(str) == str(is_name))
    ]
    summary = match.iloc[0].to_dict() if len(match) else {}

    backcalc = fit.invert(ratio)
    cal_detail = pd.DataFrame({
        "Use": [True] * len(xfit),
        "Nominal": xfit,
        "Ratio": ratio,
        "Back-calculated": backcalc,
    })
    if cal_rt is not None and not cal_rt.empty:
        cidx = idx[valid]
        art = _num(cal_rt.reindex(cidx)[analyte]) if analyte in cal_rt.columns else pd.Series(np.nan, index=cidx)
        irt = _num(cal_rt.reindex(cidx)[is_name]) if is_name in cal_rt.columns else pd.Series(np.nan, index=cidx)
        cal_detail["Analyte RT"] = art.to_numpy(float)
        cal_detail["IS RT"] = irt.to_numpy(float)
        cal_detail["ΔRT"] = cal_detail["Analyte RT"] - cal_detail["IS RT"]
    cal_detail["Bias %"] = (cal_detail["Back-calculated"] - cal_detail["Nominal"]) / cal_detail["Nominal"] * 100.0
    cal_detail["|Bias| %"] = np.abs(cal_detail["Bias %"])
    # Add excluded Stage-1 levels back to the table for transparent manual editing.
    if excluded:
        all_valid = np.isfinite(xa) & np.isfinite(aa) & np.isfinite(ia) & (xa > 0) & (ia > 0) & xa.isin(all_levels)
        ex_mask = all_valid & xa.isin(list(excluded))
        if int(ex_mask.sum()):
            ex_x = xa[ex_mask].to_numpy(float)
            ex_ratio = (aa[ex_mask] / ia[ex_mask]).to_numpy(float)
            ex_calc = fit.invert(ex_ratio)
            ex_df = pd.DataFrame({
                "Use": [False] * len(ex_x),
                "Nominal": ex_x,
                "Ratio": ex_ratio,
                "Back-calculated": ex_calc,
            })
            ex_df["Bias %"] = (ex_df["Back-calculated"] - ex_df["Nominal"]) / ex_df["Nominal"] * 100.0
            ex_df["|Bias| %"] = np.abs(ex_df["Bias %"])
            cal_detail = pd.concat([cal_detail, ex_df], ignore_index=True).sort_values("Nominal").reset_index(drop=True)

    return {
        "fit": fit,
        "x_cal": xfit,
        "ratio_cal": ratio,
        "calibrators": cal_detail,
        "qc_by_level": by_level,
        "qc_samples": sample_detail,
        "summary": summary,
    }


def refit_pair_with_exclusions(result, analyte, is_name, excluded_nominals):
    """Apply manual calibrator exclusions to one pair and refresh its ranking summary."""
    key = (str(analyte), str(is_name))
    result.setdefault("manual_exclusions", {})[key] = sorted({float(v) for v in excluded_nominals})
    detail = compute_pair_detail(result, analyte, is_name)
    fit = detail["fit"]
    cal = detail["calibrators"]
    criteria = _criteria_for_analyte(
        result["criteria"], analyte, result.get("analyte_fit_settings", {})
    )

    max_bias = float(cal.loc[cal["Use"], "|Bias| %"].max()) if cal["Use"].any() else np.nan
    mean_bias = float(cal.loc[cal["Use"], "|Bias| %"].mean()) if cal["Use"].any() else np.nan
    r2 = float(fit.stats.get("fit_r2", np.nan))
    wr2 = float(fit.stats.get("weighted_r2", np.nan))
    qc = detail["qc_samples"]
    by, qs = _qc_summary(
        qc["Calculated"].to_numpy(float),
        qc["Reference concentration"].to_numpy(float) if "Reference concentration" in qc.columns else qc["Nominal"].to_numpy(float),
        qc["Nominal"].to_numpy(float),
    ) if not qc.empty else (pd.DataFrame(), {})
    qc_pass = bool(qs) and (
        np.isfinite(qs.get("qc_mean_abs_bias_pct", np.nan))
        and qs["qc_mean_abs_bias_pct"] <= criteria.max_qc_mean_abs_bias
        and np.isfinite(qs.get("qc_max_abs_bias_pct", np.nan))
        and qs["qc_max_abs_bias_pct"] <= criteria.max_qc_abs_bias
        and (not np.isfinite(qs.get("qc_max_cv_pct", np.nan)) or qs["qc_max_cv_pct"] <= criteria.max_qc_cv)
    )
    active = cal.loc[cal["Use"], "Nominal"].to_numpy(float)
    cal_pass = (
        len(active) >= criteria.min_calibrators
        and np.isfinite(max_bias) and max_bias <= criteria.max_calibrator_bias
        and np.isfinite(r2) and r2 >= criteria.min_r2
    )

    ranking = result["ranking"]
    mask = (
        ranking["Analyte"].astype(str).eq(str(analyte))
        & ranking["Internal Standard"].astype(str).eq(str(is_name))
    )
    if mask.any():
        updates = {
            "AMR Source": "Manual edited",
            "Pass": bool(cal_pass and qc_pass),
            "Calibration Pass": bool(cal_pass),
            "QC Pass": bool(qc_pass),
            "n Cal": int(len(active)),
            "LLOQ": float(np.min(active)) if len(active) else np.nan,
            "ULOQ": float(np.max(active)) if len(active) else np.nan,
            "Span Ratio": float(np.max(active) / np.min(active)) if len(active) else np.nan,
            "Min Cal Bias %": float(cal.loc[cal["Use"], "Bias %"].min()) if cal["Use"].any() else np.nan,
            "Max Cal Bias %": float(cal.loc[cal["Use"], "Bias %"].max()) if cal["Use"].any() else np.nan,
            "Min Cal |Bias| %": float(cal.loc[cal["Use"], "|Bias| %"].min()) if cal["Use"].any() else np.nan,
            "Max Cal |Bias| %": max_bias,
            "Mean Cal |Bias| %": mean_bias,
            "Fit R2": r2,
            "Weighted R2": wr2,
            "QC n": qs.get("qc_n", 0),
            "QC Levels": qs.get("qc_levels", 0),
            "QC Min Bias %": qs.get("qc_min_bias_pct", np.nan),
            "QC Max Bias %": qs.get("qc_max_bias_pct", np.nan),
            "QC Min |Bias| %": qs.get("qc_min_abs_bias_pct", np.nan),
            "QC Mean |Bias| %": qs.get("qc_mean_abs_bias_pct", np.nan),
            "QC Max |Bias| %": qs.get("qc_max_abs_bias_pct", np.nan),
            "QC Min CV %": qs.get("qc_min_cv_pct", np.nan),
            "QC Mean CV %": qs.get("qc_mean_cv_pct", np.nan),
            "QC Max CV %": qs.get("qc_max_cv_pct", np.nan),
        }
        for col, value in updates.items():
            result["ranking"].loc[mask, col] = value
    return compute_pair_detail(result, analyte, is_name)


def sync_pair_amr_to_surrogates(result, analyte, source_is):
    """Copy the selected pair's manual calibrator exclusions to all IS pairs for one analyte."""
    key = (str(analyte), str(source_is))
    manual = result.get("manual_exclusions", {})
    if key in manual:
        exclusions = list(manual.get(key, []))
    else:
        all_levels = _usable_pair_levels(result, analyte, source_is)
        stage1 = set(float(v) for v in result.get("stage1_levels", {}).get(str(analyte), []))
        auto_removed = set(
            float(v) for v in result.get("auto_pair_exclusions", {}).get(key, [])
        )
        exclusions = [
            float(v) for v in all_levels
            if float(v) not in stage1 or float(v) in auto_removed
        ]
    ranking = result.get("ranking", pd.DataFrame())
    if ranking.empty:
        return {"updated": 0, "failed": []}

    targets = ranking.loc[
        ranking["Analyte"].astype(str).eq(str(analyte)),
        "Internal Standard",
    ].astype(str).drop_duplicates().tolist()

    updated = 0
    failed = []
    for is_name in targets:
        try:
            refit_pair_with_exclusions(result, analyte, is_name, exclusions)
            updated += 1
        except Exception as exc:
            failed.append((is_name, str(exc)))
    return {"updated": updated, "failed": failed, "exclusions": exclusions}


def _median_component_rt(rt_table, component):
    if rt_table is None or getattr(rt_table, "empty", True) or component not in rt_table.columns:
        return np.nan
    vals = _num(rt_table[component]).to_numpy(float)
    vals = vals[np.isfinite(vals)]
    return float(np.nanmedian(vals)) if vals.size else np.nan


def pair_metric_matrix(result, metric="QC Mean |Bias| %", order="Retention time"):
    r = result.get("ranking", pd.DataFrame())
    if r.empty or metric not in r.columns:
        return pd.DataFrame()
    matrix = r.pivot_table(
        index="Analyte", columns="Internal Standard", values=metric, aggfunc="first"
    )

    if order == "Retention time":
        analyte_rt = result.get("analyte_rt", {})
        is_rt = result.get("is_rt", {})

        def rt_key(name, lookup):
            value = lookup.get(str(name), np.nan)
            return (0, float(value), str(name).casefold()) if np.isfinite(value) else (1, np.inf, str(name).casefold())

        matrix = matrix.reindex(
            index=sorted(matrix.index.tolist(), key=lambda n: rt_key(n, analyte_rt)),
            columns=sorted(matrix.columns.tolist(), key=lambda n: rt_key(n, is_rt)),
        )
    elif order == "Alphabetical":
        matrix = matrix.reindex(
            index=sorted(matrix.index.tolist(), key=lambda n: str(n).casefold()),
            columns=sorted(matrix.columns.tolist(), key=lambda n: str(n).casefold()),
        )
    return matrix


def export_surrogate_workbook(result, path):
    """Export compact summaries plus detailed QC rows without retaining all pairs in memory."""
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        result["ranking"].to_excel(writer, sheet_name="Pair Ranking", index=False)
        result["stage1"].to_excel(writer, sheet_name="Stage 1 Analytes", index=False)

        level_row = 0
        sample_row = 0
        level_header = True
        sample_header = True

        for _, rec in result["ranking"].iterrows():
            analyte = str(rec["Analyte"])
            is_name = str(rec["Internal Standard"])
            try:
                d = compute_pair_detail(result, analyte, is_name)
            except Exception:
                continue

            if not d["qc_by_level"].empty:
                x = d["qc_by_level"].copy()
                x.insert(0, "Internal Standard", is_name)
                x.insert(0, "Analyte", analyte)
                x.to_excel(
                    writer, sheet_name="QC By Level", index=False,
                    header=level_header, startrow=level_row,
                )
                level_row += len(x) + (1 if level_header else 0)
                level_header = False

            if not d["qc_samples"].empty:
                x = d["qc_samples"].copy()
                x.insert(0, "Internal Standard", is_name)
                x.insert(0, "Analyte", analyte)
                x.to_excel(
                    writer, sheet_name="QC Samples", index=False,
                    header=sample_header, startrow=sample_row,
                )
                sample_row += len(x) + (1 if sample_header else 0)
                sample_header = False

        criteria = result.get("criteria")
        if criteria is not None:
            pd.DataFrame(
                [{"Setting": k, "Value": v} for k, v in vars(criteria).items()]
            ).to_excel(writer, sheet_name="Criteria", index=False)
