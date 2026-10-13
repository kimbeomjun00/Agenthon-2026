"""## Executive summary (read this first)
Forecast with domain-specific experts, fitted and selected from this unit's past only.
Covariates use supplied same-family series. No saved winner table or fitted weights load.
New experts share historical rank innovations; a joint baseline mixture limits selection risk.
"""
import numpy as np
import pandas as pd
from scipy.special import expit, logit
from scipy.stats import norm, rankdata, t as student
from qfbench2_common.scoring.crps import crps_ensemble
from qfbench2_track_forecasting.scoring import _composite
from qfbench2_track_forecasting.tail import tail_pinball
from qfbench2_track_forecasting.targets import log_return_steps
from .specialists import prepare, prefix, PRICES, _scale
from .inflation import forecast as safe_baseline

FX={'EUR','GBP','JPY','CHF','AUD','CAD','NZD','SEK','NOK','DKK'}
FACTORS={'MKT','SMB','HML','MOM','BAB','QMJ'}
RATES={'UST_2Y':24.,'UST_5Y':60.,'UST_7Y':84.,'UST_10Y':120.,'UST_20Y':240.,'UST_30Y':360.}
MACRO=PRICES|{'NFP','UNRATE'}


def family(asset):
    if asset in RATES:return 'rates'
    if asset in FX:return 'fx'
    if asset in FACTORS:return 'factors'
    if asset in MACRO:return 'macro'
    return 'other'


def menu(asset,context_assets):
    group=family(asset)
    if group=='rates':
        names=['rw_vol','fhs120','policy_trend','ridge_condition']
        if len(set(context_assets)&RATES.keys())>=3:names+=['curve_ns','curve_pca']
        return names
    if group=='fx':
        names=['rw_vol','fhs30','fhs120','gjr','ridge_condition']
        if len(set(context_assets)&FX)>=3:names+=['fx_common']
        if asset=='DKK' and 'EUR' in context_assets:names+=['fx_peg']
        return names
    if group=='factors':return ['rw_vol','fhs30','fhs120','gjr','har_proxy','ridge_condition','factor_role']
    if asset in PRICES:return ['rw_vol','kf_slow','kf_fast','growth_ar','seasonal_growth','ridge_condition']
    if asset=='NFP':return ['rw_vol','kf_slow','kf_fast','employment_robust','ridge_condition']
    if asset=='UNRATE':return ['rw_vol','unrate_logit','kf_slow','growth_ar','ridge_condition']
    return []


def context_state(panels,assets,asof,target,monthly):
    groups={family(a) for a in assets}
    expanded=list(assets)
    if len(groups)==1 and 'other' not in groups:
        group=next(iter(groups))
        available=set()
        for frame in panels.values():
            key='asset' if 'asset' in frame else 'asset_id'
            if key in frame:
                past=frame[pd.to_datetime(frame['date'])<=pd.Timestamp(asof)]
                available.update(str(a) for a in past[key].unique())
        expanded+=sorted(a for a in available if a not in assets and family(a)==group)
    # Context which radically shortens usable history is not mandatory.
    target_state=prepare(panels,assets,asof,target,monthly)
    if expanded!=assets:
        try:
            candidate=prepare(panels,expanded,asof,target,monthly)
            if len(candidate.x)>=max(30,int(.7*len(target_state.x))):return candidate
        except ValueError:pass
    return target_state


def expand_steps(s,assets,steps):
    matrix=np.tile(np.max(steps,axis=0),(len(s.assets),1))
    for i,a in enumerate(assets):matrix[s.assets.index(a)]=steps[i]
    return matrix.astype(int)


def native(s):
    x=s.x.copy();anchor=s.anchor.copy();kinds=['linear']*len(s.assets)
    if s.target=='log_return':return x,anchor,kinds
    for i,a in enumerate(s.assets):
        levels=s.levels[a].dropna()
        if (a in FX|PRICES) and (levels>0).all():
            x[:,i]=np.log(levels).diff().reindex(s.dates).to_numpy()
            anchor[i]=np.log(s.anchor[i]);kinds[i]='log'
        elif a=='UNRATE' and levels.between(0,100).all():
            transformed=pd.Series(logit(np.clip(levels.to_numpy()/100,1e-5,1-1e-5)),index=levels.index)
            x[:,i]=transformed.diff().reindex(s.dates).to_numpy()
            anchor[i]=logit(np.clip(s.anchor[i]/100,1e-5,1-1e-5));kinds[i]='logit'
    if not np.isfinite(x).all():raise ValueError('native increment alignment failed')
    return x,anchor,kinds


