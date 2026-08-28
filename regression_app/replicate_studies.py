import re
import numpy as np
import pandas as pd

from .models import MODEL_SPECS, ORIGIN_EXCLUDE

_CAL_RE = re.compile(r"\bcal\b", re.IGNORECASE)

def _num(series):
    return pd.to_numeric(series, errors="coerce")

def candidate_replicate_rows(df, analyte):
    x = df[df["Compound"].astype(str) == str(analyte)].copy()
    if x.empty:
        raise ValueError(f"No rows found for analyte {analyte!r}.")
    x["Nominal"] = _num(x.get("Std. Conc", pd.Series(index=x.index, dtype=object)))
    x["Response_numeric"] = _num(x.get("Response", pd.Series(index=x.index, dtype=object)))
    x["Injection"] = _num(x.get("#", pd.Series(index=x.index, dtype=object)))

    valid = (
        np.isfinite(x["Nominal"])
        & (x["Nominal"] > 0)
        & np.isfinite(x["Response_numeric"])
        & np.isfinite(x["Injection"])
    )

    sample = x.get("Sample Text", pd.Series("", index=x.index)).astype(str)
    looks_cal = sample.str.contains(_CAL_RE, na=False)

    # Preferred mode: explicit Cal labels in Sample Text.
    if (valid & looks_cal).any():
        x = x[valid & looks_cal].copy()
        x["Detection Mode"] = "Explicit Cal label"
        return x.sort_values("Injection").reset_index(drop=True)

    # Fallback mode for studies exported as QC/non-calibrator rows: retain all
    # valid nominal-response rows here; infer_replicate_sets() will identify
    # the repeated full-length ladder family by injection order.
    x = x[valid].copy()
    x["Detection Mode"] = "Repeated ladder"
    return x.sort_values("Injection").reset_index(drop=True)

def infer_replicate_sets(df, analyte):
    rows = candidate_replicate_rows(df, analyte)
    if rows.empty:
        raise ValueError("No calibration-like replicate rows were detected.")
    set_id = 1
    set_ids = []
    previous = None
    seen = set()
    for nominal in rows["Nominal"].to_numpy(float):
        if previous is not None and (nominal <= previous or nominal in seen):
            set_id += 1
            seen = set()
        set_ids.append(set_id)
        seen.add(nominal)
        previous = nominal
    rows["Replicate Set"] = set_ids

    # If no explicit Cal labels were available, the valid rows can contain
    # shorter QC ladders interleaved with the intended rotation ladders.
    # Keep the repeated family with the largest number of unique nominal
    # levels. Example: a 16x6 study with six 16-level ladders interspersed
    # with 9-level QC sequences should yield six rotation sets, not thirteen.
    if (
        "Detection Mode" in rows.columns
        and not rows.empty
        and rows["Detection Mode"].eq("Repeated ladder").all()
    ):
        preliminary = (
            rows.groupby("Replicate Set", as_index=False)
            .agg(levels=("Nominal", "nunique"), n=("Nominal", "size"))
        )
        max_levels = int(preliminary["levels"].max())
        keep_sets = preliminary.loc[
            preliminary["levels"] == max_levels, "Replicate Set"
        ].tolist()
        if len(keep_sets) >= 2:
            rows = rows[rows["Replicate Set"].isin(keep_sets)].copy()
            remap = {old: new for new, old in enumerate(sorted(keep_sets), start=1)}
            rows["Replicate Set"] = rows["Replicate Set"].map(remap)

    rows["Replicate Label"] = rows["Replicate Set"].map(lambda i: f"Set {i}")
    levels = sorted(rows["Nominal"].dropna().unique())
    level_map = {v: i + 1 for i, v in enumerate(levels)}
    rows["Level"] = rows["Nominal"].map(level_map)
    summary = (
        rows.groupby(["Replicate Set", "Replicate Label"], as_index=False)
        .agg(
            n=("Nominal", "size"),
            first_injection=("Injection", "min"),
            last_injection=("Injection", "max"),
            levels=("Level", "nunique"),
            min_nominal=("Nominal", "min"),
            max_nominal=("Nominal", "max"),
        )
    )
    expected = int(summary["levels"].max())
    summary["Complete"] = summary["levels"] == expected
    return rows, summary

