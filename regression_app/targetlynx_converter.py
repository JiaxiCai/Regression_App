from pathlib import Path
import re, pandas as pd
SAMPLE_CANDIDATES=["sample name","sample","sample id","sampleid","name"]
ANALYTE_CANDIDATES=["compound name","compound","analyte","target","component"]
VALUE_CANDIDATES=["calculated concentration","concentration","conc.","conc","result","response","peak area","area"]
TYPE_CANDIDATES=["sample type","type"]
FLAG_CANDIDATES=["primary flag","primary","flag"]

def read_targetlynx_export(path):
    p=Path(path)
    if p.suffix.lower() in (".xlsx",".xlsm",".xls"): return pd.read_excel(path)
    for sep in [",","\t",";"]:
        try:
            df=pd.read_csv(path,sep=sep,engine="python")
            if df.shape[1]>1:return df
        except Exception:pass
    raise ValueError("Could not parse the TargetLynx export.")

def _norm(s): return re.sub(r"\s+"," ",str(s).strip().lower())
def guess_columns(df):
    norm={_norm(c):c for c in df.columns}
    def find(cands):
        for c in cands:
            if c in norm:return norm[c]
        for k,v in norm.items():
            if any(c in k for c in cands):return v
        return None
    return {"sample":find(SAMPLE_CANDIDATES),"analyte":find(ANALYTE_CANDIDATES),"value":find(VALUE_CANDIDATES),
            "type":find(TYPE_CANDIDATES),"flag":find(FLAG_CANDIDATES)}
def to_long(df,sample_col,analyte_col=None,value_col=None):
    if analyte_col and value_col:
        return df[[sample_col,analyte_col,value_col]].copy().rename(columns={sample_col:"Sample",analyte_col:"Analyte",value_col:"Value"})
    return df.melt(id_vars=[sample_col],var_name="Analyte",value_name="Value").rename(columns={sample_col:"Sample"})
def to_wide(long_df):
    return long_df.pivot_table(index="Sample",columns="Analyte",values="Value",aggfunc="first").reset_index()
def one_dimensional(long_df,analyte,value_name="Value"):
    out=long_df[long_df["Analyte"].astype(str)==str(analyte)].copy()
    return out[["Sample","Value"]].rename(columns={"Value":value_name})
