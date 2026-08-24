from dataclasses import dataclass
from typing import Callable, Dict, Optional, Tuple
import warnings

import numpy as np
from scipy.optimize import least_squares


@dataclass
class FitResult:
    name: str
    params: np.ndarray
    predict: Callable[[np.ndarray], np.ndarray]
    invert: Callable[[np.ndarray], np.ndarray]
    yhat: np.ndarray
    residuals: np.ndarray
    backcalc_x: np.ndarray
    bias_pct: np.ndarray
    weights: np.ndarray
    stats: Dict[str, float]
    pass_mask: np.ndarray
    contiguous_range: Optional[Tuple[float, float]]
    contiguous_count: int
    notes: str = ""


def _safe_r2(y, yhat):
    ss_res = np.sum((y - yhat) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    if ss_tot <= 0:
        return np.nan
    return 1 - ss_res / ss_tot


def _stats(y, yhat, p):
    n = len(y)
    resid = y - yhat
    sse = float(np.sum(resid ** 2))
    rmse = float(np.sqrt(np.mean(resid ** 2)))
    r2 = _safe_r2(y, yhat)
    adj_r2 = np.nan
    if n > p + 1 and np.isfinite(r2):
        adj_r2 = 1 - (1-r2) * (n-1) / (n-p-1)

    if n > 0:
        sigma2 = max(sse / n, np.finfo(float).tiny)
        aic = n * np.log(sigma2) + 2 * p
        bic = n * np.log(sigma2) + p * np.log(n)
        if n > p + 1:
            aicc = aic + (2 * p * (p + 1)) / (n - p - 1)
        else:
            aicc = np.nan
    else:
        aic = aicc = bic = np.nan

    return {
        "r2": float(r2) if np.isfinite(r2) else np.nan,
        "adj_r2": float(adj_r2) if np.isfinite(adj_r2) else np.nan,
        "rmse": rmse,
        "aic": float(aic),
        "aicc": float(aicc) if np.isfinite(aicc) else np.nan,
        "bic": float(bic),
    }


def _weights(x, mode):
    x = np.asarray(x, dtype=float)
    if mode == "none":
        return np.ones_like(x)
    if np.any(x <= 0):
        raise ValueError(f"{mode} weighting requires all X values to be > 0.")
    if mode == "1/x":
        return 1.0 / x
    if mode == "1/x2":
        return 1.0 / (x ** 2)
    raise ValueError(f"Unknown weighting mode: {mode}")


def _contiguous_range(x, pass_mask, min_points):
    x = np.asarray(x, float)
    order = np.argsort(x)
    xs = x[order]
    pm = np.asarray(pass_mask, bool)[order]

    best = None
    best_len = 0
    start = None

    for i, passed in enumerate(pm):
        if passed and start is None:
            start = i
        if (not passed or i == len(pm) - 1) and start is not None:
            end = i if passed and i == len(pm) - 1 else i - 1
            length = end - start + 1
            if length > best_len:
                best_len = length
                best = (float(xs[start]), float(xs[end]))
            start = None

    if best_len < min_points:
        return None, best_len
    return best, best_len


def _bias(backcalc, x):
    backcalc = np.asarray(backcalc, float)
    x = np.asarray(x, float)
    out = np.full_like(x, np.nan, dtype=float)
    nz = x != 0
    out[nz] = (backcalc[nz] - x[nz]) / x[nz] * 100.0
    return out


def _poly_invert(coeffs_desc, yvals, x_reference):
    xr = np.asarray(x_reference, float)
    xmin, xmax = np.nanmin(xr), np.nanmax(xr)
    center = (xmin + xmax) / 2

    outs = []
    for y in np.asarray(yvals, float):
        c = np.array(coeffs_desc, dtype=float).copy()
        c[-1] -= y
        roots = np.roots(c)
        real = roots[np.abs(np.imag(roots)) < 1e-8].real
        if len(real) == 0:
            outs.append(np.nan)
            continue
        nonneg = real[real >= 0]
        candidates = nonneg if len(nonneg) else real
        inside = candidates[(candidates >= xmin) & (candidates <= xmax)]
        if len(inside):
            chosen = inside[np.argmin(np.abs(inside - center))]
        else:
            dist = np.where(candidates < xmin, xmin - candidates,
                            np.where(candidates > xmax, candidates - xmax, 0))
            chosen = candidates[np.argmin(dist)]
        outs.append(float(chosen))
    return np.array(outs, float)


def fit_polynomial(x, y, degree=1, weight_mode="none", name=None,
                   bias_limit=15.0, min_points=6):
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    w = _weights(x, weight_mode)
    coeff = np.polyfit(x, y, degree, w=np.sqrt(w))
    predict = lambda xx: np.polyval(coeff, np.asarray(xx, float))
    yhat = predict(x)
    invert = lambda yy: _poly_invert(coeff, np.asarray(yy, float), x)
    backcalc = invert(y)
    bias = _bias(backcalc, x)
    pass_mask = np.isfinite(bias) & (np.abs(bias) <= bias_limit)
    crange, ccount = _contiguous_range(x, pass_mask, min_points)
    stats = _stats(y, yhat, len(coeff))

    if name is None:
        base = "Linear" if degree == 1 else "Quadratic"
        suffix = "" if weight_mode == "none" else f" ({weight_mode})"
        name = base + suffix

    return FitResult(name, coeff, predict, invert, yhat, y-yhat, backcalc, bias,
                     w, stats, pass_mask, crange, ccount,
                     "Polynomial coefficients are ordered highest power to intercept.")


def _pade_predict(order, p, x):
    x = np.asarray(x, float)
    if order == "1/1":
        a, b, c = p
        return (a + b*x) / (1 + c*x)
    if order == "2/1":
        a, b, c, d = p
        return (a + b*x + c*x*x) / (1 + d*x)
    raise ValueError(order)


def _initial_pade(order, x, y):
    lin = np.polyfit(x, y, 1)
    slope, intercept = lin
    if order == "1/1":
        return np.array([intercept, slope, 0.0], float)
    if order == "2/1":
        q = np.polyfit(x, y, min(2, len(x)-1))
        if len(q) == 3:
            c, b, a = q
        else:
            c, b, a = 0.0, slope, intercept
        return np.array([a, b, c, 0.0], float)
    raise ValueError(order)


def _pade_invert(order, p, yvals, x_reference):
    xref = np.asarray(x_reference, float)
    xmin, xmax = np.nanmin(xref), np.nanmax(xref)
    center = (xmin + xmax) / 2
    outs = []

    for yy in np.asarray(yvals, float):
        if order == "1/1":
            a, b, c = p
            denom = yy*c - b
            if abs(denom) < 1e-14:
                outs.append(np.nan)
            else:
                outs.append(float((a-yy)/denom))
        elif order == "2/1":
            a, b, c, d = p
            roots = np.roots([c, b - yy*d, a - yy]) if abs(c) > 1e-14 else np.roots([b-yy*d, a-yy])
            real = roots[np.abs(np.imag(roots)) < 1e-8].real
            if len(real) == 0:
                outs.append(np.nan)
                continue
            nonneg = real[real >= 0]
            candidates = nonneg if len(nonneg) else real
            inside = candidates[(candidates >= xmin) & (candidates <= xmax)]
            if len(inside):
                chosen = inside[np.argmin(np.abs(inside-center))]
            else:
                dist = np.where(candidates < xmin, xmin-candidates,
                                np.where(candidates > xmax, candidates-xmax, 0))
                chosen = candidates[np.argmin(dist)]
            outs.append(float(chosen))
        else:
            raise ValueError(order)

    return np.asarray(outs, float)


def fit_pade(x, y, order="1/1", weight_mode="none", bias_limit=15.0, min_points=6):
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    w = _weights(x, weight_mode)
    sqrtw = np.sqrt(w)
    p0 = _initial_pade(order, x, y)

    def resid(p):
        den = 1 + (p[2] if order == "1/1" else p[3]) * x
        if np.any(np.abs(den) < 1e-8):
            return np.full_like(y, 1e12)
        pred = _pade_predict(order, p, x)
        if np.any(~np.isfinite(pred)):
            return np.full_like(y, 1e12)
        return sqrtw * (y - pred)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fit = least_squares(resid, p0, max_nfev=20000)

    if not fit.success:
        raise RuntimeError(f"Padé [{order}] fit failed: {fit.message}")

    p = fit.x
    predict = lambda xx: _pade_predict(order, p, np.asarray(xx, float))
    yhat = predict(x)

    grid = np.linspace(np.min(x), np.max(x), 1000)
    den = 1 + (p[2] if order == "1/1" else p[3]) * grid
    if np.any(np.abs(den) < 1e-5):
        raise RuntimeError(f"Padé [{order}] denominator approaches zero within the calibration range.")

    invert = lambda yy: _pade_invert(order, p, np.asarray(yy, float), x)
    backcalc = invert(y)
    bias = _bias(backcalc, x)
    pass_mask = np.isfinite(bias) & (np.abs(bias) <= bias_limit)
    crange, ccount = _contiguous_range(x, pass_mask, min_points)
    stats = _stats(y, yhat, len(p))

    return FitResult(f"Padé [{order}]" + ("" if weight_mode == "none" else f" ({weight_mode})"),
                     p, predict, invert, yhat, y-yhat, backcalc, bias, w, stats,
                     pass_mask, crange, ccount,
                     "Padé parameters use denominator constant fixed to 1 for identifiability.")


MODEL_SPECS = [
    ("Linear", lambda x,y,b,m: fit_polynomial(x,y,1,"none","Linear",b,m)),
    ("Linear 1/x", lambda x,y,b,m: fit_polynomial(x,y,1,"1/x","Linear 1/x",b,m)),
    ("Linear 1/x²", lambda x,y,b,m: fit_polynomial(x,y,1,"1/x2","Linear 1/x²",b,m)),
    ("Quadratic", lambda x,y,b,m: fit_polynomial(x,y,2,"none","Quadratic",b,m)),
    ("Quadratic 1/x", lambda x,y,b,m: fit_polynomial(x,y,2,"1/x","Quadratic 1/x",b,m)),
    ("Quadratic 1/x²", lambda x,y,b,m: fit_polynomial(x,y,2,"1/x2","Quadratic 1/x²",b,m)),
    ("Padé [1/1]", lambda x,y,b,m: fit_pade(x,y,"1/1","none",b,m)),
    ("Padé [2/1]", lambda x,y,b,m: fit_pade(x,y,"2/1","none",b,m)),
]