def decode(s,changes,steps,anchor,kinds):
    cumulative=np.concatenate([np.zeros((len(changes),1,len(s.assets))),np.cumsum(changes,axis=1)],axis=1)
    result=np.empty((len(changes),steps.shape[1],len(s.assets)))
    for i,kind in enumerate(kinds):
        start=int(s.offsets[i]);value=cumulative[:,start+steps[i],i]-cumulative[:,start,i,None]
        if s.target!='log_return':value+=anchor[i]
        if kind=='log':value=np.exp(np.clip(value,-30,30))
        elif kind=='logit':value=100*expit(value)
        result[:,:,i]=value
    return result


def causal_variance(x,half_life):
    var=np.maximum(np.var(x[:min(30,len(x))],axis=0,ddof=1),1e-16)
    out=np.empty_like(x);decay=np.exp(-np.log(2)/half_life)
    centre=x.mean(axis=0)
    for i,row in enumerate(x):
        out[i]=var
        var=decay*var+(1-decay)*(row-centre)**2
    return out,var


def empirical_noise(pool,u):
    pool=pool-pool.mean(axis=0)
    pool/=np.maximum(pool.std(axis=0,ddof=1),1e-12)
    sorted_pool=np.sort(pool,axis=0);grid=np.linspace(0,1,len(pool))
    return np.stack([np.interp(u[:,:,i],grid,sorted_pool[:,i]) for i in range(pool.shape[1])],axis=2)


def mean_prior(x,assets,target):
    if target!='log_return':return np.zeros(x.shape[1])
    # Unit-history estimates, not externally stored premiums. MKT keeps more long-run mean.
    long=x.mean(axis=0);recent=x[-min(1260,len(x)):].mean(axis=0)
    sd=np.maximum(x.std(axis=0,ddof=1),1e-12)
    tscore=np.abs(long)*np.sqrt(len(x))/sd
    shrink=tscore**2/(tscore**2+4.)
    for i,a in enumerate(assets):
        floor=.5 if a=='MKT' else (.2 if a in {'BAB','QMJ'} else 0.)
        shrink[i]=max(floor,shrink[i])
    return np.clip((.75*long+.25*recent)*shrink,-.08*sd,.08*sd)


def ridge_fit(x,monthly=False):
    lags=(1,3,12) if monthly else (1,5,21)
    window=180 if monthly else 1500
    arr=x[-min(window,len(x)):]
    centre=arr.mean(axis=0);sd=np.maximum(arr.std(axis=0,ddof=1),1e-12)
    z=(arr-centre)/sd;maximum=max(lags)
    features=np.stack([np.concatenate([z[i-k:i].mean(axis=0) for k in lags])
                       for i in range(maximum,len(z))])
    y=z[maximum:]
    penalty=np.eye(features.shape[1])*len(features)*.3
    beta=np.linalg.solve(features.T@features+penalty,features.T@y)
    norm_size=np.linalg.norm(beta,ord=2)
    if norm_size>.6:beta*=.6/norm_size
    residual=y-features@beta
    return lags,centre,sd,beta,residual


def role_features(buffer,assets,january):
    """Lagged return conditions; no contemporaneous/future market factor enters a forecast."""
    # Shape [path, history, asset]. Market context falls back to the supplied factor average.
    market=buffer[:,:,assets.index('MKT')] if 'MKT' in assets else buffer.mean(axis=2)
    m5=market[:,-5:].mean(axis=1);m21=market[:,-21:].mean(axis=1)
    crash_rebound=(m21<0)*m5
    volatility=np.sqrt(np.maximum((market[:,-21:]**2).mean(axis=1),1e-16))
    features=[]
    for i,a in enumerate(assets):
        own=buffer[:,:,i]
        f=np.stack([own[:,-1],own[:,-5:].mean(axis=1),own[:,-21:].mean(axis=1),
                    own[:,-126:].mean(axis=1),m5,m21,crash_rebound,volatility,
                    np.broadcast_to(january,len(buffer))],axis=1)
        allowed={'MKT':[2,3,5,7],'HML':[0,2,3,5,6],'SMB':[0,1,2,5,8],
                 'MOM':[0,1,2,5,6,7],'BAB':[2,3,5,6,7],'QMJ':[2,3,5,7]}.get(a,list(range(8)))
        mask=np.zeros(9);mask[allowed]=1;features.append(f*mask)
    return np.stack(features,axis=1)


