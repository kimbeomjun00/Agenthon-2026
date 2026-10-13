"""## Executive summary (read this first)
Choose a numerical model separately for each asset using resolved, cutoff-local folds.
Shared historical innovation rows couple every specialist across assets and horizons.
No fitted policy, benchmark losses or historical outcomes are loaded at inference time.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd
from scipy.stats import norm, rankdata
from qfbench2_common.scoring.crps import crps_ensemble
from qfbench2_track_forecasting.cli import _series, _diff_without_gaps, _draw
from qfbench2_track_forecasting.targets import log_return_steps
from qfbench2_track_forecasting.scoring import _composite
from v11_new.production_cli import _daily_e2_draws
from .numeric import FX, _scale, _causal_scales

PRICES={'CPI_ALL','CPI_CORE','PCE_ALL','PCE_CORE'}
DAILY=['baseline','ewma20','ewma120','rolling250','fhs60','fhs120','gaussian',
       'student5','garch','mean_zero','mean_shrink','momentum','ar_changes','ou_level','log_rw']
MONTHLY=['baseline','trend6','trend12','trend36','trend60','damped12','ar_changes',
         'local_linear','seasonal','robust12','mean_revert','log_trend12','log_trend36','blend_trend']

@dataclass
class State:
    levels: pd.DataFrame
    x: np.ndarray
    dates: pd.DatetimeIndex
    anchor: np.ndarray
    assets: list[str]
    target: str
    monthly: bool
    offsets: np.ndarray

def prepare(panels,assets,asof,target,monthly=False):
    series={};changes={}
    for a in assets:
        s=_series(panels,a,asof).astype(float).sort_index()
        s.index=pd.DatetimeIndex(pd.to_datetime(s.index))
        if s.index.has_duplicates:raise ValueError('duplicate dates')
        s=s.replace([np.inf,-np.inf],np.nan).dropna()
        series[a]=s
        if target=='log_return':
            x=pd.Series(log_return_steps(s),index=s.index)
            x=x.where(pd.Series(s.index,index=s.index).diff().dt.days<=10)
        elif monthly:
            x=s.diff().where(np.r_[False,np.diff(s.index.to_period('M').asi8)==1])
        else:x=_diff_without_gaps(s)
        changes[a]=x
    frame=pd.DataFrame(changes).dropna()
    if len(frame)<30:raise ValueError('insufficient aligned increments')
    levels=pd.DataFrame(series).sort_index()
    anchor=np.zeros(len(assets)) if target=='log_return' else np.array([series[a].iloc[-1] for a in assets])
    offsets=np.zeros(len(assets),int)
    if monthly:
        last=np.array([series[a].index[-1].to_period('M').ordinal for a in assets])
        offsets=last-last.min()
    return State(levels,frame.to_numpy(float),frame.index,anchor,list(assets),target,monthly,offsets)

def prefix(s,end):
    levels=s.levels.loc[:s.dates[end-1]]
    anchor=np.zeros(len(s.assets)) if s.target=='log_return' else levels.ffill().iloc[-1].to_numpy(float)
    return State(levels,s.x[:end],s.dates[:end],anchor,s.assets,s.target,s.monthly,np.zeros(len(s.assets),int))

def finish(s,path,steps,logmask=None):
    cumulative=np.concatenate([np.zeros((len(path),1,len(s.assets))),np.cumsum(path,axis=1)],axis=1)
    out=np.empty((len(path),steps.shape[1],len(s.assets)))
    for i in range(len(s.assets)):
        out[:,:,i]=cumulative[:,s.offsets[i]+steps[i],i]-cumulative[:,s.offsets[i],i,None]
    if s.target!='log_return':
        if logmask is None:logmask=np.zeros(len(s.assets),bool)
        for i,logged in enumerate(logmask):
            out[:,:,i]=s.anchor[i]*np.exp(np.clip(out[:,:,i],-15,15)) if logged else s.anchor[i]+out[:,:,i]
    return out

def pool(s,draws,maxh,seed):
    rng=np.random.default_rng(seed)
    # One actual historical row per future step supplies shocks to all specialist columns.
    idx=rng.integers(len(s.x),size=(draws,maxh))
    return idx,rng

def paths(s,steps,draws,seed,kinds):
    """Return all candidate paths with common shock rows, for asset-wise comparison."""
    x=s.x;n,d=x.shape;maxh=int((steps+s.offsets[:,None]).max())
    idx,rng=pool(s,draws,maxh,seed)
    fullsd=np.maximum(x.std(axis=0,ddof=1),1e-12)
    z=(x-x.mean(axis=0))/fullsd
    base_sd=_scale(x);base_mu=x.mean(axis=0) if s.target=='log_return' else np.zeros(d)
    # Common Gaussian and t innovations retain empirical cross-asset covariance.
    corr=np.nan_to_num(np.corrcoef(x.T),nan=0.) if d>1 else np.ones((1,1))
    corr=np.atleast_2d(corr);np.fill_diagonal(corr,1.)
    w,v=np.linalg.eigh(corr);chol=np.linalg.cholesky(v@np.diag(np.maximum(w,1e-8))@v.T)
    # Gaussianized ranks keep the same historical row coupling as every empirical model.
    normal_pool=norm.ppf((rankdata(x,axis=0)-.5)/n)
    normal_pool/=np.maximum(normal_pool.std(axis=0,ddof=1),1e-12)
    gaussian=normal_pool[idx]
    student=gaussian*np.sqrt(3/np.maximum(rng.chisquare(5,size=(draws,maxh,1)),1e-8))
    cache={}
    result={}
    for kind in kinds:
        mu=base_mu.copy();sd=base_sd.copy();innov=z[idx];logmask=None
        if not s.monthly:
            if kind=='ewma20':sd=_scale(x,20)
            elif kind=='ewma120':sd=_scale(x,120)
            elif kind=='rolling250':sd=np.sqrt(.8*np.var(x[-250:],axis=0,ddof=1)+.2*fullsd**2)
            elif kind.startswith('fhs'):
                hl=60 if kind=='fhs60' else 120
                if hl not in cache:
                    causal=_causal_scales(x,hl)
                    standardized=(x-x.mean(axis=0))/np.maximum(causal,1e-12)
                    # Repeat the burn-in-free pool by aligned row labels, rather than shifting assets.
                    standardized[:120]=standardized[120:240] if n>=240 else standardized[:120]
                    standardized-=standardized.mean(axis=0)
                    standardized/=np.maximum(standardized.std(axis=0,ddof=1),1e-12)
                    cache[hl]=standardized
                innov=cache[hl][idx];sd=_scale(x,hl)
            elif kind=='gaussian':innov=gaussian
            elif kind=='student5':innov=student
            elif kind=='mean_zero':mu=np.zeros(d)
            elif kind=='mean_shrink':mu=base_mu*.25
            elif kind=='momentum':
                mu=(x[-126:].mean(axis=0)*.15 if s.target=='log_return' else x[-63:].mean(axis=0)*.1)
                mu=np.clip(mu,-.04*sd,.04*sd)
            elif kind=='log_rw' and s.target=='level':
                logmask=np.array([a in FX and (s.levels[a].dropna()>0).all() for a in s.assets])
                logged=pd.DataFrame({a:_diff_without_gaps(np.log(s.levels[a].dropna())) if logmask[i]
                       else pd.Series(x[:,i],index=s.dates) for i,a in enumerate(s.assets)}).reindex(s.dates).to_numpy(float)
                logged=np.nan_to_num(logged)
                lsd=np.maximum(logged.std(axis=0,ddof=1),1e-12)
                innov=((logged-logged.mean(axis=0))/lsd)[idx];sd=_scale(logged)
        else:
            if kind=='baseline':sd=fullsd;innov=gaussian
            elif kind in ('trend6','trend12','trend36','trend60','damped12','seasonal','robust12','blend_trend'):
                window={'trend6':6,'trend12':12,'trend36':36,'trend60':60}.get(kind,12)
                mu=x[-window:].mean(axis=0)
                if kind=='robust12':mu=np.median(x[-12:],axis=0)
                if kind=='blend_trend':mu=.5*x[-12:].mean(axis=0)+.5*x[-36:].mean(axis=0)
                residual=x-pd.DataFrame(x).rolling(12,min_periods=6).mean().shift(1).fillna(0).to_numpy()
                sd=np.sqrt(.75*np.var(residual[-60:],axis=0,ddof=1)+.25*np.var(residual,axis=0,ddof=1))
                rz=(residual-residual.mean(axis=0))/np.maximum(residual.std(axis=0,ddof=1),1e-12)
                innov=rz[idx]
            elif kind in ('ar_changes','local_linear'):
                mu=x[-36:].mean(axis=0)
                sd=np.sqrt(.75*np.var(x[-60:],axis=0,ddof=1)+.25*fullsd**2)
            elif kind.startswith('log_trend'):
                logmask=np.array([a in PRICES and (s.levels[a].dropna()>0).all() for a in s.assets])
                lx=pd.DataFrame({a:np.log(s.levels[a].dropna()).diff() if logmask[i]
                   else pd.Series(x[:,i],index=s.dates) for i,a in enumerate(s.assets)}).reindex(s.dates).to_numpy(float)
                lx=np.nan_to_num(lx);mu=lx[-(12 if kind=='log_trend12' else 36):].mean(axis=0)
                sd=_scale(lx);innov=((lx-lx.mean(axis=0))/np.maximum(lx.std(axis=0,ddof=1),1e-12))[idx]
                # For non-price columns these candidates are ordinary level trends.
        path=innov*sd+mu
        if kind=='garch':
            variance=np.broadcast_to(sd**2,(draws,d)).copy();longvar=np.var(x[-500:],axis=0,ddof=1)
            for t in range(maxh):
                shock=innov[:,t]*np.sqrt(np.maximum(variance,1e-16));path[:,t]=mu+shock
                variance=.02*longvar+.06*shock**2+.92*variance
        if kind=='ar_changes':
            centred=x[-120:]-mu
            phi=np.clip(np.sum(centred[1:]*centred[:-1],axis=0)/np.maximum(np.sum(centred[:-1]**2,axis=0),1e-12),-.6,.6)*.6
            previous=np.broadcast_to(x[-1]-mu,(draws,d)).copy()
            for t in range(maxh):
                previous=phi*previous+innov[:,t]*sd*np.sqrt(1-phi**2)
                path[:,t]=mu+previous
        if kind=='ou_level' and s.target=='level':
            level=s.levels.ffill().dropna().iloc[-500:].to_numpy(float)
            centre=level.mean(axis=0);lag=level[:-1]-centre;delta=np.diff(level,axis=0)
            kappa=np.clip(-np.sum(lag*delta,axis=0)/np.maximum(np.sum(lag**2,axis=0),1e-12),0,.01)*.25
            current=np.broadcast_to(s.anchor,(draws,d)).copy()
            for t in range(maxh):
                path[:,t]=-kappa*(current-centre)+innov[:,t]*sd;current+=path[:,t]
        if s.monthly and kind=='mean_revert':
            centre=s.levels.ffill().iloc[-36:].mean().to_numpy(float)
            current=np.broadcast_to(s.anchor,(draws,d)).copy()
            for t in range(maxh):
                path[:,t]=.03*(centre-current)+innov[:,t]*sd;current+=path[:,t]
        if s.monthly and kind=='local_linear':
            recent=s.levels.ffill().iloc[-12:].to_numpy(float);tt=np.arange(len(recent));tt=tt-tt.mean()
            slope=np.sum(tt[:,None]*recent,axis=0)/np.sum(tt**2)
            slope=np.clip(slope,-2*fullsd,2*fullsd)
            path+=slope-mu
        if s.monthly and kind=='damped12':
            path+=mu[None,None,:]*(.95**np.arange(maxh))[None,:,None]-mu
        if s.monthly and kind=='seasonal':
            months=s.dates.month.to_numpy();last_month=s.dates[-1].month
            for t in range(maxh):
                month=(last_month+t)%12+1
                block=x[(months==month)&(np.arange(n)>=max(0,n-120))]
                seasonal=block.mean(axis=0) if len(block)>=3 else mu
                path[:,t]+=.5*(seasonal-mu)
        result[kind]=finish(s,path,steps,logmask)
    return result

def choices(s,steps,folds=8,policy='all'):
    kinds=MONTHLY if s.monthly else DAILY
    hvec=np.max(steps,axis=0).astype(int);maxh=int(hvec.max())
    mintrain=84 if s.monthly else 750
    origins=list(range(len(s.x)-maxh,mintrain-1,-maxh))[:folds][::-1]
    losses=[]
    for k,end in enumerate(origins):
        gaps=np.diff(s.dates[end-1:end+maxh].values).astype('timedelta64[D]').astype(int)
        if np.any(gaps>(65 if s.monthly else 10)):continue
        hist=prefix(s,end);truth=np.stack([np.sum(s.x[end:end+h],axis=0) for h in hvec])
        if s.target!='log_return':truth+=hist.anchor
        scale=np.maximum(_scale(hist.x)*np.sqrt(hvec[:,None]),1e-8)
        sims=paths(hist,np.tile(hvec,(len(s.assets),1)),256,1823+k,kinds)
        row=[]
        for kind in kinds:
            sample=sims[kind]
            crps=crps_ensemble(sample.reshape(len(sample),-1),truth.reshape(-1)).reshape(truth.shape)
            # The selector uses marginal CRPS, with a small tail-loss guard.
            lo,hi=np.quantile(sample,[.05,.95],axis=0)
            qloss=.5*(np.maximum(.05*(truth-lo),-.95*(truth-lo))+np.maximum(.95*(truth-hi),-.05*(truth-hi)))
            row.append(np.mean((.85*crps+.15*qloss)/scale,axis=0))
        losses.append(row)
    if len(losses)<4:return kinds,np.zeros(len(s.assets),int),{'folds':len(losses),'fallback':'insufficient folds'}
    mean=np.mean(losses,axis=0)
    eligible=np.ones_like(mean,dtype=bool)
    if policy=='conservative':
        # This candidate menu was frozen from DEVELOPMENT evidence, before this study's evaluation.
        menus={'HML':{'baseline','mean_zero','mean_shrink','momentum'},
               'BAB':{'baseline','mean_shrink'},'SMB':{'baseline','mean_zero','mean_shrink'}}
        for ai,a in enumerate(s.assets):
            allowed=set(MONTHLY)-{'mean_revert'} if s.monthly and a in PRICES|{'NFP'} else menus.get(a,{'baseline'})
            eligible[:,ai]=[k in allowed for k in kinds]
    best=np.where(eligible,mean,np.inf).argmin(axis=0)
    # Require >=3% past-fold improvement and wins in >=half of folds; else baseline.
    arr=np.array(losses);baseline=mean[0]
    for ai,ki in enumerate(best):
        gain=(baseline[ai]-mean[ki,ai])/max(baseline[ai],1e-12)
        wins=np.mean(arr[:,ki,ai]<arr[:,0,ai])
        if gain<.03 or wins<.5:best[ai]=0
        if s.monthly and s.assets[ai] not in PRICES|{'NFP','UNRATE'}:best[ai]=0
    meta={'folds':len(losses),'selection_latest_resolved_date':str(s.dates[-1].date()),
          'loss':'85% marginal CRPS + 15% 5/95% pinball, cutoff-input scaled',
          'policy':policy,'asset_models':{a:kinds[int(best[i])] for i,a in enumerate(s.assets)},
          'candidate_losses':{a:{k:float(mean[j,i]) for j,k in enumerate(kinds)} for i,a in enumerate(s.assets)}}
    return kinds,best,meta

def forecast(panels,assets,steps,asof,target,draws,seed,monthly=False,policy='all'):
    s=prepare(panels,assets,asof,target,monthly)
    kinds,best,meta=choices(s,steps,policy=policy)
    if np.all(best==0):
        stale=(pd.Timestamp(asof)-s.dates[-1]).days>=180
        if stale and not monthly:
            sample=paths(s,steps,draws,seed,['baseline'])['baseline']
        elif monthly:
            raw,_=_draw(panels,assets,list(range(steps.shape[1])),asof,draws,seed,
                         target_type=target,panel_steps=steps)
            sample=raw.transpose(0,2,1)
        else:sample,*_=_daily_e2_draws(panels,assets,steps[0].tolist(),asof,target,draws,seed)
        return sample,{'engine':'asset_specialists_gap_safe_fallback' if stale else 'asset_specialists_v11_fallback',
                       'selection':meta,'baseline_draw_fraction':1.}
    sims=paths(s,steps,draws,seed,list(dict.fromkeys(kinds[int(i)] for i in best)))
    sample=np.stack([sims[kinds[int(best[i])]][:,:,i] for i in range(len(assets))],axis=2)
    # A conservative mixture with the same-shock baseline limits local selection variance.
    baseline=paths(s,steps,draws,seed,['baseline'])['baseline']
    sel=np.random.default_rng(seed+5531).random(draws)<.25
    sample[sel]=baseline[sel]
    return sample,{'engine':'asset_specialists_shared_innovations','selection':meta,
                   'baseline_draw_fraction':.25,'n_history_rows':len(s.x),
                   'copula':'common historical innovation rows, nested future paths'}
