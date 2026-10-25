"""## Executive summary (read this first)
Forecast joint paths with gap-safe data, causal volatility filtering and past-only selection.
No model weights or historical target tables are loaded from the image.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from qfbench2_common.scoring.crps import crps_ensemble
from qfbench2_track_forecasting.cli import _series, _diff_without_gaps, _monthly_series
from qfbench2_track_forecasting.targets import log_return_steps

FX = {'EUR','GBP','JPY','CHF','AUD','CAD','NZD','SEK','NOK','DKK','CNY','CNH','BRL','INR','IDR','ZAR','TRY','MXN'}
POSITIVE_MACRO = {'CPI_ALL','CPI_CORE','PCE_ALL','PCE_CORE','NFP'}


@dataclass
class History:
    levels: pd.DataFrame
    steps: pd.DataFrame
    anchor: np.ndarray
    assets: list[str]
    target_type: str
    monthly: bool
    logarithmic: bool
    offsets: np.ndarray
    gap_count: int


def prepare(panels: dict[str,pd.DataFrame], assets: list[str], asof: str,
            target_type: str, monthly: bool = False, *, absolute: bool = False) -> History:
    series = {}
    increments = {}
    logged = target_type == 'level' and not absolute and (
        all(a in FX for a in assets) or (monthly and all(a in POSITIVE_MACRO for a in assets)))
    gap_count = 0
    for asset in assets:
        s = _series(panels,asset,asof).astype(float)
        s.index = pd.DatetimeIndex(pd.to_datetime(s.index))
        if s.index.has_duplicates:
            raise ValueError(f'duplicate dates for {asset}')
        s = s.sort_index().replace([np.inf,-np.inf],np.nan).dropna()
        if monthly:
            s=_monthly_series(s)
            s.index=s.index.to_timestamp()
        if len(s) < 3:
            raise ValueError(f'insufficient history for {asset}')
        series[asset] = s
        if target_type == 'log_return':
            ds = pd.Series(log_return_steps(s),index=s.index)
            gaps = pd.Series(s.index,index=s.index).diff().dt.days
            ds = ds.where(gaps <= max(10*float(gaps.median()),5))
        else:
            if logged and (s <= 0).any():
                raise ValueError('positive level model requires positive observations')
            transformed = np.log(s) if logged else s
            if monthly:
                periods=s.index.to_period('M').asi8
                ds=transformed.diff().where(np.r_[False,np.diff(periods)==1])
            else:
                ds = _diff_without_gaps(transformed)
        gap_count += max(0,int(ds.isna().sum())-1)
        increments[asset]=ds
    levels=pd.DataFrame(series).sort_index()
    steps=pd.DataFrame(increments).sort_index().dropna()
    if len(steps)<30:
        raise ValueError(f'insufficient aligned history ({len(steps)})')
    anchor=np.zeros(len(assets)) if target_type=='log_return' else np.array([series[a].iloc[-1] for a in assets])
    offsets=np.zeros(len(assets),dtype=int)
    if monthly:
        last=np.array([series[a].index[-1].to_period('M').ordinal for a in assets])
        offsets=last-last.min()
    return History(levels,steps,anchor,assets,target_type,monthly,logged,offsets,gap_count)


def _mean(x: np.ndarray, kind: str, h: History) -> np.ndarray:
    if h.monthly:
        if kind=='v11_safe': return np.zeros(x.shape[1])
        window=12 if kind=='trend12' else 36
        return x[-min(window,len(x)):].mean(axis=0)
    if h.target_type=='log_return':
        return x.mean(axis=0) * (0.5 if kind!='v11_safe' else 1.0)
    return np.zeros(x.shape[1])


def _scale(x: np.ndarray, hl: float = 60) -> np.ndarray:
    weights=0.5**(np.arange(len(x)-1,-1,-1)/hl)
    weights/=weights.sum()
    mu=np.sum(x*weights[:,None],axis=0)
    var=np.sum((x-mu)**2*weights[:,None],axis=0)
    full=np.var(x,axis=0,ddof=1)
    return np.sqrt(np.maximum(0.90*var+0.10*full,1e-16))


def _causal_scales(x: np.ndarray, hl: float = 60) -> np.ndarray:
    # Every row uses observations strictly BEFORE it. Initialization is burn-in only.
    alpha=1-0.5**(1/hl)
    mean=x[0].copy()
    var=np.maximum(x[0]**2,1e-12)
    out=np.empty_like(x)
    for i,row in enumerate(x):
        out[i]=np.sqrt(np.maximum(var,1e-16))
        delta=row-mean
        mean+=alpha*delta
        var=(1-alpha)*(var+alpha*delta*delta)
    return out


def _endpoints(hist: History, steps: np.ndarray) -> tuple[np.ndarray,int]:
    ends=steps.astype(int)+hist.offsets[:,None]
    return ends,int(ends.max())


def _finish(hist: History, path: np.ndarray, steps: np.ndarray) -> np.ndarray:
    cumulative=np.concatenate([np.zeros((len(path),1,path.shape[2])),np.cumsum(path,axis=1)],axis=1)
    ends,_=_endpoints(hist,steps)
    out=np.empty((len(path),steps.shape[1],len(hist.assets)))
    for ai in range(len(hist.assets)):
        for hi in range(steps.shape[1]):
            out[:,hi,ai]=cumulative[:,ends[ai,hi],ai]-cumulative[:,hist.offsets[ai],ai]
    if hist.target_type!='log_return':
        if hist.logarithmic:
            out=hist.anchor[None,None,:]*np.exp(np.clip(out,-20,20))
        else:
            out+=hist.anchor[None,None,:]
    return out


def candidate(hist: History, steps: np.ndarray, draws: int, seed: int, kind: str) -> np.ndarray:
    if kind=='v11_safe' and hist.logarithmic:
        absolute=pd.DataFrame({a:_diff_without_gaps(hist.levels[a].dropna()) for a in hist.assets}).dropna()
        hist=History(hist.levels,absolute,hist.anchor,hist.assets,hist.target_type,
                     hist.monthly,False,hist.offsets,hist.gap_count)
    x=hist.steps.to_numpy(float)
    _,max_h=_endpoints(hist,steps)
    rng=np.random.default_rng(seed)
    mu=_mean(x,kind,hist)
    hl=30.0 if kind=='fhs30' else 120.0 if kind=='fhs120' else 60.0
    sd=_scale(x,hl)
    if kind=='v11_safe':
        full_sd=np.maximum(x.std(axis=0,ddof=1),1e-12)
        pool=(x-x.mean(axis=0))/full_sd
    else:
        past_sd=_causal_scales(x,hl)
        residual=x.copy()
        if hist.monthly:
            past_mean=pd.DataFrame(x).rolling(36,min_periods=6).mean().shift(1).to_numpy()
            residual-=np.nan_to_num(past_mean,nan=0)
        elif hist.target_type=='log_return':
            residual-=x.mean(axis=0)
        burn=min(120 if not hist.monthly else 24,max(0,len(x)//3))
        pool=(residual/np.maximum(past_sd,1e-12))[burn:]
        pool=pool-pool.mean(axis=0)
        pool/=np.maximum(pool.std(axis=0,ddof=1),1e-12)
    if kind=='direct' and not hist.monthly and len(x)>=max_h+200:
        # Historical contiguous paths capture serial effects and volatility persistence.
        past=_causal_scales(x)
        burn=120
        starts=np.arange(burn,len(x)-max_h+1)
        dates=hist.steps.index
        gap=np.r_[0,np.diff(dates.values).astype('timedelta64[D]').astype(int)>10]
        counts=np.cumsum(gap)
        starts=starts[counts[starts+max_h-1]==counts[starts]]
        if len(starts)>=50:
            origins=rng.choice(starts,size=draws)
            seg=x[origins[:,None]+np.arange(max_h)[None,:]]
            if hist.target_type=='log_return': seg=seg-x.mean(axis=0)
            standardized=seg/np.maximum(past[origins,None,:],1e-12)
            # Remove the pool's mean at each future offset, using only known history.
            centre=np.empty((max_h,x.shape[1]))
            drift=x.mean(axis=0) if hist.target_type=='log_return' else 0.0
            for t in range(max_h):
                centre[t]=((x[starts+t]-drift)/np.maximum(past[starts],1e-12)).mean(axis=0)
            path=(standardized-centre[None,:,:])*sd[None,None,:]+mu
            return _finish(hist,path,steps)
    if kind=='block5':
        pool_dates=hist.steps.index[burn:]
        discontinuity=np.r_[True,np.diff(pool_dates.values).astype('timedelta64[D]').astype(int)>(65 if hist.monthly else 10)]
        idx=np.empty((draws,max_h),dtype=int)
        idx[:,0]=rng.integers(len(pool),size=draws)
        for t in range(1,max_h):
            restart=rng.random(draws)<0.2
            nxt=(idx[:,t-1]+1)%len(pool)
            restart=restart|discontinuity[nxt]
            idx[:,t]=np.where(restart,rng.integers(len(pool),size=draws),nxt)
    else:
        idx=rng.integers(len(pool),size=(draws,max_h))
    path=pool[idx]*sd[None,None,:]+mu
    if kind=='ar1' and hist.monthly:
        resid=x[-120:]-mu
        num=np.sum(resid[1:]*resid[:-1],axis=0)
        den=np.sum(resid[:-1]**2,axis=0)
        phi=np.clip(num/np.maximum(den,1e-16),-0.6,0.6)*0.7
        prev=np.broadcast_to(x[-1]-mu,(draws,x.shape[1])).copy()
        for t in range(max_h):
            innovation=pool[idx[:,t]]*sd*np.sqrt(np.maximum(1-phi**2,0.1))
            prev=phi*prev+innovation
            path[:,t]=mu+prev
    return _finish(hist,path,steps)


def _prefix(hist: History, end: int) -> History:
    when=hist.steps.index[end-1]
    levels=hist.levels.loc[:when]
    anchor=np.zeros(len(hist.assets)) if hist.target_type=='log_return' else levels.ffill().iloc[-1].to_numpy(float)
    return History(levels,hist.steps.iloc[:end],anchor,hist.assets,hist.target_type,
                   hist.monthly,hist.logarithmic,np.zeros(len(hist.assets),int),hist.gap_count)


def select(hist: History, steps: np.ndarray, *, folds: int = 8) -> tuple[list[str],np.ndarray,dict[str,Any]]:
    kinds=['v11_safe','trend12','trend36','ar1'] if hist.monthly else ['v11_safe','fhs30','fhs60','fhs120','direct','block5']
    hvec=np.max(steps,axis=0).astype(int)
    max_h=int(hvec.max())
    min_train=60 if hist.monthly else 300
    n=len(hist.steps)
    # Non-overlapping evaluation blocks, fully resolved before this task's cutoff.
    origins=list(range(n-max_h,min_train-1,-max_h))[:folds][::-1]
    losses=[]
    dates=hist.steps.index
    for fold,end in enumerate(origins):
        future=hist.steps.iloc[end:end+max_h]
        if len(future)!=max_h: continue
        gaps=np.diff(dates[end-1:end+max_h].values).astype('timedelta64[D]').astype(int)
        threshold=65 if hist.monthly else 10
        if np.any(gaps>threshold): continue
        prefix=_prefix(hist,end)
        sums=np.cumsum(future.to_numpy(float),axis=0)
        truth=np.stack([sums[h-1] for h in hvec])
        if hist.target_type!='log_return':
            truth=prefix.anchor[None,:]*np.exp(truth) if hist.logarithmic else prefix.anchor[None,:]+truth
        stepmat=np.tile(hvec,(len(hist.assets),1))
        scale=_scale(prefix.steps.to_numpy(float))*np.sqrt(hvec[:,None])
        if hist.logarithmic: scale*=prefix.anchor[None,:]
        scale=np.maximum(scale,1e-8)
        row=[]
        for kind in kinds:
            sample=candidate(prefix,stepmat,192,17011+fold,kind)
            score=crps_ensemble(sample.reshape(len(sample),-1),truth.reshape(-1)).reshape(truth.shape)
            row.append(float(np.mean(score/scale)))
        losses.append(row)
    if not losses:
        weights=np.array([0.0,0.25,0.50,0.25]) if hist.monthly else np.array([0.4,0.1,0.3,0.1,0.1,0.0])
        return kinds,weights,{'folds':0,'reason':'history too short for past-only selection'}
    arr=np.array(losses)
    # Soft selection limits winner's curse; mix at the whole-draw level, never by asset.
    mean=arr.mean(axis=0)
    temperature=max(float(np.median(mean))*0.12,0.02)
    logw=-(mean-mean.min())/temperature
    weights=np.exp(np.clip(logw,-20,0));weights/=weights.sum()
    weights=0.9*weights+0.1/len(kinds)
    return kinds,weights,{'folds':len(losses),'selection_max_date':str(dates[-1].date()),
                         'loss':'past-only normalized marginal CRPS',
                         'candidate_loss':dict(zip(kinds,map(float,mean))),
                         'weights':dict(zip(kinds,map(float,weights)))}


def forecast(panels: dict[str,pd.DataFrame],assets: list[str],steps: np.ndarray,asof: str,
             target_type: str,draws: int,seed: int,*,monthly: bool=False,
             mode: str='adaptive') -> tuple[np.ndarray,dict[str,Any]]:
    hist=prepare(panels,assets,asof,target_type,monthly,absolute=(mode=='v11_safe'))
    if mode!='adaptive':
        return candidate(hist,steps,draws,seed,mode),{'engine':mode,'gap_steps_removed':hist.gap_count,
                                                    'logarithmic_levels':hist.logarithmic}
    kinds,weights,selection=select(hist,steps)
    rng=np.random.default_rng(seed+7919)
    assignments=rng.choice(len(kinds),size=draws,p=weights)
    out=np.empty((draws,steps.shape[1],len(assets)))
    for ki,kind in enumerate(kinds):
        where=np.flatnonzero(assignments==ki)
        if not len(where): continue
        # V11's actual absolute-change representation remains one mixture component.
        out[where]=candidate(hist,steps,len(where),seed+ki*10007,kind)
    return out,{'engine':'cutoff_local_adaptive_joint_mixture','gap_steps_removed':hist.gap_count,
                'logarithmic_levels':hist.logarithmic,'n_history_rows':len(hist.steps),
                'selection':selection,'model_counts':{k:int(np.sum(assignments==i)) for i,k in enumerate(kinds)}}
