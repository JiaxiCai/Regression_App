import numpy as np
import pandas as pd

from .models import MODEL_SPECS, ORIGIN_EXCLUDE


_QUANT_TYPES = {"standard", "calibrator", "qc"}


def _num(series):
    return pd.to_numeric(series, errors="coerce")


def candidate_study_rows(df, analyte):
    """Return quantitative TargetLynx rows suitable for replicate-ladder inference.

    Unlike the older calibration-rotation parser, this does not require "Cal" in
    Sample Text. Precision/AMR studies are often exported with Type=QC.
    """
    x = df[df["Compound"].astype(str) == str(analyte)].copy()
    if x.empty:
        raise ValueError(f"No rows found for analyte {analyte!r}.")

    x["Nominal"] = _num(x.get("Std. Conc", pd.Series(index=x.index, dtype=object)))
    x["Response_numeric"] = _num(x.get("Response", pd.Series(index=x.index, dtype=object)))
    x["Injection"] = _num(x.get("#", pd.Series(index=x.index, dtype=object)))
    typ = x.get("Type", pd.Series("", index=x.index)).astype(str).str.strip().str.lower()

    keep = (
        typ.isin(_QUANT_TYPES)
        & np.isfinite(x["Nominal"].to_numpy(float))
        & (x["Nominal"].to_numpy(float) > 0)
        & np.isfinite(x["Response_numeric"].to_numpy(float))
        & np.isfinite(x["Injection"].to_numpy(float))
    )
    return x.loc[keep].sort_values("Injection").reset_index(drop=True)


def infer_study_sets(df, analyte, coverage_threshold=0.75):
    """Infer repeated concentration ladders from injection order and nominal resets.

    All detected sequences are returned. Analysis sets are those retaining at
    least coverage_threshold of the largest detected ladder. This separates full
    AMR ladders from shorter interspersed QC sequences while tolerating isolated
    missing levels.
    """
    rows = candidate_study_rows(df, analyte)
    if rows.empty:
        raise ValueError("No quantitative Standard/QC rows were detected.")

    set_id = 1
    set_ids = []
    previous = None
    seen = set()
    for nominal in rows["Nominal"].to_numpy(float):
        if previous is not None and (nominal <= previous or nominal in seen):
            set_id += 1
            seen = set()
        set_ids.append(set_id)
        seen.add(float(nominal))
        previous = float(nominal)

    rows["Replicate Set"] = set_ids
    all_levels = sorted(rows["Nominal"].dropna().unique())
    level_map = {v: i + 1 for i, v in enumerate(all_levels)}
    rows["Level"] = rows["Nominal"].map(level_map)

    summary = (
        rows.groupby("Replicate Set", as_index=False)
        .agg(
            n=("Nominal", "size"),
            levels=("Nominal", "nunique"),
            first_injection=("Injection", "min"),
            last_injection=("Injection", "max"),
            min_nominal=("Nominal", "min"),
            max_nominal=("Nominal", "max"),
        )
    )
    maximum_levels = int(summary["levels"].max())
    summary["Coverage"] = summary["levels"] / maximum_levels
    summary["Analysis Set"] = summary["Coverage"] >= float(coverage_threshold)

    selected = summary.loc[summary["Analysis Set"], "Replicate Set"].astype(int).tolist()
    if len(selected) < 2:
        raise ValueError(
            "Fewer than two replicate ladders met the study-set coverage threshold."
        )

    selected_rows = rows[rows["Replicate Set"].isin(selected)].copy()
    level_sets = [
        set(g["Nominal"].astype(float).unique())
        for _, g in selected_rows.groupby("Replicate Set")
    ]
    common_nominals = sorted(set.intersection(*level_sets)) if level_sets else []
    return rows, summary, selected, common_nominals


