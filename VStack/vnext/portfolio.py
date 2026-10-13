"""## Executive summary (read this first)
Combine rate and FX domain routers without fitting a yield curve to currency levels.
Couple whole nested trajectories to the supplied joint baseline and test resolved joint loss.
Pure-domain inputs dispatch to the frozen expert core unchanged.
"""
import numpy as np
import pandas as pd
from .experts import (forecast as expert_forecast,family,rank_align_baseline,
                      joint_loss,resolved_truth)
from .specialists import prepare,_scale
from .inflation import forecast as safe_baseline


def grouped(panels,assets,steps,asof,target,draws,seed,monthly,policy):
    base,baseline_meta=safe_baseline(panels,assets,steps,asof,target,draws,seed,monthly)
    sample=base.copy();groups={};weights={a:{'baseline':1.} for a in assets};active=False
    for group in sorted({family(a) for a in assets}):
        indices=[i for i,a in enumerate(assets) if family(a)==group]
        chosen=[assets[i] for i in indices]
        part,meta=expert_forecast(panels,chosen,steps[indices],asof,target,draws,seed,monthly,policy)
        groups[group]=meta
        group_weights=meta.get('asset_weights',{})
        if any(w.get('baseline',1.)<.999999 for w in group_weights.values()):
            sample[:,:,indices]=part;weights.update(group_weights);active=True
    if active:
        # Reorder entire trajectories, never individual horizons independently.
        sample=rank_align_baseline(sample,base,steps)
        insurance=np.random.default_rng(seed+5143).random(draws)<.2
        sample[insurance]=base[insurance]
    return sample,base,{'groups':groups,'asset_weights':weights,'active':active,'baseline':baseline_meta}


def forecast(panels,assets,steps,asof,target,draws,seed,monthly=False,policy='guarded'):
    types={family(a) for a in assets}
    if types!={'rates','fx'} or monthly:
        return expert_forecast(panels,assets,steps,asof,target,draws,seed,monthly,policy)
    s=prepare(panels,assets,asof,target,False);maximum=int(steps.max())
    sample,base,meta=grouped(panels,assets,steps,asof,target,draws,seed,False,policy)
    meta['engine']='cross_domain_portfolio_router';meta['coupling']='whole nested path rank alignment to joint baseline; 20% shared baseline insurance'
    if not meta['active']:return base,meta
    rows=[]
    origins=list(range(len(s.x)-maximum,750-1,-maximum))[:3][::-1]
    for fi,end in enumerate(origins):
        cutoff=str(s.dates[end-1].date())
        dates=s.dates[end-1:end+maximum]
        if np.any(np.diff(dates.values).astype('timedelta64[D]').astype(int)>10):continue
        past={k:frame[pd.to_datetime(frame['date'])<=pd.Timestamp(cutoff)].copy() for k,frame in panels.items()}
        predicted,control,_=grouped(past,assets,steps,cutoff,target,256,3171+fi,False,policy)
        truth=resolved_truth(s,assets,steps,end)
        scale=np.maximum(_scale(s.x[:end])*np.sqrt(steps.T),1e-8)
        anchor=s.levels.ffill().loc[:s.dates[end-1]].iloc[-1].to_numpy(float)
        rows.append([joint_loss(predicted,truth,scale,anchor),joint_loss(control,truth,scale,anchor)])
    meta['folds']=len(rows)
    if rows:
        scores=np.asarray(rows);gain=1-scores[:,0].mean()/max(scores[:,1].mean(),1e-12)
        meta['cross_domain_past_joint_gain']=float(gain)
        accepted=gain>=0 and np.mean(scores[:,0]<=scores[:,1])>=.5
    else:accepted=False
    if policy=='guarded' and (len(rows)<3 or not accepted):
        meta['active']=False;meta['asset_weights']={a:{'baseline':1.} for a in assets}
        meta['cross_domain_guard']='retain original baseline joint distribution'
        return base,meta
    meta['cross_domain_guard']='past loss gate passed' if policy=='guarded' else 'diagnostic unguarded'
    return sample,meta
