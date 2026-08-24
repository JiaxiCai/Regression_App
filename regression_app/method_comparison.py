from dataclasses import dataclass
from typing import Tuple
import numpy as np
from scipy.stats import norm

@dataclass
class MethodComparisonResult:
    method: str
    slope: float
    intercept: float
    slope_ci: Tuple[float, float]
    intercept_ci: Tuple[float, float]
    yhat: np.ndarray
    residuals: np.ndarray
    notes: str

def deming_regression(x, y, lambda_ratio=1.0, confidence=0.95, bootstrap=1000, seed=12345):
    x = np.asarray(x, float); y = np.asarray(y, float)
    if len(x) < 3: raise ValueError("Deming regression requires at least 3 paired observations.")
    if lambda_ratio <= 0: raise ValueError("Deming lambda must be > 0.")

    def fit_once(xx, yy):
        xb, yb = np.mean(xx), np.mean(yy)
        dx, dy = xx-xb, yy-yb
        sxx = np.mean(dx*dx); syy = np.mean(dy*dy); sxy = np.mean(dx*dy)
        if abs(sxy) < 1e-15: raise ValueError("Deming regression is undefined when covariance is zero.")
        lam = float(lambda_ratio)
        disc = (syy - lam*sxx)**2 + 4*lam*sxy*sxy
        b = (syy - lam*sxx + np.sqrt(disc)) / (2*sxy)
        a = yb - b*xb
        return a, b

    a, b = fit_once(x, y)
    yhat = a + b*x
    rng = np.random.default_rng(seed)
    boots=[]; n=len(x)
    for _ in range(int(bootstrap)):
        idx=rng.integers(0,n,n)
        try:
            aa,bb=fit_once(x[idx],y[idx])
            if np.isfinite(aa) and np.isfinite(bb): boots.append((aa,bb))
        except Exception:
            pass
    if len(boots) >= 50:
        arr=np.asarray(boots); alpha=1-confidence
        a_ci=tuple(np.quantile(arr[:,0],[alpha/2,1-alpha/2]))
        b_ci=tuple(np.quantile(arr[:,1],[alpha/2,1-alpha/2]))
    else:
        a_ci=(np.nan,np.nan); b_ci=(np.nan,np.nan)

    return MethodComparisonResult(
        "Deming", float(b), float(a),
        (float(b_ci[0]),float(b_ci[1])), (float(a_ci[0]),float(a_ci[1])),
        yhat, y-yhat,
        f"Classical Deming regression with λ = σy²/σx² = {lambda_ratio:g}. "
        f"95% CIs use {bootstrap} paired bootstrap resamples."
    )

def passing_bablok(x, y, confidence=0.95):
    x=np.asarray(x,float); y=np.asarray(y,float); n=len(x)
    if n < 3: raise ValueError("Passing–Bablok regression requires at least 3 paired observations.")
    slopes=[]
    for i in range(n-1):
        for j in range(i+1,n):
            dx=x[j]-x[i]
            if dx == 0: continue
            s=(y[j]-y[i])/dx
            if np.isclose(s,-1.0,atol=1e-12,rtol=0): continue
            if np.isfinite(s): slopes.append(float(s))
    if len(slopes)<2: raise ValueError("Not enough finite pairwise slopes.")
    slopes=np.sort(np.asarray(slopes)); N=len(slopes); K=int(np.sum(slopes < -1.0))
    if N%2:
        rank=(N+1)//2 + K
        if not 1 <= rank <= N: raise ValueError("Shifted median rank outside valid range.")
        b=slopes[rank-1]
    else:
        r1=N//2+K; r2=r1+1
        if not (1<=r1<=N and 1<=r2<=N): raise ValueError("Shifted median ranks outside valid range.")
        b=0.5*(slopes[r1-1]+slopes[r2-1])
    a=float(np.median(y-b*x)); yhat=a+b*x

    alpha=1-confidence; z=norm.ppf(1-alpha/2)
    C=z*np.sqrt(n*(n-1)*(2*n+5)/18)
    M1=int(np.rint((N-C)/2)); M2=N-M1+1
    lr=M1+K; hr=M2+K
    if 1<=lr<=N and 1<=hr<=N:
        bl=float(slopes[lr-1]); bh=float(slopes[hr-1])
        if bl>bh: bl,bh=bh,bl
        al=float(np.median(y-bh*x)); ah=float(np.median(y-bl*x))
    else:
        bl=bh=al=ah=np.nan
    return MethodComparisonResult(
        "Passing–Bablok", float(b), float(a), (bl,bh), (al,ah), yhat, y-yhat,
        "Passing–Bablok 1983 method-comparison estimator using the shifted median of pairwise slopes; "
        "95% confidence intervals use the rank-based normal approximation."
    )
