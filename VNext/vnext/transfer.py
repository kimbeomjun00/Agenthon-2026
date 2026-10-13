"""## Executive summary (read this first)
For stale FX target histories, blend old target paths with cutoff-valid proxy paths.
Loadings are fitted only on dates where the target and G10 proxies were both observed.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from qfbench2_track_forecasting.cli import _asset_col
from .numeric import FX,prepare,_scale,_causal_scales,_finish


def adjust(panels,assets,steps,asof,base,seed):
    if not all(a in FX for a in assets): return base,{'applied':False}
    hist=prepare(panels,assets,asof,'level')
    lag=(pd.Timestamp(asof)-hist.steps.index[-1]).days
    if lag<180: return base,{'applied':False}
    proxies=[]
    for df in panels.values():
        ac=_asset_col(df)
        if ac is not None:
            proxies.extend(str(a) for a in df[ac].unique() if str(a) in FX and str(a) not in assets)
    proxies=sorted(set(proxies))
    if len(proxies)<2: return base,{'applied':False,'reason':'no contemporaneous proxy group','staleness_days':lag}
    ph=prepare(panels,proxies,asof,'level')
    overlap=hist.steps.join(ph.steps,how='inner',lsuffix='_target',rsuffix='_proxy').dropna()
    if len(overlap)<60: return base,{'applied':False,'reason':'fewer than 60 overlapping proxy rows','staleness_days':lag}
    x=overlap[proxies].to_numpy(float)
    y=overlap[assets].to_numpy(float)
    xmean=x.mean(axis=0);ymean=y.mean(axis=0)
    xsd=np.maximum(x.std(axis=0,ddof=1),1e-12)
    xz=(x-xmean)/xsd
    beta=np.linalg.solve(xz.T@xz+len(xz)*0.1*np.eye(len(proxies)),xz.T@(y-ymean))
    residual=(y-ymean)-xz@beta
    residual-=residual.mean(axis=0)
    current=ph.steps.to_numpy(float)
    psd=_scale(current)
    causal=_causal_scales(current)
    pool=(current/np.maximum(causal,1e-12))[min(120,len(current)//3):]
    pool-=pool.mean(axis=0)
    pool/=np.maximum(pool.std(axis=0,ddof=1),1e-12)
    rng=np.random.default_rng(seed+99031)
    max_h=int(steps.max())
    n=len(base)
    pidx=rng.integers(len(pool),size=(n,max_h))
    eidx=rng.integers(len(residual),size=(n,max_h))
    paths=(pool[pidx]*psd/xsd)@beta+residual[eidx]
    proxy_draws=_finish(hist,paths,steps)
    # Keep half the original joint paths; the regression is uncertain across the missing years.
    chosen=rng.random(n)<0.5
    out=base.copy();out[chosen]=proxy_draws[chosen]
    return out,{'applied':True,'method':'50/50 stale-target and current-proxy joint path mixture',
                'staleness_days':lag,'overlap_rows':len(overlap),'proxy_assets':proxies,
                'fit_last_date':str(overlap.index[-1].date()),'ridge_strength':0.1,
                'proxy_draws':int(chosen.sum())}
