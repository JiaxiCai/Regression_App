from dataclasses import dataclass
from typing import Callable, Dict, Optional, Tuple
import warnings

import numpy as np
from scipy.optimize import least_squares


ORIGIN_EXCLUDE = "Exclude"
ORIGIN_INCLUDE = "Include"
ORIGIN_FORCE = "Force"


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
    equation: str = ""
    parameter_names: tuple = ()
    calculation_notes: str = ""
    notes: str = ""


def _pearson_r(x, y):
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    if len(x) < 2 or np.std(x) == 0 or np.std(y) == 0:
        return np.nan
    return float(np.corrcoef(x, y)[0, 1])


def _pearson_r2(x, y):
    r = _pearson_r(x, y)
    return float(r * r) if np.isfinite(r) else np.nan


def _fit_r2(y, yhat):
    ss_res = np.sum((y - yhat) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    if ss_tot <= 0:
        return np.nan
    return float(1 - ss_res / ss_tot)


def _weighted_r2(y, yhat, w):
    y = np.asarray(y, float)
    yhat = np.asarray(yhat, float)
    w = np.asarray(w, float)
    finite = np.isfinite(y) & np.isfinite(yhat) & np.isfinite(w) & (w > 0)
    if finite.sum() < 2:
        return np.nan
    y, yhat, w = y[finite], yhat[finite], w[finite]
    ybar_w = np.sum(w * y) / np.sum(w)
    sse_w = np.sum(w * (y - yhat) ** 2)
    sst_w = np.sum(w * (y - ybar_w) ** 2)
    if sst_w <= 0:
        return np.nan
    return float(1 - sse_w / sst_w)


def _stats(x, y, yhat, p, w):
    n = len(y)
    resid = y - yhat
    sse = float(np.sum(resid ** 2))
    rmse = float(np.sqrt(np.mean(resid ** 2)))
    fit_r2 = _fit_r2(y, yhat)
    pearson_r = _pearson_r(x, y)
    pearson_r2 = float(pearson_r * pearson_r) if np.isfinite(pearson_r) else np.nan
    weighted_r2 = _weighted_r2(y, yhat, w)

    adj_r2 = np.nan
    if n > p + 1 and np.isfinite(fit_r2):
        adj_r2 = 1 - (1-fit_r2) * (n-1) / (n-p-1)

    if n > 0:
        sigma2 = max(sse / n, np.finfo(float).tiny)
        aic = n * np.log(sigma2) + 2 * p
        bic = n * np.log(sigma2) + p * np.log(n)
        aicc = aic + (2 * p * (p + 1)) / (n - p - 1) if n > p + 1 else np.nan
    else:
        aic = aicc = bic = np.nan

    return {
        "pearson_r": pearson_r,
        "pearson_r2": pearson_r2,
        "fit_r2": fit_r2,
        "weighted_r2": weighted_r2,
        "adj_r2": float(adj_r2) if np.isfinite(adj_r2) else np.nan,
        "rmse": rmse,
        "aic": float(aic),
        "aicc": float(aicc) if np.isfinite(aicc) else np.nan,
        "bic": float(bic),
    }


def _weights(x, mode, origin_include=False):
    x = np.asarray(x, dtype=float)
    if mode == "none":
        return np.ones_like(x)
    if mode not in ("1/x", "1/x2"):
        raise ValueError(f"Unknown weighting mode: {mode}")
    w = np.empty_like(x)
    zero = x == 0
    nonzero = ~zero
    if np.any(x[nonzero] < 0):
        raise ValueError(f"{mode} weighting requires non-zero X values to be positive.")
    if np.any(zero) and not origin_include:
        raise ValueError(f"{mode} weighting cannot be applied to an experimental X=0 row.")
    w[zero] = 1.0
    if mode == "1/x":
        w[nonzero] = 1.0 / x[nonzero]
    else:
        w[nonzero] = 1.0 / (x[nonzero] ** 2)
    return w


def _prepare_origin(x, y, origin_mode):
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    if origin_mode == ORIGIN_INCLUDE:
        return np.concatenate([[0.0], x]), np.concatenate([[0.0], y]), True
    return x.copy(), y.copy(), False


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
        if (not passed or i == len(pm)-1) and start is not None:
            end = i if passed and i == len(pm)-1 else i-1
            length = end-start+1
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
    center = (xmin+xmax)/2
    outs = []
    for y in np.asarray(yvals, float):
        c = np.array(coeffs_desc, dtype=float).copy()
        c[-1] -= y
        roots = np.roots(c)
        real = roots[np.abs(np.imag(roots)) < 1e-8].real
        if len(real) == 0:
            outs.append(np.nan); continue
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
    return np.array(outs, float)


def _polyfit_force_origin(x, y, degree, w):
    if degree == 1:
        X = x[:, None]
        names = ("slope",)
    elif degree == 2:
        X = np.column_stack([x**2, x])
        names = ("quadratic", "linear")
    else:
        raise ValueError("Force origin currently supports linear/quadratic only.")
    sw = np.sqrt(w)
    beta, *_ = np.linalg.lstsq(X * sw[:, None], y * sw, rcond=None)
    coeff = np.concatenate([beta, [0.0]])
    return coeff, names


def fit_polynomial(x, y, degree=1, weight_mode="none", name=None,
                   bias_limit=15.0, min_points=6, origin_mode=ORIGIN_EXCLUDE):
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    x_fit, y_fit, synthetic_origin = _prepare_origin(x, y, origin_mode)
    w_fit = _weights(x_fit, weight_mode, origin_include=synthetic_origin)
    if origin_mode == ORIGIN_FORCE:
        w_original = _weights(x, weight_mode, origin_include=False)
        coeff, _ = _polyfit_force_origin(x, y, degree, w_original)
    else:
        coeff = np.polyfit(x_fit, y_fit, degree, w=np.sqrt(w_fit))
    predict = lambda xx: np.polyval(coeff, np.asarray(xx, float))
    yhat = predict(x)
    invert = lambda yy: _poly_invert(coeff, np.asarray(yy, float), x)
    backcalc = invert(y)
    bias = _bias(backcalc, x)
    pass_mask = np.isfinite(bias) & (np.abs(bias) <= bias_limit)
    crange, ccount = _contiguous_range(x, pass_mask, min_points)
    w_original = _weights(x, weight_mode, origin_include=False)
    p_free = degree if origin_mode == ORIGIN_FORCE else degree + 1
    stats = _stats(x, y, yhat, p_free, w_original)
    if degree == 1:
        slope, intercept = coeff
        equation = "y = slope·x + intercept"
        parameter_names = ("slope", "intercept")
    else:
        quad, linear, intercept = coeff
        equation = "y = quadratic·x² + linear·x + intercept"
        parameter_names = ("quadratic", "linear", "intercept")
    weighting_text = {"none":"None (wᵢ = 1)", "1/x":"1/x (wᵢ = 1/xᵢ)",
                      "1/x2":"1/x² (wᵢ = 1/xᵢ²)"}[weight_mode]
    notes = [
        f"Fit criterion: minimize Σ wᵢ(yᵢ − ŷᵢ)². Weighting: {weighting_text}.",
        f"Origin handling: {origin_mode}.",
        "Pearson r = corr(x,y) and preserves the sign of the X–Y association.",
        "Pearson r² = r² and does not use the fitted residuals.",
        "Fit R² = 1 − Σ(y−ŷ)² / Σ(y−ȳ)².",
        "Weighted R² = 1 − Σw(y−ŷ)² / Σw(y−ȳw)², where ȳw = Σwy/Σw.",
        "RMSE = sqrt(mean((y−ŷ)²)).",
        "Back-calculated X values are obtained by algebraically inverting the fitted equation.",
    ]
    if synthetic_origin and weight_mode != "none":
        notes.append("For Include + reciprocal weighting, the synthetic (0,0) origin receives unit weight because 1/0 is undefined; non-zero calibrators receive the requested reciprocal weight.")
    return FitResult(name=name or ("Linear" if degree == 1 else "Quadratic"), params=coeff,
        predict=predict, invert=invert, yhat=yhat, residuals=y-yhat, backcalc_x=backcalc,
        bias_pct=bias, weights=w_original, stats=stats, pass_mask=pass_mask,
        contiguous_range=crange, contiguous_count=ccount, equation=equation,
        parameter_names=parameter_names, calculation_notes="\n".join(notes),
        notes="Polynomial coefficients are shown explicitly by term.")


def _pade_predict(order, p, x):
    x = np.asarray(x, float)
    if order == "1/1":
        a,b,c = p
        return (a+b*x)/(1+c*x)
    if order == "2/1":
        a,b,c,d = p
        return (a+b*x+c*x*x)/(1+d*x)
    raise ValueError(order)


def _initial_pade(order, x, y, force=False):
    lin = np.polyfit(x, y, 1)
    slope, intercept = lin
    if force: intercept = 0.0
    if order == "1/1": return np.array([intercept, slope, 0.0])
    q = np.polyfit(x, y, min(2, len(x)-1))
    if len(q) == 3: c,b,a = q
    else: c,b,a = 0.0,slope,intercept
    if force: a = 0.0
    return np.array([a,b,c,0.0])


def _pade_invert(order, p, yvals, x_reference):
    xref = np.asarray(x_reference, float)
    xmin, xmax = np.nanmin(xref), np.nanmax(xref)
    center=(xmin+xmax)/2
    outs=[]
    for yy in np.asarray(yvals,float):
        if order=="1/1":
            a,b,c=p; denom=yy*c-b
            outs.append(np.nan if abs(denom)<1e-14 else float((a-yy)/denom))
        else:
            a,b,c,d=p
            roots=np.roots([c,b-yy*d,a-yy]) if abs(c)>1e-14 else np.roots([b-yy*d,a-yy])
            real=roots[np.abs(np.imag(roots))<1e-8].real
            if len(real)==0: outs.append(np.nan); continue
            nonneg=real[real>=0]; candidates=nonneg if len(nonneg) else real
            inside=candidates[(candidates>=xmin)&(candidates<=xmax)]
            if len(inside): chosen=inside[np.argmin(np.abs(inside-center))]
            else:
                dist=np.where(candidates<xmin,xmin-candidates,np.where(candidates>xmax,candidates-xmax,0))
                chosen=candidates[np.argmin(dist)]
            outs.append(float(chosen))
    return np.asarray(outs,float)


def fit_pade(x, y, order="1/1", weight_mode="none", bias_limit=15.0,
             min_points=6, origin_mode=ORIGIN_EXCLUDE):
    x=np.asarray(x,float); y=np.asarray(y,float)
    x_fit,y_fit,synthetic_origin=_prepare_origin(x,y,origin_mode)
    w_fit=_weights(x_fit,weight_mode,origin_include=synthetic_origin)
    sqrtw=np.sqrt(w_fit); force=origin_mode==ORIGIN_FORCE
    p0=_initial_pade(order,x_fit,y_fit,force=force)
    def unpack(q):
        if not force: return q
        if order=="1/1": return np.array([0.0,q[0],q[1]])
        return np.array([0.0,q[0],q[1],q[2]])
    q0 = p0 if not force else p0[1:]
    def resid(q):
        p=unpack(q)
        den=1+p[2]*x_fit if order=="1/1" else 1+p[3]*x_fit
        if np.any(np.abs(den)<1e-8): return np.full_like(y_fit,1e12)
        pred=_pade_predict(order,p,x_fit)
        if np.any(~np.isfinite(pred)): return np.full_like(y_fit,1e12)
        return sqrtw*(y_fit-pred)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fit=least_squares(resid,q0,max_nfev=20000)
    if not fit.success: raise RuntimeError(f"Padé [{order}] fit failed: {fit.message}")
    p=unpack(fit.x)
    predict=lambda xx:_pade_predict(order,p,np.asarray(xx,float))
    yhat=predict(x)
    grid=np.linspace(np.min(x),np.max(x),1000)
    den=1+p[2]*grid if order=="1/1" else 1+p[3]*grid
    if np.any(np.abs(den)<1e-5):
        raise RuntimeError(f"Padé [{order}] denominator approaches zero within the calibration range.")
    invert=lambda yy:_pade_invert(order,p,np.asarray(yy,float),x)
    backcalc=invert(y); bias=_bias(backcalc,x)
    pass_mask=np.isfinite(bias)&(np.abs(bias)<=bias_limit)
    crange,ccount=_contiguous_range(x,pass_mask,min_points)
    w_original=_weights(x,weight_mode,origin_include=False)
    p_free=len(p)-1 if force else len(p)
    stats=_stats(x,y,yhat,p_free,w_original)
    if order=="1/1": equation="y = (a + b·x) / (1 + c·x)"; parameter_names=("a","b","c")
    else: equation="y = (a + b·x + c·x²) / (1 + d·x)"; parameter_names=("a","b","c","d")
    calc_notes = (f"Nonlinear weighted least squares minimizes Σ wᵢ(yᵢ − ŷᵢ)². Origin handling: {origin_mode}. "
        "The denominator constant is fixed at 1 for identifiability.\n"
        "Pearson r = corr(x,y); Pearson r² = r². Fit R² uses ordinary residual sums of squares. Weighted R² uses weighted residual and weighted total sums of squares.")
    return FitResult(name=f"Padé [{order}]", params=p, predict=predict, invert=invert, yhat=yhat,
        residuals=y-yhat, backcalc_x=backcalc, bias_pct=bias, weights=w_original, stats=stats,
        pass_mask=pass_mask, contiguous_range=crange, contiguous_count=ccount, equation=equation,
        parameter_names=parameter_names, calculation_notes=calc_notes,
        notes="Padé parameters use denominator constant fixed to 1 for identifiability.")


MODEL_SPECS = [
    ("Linear", lambda x,y,b,m,o: fit_polynomial(x,y,1,"none","Linear",b,m,o)),
    ("Linear 1/x", lambda x,y,b,m,o: fit_polynomial(x,y,1,"1/x","Linear 1/x",b,m,o)),
    ("Linear 1/x²", lambda x,y,b,m,o: fit_polynomial(x,y,1,"1/x2","Linear 1/x²",b,m,o)),
    ("Quadratic", lambda x,y,b,m,o: fit_polynomial(x,y,2,"none","Quadratic",b,m,o)),
    ("Quadratic 1/x", lambda x,y,b,m,o: fit_polynomial(x,y,2,"1/x","Quadratic 1/x",b,m,o)),
    ("Quadratic 1/x²", lambda x,y,b,m,o: fit_polynomial(x,y,2,"1/x2","Quadratic 1/x²",b,m,o)),
    ("Padé [1/1]", lambda x,y,b,m,o: fit_pade(x,y,"1/1","none",b,m,o)),
    ("Padé [2/1]", lambda x,y,b,m,o: fit_pade(x,y,"2/1","none",b,m,o)),
]
