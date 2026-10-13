"""## Executive summary (read this first)
Research cutoff-local inflation ensembles and predictive scale calibration.
Weights and calibration use resolved historical folds, never a scored future outcome.
"""
import numpy as np
from qfbench2_common.scoring.crps import crps_ensemble
from qfbench2_track_forecasting.tail import tail_pinball
from .specialists import prepare,prefix,PRICES,_scale
from .inflation import candidates,forecast as fixed_forecast
from .daily import forecast as daily_forecast,simulate

def loss(sample,truth,scale):
    crps=crps_ensemble(sample.reshape(len(sample),-1),truth.reshape(-1)).reshape(truth.shape)
    tail=np.array([tail_pinball(sample[:,:,i]/scale[:,i],truth[:,i]/scale[:,i],(.01,.05,.95,.99))
                   for i in range(truth.shape[1])])
    return .8*np.mean(crps/scale,axis=0)+.2*tail

def weight_matrix(losses,names,assets,monthly):
    mean=losses.mean(axis=0);d=len(assets);out=np.zeros((len(names),d));out[0]=1.
    for ai,a in enumerate(assets):
        if monthly and a not in PRICES:continue
        permitted=np.ones(len(names),bool)
        if not monthly:
            for ki,name in enumerate(names):
                scale,drift=map(float,name.split(':'))
                if a=='MKT' and drift<.75:permitted[ki]=False
        masked=np.where(permitted,mean[:,ai],np.inf);best=int(masked.argmin())
        gain=1-mean[best,ai]/max(mean[0,ai],1e-12)
        wins=np.mean(losses[:,best,ai]<losses[:,0,ai])
        if gain<.03 or wins<.625:continue
        temperature=max(.10*float(np.median(masked[np.isfinite(masked)])),.02)
        acceptable=permitted&(masked<=masked[best]*1.25)
        w=np.where(acceptable,np.exp(np.clip(-(masked-masked[best])/temperature,-30,0)),0.)
        w/=w.sum();out[:,ai]=.85*w;out[0,ai]+=.15
    return out

def mixture(sims,names,weights,seed):
    n=len(sims[names[0]]);d=weights.shape[1]
    u=np.random.default_rng(seed+7331).random(n)
    sample=np.empty_like(sims[names[0]])
    for ai in range(d):
        choice=np.searchsorted(np.cumsum(weights[:,ai]),u,side='right')
        choice=np.minimum(choice,len(names)-1)
        for ki,name in enumerate(names):
            where=choice==ki;sample[where,:,ai]=sims[name][where,:,ai]
    return sample

def daily_candidates(s,steps,draws,seed):
    base=simulate(s,steps,draws,seed);h=steps.T.astype(float)
    mu=s.x.mean(axis=0) if s.target=='log_return' else np.zeros(len(s.assets))
    centre=s.anchor[None,:]+h*mu
    residual=base-centre
    result={'1:1':base}
    for sigma in (.85,1.,1.15):
        for drift in ((0.,.25,.75,1.) if s.target=='log_return' else (1.,)):
            if sigma==1. and drift==1.:continue
            result[f'{sigma:g}:{drift:g}']=s.anchor[None,None,:]+h[None,:,:]*mu*drift+residual*sigma
    return result

def folds(s,steps,monthly):
    hvec=steps.max(axis=0).astype(int);maximum=int(hvec.max())
    minimum=84 if monthly else 750
    origins=list(range(len(s.x)-maximum,minimum-1,-maximum))[:8][::-1]
    output=[]
    for fi,end in enumerate(origins):
        dates=s.dates[end-1:end+maximum]
        if monthly:
            if np.any(np.diff(dates.to_period('M').asi8)!=1):continue
        elif np.any(np.diff(dates.values).astype('timedelta64[D]').astype(int)>10):continue
        hist=prefix(s,end);truth=np.stack([s.x[end:end+h].sum(axis=0) for h in hvec])
        stepmat=np.tile(hvec,(len(s.assets),1))
        if not np.all(steps==steps[0]):
            stepmat=steps.copy()
            accumulated=np.cumsum(s.x[end:end+maximum],axis=0)
            truth=np.stack([accumulated[steps[ai]-1,ai] for ai in range(len(s.assets))],axis=1)
        if s.target!='log_return':truth+=hist.anchor
        scale=np.maximum(_scale(hist.x)*np.sqrt(stepmat.T),1e-8)
        sims=(candidates if monthly else daily_candidates)(hist,stepmat,256,2251+fi)
        names=list(sims);scores=np.array([loss(sims[k],truth,scale) for k in names])
        output.append((sims,truth,scale,scores))
    return output