def candidates(s,steps,draws,seed):
    x,anchor,kinds=native(s);n,d=x.shape;maxh=int((steps+s.offsets[:,None]).max())
    rng=np.random.default_rng(seed)
    idx=rng.integers(n,size=(draws,maxh))
    ranks=(rankdata(x,axis=0)-.5)/n;u=ranks[idx]
    secondary=ranks[np.random.default_rng(seed+1151).integers(n,size=(draws,maxh))]
    gaussian=norm.ppf(u);extra=norm.ppf(secondary)
    full=np.maximum(x.std(axis=0,ddof=1),1e-12);sd=_scale(x,45)
    mu=mean_prior(x,s.assets,s.target)
    noise=empirical_noise(x,u)
    names=list(dict.fromkeys(k for a in s.assets for k in menu(a,s.assets)))
    result={};lagfit=None;fhs_cache={}
    for name in names:
        path=np.empty((draws,maxh,d))
        if name in {'rw_vol','fhs30','fhs120','gjr','har_proxy'}:
            hl=30 if name=='fhs30' else 120
            shocks=noise;variance=np.broadcast_to(sd**2,(draws,d)).copy()
            long=np.var(x[-min(1260,n):],axis=0,ddof=1)
            if name.startswith('fhs'):
                past,last=causal_variance(x,hl)
                shocks=empirical_noise(((x-x.mean(axis=0))/np.sqrt(np.maximum(past,1e-16)))[30:],u)
                variance[:]=.9*last+.1*full**2
            if name=='har_proxy':
                q=(x-mu)**2;w=min(n,1500);q=q[-w:]
                long=np.mean(q,axis=0);features=[];ys=[]
                for i in range(22,len(q)):
                    features.append(np.stack([q[i-1],q[i-5:i].mean(axis=0),q[i-22:i].mean(axis=0)],axis=1))
                    ys.append(q[i])
                features=np.array(features);ys=np.array(ys);coeff=np.empty((3,d))
                prior=np.array([.05,.15,.7])
                for ai in range(d):
                    f=features[:,ai,:]/max(long[ai],1e-16)
                    y=ys[:,ai]/max(long[ai],1e-16)
                    penalty=len(y)*.5
                    fitted=np.linalg.solve(f.T@f+penalty*np.eye(3),f.T@y+penalty*prior)
                    fitted=np.maximum(fitted,0.)
                    coeff[:,ai]=fitted*min(1.,.985/max(fitted.sum(),1e-12))
                buffer=np.broadcast_to(q[-22:],(draws,22,d)).copy()
            for step in range(maxh):
                if name=='har_proxy':
                    forecast=(1-coeff.sum(axis=0))*long+coeff[0]*buffer[:,-1]+coeff[1]*buffer[:,-5:].mean(axis=1)+coeff[2]*buffer.mean(axis=1)
                    variance=np.clip(forecast,.05*long,20*long)
                shock=shocks[:,step]*np.sqrt(np.maximum(variance,1e-16))
                path[:,step]=mu+shock
                if name=='gjr':variance=.02*long+.04*shock**2+.08*shock**2*(shock<0)+.9*variance
                elif name.startswith('fhs'):
                    decay=np.exp(-np.log(2)/hl)
                    variance=decay*variance+(1-decay)*shock**2
                elif name=='har_proxy':buffer=np.concatenate([buffer[:,1:],shock[:,None,:]**2],axis=1)
        elif name in {'ridge_condition','curve_pca','fx_common'}:
            xx=x
            loading=None
            if name in {'curve_pca','fx_common'} and d>=3:
                z=(x-x.mean(axis=0))/full
                _,_,vectors=np.linalg.svd(z[-min(n,1500):],full_matrices=False)
                rank=min(3 if name=='curve_pca' else 2,d)
                loading=vectors[:rank].T;xx=z@loading
            lags,centre,fit_sd,beta,residual=ridge_fit(xx,s.monthly)
            maximum=max(lags);standard=(xx-centre)/fit_sd
            buffer=np.broadcast_to(standard[-maximum:],(draws,maximum,xx.shape[1])).copy()
            intercept=centre if s.monthly and loading is None else mu
            for step in range(maxh):
                f=np.concatenate([buffer[:,-k:].mean(axis=1) for k in lags],axis=1)
                mean=f@beta
                conditional=mean*fit_sd
                if loading is not None:conditional=(conditional@loading.T)*full
                conditional=np.clip(conditional,-.5*sd,.5*sd)
                change=intercept+conditional+noise[:,step]*sd
                path[:,step]=change
                next_standard=((change-mu)/full)@loading if loading is not None else change
                next_standard=(next_standard-centre)/fit_sd
                buffer=np.concatenate([buffer[:,1:],next_standard[:,None,:]],axis=1)
        elif name=='factor_role':
            z=(x-mu)/full;start=max(126,n-1500)
            features=[]
            for row in range(start,n):
                f=role_features(z[row-126:row][None,:,:],s.assets,float(s.dates[row].month==1))[0]
                features.append(f)
            features=np.asarray(features);y=z[start:];coeff=np.empty((d,9));centres=features.mean(axis=0)
            scales=np.maximum(features.std(axis=0,ddof=1),1e-8)
            for ai in range(d):
                f=(features[:,ai]-centres[ai])/scales[ai]
                beta=np.linalg.solve(f.T@f+len(f)*.5*np.eye(9),f.T@(y[:,ai]-y[:,ai].mean()))
                size=np.linalg.norm(beta)
                coeff[ai]=beta*min(1.,.35/max(size,1e-12))
            buffer=np.broadcast_to(z[-126:],(draws,126,d)).copy()
            for step in range(maxh):
                future_date=s.dates[-1]+pd.offsets.BDay(step+1)
                f=role_features(buffer,s.assets,float(future_date.month==1))
                conditional=np.sum((f-centres)/scales*coeff,axis=2)*full
                conditional=np.clip(conditional,-.25*sd,.25*sd)
                change=mu+conditional+noise[:,step]*sd
                path[:,step]=change
                buffer=np.concatenate([buffer[:,1:],((change-mu)/full)[:,None,:]],axis=1)
        elif name=='policy_trend':
            recent=x[-min(126,n):]
            drift=np.clip(.15*np.median(recent,axis=0)+.05*recent.mean(axis=0),-.06*sd,.06*sd)
            uncertain=extra[:,0]*sd/np.sqrt(min(126,n))*.35
            for step in range(maxh):path[:,step]=noise[:,step]*sd+(drift+uncertain)*np.exp(-step/63.)
        elif name=='curve_ns':
            tenors=np.array([RATES.get(a,120.) for a in s.assets])
            decay=.025*tenors;first=(1-np.exp(-decay))/decay
            loading=np.stack([np.ones(d),first,first-np.exp(-decay)],axis=1)
            projection=np.linalg.pinv(loading)
            levels=s.levels.ffill().loc[s.dates].to_numpy(float)
            factors=levels@projection.T;recent=factors[-min(756,n):]
            centre=recent.mean(axis=0);z=recent-centre
            phi=np.clip(np.sum(z[1:]*z[:-1],axis=0)/np.maximum(np.sum(z[:-1]**2,axis=0),1e-12),.9,.9995)
            kappa=(1-phi)*.25;kappa[0]=0.
            current=np.broadcast_to(anchor,(draws,d)).copy()
            for step in range(maxh):
                beta_now=current@projection.T
                drift=((centre-beta_now)*kappa)@loading.T
                change=np.clip(drift,-.08*sd,.08*sd)+noise[:,step]*sd
                path[:,step]=change;current+=change
        elif name=='fx_peg':
            path[:]=noise*sd+mu
            if 'DKK' in s.assets and 'EUR' in s.assets:
                dk=s.assets.index('DKK');eu=s.assets.index('EUR')
                logs=np.log(s.levels[['DKK','EUR']].ffill().loc[s.dates])
                returns=np.diff(logs.to_numpy(),axis=0)[-min(500,n-1):]
                # Quote directions may be inverse. Learn the sign/hedge ratio from this history.
                centred=returns-returns.mean(axis=0)
                hedge=float(np.clip(np.sum(centred[:,0]*centred[:,1])/max(np.sum(centred[:,1]**2),1e-16),-1.2,1.2))
                spread=(logs['DKK']-hedge*logs['EUR']).to_numpy()
                centre=np.median(spread[-min(500,n):]);resid=np.diff(spread)
                spread_sd=float(max(_scale(resid[:,None],60)[0],1e-8))
                spread_noise=empirical_noise(np.column_stack([resid]*d),u)[:,:,dk]
                current=np.full(draws,anchor[dk]-hedge*anchor[eu])
                for step in range(maxh):
                    next_spread=current+.05*(centre-current)+spread_noise[:,step]*spread_sd
                    path[:,step,dk]=hedge*path[:,step,eu]+next_spread-current
                    current=next_spread
        elif name in {'kf_slow','kf_fast'}:
            ratio=.01 if name=='kf_slow' else .10
            observation=np.maximum(np.var(np.diff(x,axis=0),axis=0,ddof=1)/2,.1*full**2)
            process=observation*ratio;trend=x[:12].mean(axis=0);variance=observation.copy()
            residual=[]
            for row in x:
                predicted=variance+process;gain=predicted/(predicted+observation)
                residual.append(row-trend);trend=trend+gain*(row-trend);variance=(1-gain)*predicted
            shocks=empirical_noise(np.asarray(residual)[12:],u)
            initial=ranks[np.random.default_rng(seed+1175).integers(n,size=draws)]
            current=trend+norm.ppf(initial)*np.sqrt(variance)
            long=x[-min(60,n):].mean(axis=0)
            for step in range(maxh):
                current=long+.98*(current-long)+extra[:,step]*np.sqrt(process)
                path[:,step]=current+shocks[:,step]*np.sqrt(observation)
        elif name in {'growth_ar','seasonal_growth','employment_robust'}:
            window=min(60,n);recent=x[-window:]
            centre=np.median(recent,axis=0) if name=='employment_robust' else recent.mean(axis=0)
            centred=recent-centre
            phi=np.clip(np.sum(centred[1:]*centred[:-1],axis=0)/np.maximum(np.sum(centred[:-1]**2,axis=0),1e-12),-.3,.8)*.65
            current=np.broadcast_to(x[-1],(draws,d)).copy()
            shock_sd=np.sqrt(.75*np.var(recent,axis=0,ddof=1)+.25*full**2)
            shocks=noise
            if name=='employment_robust':
                robust=1.4826*np.median(np.abs(recent-centre),axis=0)
                shock_sd=np.sqrt(.8*robust**2+.2*full**2)
                shocks=student.ppf(np.clip(u,1e-5,1-1e-5),5)*np.sqrt(3/5)
            for step in range(maxh):
                mean=centre+phi*(current-centre)
                if name=='seasonal_growth':
                    month=(s.dates[-1].month+step)%12+1
                    selected=x[(s.dates.month==month)&(np.arange(n)>=max(0,n-120))]
                    if len(selected):mean+=.35*(selected.mean(axis=0)-centre)
                current=mean+shocks[:,step]*shock_sd*np.sqrt(1-phi**2)
                path[:,step]=current
        elif name=='unrate_logit':
            levels=np.concatenate([anchor[None,:]-np.cumsum(x[::-1],axis=0)[::-1],anchor[None,:]],axis=0)
            centre=np.median(levels[-min(96,len(levels)):],axis=0)
            lag=levels[-min(96,len(levels)):-1]-centre;delta=np.diff(levels[-min(96,len(levels)):],axis=0)
            kappa=np.clip(-np.sum(lag*delta,axis=0)/np.maximum(np.sum(lag**2,axis=0),1e-12),0,.15)*.5
            current=np.broadcast_to(anchor,(draws,d)).copy()
            for step in range(maxh):
                change=kappa*(centre-current)+noise[:,step]*_scale(x,12)
                path[:,step]=change;current+=change
        else:raise ValueError(name)
        result[name]=decode(s,path,steps,anchor,kinds)
    return result


