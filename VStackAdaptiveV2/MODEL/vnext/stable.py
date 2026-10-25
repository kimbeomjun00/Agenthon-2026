"""Conservative release candidate; explicitly a post-comparison composition.

Pure-domain calls are exactly the preceding fast_price function. Heterogeneous and
unknown domains retain the numerical joint baseline instead of cross-domain coupling.
No learned weights, asset winner table, outcomes or evaluation dates are consulted.
"""
from .experts import family
from .fast_price import forecast as previous_forecast
from .inflation import forecast as safe_forecast


def forecast(panels,assets,steps,asof,target,draws,seed,monthly=False):
    groups={family(a) for a in assets}
    if len(groups)!=1 or 'other' in groups:
        sample,meta=safe_forecast(panels,assets,steps,asof,target,draws,seed,monthly)
        return sample,{'engine':'stable_mixed_or_unknown_joint_baseline','baseline':meta,
                       'release_policy':'post-comparison conservative composition'}
    sample,meta=previous_forecast(panels,assets,steps,asof,target,draws,seed,monthly)
    return sample,{**meta,'release_policy':'post-comparison conservative composition; pure domain exactly previous_fast'}