def forecast(panels,assets,steps,asof,target,draws,seed,monthly=False,mode='soft'):
    if monthly and mode=='cpi_soft':
        base,base_meta=fixed_forecast(panels,assets,steps,asof,target,draws,seed,True)
        if 'CPI_ALL' not in assets:return base,base_meta
        mixed,mixed_meta=forecast(panels,assets,steps,asof,target,draws,seed,True,'soft')
        ai=assets.index('CPI_ALL');base[:,:,ai]=mixed[:,:,ai]
        return base,{'engine':'cpi_all_only_soft_hybrid','cpi_selection':mixed_meta,
                     'other_assets':'repaired VSpecial unchanged','joint_shocks':'same seed and original Gaussian correlation'}
    if monthly and mode in ('term','daily_calibrated'):
        return fixed_forecast(panels,assets,steps,asof,target,draws,seed,True)
    if not monthly and mode!='daily_calibrated':
        return daily_forecast(panels,assets,steps,asof,target,draws,seed,mode='term' if mode=='term' else 'fixed')
    if monthly and not any(a in PRICES for a in assets):
        return fixed_forecast(panels,assets,steps,asof,target,draws,seed,True)
    s=prepare(panels,assets,asof,target,monthly);history=folds(s,steps,monthly)
    if len(history)<4:return fixed_forecast(panels,assets,steps,asof,target,draws,seed,monthly)
    names=list(history[0][0]);arr=np.array([h[3] for h in history])
    weights=weight_matrix(arr,names,assets,monthly)
    current=(candidates if monthly else daily_candidates)(s,steps,draws,seed)
    sample=mixture(current,names,weights,seed)
    calibrated=np.ones(len(assets));calibration_folds=0
    if mode=='calibrated' and monthly:
        factors=np.array([.9,1.,1.1,1.25,1.5]);calibration=[]
        for fi in range(3,len(history)):
            sims,truth,scale,_=history[fi]
            # Earlier resolved folds alone choose the distribution evaluated on this fold.
            pastweights=weight_matrix(arr[:fi],names,assets,True)
            pred=mixture(sims,names,pastweights,9811+fi);centre=pred.mean(axis=0)
            calibration.append([loss(centre+(pred-centre)*f,truth,scale) for f in factors])
        if calibration:
            scores=np.array(calibration);average=scores.mean(axis=0);control=average[1]
            for ai,a in enumerate(assets):
                if a not in PRICES or weights[0,ai]==1.:continue
                ki=int(average[:,ai].argmin());gain=1-average[ki,ai]/max(control[ai],1e-12)
                if gain>=.02 and np.mean(scores[:,ki,ai]<scores[:,1,ai])>=.6:calibrated[ai]=factors[ki]
            centre=sample.mean(axis=0);sample=centre+(sample-centre)*calibrated
            calibration_folds=len(calibration)
    return sample,{'engine':f'cutoff_local_{mode}','folds':len(history),'calibration_folds':calibration_folds,
        'selected_scale':dict(zip(assets,map(float,calibrated))),
        'weights':{a:{k:float(weights[ki,ai]) for ki,k in enumerate(names) if weights[ki,ai]>0}
                   for ai,a in enumerate(assets)},'selector':'80% scaled marginal CRPS + 20% canonical tail pinball',
        'coupling':'shared shocks and a common whole-path mixture uniform; evaluated joint metrics separately'}