def _fit_one_rotation(
    rows,
    calibration_set,
    fit_levels,
    model_name,
    max_calibrator_bias,
    max_qc_cv,
    max_qc_mean_bias,
    min_r2,
    min_calibrators,
    origin_mode,
):
    model_lookup = dict(MODEL_SPECS)
    if model_name not in model_lookup:
        raise ValueError(f"Unknown model: {model_name}")
    fn = model_lookup[model_name]

    fit_levels = list(map(float, fit_levels))
    cal = rows[
        (rows["Replicate Set"] == calibration_set)
        & rows["Nominal"].astype(float).isin(fit_levels)
    ].copy()
    cal = (
        cal.groupby("Nominal", as_index=False)
        .agg(Response_numeric=("Response_numeric", "mean"), Injection=("Injection", "min"))
        .sort_values("Nominal")
    )

    if cal["Nominal"].nunique() < min_calibrators:
        return {
            "Calibration Set": calibration_set,
            "Pass": False,
            "Status": "Insufficient calibrators",
            "Max Cal |Bias| %": np.nan,
            "Fit R2": np.nan,
            "Weighted R2": np.nan,
            "QC Max CV %": np.nan,
            "QC Max |Mean Bias| %": np.nan,
            "fit": None,
            "quantified": pd.DataFrame(),
            "by_level": pd.DataFrame(),
        }

    try:
        fit = fn(
            cal["Nominal"].to_numpy(float),
            cal["Response_numeric"].to_numpy(float),
            max_calibrator_bias,
            min_calibrators,
            origin_mode,
        )
    except Exception as exc:
        return {
            "Calibration Set": calibration_set,
            "Pass": False,
            "Status": f"Fit failed: {exc}",
            "Max Cal |Bias| %": np.nan,
            "Fit R2": np.nan,
            "Weighted R2": np.nan,
            "QC Max CV %": np.nan,
            "QC Max |Mean Bias| %": np.nan,
            "fit": None,
            "quantified": pd.DataFrame(),
            "by_level": pd.DataFrame(),
        }

    max_cal_bias = float(np.nanmax(np.abs(fit.bias_pct)))
    fit_r2 = float(fit.stats.get("fit_r2", np.nan))
    weighted_r2 = float(fit.stats.get("weighted_r2", np.nan))

    qc = rows[
        (rows["Replicate Set"] != calibration_set)
        & rows["Nominal"].astype(float).isin(fit_levels)
    ].copy()
    calc = fit.invert(qc["Response_numeric"].to_numpy(float))
    nominal = qc["Nominal"].to_numpy(float)
    qc["Calculated"] = calc
    qc["Bias %"] = (calc - nominal) / nominal * 100.0
    qc["Calibration Set"] = calibration_set

    by_level = (
        qc.groupby("Nominal", as_index=False)
        .agg(
            n=("Calculated", "count"),
            mean_calculated=("Calculated", "mean"),
            sd=("Calculated", "std"),
            mean_bias_pct=("Bias %", "mean"),
            max_abs_bias_pct=("Bias %", lambda s: float(np.nanmax(np.abs(s)))),
        )
    )
    by_level["cv_pct"] = by_level["sd"] / by_level["mean_calculated"] * 100.0
    by_level["qc_bias_pass"] = np.abs(by_level["mean_bias_pct"]) <= max_qc_mean_bias
    by_level["qc_cv_pass"] = (
        np.isfinite(by_level["cv_pct"]) & (by_level["cv_pct"] <= max_qc_cv)
    )
    by_level["Pass"] = by_level["qc_bias_pass"] & by_level["qc_cv_pass"]
    by_level["Calibration Set"] = calibration_set

    qc_max_cv = float(np.nanmax(by_level["cv_pct"])) if len(by_level) else np.nan
    qc_max_bias = (
        float(np.nanmax(np.abs(by_level["mean_bias_pct"]))) if len(by_level) else np.nan
    )

    cal_ok = np.isfinite(max_cal_bias) and max_cal_bias <= max_calibrator_bias
    r2_ok = np.isfinite(fit_r2) and fit_r2 >= min_r2
    qc_ok = bool(len(by_level)) and bool(by_level["Pass"].all())
    passed = bool(cal_ok and r2_ok and qc_ok)

    failures = []
    if not cal_ok:
        failures.append(f"cal bias {max_cal_bias:.2f}%")
    if not r2_ok:
        failures.append(f"R² {fit_r2:.6f}")
    if not qc_ok:
        bad = by_level.loc[~by_level["Pass"]]
        if len(bad):
            failures.append(f"{len(bad)} QC level(s) outside bias/CV limits")
        else:
            failures.append("QC criteria")

    return {
        "Calibration Set": calibration_set,
        "Pass": passed,
        "Status": "PASS" if passed else "FAIL: " + "; ".join(failures),
        "Max Cal |Bias| %": max_cal_bias,
        "Fit R2": fit_r2,
        "Weighted R2": weighted_r2,
        "QC Max CV %": qc_max_cv,
        "QC Max |Mean Bias| %": qc_max_bias,
        "fit": fit,
        "quantified": qc,
        "by_level": by_level,
    }


