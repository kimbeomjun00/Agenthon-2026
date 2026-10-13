"""Global design frozen on purged 2006-2019 development; fit weights on unit past."""
from .stacking import forecast as _forecast

SELECTED_MODE = 'stack50'


def forecast(panels, assets, steps, asof, target_type, draws, seed, monthly=False):
    return _forecast(panels, assets, steps, asof, target_type, draws, seed, monthly,
                     mode=SELECTED_MODE)