def rotate_calibration(
    mapped_rows,
    model_name="Linear 1/x",
    calibrator_bias=15.0,
    min_calibrators=6,
    origin_mode=ORIGIN_EXCLUDE,
):
    model_lookup = dict(MODEL_SPECS)
    if model_name not in model_lookup:
        raise ValueError(f"Unknown model: {model_name}")
    fn = model_lookup[model_name]
    sets = sorted(mapped_rows["Replicate Set"].unique())

    # Use a common calibration range across all replicate sets. This allows
    # rotation to remain valid when one or more sets are missing isolated
    # low/high calibrators (for example, a blank/No Peak TargetLynx response),
    # while ensuring every calibration and evaluation uses the same levels.
    level_sets = []
    for set_id in sets:
        g = mapped_rows[mapped_rows["Replicate Set"] == set_id]
        level_sets.append(set(g["Level"].dropna().astype(int).unique()))

    common_levels = set.intersection(*level_sets) if level_sets else set()
    if len(common_levels) < min_calibrators:
        raise ValueError(
            f"Only {len(common_levels)} calibration level(s) are shared by all "
            f"replicate sets; at least {min_calibrators} are required."
        )

    levels = sorted(common_levels)
    working_rows = mapped_rows[mapped_rows["Level"].isin(levels)].copy()
    expected_levels = len(levels)

    results = []
    fit_rows = []
    for cal_set in sets:
        cal = working_rows[working_rows["Replicate Set"] == cal_set].copy()
        if cal["Level"].nunique() != expected_levels:
            continue
        cal = cal.sort_values("Nominal")
        x = cal["Nominal"].to_numpy(float)
        y = cal["Response_numeric"].to_numpy(float)
        try:
            fit = fn(x, y, calibrator_bias, min_calibrators, origin_mode)
        except Exception as exc:
            fit_rows.append({
                "Calibration Set": cal_set,
                "Status": f"Fit failed: {exc}",
            })
            continue
        fit_rows.append({
            "Calibration Set": cal_set,
            "Status": "OK",
            "Pearson r": fit.stats.get("pearson_r", np.nan),
            "Pearson r2": fit.stats.get("pearson_r2", np.nan),
            "Fit R2": fit.stats.get("fit_r2", np.nan),
            "Weighted R2": fit.stats.get("weighted_r2", np.nan),
            "RMSE": fit.stats.get("rmse", np.nan),
            "Contiguous AMR": (
                f"{fit.contiguous_range[0]:g}–{fit.contiguous_range[1]:g}"
                if fit.contiguous_range else ""
            ),
        })
        eval_rows = working_rows[working_rows["Replicate Set"] != cal_set].copy()
        calc = fit.invert(eval_rows["Response_numeric"].to_numpy(float))
        nominal = eval_rows["Nominal"].to_numpy(float)
        bias = np.full_like(nominal, np.nan, dtype=float)
        nz = nominal != 0
        bias[nz] = (calc[nz] - nominal[nz]) / nominal[nz] * 100.0
        eval_rows["Calibration Set"] = cal_set
        eval_rows["Calculated"] = calc
        eval_rows["Bias %"] = bias
        results.append(eval_rows)
    if not results:
        raise ValueError("No replicate set could be fitted as a complete calibration ladder.")
    quantified = pd.concat(results, ignore_index=True)
    fits = pd.DataFrame(fit_rows)
    by_level = (
        quantified.groupby(["Calibration Set", "Level", "Nominal"], as_index=False)
        .agg(
            n=("Calculated", "count"),
            mean_calculated=("Calculated", "mean"),
            sd=("Calculated", "std"),
            mean_bias_pct=("Bias %", "mean"),
            max_abs_bias_pct=("Bias %", lambda s: np.nanmax(np.abs(s))),
        )
    )
    by_level["cv_pct"] = by_level["sd"] / by_level["mean_calculated"] * 100.0
    matrix = (
        quantified.groupby(["Calibration Set", "Replicate Set"])["Bias %"]
        .apply(lambda s: float(np.nanmean(np.abs(s))))
        .unstack("Replicate Set")
    )
    matrix.index = [f"Cal Set {int(i)}" for i in matrix.index]
    matrix.columns = [f"Eval Set {int(i)}" for i in matrix.columns]
    drift_rows = []
    for cal_set, g in quantified.groupby("Calibration Set"):
        gg = g[np.isfinite(g["Injection"]) & np.isfinite(g["Bias %"])].copy()
        if len(gg) >= 3 and np.ptp(gg["Injection"]) > 0:
            slope, intercept = np.polyfit(gg["Injection"], gg["Bias %"], 1)
            pred = intercept + slope * gg["Injection"].to_numpy(float)
            y = gg["Bias %"].to_numpy(float)
            den = np.sum((y - np.mean(y))**2)
            r2 = 1 - np.sum((y-pred)**2)/den if den > 0 else np.nan
        else:
            slope = intercept = r2 = np.nan
        drift_rows.append({
            "Calibration Set": cal_set,
            "Bias slope per 100 injections": slope * 100 if np.isfinite(slope) else np.nan,
            "Sequence-trend R2": r2,
        })
    drift = pd.DataFrame(drift_rows)
    return {
        "quantified": quantified,
        "fits": fits,
        "by_level": by_level,
        "matrix": matrix,
        "drift": drift,
    }