def baseline_state(s,assets,steps,draws,seed):
    frame=s.levels.stack().rename('value').reset_index()
    frame.columns=['date','asset','value']
    sample,_=safe_baseline({'history':frame},assets,steps,str(s.dates[-1].date()),s.target,draws,seed,s.monthly)
    return sample


def resolved_truth(s,assets,steps,end):
    # Target horizon grain follows the target set, not additional covariates' missing dates.
    # The entire state was already cut at the current unit asof, so these are resolved past rows.
    cutoff=s.dates[end-1]
    future=s.levels[assets].dropna().loc[lambda frame:frame.index>cutoff].iloc[:int(steps.max())]
    if len(future)<int(steps.max()):raise ValueError('insufficient resolved target rows')
    values=log_return_steps(future.to_numpy(float)) if s.target=='log_return' else future.to_numpy(float)
    return np.stack([np.array([values[:h,ai].sum() if s.target=='log_return' else values[h-1,ai]
                               for h in steps[ai]]) for ai in range(len(assets))],axis=1)


def marginal_loss(sample,truth,scale):
    crps=crps_ensemble(sample.reshape(len(sample),-1),truth.reshape(-1)).reshape(truth.shape)
    tail=np.array([tail_pinball(sample[:,:,i]/scale[:,i],truth[:,i]/scale[:,i],(.01,.05,.95,.99))
                   for i in range(truth.shape[1])])
    return .85*np.mean(crps/scale,axis=0)+.15*tail


