"""## Executive summary (read this first)
Inflation specialists add shared uncertainty about the future trend to ordinary shocks.
Choose trend and uncertainty from resolved folds inside the current cutoff only.
Other assets retain the uploaded V11 distribution; this is the conservative release engine.
"""
import numpy as np
import pandas as pd
from qfbench2_common.scoring.crps import crps_ensemble
from qfbench2_track_forecasting.cli import _draw
from v11_new.production_cli import _daily_e2_draws
from .specialists import prepare,prefix,paths,finish,PRICES,_scale

KINDS=['trend6','trend12','trend36','trend60','blend_trend','seasonal','robust12','local_linear']
UNCERTAINTY=[0.,.5,1.,1.5]

def candidates(s,steps,draws,seed):
    x=s.x;d=len(s.assets);maxh=int((steps+s.offsets[:,None]).max())
    fullsd=np.maximum(x.std(axis=0,ddof=1),1e-12)
    corr=np.nan_to_num(np.corrcoef(x.T),nan=0.) if d>1 else np.ones((1,1))
    corr=np.atleast_2d(corr);np.fill_diagonal(corr,1.)
    w,v=np.linalg.eigh(corr);chol=np.linalg.cholesky(v@np.diag(np.maximum(w,1e-8))@v.T)
    # Time-major draws match the official monthly sampler's RNG traversal.
    z=np.random.default_rng(seed).standard_normal((maxh,draws,d)).transpose(1,0,2)@chol.T
    ordinary={'baseline':finish(s,z*fullsd,steps)}
    residual=x-pd.DataFrame(x).rolling(12,min_periods=6).mean().shift(1).fillna(0).to_numpy()
    sd=np.sqrt(.75*np.var(residual[-60:],axis=0,ddof=1)+.25*np.var(residual,axis=0,ddof=1))
    for kind in KINDS:
        window={'trend6':6,'trend12':12,'trend36':36,'trend60':60}.get(kind,12)
        mu=x[-window:].mean(axis=0)
        if kind=='blend_trend':mu=.5*x[-12:].mean(axis=0)+.5*x[-36:].mean(axis=0)
        elif kind=='robust12':mu=np.median(x[-12:],axis=0)
        elif kind=='local_linear':
            recent=s.levels.ffill().iloc[-12:].to_numpy(float);tt=np.arange(len(recent));tt=tt-tt.mean()
            mu=np.clip(np.sum(tt[:,None]*recent,axis=0)/np.sum(tt**2),-2*fullsd,2*fullsd)
        increments=z*sd+mu
        if kind=='seasonal':
            months=s.dates.month.to_numpy();last=s.dates[-1].month
            for t in range(maxh):
                block=x[(months==(last+t)%12+1)&(np.arange(len(x))>=max(0,len(x)-120))]
                if len(block)>=3:increments[:,t]+=.5*(block.mean(axis=0)-mu)
        ordinary[kind]=finish(s,increments,steps)
    means=pd.DataFrame(s.x).rolling(12,min_periods=12).mean()
    drift=(means-means.rolling(36,min_periods=12).mean()).dropna().to_numpy(float,copy=True)
    if not len(drift):drift=np.zeros((1,len(s.assets)))
    drift-=drift.mean(axis=0)
    # A single historical trend-change vector supplies coherent inflation-regime uncertainty.
    idx=np.random.default_rng(seed+331).integers(len(drift),size=draws)
    shift=drift[idx][:,None,:]*steps.T[None,:,:]
    result={'baseline':ordinary['baseline']}
    for kind in KINDS:
        for amount in UNCERTAINTY:
            result[f'{kind}:u{amount:g}']=ordinary[kind]+amount*shift
    return result

def choose(s,steps):
    hvec=steps.max(axis=0).astype(int);maximum=int(hvec.max())
    origins=list(range(len(s.x)-maximum,83,-maximum))[:8][::-1]
    losses=[];names=None
    for fold,end in enumerate(origins):
        gaps=np.diff(s.dates[end-1:end+maximum].values).astype('timedelta64[D]').astype(int)
        if np.any(gaps>65):continue
        hist=prefix(s,end);truth=np.stack([s.x[end:end+h].sum(axis=0) for h in hvec])+hist.anchor
        scale=np.maximum(_scale(hist.x)*np.sqrt(hvec[:,None]),1e-8)
        sims=candidates(hist,np.tile(hvec,(len(s.assets),1)),384,1553+fold)
        names=list(sims);row=[]
        for sample in sims.values():
            crps=crps_ensemble(sample.reshape(len(sample),-1),truth.reshape(-1)).reshape(truth.shape)
            lo,hi=np.quantile(sample,[.05,.95],axis=0)
            tail=.5*(np.maximum(.05*(truth-lo),-.95*(truth-lo))+np.maximum(.95*(truth-hi),-.05*(truth-hi)))
            row.append(np.mean((.8*crps+.2*tail)/scale,axis=0))
        losses.append(row)
    if len(losses)<4:return ['baseline']*len(s.assets),{'folds':len(losses),'fallback':'insufficient history'}
    arr=np.array(losses);mean=arr.mean(axis=0);best=mean.argmin(axis=0)
    for ai,ki in enumerate(best):
        improvement=1-mean[ki,ai]/max(mean[0,ai],1e-12)
        if improvement<.03 or np.mean(arr[:,ki,ai]<arr[:,0,ai])<.5:best[ai]=0
    selected=[names[i] for i in best]
    return selected,{'folds':len(losses),'asset_models':dict(zip(s.assets,selected)),
        'selection_latest_resolved_date':str(s.dates[-1].date()),
        'criterion':'80% scaled marginal CRPS + 20% 5/95% pinball',
        'candidate_losses':{a:{k:float(mean[ki,ai]) for ki,k in enumerate(names)} for ai,a in enumerate(s.assets)}}

def forecast(panels,assets,steps,asof,target,draws,seed,monthly=False):
    if not monthly or not any(a in PRICES for a in assets):
        if monthly:
            raw,_=_draw(panels,assets,list(range(steps.shape[1])),asof,draws,seed,target_type=target,panel_steps=steps)
            base=raw.transpose(0,2,1)
        else:
            s=prepare(panels,assets,asof,target,False)
            stale=(pd.Timestamp(asof)-s.dates[-1]).days>=180
            if stale:base=paths(s,steps,draws,seed,['baseline'])['baseline']
            else:base,*_=_daily_e2_draws(panels,assets,steps[0].tolist(),asof,target,draws,seed)
        return base,{'engine':'price_specialists_v11_fallback','asset_models':dict.fromkeys(assets,'V11'),
                     'gap_safe':bool(not monthly and stale)}
    s=prepare(panels,assets,asof,target,True)
    selected,meta=choose(s,steps)
    sims=candidates(s,steps,draws,seed)
    for i,a in enumerate(assets):
        if a not in PRICES:selected[i]='baseline'
    sample=np.stack([sims[selected[i]][:,:,i] for i in range(len(assets))],axis=2)
    # Shared whole-draw insurance component preserves joint path interpretation.
    conservative=np.random.default_rng(seed+15531).random(draws)<.15
    sample[conservative]=sims['baseline'][conservative]
    meta['asset_models']=dict(zip(assets,selected))
    return sample,{'engine':'inflation_uncertain_trend_shared_shocks','selection':meta,
                  'baseline_draw_fraction':.15,'n_history_rows':len(s.x),
                  'note':'Only CPI/PCE use specialists; other columns retain the original monthly Gaussian walk with shared Gaussian shocks.'}