def evaluate_amr_candidate(
    mapped_rows,
    analysis_sets,
    span_levels,
    excluded_levels=None,
    model_name="Linear 1/x",
    max_calibrator_bias=15.0,
    max_qc_cv=15.0,
    max_qc_mean_bias=15.0,
    min_r2=0.995,
    min_calibrators=6,
    required_rotations=None,
    origin_mode=ORIGIN_EXCLUDE,
):
    excluded = set(float(x) for x in (excluded_levels or []))
    span_levels = list(map(float, span_levels))
    fit_levels = [x for x in span_levels if x not in excluded]
    analysis_sets = sorted(map(int, analysis_sets))
    if len(fit_levels) < min_calibrators:
        return None

    rows = mapped_rows[mapped_rows["Replicate Set"].isin(analysis_sets)].copy()
    rotations = []
    quant = []
    level_parts = []

    for cal_set in analysis_sets:
        r = _fit_one_rotation(
            rows=rows,
            calibration_set=cal_set,
            fit_levels=fit_levels,
            model_name=model_name,
            max_calibrator_bias=max_calibrator_bias,
            max_qc_cv=max_qc_cv,
            max_qc_mean_bias=max_qc_mean_bias,
            min_r2=min_r2,
            min_calibrators=min_calibrators,
            origin_mode=origin_mode,
        )
        rotations.append({k: v for k, v in r.items() if k not in {"fit", "quantified", "by_level"}})
        if len(r["quantified"]):
            quant.append(r["quantified"])
        if len(r["by_level"]):
            level_parts.append(r["by_level"])

    rotation_df = pd.DataFrame(rotations)
    pass_count = int(rotation_df["Pass"].sum()) if len(rotation_df) else 0
    total = len(analysis_sets)
    required = total if required_rotations in (None, 0) else min(int(required_rotations), total)
    passes = pass_count >= required

    def _safe_extreme(series, mode):
        s = pd.to_numeric(series, errors="coerce")
        s = s[np.isfinite(s)]
        if not len(s):
            return np.nan
        return float(s.max() if mode == "max" else s.min())

    summary = {
        "Pass": bool(passes),
        "LLOQ": float(min(span_levels)),
        "ULOQ": float(max(span_levels)),
        "Span ratio": float(max(span_levels) / min(span_levels)),
        "Levels in span": int(len(span_levels)),
        "Levels fitted": int(len(fit_levels)),
        "Excluded levels": ", ".join(f"{x:g}" for x in sorted(excluded.intersection(span_levels))),
        "Passing rotations": pass_count,
        "Required rotations": required,
        "Total rotations": total,
        "Max Cal |Bias| %": _safe_extreme(rotation_df.get("Max Cal |Bias| %", []), "max"),
        "Min Fit R2": _safe_extreme(rotation_df.get("Fit R2", []), "min"),
        "Max QC CV %": _safe_extreme(rotation_df.get("QC Max CV %", []), "max"),
        "Max QC |Mean Bias| %": _safe_extreme(rotation_df.get("QC Max |Mean Bias| %", []), "max"),
    }
    return {
        "summary": summary,
        "rotations": rotation_df,
        "quantified": pd.concat(quant, ignore_index=True) if quant else pd.DataFrame(),
        "by_level": pd.concat(level_parts, ignore_index=True) if level_parts else pd.DataFrame(),
        "fit_levels": fit_levels,
        "span_levels": span_levels,
    }


