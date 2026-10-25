"""Cutoff-local convex distribution stacking and nested affine calibration.

All fits use resolved folds of the supplied unit. No offline fitted weights or score
tables are loaded. Chronological guard folds cannot choose their own parameters.
Price anchor retains VExpert fast_price; other anchors retain the numerical baseline.
"""
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit,logit
from qfbench2_common.scoring.crps import crps_ensemble
from . import experts as ex
from .specialists import prefix,PRICES,_scale
from .inflation import forecast as safe

CONFIGS={
    'calibration':{'stack':False,'calibrate':True,'floor':.5,'ridge':.10},
    'stack50':{'stack':True,'calibrate':False,'floor':.5,'ridge':.05},
    'stack70':{'stack':True,'calibrate':False,'floor':.7,'ridge':.15},
    'stackcal':{'stack':True,'calibrate':True,'floor':.5,'ridge':.10},
}

def cross_abs(x,z):
    """Exact E|X-Z| for independently drawn empirical components, O(n log n)."""
    z=np.sort(z);prefix_sum=np.concatenate([[0.],np.cumsum(z)])
    count=np.searchsorted(z,x,side='right')
    return np.mean(count*x-prefix_sum[count]+prefix_sum[-1]-prefix_sum[count]-(len(z)-count)*x)/len(z)

def moments(sims,truth,scale,names):
    k=len(names);d=truth.shape[1];A=np.zeros((k,d));B=np.zeros((k,k,d))
    for ai in range(d):
        for hi in range(truth.shape[0]):
            values=[sims[name][:,hi,ai]/scale[hi,ai] for name in names]
            y=truth[hi,ai]/scale[hi,ai]
            for i in range(k):
                A[i,ai]+=np.abs(values[i]-y).mean()/truth.shape[0]
                for j in range(i+1):
                    B[i,j,ai]+=cross_abs(values[i],values[j])/truth.shape[0]
                    B[j,i,ai]=B[i,j,ai]
    return A,B

def fit_weights(folds,names,assets,context,config):
    A=np.mean([f['A'] for f in folds],axis=0);B=np.mean([f['B'] for f in folds],axis=0)
    out=np.zeros_like(A);out[0]=1.
    for ai,asset in enumerate(assets):
        if asset in PRICES:
            # Price architecture was already selected in the prior round; this round
            # calibrates it but does not rescan its known failed drift alternatives.
            continue
        allowed=[i for i,n in enumerate(names) if n=='anchor' or n in ex.menu(asset,context)]
        a=A[allowed,ai];b=B[np.ix_(allowed,allowed,[ai])][:,:,0]
        prior=np.zeros(len(allowed));prior[0]=1.
        baseline=max(a[0]-.5*b[0,0],1e-10);reg=config['ridge']*baseline
        objective=lambda w:float(w@a-.5*w@b@w+reg*np.sum((w-prior)**2))
        gradient=lambda w:a-b@w+2*reg*(w-prior)
        bounds=[(config['floor'],1.)]+[(0.,1.)]*(len(allowed)-1)
        result=minimize(objective,prior,jac=gradient,bounds=bounds,
                        constraints=[{'type':'eq','fun':lambda w:w.sum()-1.,'jac':lambda w:np.ones_like(w)}],
                        method='SLSQP',options={'maxiter':60,'ftol':1e-9})
        if result.success and np.isfinite(result.x).all():
            w=np.maximum(result.x,0.);w/=w.sum();out[allowed,ai]=w
    return out

def coupled_mix(sims,names,weights,steps,seed):
    base=sims['anchor'];out=base.copy()
    if np.allclose(weights[0],1.,atol=1e-9):return out
    # A common stratified latent uniform selects full trajectories. Component paths
    # are terminal-rank aligned to anchor paths, not independently sorted per horizon.
    order=np.random.default_rng(seed+7147).permutation(len(base))
    u=(order+.5)/len(base)
    for ki,name in enumerate(names):
        if ki==0:continue
        if np.any(weights[ki]>1e-9):
            aligned=ex.rank_align_baseline(sims[name],base,steps)
            lower=weights[:ki].sum(axis=0);upper=lower+weights[ki]
            for ai in range(base.shape[2]):
                chosen=(u>=lower[ai])&(u<upper[ai])
                out[chosen,:,ai]=aligned[chosen,:,ai]
    return out

