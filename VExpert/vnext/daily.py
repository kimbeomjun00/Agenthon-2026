"""## Executive summary (read this first)
Keep V11 on ordinary daily inputs; repair internal gaps and unequal current anchors.
Optional researched modes project volatility or select scale/drift from resolved folds.
"""
import numpy as np
import pandas as pd
from v11_new.production_cli import _daily_e2_draws
from .specialists import prepare,finish,_scale

def simulate(s,steps,draws,seed,scale=1.,drift_weight=1.,term=False):
    x=s.x;maxh=int(steps.max());rng=np.random.default_rng(seed)
    fullsd=np.maximum(x.std(axis=0,ddof=1),1e-12)
    z=(x-x.mean(axis=0))/fullsd
    idx=rng.integers(len(x),size=(draws,maxh))
    sd=_scale(x)
    if term:
        long=np.var(x[-min(1000,len(x)):],axis=0,ddof=1)
        projected=long+(sd**2-long)*np.exp(-np.arange(maxh)[:,None]/63.)
        sigma=np.sqrt(np.maximum(projected,1e-16))
    else:sigma=np.broadcast_to(sd,(maxh,len(s.assets)))
    mu=x.mean(axis=0)*drift_weight if s.target=='log_return' else np.zeros(len(s.assets))
    return finish(s,z[idx]*sigma*np.asarray(scale)+mu,steps)

def forecast(panels,assets,steps,asof,target,draws,seed,mode='fixed'):
    s=prepare(panels,assets,asof,target,False)
    if mode=='term':return simulate(s,steps,draws,seed,term=True),{'engine':'projected_volatility_term','history_rows':len(s.x)}
    # Compare the usable increment dates with the original common level/return history.
    common=s.levels.dropna()
    old_dates=common.index if target=='log_return' else common.index[1:]
    anchors=common.iloc[-1].to_numpy(float) if target!='log_return' else np.zeros(len(assets))
    repair=not old_dates.equals(s.dates) or not np.array_equal(anchors,s.anchor) or len(s.x)<100
    if repair:
        sample=simulate(s,steps,draws,seed)
    else:sample,*_=_daily_e2_draws(panels,assets,steps[0].tolist(),asof,target,draws,seed)
    return sample,{'engine':'v11_gap_anchor_repair' if repair else 'v11_unchanged',
                   'history_rows':len(s.x),'gap_safe':bool(repair)}