def choose_weights(losses,names,assets,context_assets):
    mean=losses.mean(axis=0);out=np.zeros_like(mean);out[0]=1.
    for i,a in enumerate(assets):
        permitted=np.array([name=='baseline' or name in menu(a,context_assets) for name in names])
        best=int(np.where(permitted,mean[:,i],np.inf).argmin())
        gain=1-mean[best,i]/max(mean[0,i],1e-12)
        wins=np.mean(losses[:,best,i]<losses[:,0,i])
        if gain<.03 or wins<.6:continue
        eligible=permitted&(mean[:,i]<=mean[best,i]*1.02)
        weights=np.where(eligible,np.exp(np.clip(-(mean[:,i]-mean[best,i])/max(.05*mean[0,i],1e-8),-30,0)),0.)
        weights/=weights.sum();out[:,i]=.65*weights;out[0,i]+=.35
    return out


def rank_align_baseline(base,reference,steps):
    aligned=np.empty_like(base)
    for i in range(base.shape[2]):
        h=int(np.argmax(steps[i]));order=np.argsort(reference[:,h,i],kind='stable')
        ranked=base[np.argsort(base[:,h,i],kind='stable'),:,i]
        aligned[order,:,i]=ranked
    return aligned


def mix(sims,names,weights,steps,seed):
    base=sims['baseline']
    if np.all(weights[0]==1.):return base.copy()
    # Whole-trajectory reordering preserves every baseline marginal and its nested horizons.
    # It couples baseline columns in the expert branch, not an assertion of exact covariance.
    aligned=rank_align_baseline(base,sims['rw_vol'],steps)
    rng=np.random.default_rng(seed+9941);u=rng.random(len(base));out=np.empty_like(base)
    for i in range(base.shape[2]):
        choice=np.minimum(np.searchsorted(np.cumsum(weights[:,i]),u,side='right'),len(names)-1)
        for k,name in enumerate(names):
            mask=choice==k;source=aligned if name=='baseline' else sims[name]
            out[mask,:,i]=source[mask,:,i]
    # Shared insurance draws retain the original baseline joint paths exactly.
    insurance=rng.random(len(base))<.2;out[insurance]=base[insurance]
    return out


