"""## Executive summary (read this first)
Research a proportional-growth inflation model using the existing cutoff-local trend choice.
Keep non-price targets and the 15% insurance component on the original absolute baseline.
"""
import numpy as np
import pandas as pd
from .specialists import prepare,State,PRICES
from .inflation import candidates,choose,forecast as fixed

def forecast(panels,assets,steps,asof,target,draws,seed,monthly=False):
    if not monthly or not any(a in PRICES for a in assets):return fixed(panels,assets,steps,asof,target,draws,seed,monthly)
    s=prepare(panels,assets,asof,target,True);selected,meta=choose(s,steps)
    levels=s.levels.copy();anchor=s.anchor.copy();x=s.x.copy()
    for ai,a in enumerate(assets):
        if a not in PRICES or (levels[a].dropna()<=0).any():selected[ai]='baseline';continue
        levels[a]=np.log(levels[a]);anchor[ai]=np.log(anchor[ai])
        transformed=levels[a].dropna().diff()
        x[:,ai]=transformed.reindex(s.dates).to_numpy(float)
    logged=State(levels,x,s.dates,anchor,s.assets,s.target,s.monthly,s.offsets)
    sims=candidates(logged,steps,draws,seed,correlation_source=s.x)
    original=candidates(s,steps,draws,seed)['baseline'];sample=original.copy()
    for ai,a in enumerate(assets):
        if a in PRICES and selected[ai]!='baseline':sample[:,:,ai]=np.exp(np.clip(sims[selected[ai]][:,:,ai],-700,700))
    insured=np.random.default_rng(seed+15531).random(draws)<.15
    sample[insured]=original[insured]
    return sample,{'engine':'proportional_inflation_growth','selection':meta,'baseline_draw_fraction':.15,
                   'note':'Raw-history trend menu choice, log-history numerical growth; shared original Gaussian correlation.'}
