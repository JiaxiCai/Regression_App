from __future__ import annotations

from dataclasses import dataclass
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
    out["Component"] = df["Compound"].astype(str)
    out["Component Group"] = df["Compound"].astype(str)
    is_flag = df.get("Is Internal Standard", False)
    if not isinstance(is_flag, pd.Series):
        is_flag = pd.Series(bool(is_flag), index=df.index)
    out["Component Role"] = np.where(is_flag.astype(bool), "IS", "Analyte")
    out["Auto Role"] = out["Component Role"]
    out["Nominal"] = _num(df.get("Std. Conc", np.nan))
    out["Area"] = _num(df["Area"])
    out["Injection"] = _num(df[inj_col]) if inj_col else np.arange(1, len(df) + 1)
    return out.reset_index(drop=True)


def normalize_generic_long(df):
    cols = list(df.columns)
    sample_index = _first_existing(cols, ["Sample Index", "Injection", "#", "ID"])
    sample_name = _first_existing(cols, ["Sample Name", "Name", "Sample Text"])
    sample_type = _first_existing(cols, ["Sample Type", "Type"])
    component_type = _first_existing(cols, ["Component Type", "Role"])
    component_name = _first_existing(cols, ["Component Name", "Compound", "Analyte"])
    component_group = _first_existing(cols, ["Component Group Name", "Component Group", "Analyte Group"])
    concentration = _first_existing(cols, ["Actual Concentration", "Std. Conc", "Nominal", "Concentration"])
    area = _first_existing(cols, ["Area", "Peak Area", "Response"])
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
    out["Injection"] = _num(df[injection]) if injection else np.arange(1, len(df) + 1)
    return out.reset_index(drop=True)


