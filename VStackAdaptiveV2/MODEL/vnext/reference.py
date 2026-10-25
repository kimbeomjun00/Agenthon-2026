"""Short-horizon joint Gaussian random walk fitted only to cutoff-valid history.

This is a submission-safe reconstruction of the published text-blind reference idea.
It reads no answer table and stores no fitted parameters.  The final 300 observations
are used so that old regimes do not dominate a one-to-four-business-day forecast.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from .numeric import History, _finish, prepare


def _regularized_covariance(x: np.ndarray) -> np.ndarray:
    cov = np.atleast_2d(np.cov(x, rowvar=False, ddof=1)).astype(float)
    cov[np.diag_indices_from(cov)] += 1e-10
    cov += np.eye(cov.shape[0], dtype=float) * 1e-9
    try:
        np.linalg.cholesky(cov)
    except np.linalg.LinAlgError:
        cov = np.diag(np.maximum(np.diag(cov), 1e-9))
    return cov


def forecast(
    panels,
    assets,
    steps,
    asof,
    target_type,
    draws,
    seed,
    monthly=False,
) -> tuple[np.ndarray, dict[str, Any]]:
    if monthly:
        raise ValueError("short-horizon Gaussian reference is daily-only")
    hist = prepare(panels, assets, asof, target_type, monthly=False, absolute=True)
    recent = hist.steps.tail(299)
    if len(recent) < 30:
        raise ValueError("insufficient aligned recent history for Gaussian reference")
    x = recent.to_numpy(dtype=float)
    mean = x.mean(axis=0)
    covariance = _regularized_covariance(x)
    max_h = int(np.max(steps))
    rng = np.random.default_rng(seed)
    innovations = rng.multivariate_normal(mean, covariance, size=(draws, max_h))
    sample = _finish(hist, innovations, steps)
    return sample, {
        "engine": "short_horizon_joint_gaussian_reference",
        "history_steps": int(len(recent)),
        "drift": dict(zip(assets, map(float, mean))),
        "innovation_sd": dict(zip(assets, map(float, np.sqrt(np.diag(covariance))))),
        "gap_steps_removed": int(hist.gap_count),
        "answer_data_used": False,
    }

