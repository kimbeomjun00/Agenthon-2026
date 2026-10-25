"""Conservative panel/family router for one-to-four-business-day cards.

The policy is deliberately coarse and declared before looking at any card identity:
retain the established numerical baseline where it was structurally strongest
(single-asset/continuation and regime-shift Treasury cards), and otherwise use the
published-style joint Gaussian random walk.  Monthly and unsupported inputs fall
back to the frozen stable model.
"""
from __future__ import annotations

from typing import Any

from .inflation import forecast as established_baseline
from .numeric import FX, forecast as numeric_forecast
from .reference import forecast as gaussian_forecast
from .stable import forecast as stable_forecast
from .volatility import adjust as volatility_adjust


def forecast(
    panels,
    assets,
    steps,
    asof,
    target_type,
    draws,
    seed,
    monthly=False,
    *,
    panel_id="",
    card_family="",
    fx_f3_direct=False,
    volatility_power=0.0,
    volatility_f3_only=False,
) -> tuple[object, dict[str, Any]]:
    active_volatility_power = (
        volatility_power
        if not volatility_f3_only or card_family == "T2-F3"
        else 0.0
    )
    if monthly or target_type != "level":
        sample, meta = stable_forecast(
            panels, assets, steps, asof, target_type, draws, seed, monthly
        )
        return sample, {
            **meta,
            "short_horizon_route": "stable_unsupported_or_monthly",
            "panel_id": panel_id,
            "card_family": card_family,
        }

    rates = panel_id == "rates_daily" or all(str(asset).startswith("UST_") for asset in assets)
    if rates and card_family in {"T2-F1", "T2-F2"}:
        sample, meta = established_baseline(
            panels, assets, steps, asof, target_type, draws, seed, monthly
        )
        return sample, {
            **meta,
            "engine": "short_horizon_router_established_rates",
            "component": meta,
            "short_horizon_route": "established_rates_f1_f2",
            "panel_id": panel_id,
            "card_family": card_family,
            "volatility_regime": {
                "applied": False,
                "reason": "established rates F1/F2 route preserved exactly",
            },
        }

    fx = panel_id in {"g10_fx_daily", "em_fx_ecb_daily"} or all(asset in FX for asset in assets)
    if fx_f3_direct and fx and card_family == "T2-F3":
        sample, meta = numeric_forecast(
            panels,
            assets,
            steps,
            asof,
            target_type,
            draws,
            seed,
            monthly=False,
            mode="direct",
        )
        sample, vol_meta = volatility_adjust(
            panels, assets, asof, target_type, sample, power=active_volatility_power
        )
        return sample, {
            **meta,
            "engine": "short_horizon_router_fx_f3_direct",
            "component": meta,
            "short_horizon_route": "direct_fx_f3",
            "panel_id": panel_id,
            "card_family": card_family,
            "volatility_regime": vol_meta,
        }

    try:
        sample, meta = gaussian_forecast(
            panels, assets, steps, asof, target_type, draws, seed, monthly
        )
        sample, vol_meta = volatility_adjust(
            panels, assets, asof, target_type, sample, power=active_volatility_power
        )
        return sample, {
            **meta,
            "engine": "short_horizon_router_gaussian",
            "component": meta,
            "short_horizon_route": "gaussian_daily",
            "panel_id": panel_id,
            "card_family": card_family,
            "volatility_regime": vol_meta,
        }
    except ValueError as exc:
        sample, meta = stable_forecast(
            panels, assets, steps, asof, target_type, draws, seed, monthly
        )
        return sample, {
            **meta,
            "short_horizon_route": "stable_gaussian_unavailable",
            "route_fallback_reason": str(exc),
            "panel_id": panel_id,
            "card_family": card_family,
        }

