"""## Executive summary (read this first)
Research post-comparison composition: fast native-growth filter for all four price indices.
Keep non-price macro on VSpecial; daily assets still use the evaluated portfolio router.
No fitted coefficients, unit answers, event dates or benchmark winner table are loaded.
"""
import numpy as np
from .experts import context_state,expand_steps,rank_align_baseline
from . import experts
from .portfolio import forecast as portfolio_forecast
from .inflation import forecast as baseline_forecast
from .specialists import PRICES

def forecast(panels,assets,steps,asof,target,draws,seed,monthly=False):
    if not monthly:return portfolio_forecast(panels,assets,steps,asof,target,draws,seed,False)
    base,original=baseline_forecast(panels,assets,steps,asof,target,draws,seed,True)
    if target!='level' or not any(a in PRICES for a in assets):
        return base,{'engine':'fast_price_nonprice_baseline','baseline':original}
    s=context_state(panels,assets,asof,target,True)
    simulated=experts.candidates(s,expand_steps(s,assets,steps),draws,seed)['kf_fast']
    sample=base.copy()
    for i,a in enumerate(assets):
        if a in PRICES:sample[:,:,i]=simulated[:,:,s.assets.index(a)]
    sample=rank_align_baseline(sample,base,steps)
    insurance=np.random.default_rng(seed+6179).random(draws)<.2
    sample[insurance]=base[insurance]
    # Non-price marginal paths remain exactly the baseline even after the rank permutation.
    for i,a in enumerate(assets):
        if a not in PRICES:sample[:,:,i]=base[:,:,i]
    return sample,{'engine':'fast_price_family_research_hybrid','context_assets':s.assets,
        'asset_models':{a:('kf_fast_native_growth' if a in PRICES else 'VSpecial_macro_baseline') for a in assets},
        'baseline_joint_insurance_probability':.2,
        'coupling':'whole price trajectories ranked to baseline; non-price paths unchanged',
        'selection_scope':'family architecture chosen after primary comparison; reused-period research, not independent confirmation',
        'parameters':'all filter states, observation variance and native growth estimated from current supplied history'}
