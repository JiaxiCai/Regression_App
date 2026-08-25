import numpy as np, pandas as pd
from scipy import stats

def descriptive_statistics(values):
    x=np.asarray(values,float); x=x[np.isfinite(x)]
    if len(x)==0: raise ValueError("No finite values.")
    q1,med,q3=np.percentile(x,[25,50,75]); mean=np.mean(x); sd=np.std(x,ddof=1) if len(x)>1 else np.nan
    return {"n":len(x),"mean":mean,"sd":sd,"cv_pct":sd/mean*100 if np.isfinite(sd) and mean!=0 else np.nan,
            "median":med,"min":np.min(x),"max":np.max(x),"iqr":q3-q1}

def shapiro_test(values):
    x=np.asarray(values,float); x=x[np.isfinite(x)]
    if len(x)<3: raise ValueError("Shapiro–Wilk requires at least 3 values.")
    w,p=stats.shapiro(x); return {"W":w,"p":p}

def precision_summary(df):
    rows=[]
    for level,g in df.groupby("level",sort=True):
        v=pd.to_numeric(g["value"],errors="coerce").dropna().to_numpy(float)
        if len(v)==0: continue
        mean=np.mean(v); sd=np.std(v,ddof=1) if len(v)>1 else np.nan
        rows.append({"level":level,"n":len(v),"mean":mean,"sd":sd,"cv_pct":sd/mean*100 if np.isfinite(sd) and mean!=0 else np.nan})
    return pd.DataFrame(rows)

def precision_components(df):
    w=df.copy(); w["value"]=pd.to_numeric(w["value"],errors="coerce"); w=w.dropna(subset=["run","value"])
    groups=[g["value"].to_numpy(float) for _,g in w.groupby("run") if len(g)>=2]
    if len(groups)<2:return {"within_sd":np.nan,"between_run_sd":np.nan,"total_sd":np.nan}
    ni=np.array([len(g) for g in groups],float); means=np.array([np.mean(g) for g in groups]); grand=np.sum(ni*means)/np.sum(ni)
    msw=sum(np.sum((g-np.mean(g))**2) for g in groups)/sum(len(g)-1 for g in groups)
    msb=np.sum(ni*(means-grand)**2)/(len(groups)-1)
    n0=(np.sum(ni)-np.sum(ni**2)/np.sum(ni))/(len(groups)-1)
    br=max((msb-msw)/n0,0)
    return {"within_sd":np.sqrt(msw),"between_run_sd":np.sqrt(br),"total_sd":np.sqrt(msw+br)}

def lob_lod(blank,low,alpha=0.95):
    b=np.asarray(blank,float); b=b[np.isfinite(b)]; l=np.asarray(low,float); l=l[np.isfinite(l)]
    if len(b)<2 or len(l)<2: raise ValueError("Need at least 2 blank and 2 low-level results.")
    z=stats.norm.ppf(alpha); lob=np.mean(b)+z*np.std(b,ddof=1); lod=lob+z*np.std(l,ddof=1)
    return {"LoB":lob,"LoD":lod,"blank_mean":np.mean(b),"blank_sd":np.std(b,ddof=1),"low_mean":np.mean(l),"low_sd":np.std(l,ddof=1)}

def loq_from_precision(levels,cvs,target_cv=20):
    x=np.asarray(levels,float); y=np.asarray(cvs,float); m=np.isfinite(x)&np.isfinite(y)&(x>0); x,y=x[m],y[m]
    if len(x)<2:return np.nan
    o=np.argsort(x); x,y=x[o],y[o]; inds=np.where(y<=target_cv)[0]
    if not len(inds):return np.nan
    i=inds[0]
    if i==0:return float(x[0])
    x1,x2=x[i-1],x[i]; y1,y2=y[i-1],y[i]
    return float(x2 if y2==y1 else x1+(target_cv-y1)*(x2-x1)/(y2-y1))

def linearity_analysis(x,y,allowable_pct=10):
    x=np.asarray(x,float); y=np.asarray(y,float); m=np.isfinite(x)&np.isfinite(y); x,y=x[m],y[m]
    if len(x)<4: raise ValueError("Linearity requires at least 4 points.")
    lin=np.polyfit(x,y,1); quad=np.polyfit(x,y,2); yl=np.polyval(lin,x); yq=np.polyval(quad,x); den=np.sum((y-np.mean(y))**2)
    pct=np.full_like(x,np.nan); nz=np.abs(yl)>1e-15; pct[nz]=(yq[nz]-yl[nz])/yl[nz]*100; mx=np.nanmax(np.abs(pct))
    return {"linear_r2":1-np.sum((y-yl)**2)/den,"quadratic_r2":1-np.sum((y-yq)**2)/den,"max_abs_nonlinearity_pct":mx,"passes":bool(mx<=allowable_pct)}

def reference_interval(values,bootstrap=2000,seed=12345):
    x=np.asarray(values,float); x=x[np.isfinite(x)]
    if len(x)<3: raise ValueError("Need at least 3 values.")
    lo,hi=np.percentile(x,[2.5,97.5]); rng=np.random.default_rng(seed)
    b=np.asarray([np.percentile(rng.choice(x,size=len(x),replace=True),[2.5,97.5]) for _ in range(bootstrap)])
    return {"n":len(x),"lower":lo,"upper":hi,"lower_ci":tuple(np.percentile(b[:,0],[2.5,97.5])),
            "upper_ci":tuple(np.percentile(b[:,1],[2.5,97.5])),"median":np.median(x)}

def interference_analysis(control,test):
    c=np.asarray(control,float); t=np.asarray(test,float); c=c[np.isfinite(c)]; t=t[np.isfinite(t)]
    if not len(c) or not len(t):raise ValueError("Need control and test values.")
    cm,tm=np.mean(c),np.mean(t); bias=tm-cm
    return {"control_mean":cm,"test_mean":tm,"absolute_bias":bias,"percent_bias":bias/cm*100 if cm!=0 else np.nan}

def roc_analysis(labels,scores):
    labels=np.asarray(labels); scores=np.asarray(scores,float); m=np.isfinite(scores); labels,scores=labels[m],scores[m]
    u=np.unique(labels)
    if len(u)!=2: raise ValueError("ROC requires exactly two classes.")
    pos=u[-1]; y=(labels==pos).astype(int); ths=np.r_[np.inf,np.sort(np.unique(scores))[::-1],-np.inf]; rows=[]
    for th in ths:
        pred=scores>=th; tp=np.sum(pred&(y==1)); fp=np.sum(pred&(y==0)); tn=np.sum((~pred)&(y==0)); fn=np.sum((~pred)&(y==1))
        sens=tp/(tp+fn) if tp+fn else np.nan; spec=tn/(tn+fp) if tn+fp else np.nan; rows.append((th,sens,spec))
    df=pd.DataFrame(rows,columns=["threshold","sensitivity","specificity"]).dropna()
    fpr=1-df["specificity"].to_numpy(); tpr=df["sensitivity"].to_numpy(); o=np.argsort(fpr); auc=np.trapezoid(tpr[o],fpr[o])
    best=df.iloc[int(np.nanargmax((df["sensitivity"]+df["specificity"]-1).to_numpy()))]
    return {"auc":float(auc),"best":best.to_dict(),"positive_class":pos,"curve":df.copy()}