def joint_loss(sample,truth,scale,anchor):
    standardized=(sample-anchor)/scale
    y=(truth-anchor)/scale
    score=_composite(standardized.transpose(0,2,1).reshape(len(sample),-1),y.T.reshape(-1),
                     weights=(.5,.3,.2),tail_levels=(.01,.05,.95,.99),joint='variogram',tail_metric='pinball',ref_scale=None)
    return score['composite'] if 'composite' in score else .5*score['marginal']+.3*score['joint']+.2*score['tail']


def forecast(panels,assets,steps,asof,target,draws,seed,monthly=False,policy='guarded'):
    base,base_meta=safe_baseline(panels,assets,steps,asof,target,draws,seed,monthly)
    if not any(menu(a,assets) for a in assets):return base,{'engine':'expert_unknown_asset_baseline','baseline':base_meta}
    s=context_state(panels,assets,asof,target,monthly)
    if (not monthly and (pd.Timestamp(asof)-s.dates[-1]).days>=180):
        return base,{'engine':'expert_stale_history_baseline','baseline':base_meta}
    minimum=84 if monthly else 750;maximum=int(steps.max())
    origins=list(range(len(s.x)-maximum,minimum-1,-maximum))[:6][::-1]
    indices=[s.assets.index(a) for a in assets];folds=[];names=None
    for fi,end in enumerate(origins):
        dates=s.dates[end-1:end+maximum]
        if (monthly and np.any(np.diff(dates.to_period('M').asi8)!=1)) or (not monthly and np.any(np.diff(dates.values).astype('timedelta64[D]').astype(int)>10)):continue
        hist=prefix(s,end);matrix=expand_steps(hist,assets,steps)
        sims={k:v[:,:,indices] for k,v in candidates(hist,matrix,192,1157+fi).items()}
        sims={'baseline':baseline_state(hist,assets,steps,192,1157+fi),**sims}
        names=list(sims)
        truth=resolved_truth(s,assets,steps,end)
        scale=np.maximum(_scale(hist.x[:,indices])*np.sqrt(steps.T),1e-8)
        losses=np.array([marginal_loss(sims[k],truth,scale) for k in names])
        folds.append((sims,truth,scale,hist.anchor[indices] if target!='log_return' else np.zeros(len(assets)),losses))
    if len(folds)<4:return base,{'engine':'expert_insufficient_folds_baseline','folds':len(folds),'baseline':base_meta}
    losses=np.array([f[-1] for f in folds]);weights=choose_weights(losses,names,assets,s.assets)
    # Leave-one-fold-out assessment of the integration guard; the scored fold cannot select itself.
    unguarded=weights.copy();guard=[]
    for fi,(sims,truth,scale,anchor,_) in enumerate(folds):
        training=np.delete(losses,fi,axis=0)
        w=choose_weights(training,names,assets,s.assets)
        sample=mix(sims,names,w,steps,seed+fi)
        guard.append([joint_loss(sample,truth,scale,anchor),joint_loss(sims['baseline'],truth,scale,anchor)])
    guard=np.asarray(guard)
    joint_gain=1-guard[:,0].mean()/max(guard[:,1].mean(),1e-12)
    if policy=='guarded' and (joint_gain<0 or np.mean(guard[:,0]<=guard[:,1])<.5):
        weights[:]=0.;weights[0]=1.
    metadata={'engine':'domain_expert_joint_router','folds':len(folds),'context_assets':s.assets,
              'policy':policy,'loo_joint_gain':float(joint_gain),'loss':'85% input-scaled CRPS + 15% canonical tail pinball',
              'asset_weights':{a:{k:float(weights[ki,ai]) for ki,k in enumerate(names) if weights[ki,ai]>0}
                               for ai,a in enumerate(assets)},
              'unguarded_asset_weights':{a:{k:float(unguarded[ki,ai]) for ki,k in enumerate(names) if unguarded[ki,ai]>0}
                                        for ai,a in enumerate(assets)},
              'candidate_mean_losses':{a:{k:float(losses[:,ki,ai].mean()) for ki,k in enumerate(names)
                                          if k=='baseline' or k in menu(a,s.assets)} for ai,a in enumerate(assets)},
              'coupling':'common per-step historical ranks; whole baseline trajectories aligned only in expert branch; shared 20% insurance',
              'selection_latest_input_date':str(s.dates[-1].date()),'no_saved_parameters':True}
    if np.all(weights[0]==1.):return base,metadata
    sims={k:v[:,:,indices] for k,v in candidates(s,expand_steps(s,assets,steps),draws,seed).items()}
    sims={'baseline':base,**sims}
    sample=mix(sims,names,weights,steps,seed)
    if not np.isfinite(sample).all():raise ValueError('non-finite expert mixture')
    return sample,metadata
