"""Cutoff-local volatility-regime adjustment for short-horizon forecasts.

The adjustment is intentionally small and direction-free.  It compares a fast
and a slow causal volatility estimate from the supplied history, shrinks the
ratio toward one, and rescales complete simulated paths around the last known
level.  No outcome table, card identity, calendar date, or external data is
consulted.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from .numeric import _scale, prepare


def _regime_multipliers(
    steps_history: np.ndarray,
    *,
    power: float,
    fast_half_life: float = 20.0,
    slow_half_life: float = 120.0,
    max_history: int = 756,
    lower: float = 0.80,
    upper: float = 1.25,
    deadband: float = 0.05,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Return conservative per-asset fast/slow volatility multipliers."""
    x = np.asarray(steps_history, dtype=float)
    if x.ndim != 2 or len(x) < 120:
        width = x.shape[1] if x.ndim == 2 else 1
        ones = np.ones(width, dtype=float)
        return ones, {
            "applied": False,
            "reason": "fewer than 120 aligned daily increments",
            "history_steps": int(len(x)) if x.ndim else 0,
            "multipliers": ones.tolist(),
        }

    recent = x[-min(max_history, len(x)) :]
    fast = np.maximum(_scale(recent, fast_half_life), 1e-12)
    slow = np.maximum(_scale(recent, slow_half_life), 1e-12)
    raw_ratio = np.clip(fast / slow, 0.50, 2.00)

    # Remove small estimator noise, shrink large changes, and share a little
    # regime information across assets without forcing identical volatilities.
    log_ratio = np.log(raw_ratio)
    threshold = float(np.log1p(deadband))
    active = np.sign(log_ratio) * np.maximum(np.abs(log_ratio) - threshold, 0.0)
    common = float(np.median(active))
    pooled = 0.75 * active + 0.25 * common
    multiplier = np.clip(np.exp(float(power) * pooled), lower, upper)

    return multiplier, {
        "applied": bool(np.any(np.abs(multiplier - 1.0) > 1e-12)),
        "history_steps": int(len(recent)),
        "fast_half_life": float(fast_half_life),
        "slow_half_life": float(slow_half_life),
        "power": float(power),
        "deadband": float(deadband),
        "clip": [float(lower), float(upper)],
        "fast_sd": fast.tolist(),
        "slow_sd": slow.tolist(),
        "raw_fast_slow_ratio": raw_ratio.tolist(),
        "multipliers": multiplier.tolist(),
        "answer_data_used": False,
    }


def adjust(
    panels,
    assets,
    asof,
    target_type,
    sample: np.ndarray,
    *,
    power: float = 0.50,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Rescale full paths around their cutoff-valid anchor."""
    if power <= 0:
        return sample, {"applied": False, "reason": "zero adaptation power"}
    hist = prepare(panels, assets, asof, target_type, monthly=False)
    multiplier, meta = _regime_multipliers(hist.steps.to_numpy(float), power=power)
    if not meta["applied"]:
        return sample, meta

    out = np.asarray(sample, dtype=float).copy()
    scale = multiplier[None, None, :]
    anchor = hist.anchor[None, None, :]
    if hist.logarithmic:
        if np.any(out <= 0) or np.any(hist.anchor <= 0):
            return sample, {**meta, "applied": False, "reason": "nonpositive log-level path"}
        move = np.log(out / anchor)
        out = anchor * np.exp(np.clip(move * scale, -20.0, 20.0))
        transform = "log_move_around_last_level"
    else:
        out = anchor + (out - anchor) * scale
        transform = "linear_move_around_last_level"
    if not np.isfinite(out).all():
        raise ValueError("volatility adaptation produced non-finite values")
    return out, {**meta, "transform": transform}
