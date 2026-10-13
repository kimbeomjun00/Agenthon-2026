"""## Executive summary (read this first)
Research joint daily predictors: ridge VAR and a PCA mean-reverting level model.
All regression coefficients fit only from this task's as-of-valid history.
These are tested candidates, not the default release policy.
"""
import numpy as np
from .specialists import finish,_scale

KINDS=['ridge_var','ridge_var_long','smooth_var','pca_revert']

def candidate(s,steps,draws,seed,kind):
    x=s.x;d=x.shape[1];n=len(x);maxh=int(steps.max());rng=np.random.default_rng(seed)
    sigma=_scale(x);full=np.maximum(x.std(axis=0,ddof=1),1e-12)
    mean=x.mean(axis=0) if s.target=='log_return' else np.zeros(d)
    window=3000 if kind=='ridge_var_long' else 1000
    train=x[-min(window,n):];centre=train.mean(axis=0)
    if kind=='pca_revert' and s.target=='level':
        levels=s.levels.ffill().dropna().to_numpy(float)[-min(window,n):]
        location=levels.mean(axis=0);whiten=(levels-location)/full
        _,vectors=np.linalg.eigh(np.cov(whiten.T) if d>1 else np.atleast_2d(np.var(whiten)))
        pcs=whiten@vectors
        ph=np.sum(pcs[:-1]*pcs[1:],axis=0)/np.maximum(np.sum(pcs[:-1]**2,axis=0),1e-12)
        # Conservative shrinkage toward a random walk, excluding explosive fitted roots.
        phi=1-.25*(1-np.clip(ph,.8,1.))
        residual=np.diff(levels,axis=0)-(((pcs[:-1]*(phi-1))@vectors.T)*full)
        z=(residual-residual.mean(axis=0))/np.maximum(residual.std(axis=0,ddof=1),1e-12)
        indices=rng.integers(len(z),size=(draws,maxh));state=np.broadcast_to(s.anchor,(draws,d)).copy()
        path=np.empty((draws,maxh,d))
        for t in range(maxh):
            expected=((((state-location)/full)@vectors)*(phi-1))@vectors.T*full
            expected=np.clip(expected,-.15*sigma,.15*sigma)
            path[:,t]=expected+z[indices[:,t]]*sigma;state+=path[:,t]
        return finish(s,path,steps)
    standardized=(train-centre)/full
    if kind=='smooth_var':
        features=np.array([np.concatenate([standardized[t-1],standardized[t-5:t].mean(axis=0),
                           standardized[t-20:t].mean(axis=0)]) for t in range(20,len(train))])
        target=standardized[20:];penalty=.3;lag=20
    else:
        features=standardized[:-1];target=standardized[1:];penalty=.1;lag=1
    beta=np.linalg.solve(features.T@features+len(features)*penalty*np.eye(features.shape[1]),features.T@target)
    residual=target-features@beta
    residual-=residual.mean(axis=0);residual/=np.maximum(residual.std(axis=0,ddof=1),1e-12)
    indices=rng.integers(len(residual),size=(draws,maxh))
    memory=np.broadcast_to(x[-lag:][None,:,:],(draws,lag,d)).copy();path=np.empty((draws,maxh,d))
    drift=mean*.25 if s.target=='log_return' else mean
    for t in range(maxh):
        z=(memory-centre)/full
        feature=np.concatenate([z[:,-1],z[:,-5:].mean(axis=1),z.mean(axis=1)],axis=1) if kind=='smooth_var' else z[:,-1]
        predictable=(feature@beta)*full
        predictable=np.clip(predictable,-.15*sigma,.15*sigma)
        path[:,t]=drift+predictable+residual[indices[:,t]]*sigma
        memory=np.concatenate([memory[:,1:],path[:,t:t+1]],axis=1)
    return finish(s,path,steps)