def component_mapping_table(normalized):
    """Return one editable setup row per detected component."""
    rows = []
    for component, g in normalized.groupby("Component", sort=True):
        auto = str(g.get("Auto Role", g["Component Role"]).iloc[0])
        rows.append({
            "Component": str(component),
            "Automatic Role": auto,
            "Role": str(g["Component Role"].iloc[0]),
            "Include": str(g["Component Role"].iloc[0]) != "Ignore",
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
    for _, row in mapping.iterrows():
        name = str(row["Component"])
        role = str(row.get("Role", row.get("Automatic Role", "Ignore")))
        include = bool(row.get("Include", True))
        role_map[name] = role
        include_map[name] = include

    data["Component Role"] = data["Component"].astype(str).map(role_map).fillna(data["Component Role"])
    keep = data["Component"].astype(str).map(include_map).fillna(True).astype(bool)
    keep &= data["Component Role"].astype(str).isin(["Analyte", "IS"])
    return data.loc[keep].copy()


def qc_sample_mapping_table(normalized):
    """Return one editable Include/Exclude row per detected QC sample."""
    qc = normalized.loc[_sample_type_mask(normalized["Sample Type"], "qc")].copy()
    if qc.empty:
        return pd.DataFrame(columns=["Sample Key", "Sample Name", "Sample Type", "Automatic Include", "Include"])

    rows = []
    for (sample_key, sample_name), g in qc.groupby(["Sample Key", "Sample Name"], sort=False):
        name_text = str(sample_name)
        # Conservative automatic exclusion for explicitly labeled IS-stress samples.
        normalized_name = name_text.casefold().replace("_", " ").replace("-", " ")
        auto_include = "low is" not in normalized_name
        rows.append({
            "Sample Key": str(sample_key),
            "Sample Name": name_text,
            "Sample Type": str(g["Sample Type"].iloc[0]),
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


def _pivot(normalized, rows):
    return normalized.loc[rows].pivot_table(
        index=["Sample Key", "Sample Name"], columns="Component", values="Area", aggfunc="first"
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
    max_bias = float(np.nanmax(np.abs(bias))) if np.isfinite(bias).any() else np.nan
    mean_abs = float(np.nanmean(np.abs(bias))) if np.isfinite(bias).any() else np.nan
    r2 = float(fit.stats.get("fit_r2", np.nan))
    wr2 = float(fit.stats.get("weighted_r2", np.nan))
    passed = (
        len(x) >= criteria.min_calibrators and np.isfinite(max_bias)
        and max_bias <= criteria.max_calibrator_bias
        and np.isfinite(r2) and r2 >= criteria.min_r2
    )
    return {
        "fit": fit, "n_cal": int(len(x)), "max_cal_abs_bias_pct": max_bias,
        "mean_cal_abs_bias_pct": mean_abs, "fit_r2": r2, "weighted_r2": wr2,
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


def _qc_summary(calc, nominal):
    d = pd.DataFrame({"calc": calc, "nominal": nominal}).replace([np.inf, -np.inf], np.nan).dropna()
    d = d[d["nominal"] > 0]
    if d.empty:
        return pd.DataFrame(), {}
    d["bias_pct"] = (d["calc"] - d["nominal"]) / d["nominal"] * 100.0
    by = d.groupby("nominal", as_index=False).agg(
        n=("calc", "count"), mean_calc=("calc", "mean"), sd=("calc", "std"),
        mean_bias_pct=("bias_pct", "mean"),
        mean_abs_bias_pct=("bias_pct", lambda s: float(np.nanmean(np.abs(s)))),
        max_abs_bias_pct=("bias_pct", lambda s: float(np.nanmax(np.abs(s)))),
    )
    by["cv_pct"] = by["sd"] / by["mean_calc"] * 100.0
    return by, {
        "qc_n": int(len(d)), "qc_levels": int(by["nominal"].nunique()),
        "qc_mean_abs_bias_pct": float(np.nanmean(np.abs(d["bias_pct"]))),
        "qc_max_abs_bias_pct": float(np.nanmax(np.abs(d["bias_pct"]))),
        "qc_max_cv_pct": float(np.nanmax(by["cv_pct"])) if np.isfinite(by["cv_pct"]).any() else np.nan,
    }


def analyze_surrogate_is(normalized, criteria=None, component_mapping=None, qc_sample_mapping=None, user_amr=None):
    criteria = criteria or SurrogateCriteria()
    data = apply_component_mapping(normalized, component_mapping)
    data = apply_qc_sample_mapping(data, qc_sample_mapping)
    cal_rows = _sample_type_mask(data["Sample Type"], "cal")
    qc_rows = _sample_type_mask(data["Sample Type"], "qc")
    if not cal_rows.any(): raise ValueError("No calibrator/standard rows were detected.")
    if not qc_rows.any(): raise ValueError("No QC rows were detected.")

    cal_area = _pivot(data, cal_rows); qc_area = _pivot(data, qc_rows)
    cal_nom = _analyte_nominals(data, cal_rows); qc_nom = _analyte_nominals(data, qc_rows)
    analytes = [c for c in cal_nom.columns if c in cal_area.columns]
    is_names = sorted(data.loc[data["Component Role"] == "IS", "Component"].astype(str).unique())
    if not analytes: raise ValueError("No analyte components with calibration concentrations were detected.")
    if not is_names: raise ValueError("No internal-standard components were detected.")
    groups = _group_lookup(data)
    amr_lookup = user_amr_lookup(user_amr)

    rankings = []; stage1_rows = []; stage1_levels = {}; stage1_sources = {}
    for analyte in analytes:
        idx = cal_area.index.intersection(cal_nom.index)
        x = _num(cal_nom.loc[idx, analyte]); y = _num(cal_area.loc[idx, analyte])
        valid = np.isfinite(x) & np.isfinite(y) & (x > 0)
        if str(analyte) in amr_lookup:
            user_lloq, user_uloq = amr_lookup[str(analyte)]
            xd = np.asarray(x[valid], float); yd = np.asarray(y[valid], float)
            level_mask = (xd >= user_lloq) & (xd <= user_uloq)
            levels = sorted(np.unique(xd[level_mask]).astype(float).tolist())
            s1 = _fit_candidate(xd[level_mask], yd[level_mask], criteria) if int(level_mask.sum()) >= criteria.min_calibrators else None
            amr_source = "User-defined"
        else:
            levels, s1 = select_stage1_levels(x[valid], y[valid], criteria)
            amr_source = "Automatic"
        stage1_rows.append({
            "Analyte": analyte, "Group": groups.get(analyte, analyte),
            "AMR Source": amr_source,
            "Stage 1 Pass": bool(levels), "Stage 1 LLOQ": min(levels) if levels else np.nan,
            "Stage 1 ULOQ": max(levels) if levels else np.nan, "Stage 1 n": len(levels),
            "Stage 1 Max |Bias| %": s1["max_cal_abs_bias_pct"] if s1 else np.nan,
            "Stage 1 Fit R2": s1["fit_r2"] if s1 else np.nan,
        })
        stage1_levels[str(analyte)] = list(map(float, levels))
        stage1_sources[str(analyte)] = amr_source
        if not levels: continue

        for is_name in is_names:
            if is_name not in cal_area.columns: continue
            idx = cal_area.index.intersection(cal_nom.index)
            xa = _num(cal_nom.loc[idx, analyte]); aa = _num(cal_area.loc[idx, analyte])
            ia = _num(cal_area.loc[idx, is_name])
            valid = np.isfinite(xa) & np.isfinite(aa) & np.isfinite(ia) & (xa > 0) & (ia > 0) & xa.isin(levels)
            if int(valid.sum()) < criteria.min_calibrators: continue
            xfit = xa[valid].to_numpy(float); ratio = (aa[valid] / ia[valid]).to_numpy(float)
            m = _fit_candidate(xfit, ratio, criteria)
            if m is None: continue
            fit = m["fit"]

            qidx = qc_area.index.intersection(qc_nom.index)
            if analyte in qc_area.columns and is_name in qc_area.columns and analyte in qc_nom.columns:
                qa = _num(qc_area.loc[qidx, analyte]); qi = _num(qc_area.loc[qidx, is_name])
                qn = _num(qc_nom.loc[qidx, analyte])
                qvalid = np.isfinite(qa) & np.isfinite(qi) & np.isfinite(qn) & (qi > 0) & (qn >= m["lloq"]) & (qn <= m["uloq"])
                qratio = (qa[qvalid] / qi[qvalid]).to_numpy(float)
                qnom = qn[qvalid].to_numpy(float); qcalc = fit.invert(qratio)
                by_level, qs = _qc_summary(qcalc, qnom)
            else:
                by_level, qs = pd.DataFrame(), {}

            qc_pass = bool(qs) and (
                np.isfinite(qs.get("qc_mean_abs_bias_pct", np.nan))
                and qs["qc_mean_abs_bias_pct"] <= criteria.max_qc_mean_abs_bias
                and np.isfinite(qs.get("qc_max_abs_bias_pct", np.nan))
                and qs["qc_max_abs_bias_pct"] <= criteria.max_qc_abs_bias
                and (not np.isfinite(qs.get("qc_max_cv_pct", np.nan)) or qs["qc_max_cv_pct"] <= criteria.max_qc_cv)
            )
            row = {
                "Analyte": analyte, "Group": groups.get(analyte, analyte), "Internal Standard": is_name,
                "AMR Source": stage1_sources.get(str(analyte), "Automatic"),
                "Pass": bool(m["pass_cal"] and qc_pass), "Calibration Pass": bool(m["pass_cal"]), "QC Pass": qc_pass,
                "n Cal": m["n_cal"], "LLOQ": m["lloq"], "ULOQ": m["uloq"], "Span Ratio": m["uloq"] / m["lloq"],
                "Max Cal |Bias| %": m["max_cal_abs_bias_pct"], "Mean Cal |Bias| %": m["mean_cal_abs_bias_pct"],
                "Fit R2": m["fit_r2"], "Weighted R2": m["weighted_r2"], "QC n": qs.get("qc_n", 0),
                "QC Levels": qs.get("qc_levels", 0), "QC Mean |Bias| %": qs.get("qc_mean_abs_bias_pct", np.nan),
                "QC Max |Bias| %": qs.get("qc_max_abs_bias_pct", np.nan), "QC Max CV %": qs.get("qc_max_cv_pct", np.nan),
            }
            rankings.append(row)

    ranking = pd.DataFrame(rankings)
    if not ranking.empty:
        ranking = ranking.sort_values(
            ["Analyte", "Pass", "QC Mean |Bias| %", "QC Max CV %", "Max Cal |Bias| %"],
            ascending=[True, False, True, True, True], na_position="last"
        ).reset_index(drop=True)
    return {
        "ranking": ranking, "stage1": pd.DataFrame(stage1_rows),
        "criteria": criteria, "analytes": analytes, "internal_standards": is_names,
        "pair_count_requested": int(len(analytes) * len(is_names)),
        "qc_sample_mapping": qc_sample_mapping,
        "user_amr": user_amr,
        "stage1_levels": stage1_levels,
        "stage1_sources": stage1_sources,
        "manual_exclusions": {},
        "_cache": {
            "cal_area": cal_area, "qc_area": qc_area,
            "cal_nom": cal_nom, "qc_nom": qc_nom,
        },
    }


def compute_pair_detail(result, analyte, is_name):
    """Recompute detailed calibration/QC data for one selected pair only.

    Bulk analysis intentionally stores only compact pair summaries. This
    function reconstructs the fit and QC sample tables on demand so memory
    usage does not scale with pair_count × QC_rows.
    """
    criteria = result["criteria"]
    cache = result.get("_cache", {})
    cal_area = cache.get("cal_area"); qc_area = cache.get("qc_area")
    cal_nom = cache.get("cal_nom"); qc_nom = cache.get("qc_nom")
    if any(x is None for x in (cal_area, qc_area, cal_nom, qc_nom)):
        raise ValueError("Detailed pair cache is unavailable.")

    levels = result.get("stage1_levels", {}).get(str(analyte), [])
    if not levels:
        raise ValueError(f"No Stage 1 calibration range is available for {analyte}.")
    excluded = set(
        float(v) for v in result.get("manual_exclusions", {}).get((str(analyte), str(is_name)), [])
    )
    active_levels = [float(v) for v in levels if float(v) not in excluded]

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
        by_level, _ = _qc_summary(qcalc, qnom)
        sample_detail = pd.DataFrame({
            "Sample Key": [i[0] for i in qidx[qvalid]],
            "Sample Name": [i[1] for i in qidx[qvalid]],
            "Nominal": qnom,
            "Ratio": qratio,
            "Calculated": qcalc,
        })
        sample_detail["Bias %"] = (
            (sample_detail["Calculated"] - sample_detail["Nominal"])
            / sample_detail["Nominal"] * 100.0
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
    cal_detail["Bias %"] = (cal_detail["Back-calculated"] - cal_detail["Nominal"]) / cal_detail["Nominal"] * 100.0
    cal_detail["|Bias| %"] = np.abs(cal_detail["Bias %"])
    # Add excluded Stage-1 levels back to the table for transparent manual editing.
    if excluded:
        all_valid = np.isfinite(xa) & np.isfinite(aa) & np.isfinite(ia) & (xa > 0) & (ia > 0) & xa.isin(levels)
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
    criteria = result["criteria"]

    max_bias = float(cal.loc[cal["Use"], "|Bias| %"].max()) if cal["Use"].any() else np.nan
    mean_bias = float(cal.loc[cal["Use"], "|Bias| %"].mean()) if cal["Use"].any() else np.nan
    r2 = float(fit.stats.get("fit_r2", np.nan))
    wr2 = float(fit.stats.get("weighted_r2", np.nan))
    qc = detail["qc_samples"]
    by, qs = _qc_summary(qc["Calculated"].to_numpy(float), qc["Nominal"].to_numpy(float)) if not qc.empty else (pd.DataFrame(), {})
    qc_pass = bool(qs) and (
        np.isfinite(qs.get("qc_mean_abs_bias_pct", np.nan))
        and qs["qc_mean_abs_bias_pct"] <= criteria.max_qc_mean_abs_bias
        and np.isfinite(qs.get("qc_max_abs_bias_pct", np.nan))
        and qs["qc_max_abs_bias_pct"] <= criteria.max_qc_abs_bias
        and (not np.isfinite(qs.get("qc_max_cv_pct", np.nan)) or qs["qc_max_cv_pct"] <= criteria.max_qc_cv)
    )
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
        active = cal.loc[cal["Use"], "Nominal"].to_numpy(float)
        updates = {
            "AMR Source": "Manual edited" if excluded_nominals else result.get("stage1_sources", {}).get(str(analyte), "Automatic"),
            "Pass": bool(cal_pass and qc_pass),
            "Calibration Pass": bool(cal_pass),
            "QC Pass": bool(qc_pass),
            "n Cal": int(len(active)),
            "LLOQ": float(np.min(active)) if len(active) else np.nan,
            "ULOQ": float(np.max(active)) if len(active) else np.nan,
            "Span Ratio": float(np.max(active) / np.min(active)) if len(active) else np.nan,
            "Max Cal |Bias| %": max_bias,
            "Mean Cal |Bias| %": mean_bias,
            "Fit R2": r2,
            "Weighted R2": wr2,
            "QC n": qs.get("qc_n", 0),
            "QC Levels": qs.get("qc_levels", 0),
            "QC Mean |Bias| %": qs.get("qc_mean_abs_bias_pct", np.nan),
            "QC Max |Bias| %": qs.get("qc_max_abs_bias_pct", np.nan),
            "QC Max CV %": qs.get("qc_max_cv_pct", np.nan),
        }
        for col, value in updates.items():
            result["ranking"].loc[mask, col] = value
    return compute_pair_detail(result, analyte, is_name)


def pair_metric_matrix(result, metric="QC Mean |Bias| %"):
    r = result.get("ranking", pd.DataFrame())
    if r.empty or metric not in r.columns: return pd.DataFrame()
    return r.pivot_table(index="Analyte", columns="Internal Standard", values=metric, aggfunc="first")


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