def encoded(sample,assets):
    z=sample.copy();kinds=[]
    for ai,a in enumerate(assets):
        if a in ex.FX|PRICES:
            z[:,:,ai]=np.log(np.maximum(sample[:,:,ai],1e-12));kinds.append('log')
        elif a=='UNRATE':
            z[:,:,ai]=logit(np.clip(sample[:,:,ai]/100,1e-5,1-1e-5));kinds.append('logit')
        else:kinds.append('linear')
    return z,kinds

def decoded(z,kinds):
    out=z.copy()
    for ai,kind in enumerate(kinds):
        if kind=='log':out[:,:,ai]=np.exp(np.clip(z[:,:,ai],-30,30))
        elif kind=='logit':out[:,:,ai]=100*expit(z[:,:,ai])
    return out

def calibration_data(sample,truth,assets):
    z,kinds=encoded(sample,assets);y,_=encoded(truth[None,:,:],assets)
    centre=np.median(z,axis=0);width=np.maximum(np.std(z,axis=0,ddof=1),1e-10)
    return (z-centre)/width,(y[0]-centre)/width,kinds

def fit_calibration(samples,truths,assets):
    pairs=[calibration_data(s,y,assets) for s,y in zip(samples,truths)]
    H,D=truths[0].shape;shift=np.zeros((H,D));spread=np.ones(D)
    for ai in range(D):
        errors=np.array([y[:,ai] for _,y,_ in pairs])
        # A weak, clipped horizon-specific location estimate with one shared spread.
        bias=np.clip(.25*np.median(errors,axis=0),-.35,.35)
        best=float('inf');chosen=(np.zeros(H),1.)
        for location in [np.zeros(H),bias]:
            for factor in [.85,1.,1.2,1.5]:
                loss=np.mean([crps_ensemble(z[:,:,ai]*factor+location,y[:,ai]).mean() for z,y,_ in pairs])
                loss+=.08*(factor-1)**2+.08*np.mean(location**2)
                if loss<best:best=loss;chosen=(location,factor)
        shift[:,ai],spread[ai]=chosen
    return shift,spread

def apply_calibration(sample,assets,parameters):
    shift,spread=parameters
    if np.all(shift==0) and np.all(spread==1):return sample.copy()
    z,kinds=encoded(sample,assets);centre=np.median(z,axis=0)
    width=np.maximum(np.std(z,axis=0,ddof=1),1e-10)
    return decoded(centre+(z-centre)*spread[None,None,:]+shift[None,:,:]*width,kinds)

def components(s,assets,steps,draws,seed,base=None):
    indices=[s.assets.index(a) for a in assets]
    raw={k:v[:,:,indices] for k,v in ex.candidates(s,ex.expand_steps(s,assets,steps),draws,seed).items()}
    if base is None:base=ex.baseline_state(s,assets,steps,draws,seed)
    anchor=base.copy()
    if s.monthly and s.target=='level' and any(a in PRICES for a in assets):
        fast=raw['kf_fast'];combined=base.copy()
        for ai,a in enumerate(assets):
            if a in PRICES:combined[:,:,ai]=fast[:,:,ai]
        combined=ex.rank_align_baseline(combined,base,steps)
        insurance=np.random.default_rng(seed+6179).random(draws)<.2
        combined[insurance]=base[insurance]
        for ai,a in enumerate(assets):
            if a in PRICES:anchor[:,:,ai]=combined[:,:,ai]
    return {'anchor':anchor,**raw}

def optimize_fold(folds,names,assets,context,steps,config,seed,held):
    weights=fit_weights(folds,names,assets,context,config) if config['stack'] else np.eye(len(names),1)@np.ones((1,len(assets)))
    sample=coupled_mix(held['sims'],names,weights,steps,seed)
    if config['calibrate']:
        train=[coupled_mix(f['sims'],names,weights,steps,seed+i+1) for i,f in enumerate(folds)]
        params=fit_calibration(train,[f['truth'] for f in folds],assets)
        sample=apply_calibration(sample,assets,params)
    else:params=(np.zeros(held['truth'].shape),np.ones(len(assets)))
    return sample,weights,params

