import numpy as np
import pandas as pd

from vnext.volatility import _regime_multipliers, adjust


def test_regime_multiplier_increases_after_high_volatility_cluster():
    rng = np.random.default_rng(7)
    calm = rng.normal(0, 1, size=(400, 2))
    stressed = rng.normal(0, 3, size=(80, 2))
    multiplier, meta = _regime_multipliers(np.vstack([calm, stressed]), power=0.5)
    assert meta["applied"] is True
    assert np.all(multiplier > 1.0)
    assert np.all(multiplier <= 1.25)


def test_regime_multiplier_decreases_after_calm_cluster():
    rng = np.random.default_rng(11)
    stressed = rng.normal(0, 3, size=(400, 2))
    calm = rng.normal(0, 0.6, size=(80, 2))
    multiplier, _ = _regime_multipliers(np.vstack([stressed, calm]), power=0.5)
    assert np.all(multiplier < 1.0)
    assert np.all(multiplier >= 0.80)


def test_adjust_preserves_positive_fx_paths(monkeypatch):
    dates = pd.bdate_range("2020-01-01", periods=300)
    levels = pd.DataFrame({"EUR": np.exp(np.cumsum(np.full(300, 0.0001)))}, index=dates)
    steps = np.zeros((299, 1))
    steps[-80:] = 0.01 * np.sin(np.arange(80))[:, None]

    class Hist:
        pass

    hist = Hist()
    hist.steps = pd.DataFrame(steps, index=dates[1:])
    hist.anchor = levels.iloc[-1].to_numpy(float)
    hist.logarithmic = True
    monkeypatch.setattr("vnext.volatility.prepare", lambda *a, **k: hist)
    sample = np.array([[[hist.anchor[0] * 0.99]], [[hist.anchor[0] * 1.01]]])
    out, meta = adjust({}, ["EUR"], "2021-01-01", "level", sample, power=0.5)
    assert np.isfinite(out).all()
    assert (out > 0).all()
    assert "multipliers" in meta