def systematic_amr_search(
    mapped_rows,
    analysis_sets,
    common_levels,
    excluded_levels=None,
    model_name="Linear 1/x",
    max_calibrator_bias=15.0,
    max_qc_cv=15.0,
    max_qc_mean_bias=15.0,
    min_r2=0.995,
    min_calibrators=6,
    required_rotations=None,
    origin_mode=ORIGIN_EXCLUDE,
):
    """Evaluate every contiguous nominal span and return the best passing AMR.

    Manually excluded levels remain excluded from fitting but may lie inside the
    reported span; this is reported explicitly as e.g. 15/16 levels fitted.
    """
    levels = sorted(map(float, common_levels))
    if len(levels) < min_calibrators:
        raise ValueError(
            f"Only {len(levels)} concentration levels are shared by the selected "
            f"replicate ladders; at least {min_calibrators} are required."
        )

    candidates = []
    excluded_set = set(excluded_levels or [])
    for i in range(len(levels)):
        for j in range(i + 1, len(levels)):
            span = levels[i:j + 1]
            active = [x for x in span if x not in excluded_set]
            if len(active) < min_calibrators:
                continue
            ev = evaluate_amr_candidate(
                mapped_rows=mapped_rows,
                analysis_sets=analysis_sets,
                span_levels=span,
                excluded_levels=excluded_levels,
                model_name=model_name,
                max_calibrator_bias=max_calibrator_bias,
                max_qc_cv=max_qc_cv,
                max_qc_mean_bias=max_qc_mean_bias,
                min_r2=min_r2,
                min_calibrators=min_calibrators,
                required_rotations=required_rotations,
                origin_mode=origin_mode,
            )
            if ev is not None:
                candidates.append(ev)

    if not candidates:
        raise ValueError("No candidate range contained enough calibrators to evaluate.")

    passing = [c for c in candidates if c["summary"]["Pass"]]
    pool = passing if passing else candidates

    def score(c):
        s = c["summary"]
        if passing:
            return (
                np.log10(max(s["Span ratio"], 1.0)),
                s["Levels fitted"],
                s["Passing rotations"],
                -s["Max QC CV %"] if np.isfinite(s["Max QC CV %"]) else -np.inf,
            )
        return (
            s["Passing rotations"],
            np.log10(max(s["Span ratio"], 1.0)),
            s["Levels fitted"],
        )

    best = max(pool, key=score)
    candidate_summary = pd.DataFrame([c["summary"] for c in candidates])
    candidate_summary = candidate_summary.sort_values(
        ["Pass", "Passing rotations", "Span ratio", "Levels fitted"],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)

    best["candidates"] = candidate_summary
    best["found_passing_amr"] = bool(passing)
    return best


def level_diagnostics(result):
    """Collapse rotation-specific QC output to one row per nominal concentration."""
    by = result.get("by_level", pd.DataFrame())
    if by.empty:
        return pd.DataFrame()
    out = (
        by.groupby("Nominal", as_index=False)
        .agg(
            max_qc_cv_pct=("cv_pct", "max"),
            max_abs_qc_mean_bias_pct=("mean_bias_pct", lambda s: float(np.nanmax(np.abs(s)))),
            rotations_passing=("Pass", "sum"),
            rotations_evaluated=("Pass", "size"),
        )
    )
    return out