def forecast(panels,assets,steps,asof,target,draws,seed,monthly=False,mode='stack70'):
    if mode not in CONFIGS:raise ValueError('unknown optimization mode')
    base,base_meta=safe(panels,assets,steps,asof,target,draws,seed,monthly)
    groups={ex.family(a) for a in assets}
    if len(groups)!=1 or 'other' in groups:
        return base,{'engine':'optimization_mixed_or_unknown_joint_baseline','no_saved_parameters':True,'baseline':base_meta}
    s=ex.context_state(panels,assets,asof,target,monthly)
    if not monthly and (pd.Timestamp(asof)-s.dates[-1]).days>=180:
        return base,{'engine':'optimization_stale_history_baseline','baseline':base_meta}
    current=components(s,assets,steps,draws,seed,base)
    anchor=current['anchor'];names=list(current);config=CONFIGS[mode]
    maximum=int(steps.max());minimum=84 if monthly else 750
    origins=list(range(len(s.x)-maximum,minimum-1,-maximum))[:8][::-1]
    indices=[s.assets.index(a) for a in assets];folds=[]
    for fi,end in enumerate(origins):
        dates=s.dates[end-1:end+maximum]
        if (monthly and np.any(np.diff(dates.to_period('M').asi8)!=1)) or (not monthly and np.any(np.diff(dates.values).astype('timedelta64[D]').astype(int)>10)):continue
        hist=prefix(s,end);sims=components(hist,assets,steps,256,8101+fi)
        truth=ex.resolved_truth(s,assets,steps,end)
        scale=np.maximum(_scale(hist.x[:,indices])*np.sqrt(steps.T),1e-8)
        A,B=moments(sims,truth,scale,names) if config['stack'] else (None,None)
        folds.append({'sims':sims,'truth':truth,'scale':scale,'A':A,'B':B,
                      'anchor':hist.anchor[indices] if target!='log_return' else np.zeros(len(assets)),
                      'input_end':str(hist.dates[-1].date()),'resolved_end':str(dates[-1].date())})
    meta={'engine':'chronological_distribution_optimization','mode':mode,'folds':len(folds),
          'context_assets':s.assets,'no_saved_parameters':True,'fold_input_ends':[f['input_end'] for f in folds],
          'guard':'train earlier resolved folds; score each later fold without self-selection',
          'price_prior':'previous-round fast_price, post-selected on previously explored data'}
    if len(folds)<6:
        meta['accepted']=False;meta['reason']='insufficient chronological folds';return anchor,meta
    per=[];guard_samples=[]
    for fi in range(4,len(folds)):
        held=folds[fi]
        sample,_,_=optimize_fold(folds[:fi],names,assets,s.assets,steps,config,seed+fi,held)
        baseline=held['sims']['anchor']
        loss=ex.marginal_loss(sample,held['truth'],held['scale']);control=ex.marginal_loss(baseline,held['truth'],held['scale'])
        per.append([loss,control]);guard_samples.append((sample,baseline,held))
    per=np.array(per);gain=1-per[:,0].mean(axis=0)/np.maximum(per[:,1].mean(axis=0),1e-12)
    wins=np.mean(per[:,0]<=per[:,1],axis=0)
    active=(gain>=.01)&(wins>=.6)
    sample,weights,params=optimize_fold(folds,names,assets,s.assets,steps,config,seed,current|{'sims':current,'truth':folds[-1]['truth']})
    sample[:,:,~active]=anchor[:,:,~active]
    joint=[]
    for predicted,control,held in guard_samples:
        screened=predicted.copy();screened[:,:,~active]=control[:,:,~active]
        joint.append([ex.joint_loss(screened,held['truth'],held['scale'],held['anchor']),
                      ex.joint_loss(control,held['truth'],held['scale'],held['anchor'])])
    joint=np.array(joint);joint_gain=1-joint[:,0].mean()/max(joint[:,1].mean(),1e-12)
    accepted=joint_gain>=-.005 and np.mean(joint[:,0]<=joint[:,1])>=.5
    if not accepted:sample=anchor.copy();active[:]=False
    meta.update({'accepted':bool(np.any(active)),'chronological_joint_gain':float(joint_gain),
                 'asset_gain':dict(zip(assets,map(float,gain))),'asset_win_rate':dict(zip(assets,map(float,wins))),
                 'asset_weights':{a:({k:float(weights[ki,ai]) for ki,k in enumerate(names) if weights[ki,ai]>1e-8} if active[ai] else {'anchor':1.}) for ai,a in enumerate(assets)},
                 'active_assets':[a for ai,a in enumerate(assets) if active[ai]],
                 'calibration_shift':params[0].tolist(),'calibration_spread':params[1].tolist(),
                 'latest_input_date':str(s.dates[-1].date()),'coupling':'whole component trajectories terminal-ranked to common anchor; common stratified mixture selector'})
    if not np.isfinite(sample).all():raise ValueError('invalid optimized sample')
    return sample,meta
