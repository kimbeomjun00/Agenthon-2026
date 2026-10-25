"""Unit checks for the short-horizon numerical router and Gaussian component."""
from __future__ import annotations

import numpy as np
import pandas as pd

from vnext import reference, short_horizon


def _marker(value, engine):
    return np.full((8, 2, 1), value, dtype=float), {"engine": engine}


def test_rates_f1_uses_established_baseline(monkeypatch):
    monkeypatch.setattr(short_horizon, "established_baseline", lambda *a, **k: _marker(1.0, "old"))
    monkeypatch.setattr(short_horizon, "gaussian_forecast", lambda *a, **k: _marker(2.0, "gaussian"))
    sample, meta = short_horizon.forecast(
        {}, ["UST_3M"], np.array([[1, 4]]), "2024-01-01", "level", 8, 42,
        panel_id="rates_daily", card_family="T2-F1", fx_f3_direct=True,
    )
    assert np.all(sample == 1.0)
    assert meta["short_horizon_route"] == "established_rates_f1_f2"


def test_fx_f3_uses_contiguous_joint_paths(monkeypatch):
    monkeypatch.setattr(short_horizon, "numeric_forecast", lambda *a, **k: _marker(3.0, "direct"))
    monkeypatch.setattr(short_horizon, "gaussian_forecast", lambda *a, **k: _marker(2.0, "gaussian"))
    sample, meta = short_horizon.forecast(
        {}, ["MXN"], np.array([[1, 4]]), "2024-01-01", "level", 8, 42,
        panel_id="em_fx_ecb_daily", card_family="T2-F3", fx_f3_direct=True,
    )
    assert np.all(sample == 3.0)
    assert meta["short_horizon_route"] == "direct_fx_f3"


def test_fx_f4_keeps_gaussian_safety_net(monkeypatch):
    monkeypatch.setattr(short_horizon, "numeric_forecast", lambda *a, **k: _marker(3.0, "direct"))
    monkeypatch.setattr(short_horizon, "gaussian_forecast", lambda *a, **k: _marker(2.0, "gaussian"))
    sample, meta = short_horizon.forecast(
        {}, ["BRL"], np.array([[1, 4]]), "2024-01-01", "level", 8, 42,
        panel_id="em_fx_ecb_daily", card_family="T2-F4", fx_f3_direct=True,
    )
    assert np.all(sample == 2.0)
    assert meta["short_horizon_route"] == "gaussian_daily"


def test_volatility_adaptation_is_not_applied_to_established_rates(monkeypatch):
    monkeypatch.setattr(short_horizon, "established_baseline", lambda *a, **k: ("base", {}))
    sample, meta = short_horizon.forecast(
        {}, ["UST_3M"], np.array([[1, 4]]), "2024-01-01", "level", 8, 42,
        panel_id="rates_daily", card_family="T2-F1", fx_f3_direct=True,
        volatility_power=0.5,
    )
    assert sample == "base"
    assert meta["volatility_regime"]["applied"] is False


def test_volatility_adaptation_wraps_fx_f3(monkeypatch):
    raw = np.ones((8, 2, 3))
    monkeypatch.setattr(short_horizon, "numeric_forecast", lambda *a, **k: (raw, {}))
    monkeypatch.setattr(
        short_horizon,
        "volatility_adjust",
        lambda *a, **k: (raw * 2, {"applied": True, "power": k["power"]}),
    )
    sample, meta = short_horizon.forecast(
        {}, ["MXN", "BRL", "ZAR"], np.tile([1, 4], (3, 1)), "2024-01-01",
        "level", 8, 42, panel_id="em_fx_ecb_daily", card_family="T2-F3",
        fx_f3_direct=True, volatility_power=0.5,
    )
    assert np.array_equal(sample, raw * 2)
    assert meta["volatility_regime"]["power"] == 0.5


def test_f3_only_policy_leaves_other_families_unchanged(monkeypatch):
    raw = np.ones((8, 2, 1))
    monkeypatch.setattr(short_horizon, "gaussian_forecast", lambda *a, **k: (raw, {}))
    seen = {}

    def fake_adjust(*args, **kwargs):
        seen["power"] = kwargs["power"]
        return raw, {"applied": False}

    monkeypatch.setattr(short_horizon, "volatility_adjust", fake_adjust)
    short_horizon.forecast(
        {}, ["MXN"], np.array([[1, 4]]), "2024-01-01", "level", 8, 42,
        panel_id="em_fx_ecb_daily", card_family="T2-F2", fx_f3_direct=True,
        volatility_power=1.0, volatility_f3_only=True,
    )
    assert seen["power"] == 0.0


def test_gaussian_component_is_joint_shaped_and_seed_deterministic():
    dates = pd.bdate_range("2020-01-01", periods=420)
    rng = np.random.default_rng(7)
    shocks = rng.multivariate_normal([0.0001, -0.00005], [[0.01, 0.006], [0.006, 0.02]], size=len(dates))
    levels = 5.0 + np.cumsum(shocks, axis=0)
    panel = pd.DataFrame(
        {
            "date": np.repeat(dates, 2),
            "asset": np.tile(["A", "B"], len(dates)),
            "value": levels.reshape(-1),
        }
    )
    panels = {"synthetic": panel}
    steps = np.array([[1, 2, 4], [1, 2, 4]])
    first, meta = reference.forecast(panels, ["A", "B"], steps, str(dates[-1].date()), "level", 200, 9)
    second, _ = reference.forecast(panels, ["A", "B"], steps, str(dates[-1].date()), "level", 200, 9)
    third, _ = reference.forecast(panels, ["A", "B"], steps, str(dates[-1].date()), "level", 200, 10)
    assert first.shape == (200, 3, 2)
    assert np.array_equal(first, second)
    assert not np.array_equal(first, third)
    assert np.isfinite(first).all()
    assert meta["history_steps"] == 299
    assert meta["answer_data_used"] is False
