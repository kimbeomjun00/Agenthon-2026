"""Answer-free rolling pseudo-Final backtest for the F3 volatility adjustment.

The test creates synthetic Monday 1-4 business-day F3 tasks from the histories
shipped inside official public units.  Every forecast origin and every target is
strictly before the unit cutoff.  Published practice answers are never opened.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from qfbench2_common.scoring.crps import crps_ensemble, variogram_score
from qfbench2_track_forecasting.cli import _read_panels, _series
from qfbench2_track_forecasting.tail import tail_pinball

from vnext.numeric import _scale, prepare
from vnext.short_horizon import forecast as short_forecast
from vnext.volatility import adjust as volatility_adjust


ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
UNIT_ROOT = ROOT / "official-track2" / "units"
HORIZONS = np.array([1, 2, 3, 4], dtype=int)
POWERS = (0.0, 0.50, 0.75, 1.0)

CONFIGS = (
    {
        "name": "rates_bills",
        "unit": "t2-F2-curve-ust6m-004-ps1",
        "panel_id": "rates_daily",
        "assets": ["UST_3M", "UST_6M", "UST_1Y"],
    },
    {
        "name": "rates_curve",
        "unit": "t2-F1-hawkish-cut-2024",
        "panel_id": "rates_daily",
        "assets": ["UST_2Y", "UST_5Y", "UST_10Y", "UST_30Y"],
    },
    {
        "name": "g10_fx",
        "unit": "t2-F3-election-2024-joint",
        "panel_id": "g10_fx_daily",
        "assets": ["EUR", "JPY", "CHF"],
    },
    {
        "name": "em_fx_latam",
        "unit": "t2-F2-fx-krw-015-ps1",
        "panel_id": "em_fx_ecb_daily",
        "assets": ["MXN", "BRL", "ZAR"],
    },
    {
        "name": "em_fx_asia_africa",
        "unit": "t2-F2-fx-krw-015-ps1",
        "panel_id": "em_fx_ecb_daily",
        "assets": ["KRW", "INR", "ZAR"],
    },
)


def stable_seed(label: str) -> int:
    return int.from_bytes(hashlib.sha256(label.encode()).digest()[:4], "little")


def common_levels(panels, assets: list[str], cutoff: str) -> pd.DataFrame:
    levels = pd.DataFrame({asset: _series(panels, asset, cutoff) for asset in assets}).dropna()
    levels.index = pd.DatetimeIndex(pd.to_datetime(levels.index))
    return levels.sort_index()


def origins(levels: pd.DataFrame) -> list[pd.Timestamp]:
    # Mondays, roughly monthly, with >=756 earlier observations and four later rows.
    eligible = [
        pd.Timestamp(date)
        for i, date in enumerate(levels.index)
        if i >= 756 and i + int(HORIZONS.max()) < len(levels)
        and pd.Timestamp(date).weekday() == 0
        and pd.Timestamp(date) >= pd.Timestamp("2012-01-01")
        and pd.Timestamp(levels.index[i + int(HORIZONS.max())]) - pd.Timestamp(date)
        <= pd.Timedelta(days=7)
    ]
    return eligible[::4]


def standardized(panel_sample, truth, hist, scale):
    anchor = hist.anchor[None, None, :]
    if hist.logarithmic:
        simulated_move = np.log(np.maximum(panel_sample, 1e-300) / anchor)
        truth_move = np.log(np.maximum(truth, 1e-300) / hist.anchor[None, :])
    else:
        simulated_move = panel_sample - anchor
        truth_move = truth - hist.anchor[None, :]
    return simulated_move / scale[None, :, :], truth_move / scale


def metrics(samples: np.ndarray, truth: np.ndarray) -> dict[str, float]:
    flat_sample = samples.reshape(len(samples), -1)
    flat_truth = truth.reshape(-1)
    return {
        "marginal": float(crps_ensemble(flat_sample, flat_truth).mean()),
        "joint": float(variogram_score(flat_sample, flat_truth, p=0.5)),
        "tail": float(tail_pinball(flat_sample, flat_truth, (0.01, 0.05, 0.95, 0.99))),
    }


def main() -> int:
    rows: list[dict[str, object]] = []
    for config in CONFIGS:
        panel_id = str(config["panel_id"])
        unit_dir = UNIT_ROOT / str(config["unit"])
        loaded = _read_panels(unit_dir)
        panels = {panel_id: loaded[panel_id]}
        assets = list(config["assets"])
        levels = common_levels(panels, assets, "9999-12-31")
        dates = origins(levels)
        if not dates:
            raise RuntimeError(f"no origins for {config['name']}")
        positions = {date: i for i, date in enumerate(levels.index)}
        steps = np.tile(HORIZONS, (len(assets), 1))
        for origin in dates:
            pos = positions[origin]
            truth = np.stack(
                [levels.iloc[pos + int(h)].to_numpy(float) for h in HORIZONS], axis=0
            )
            hist = prepare(panels, assets, str(origin.date()), "level", monthly=False)
            history = hist.steps.to_numpy(float)[-756:]
            step_sd = np.maximum(_scale(history, 120.0), 1e-12)
            scale = np.sqrt(HORIZONS[:, None]) * step_sd[None, :]
            seed = stable_seed(f"{config['name']}|{origin.date()}")
            base, meta = short_forecast(
                panels,
                assets,
                steps,
                str(origin.date()),
                "level",
                512,
                seed,
                False,
                panel_id=str(config["panel_id"]),
                card_family="T2-F3",
                fx_f3_direct=True,
                volatility_power=0.0,
            )
            for power in POWERS:
                if power == 0:
                    sample = base
                    vol_meta = {"multipliers": [1.0] * len(assets)}
                else:
                    sample, vol_meta = volatility_adjust(
                        panels,
                        assets,
                        str(origin.date()),
                        "level",
                        base,
                        power=power,
                    )
                normalized_sample, normalized_truth = standardized(
                    sample, truth, hist, scale
                )
                score = metrics(normalized_sample, normalized_truth)
                rows.append(
                    {
                        "dataset": config["name"],
                        "source_unit": config["unit"],
                        "panel_id": config["panel_id"],
                        "assets": "|".join(assets),
                        "origin": str(origin.date()),
                        "period": "2018-2024" if origin.year >= 2018 else "2012-2017",
                        "power": power,
                        "route": meta["short_horizon_route"],
                        "multipliers": json.dumps(vol_meta.get("multipliers", [])),
                        **score,
                    }
                )
        print(f"{config['name']}: {len(dates)} origins", flush=True)

    frame = pd.DataFrame(rows)
    frame.to_csv(OUT / "adaptive_rolling_backtest_rows.csv", index=False)

    grouped = (
        frame.groupby(["dataset", "period", "power"], as_index=False)
        .agg(origins=("origin", "nunique"), marginal=("marginal", "mean"),
             joint=("joint", "mean"), tail=("tail", "mean"))
    )
    grouped_parts = []
    for (_, _), part in grouped.groupby(["dataset", "period"], sort=False):
        reference = part.loc[part["power"] == 0].iloc[0]
        part = part.copy()
        for component in ("marginal", "joint", "tail"):
            part[f"{component}_ratio"] = part[component] / float(reference[component])
        part["relative_composite"] = (
            0.5 * part["marginal_ratio"]
            + 0.3 * part["joint_ratio"]
            + 0.2 * part["tail_ratio"]
        )
        part["improvement_vs_unadapted_pct"] = 100 * (1 - part["relative_composite"])
        grouped_parts.append(part)
    grouped = pd.concat(grouped_parts, ignore_index=True)
    overall = (
        frame.groupby("power", as_index=False)
        .agg(observations=("origin", "size"), origins=("origin", "nunique"),
             marginal=("marginal", "mean"), joint=("joint", "mean"), tail=("tail", "mean"))
    )
    base = overall.loc[overall["power"] == 0].iloc[0]
    for component, weight in (("marginal", 0.5), ("joint", 0.3), ("tail", 0.2)):
        overall[f"{component}_ratio"] = overall[component] / float(base[component])
    overall["relative_composite"] = (
        0.5 * overall["marginal_ratio"]
        + 0.3 * overall["joint_ratio"]
        + 0.2 * overall["tail_ratio"]
    )
    overall["improvement_vs_unadapted_pct"] = 100 * (1 - overall["relative_composite"])

    period = (
        frame.groupby(["period", "power"], as_index=False)
        .agg(observations=("origin", "size"), marginal=("marginal", "mean"),
             joint=("joint", "mean"), tail=("tail", "mean"))
    )
    period_rows = []
    for label, part in period.groupby("period"):
        reference = part.loc[part["power"] == 0].iloc[0]
        part = part.copy()
        for component in ("marginal", "joint", "tail"):
            part[f"{component}_ratio"] = part[component] / float(reference[component])
        part["relative_composite"] = (
            0.5 * part["marginal_ratio"] + 0.3 * part["joint_ratio"] + 0.2 * part["tail_ratio"]
        )
        part["improvement_vs_unadapted_pct"] = 100 * (1 - part["relative_composite"])
        period_rows.append(part)
    period_summary = pd.concat(period_rows, ignore_index=True)

    grouped.to_csv(OUT / "adaptive_rolling_backtest_dataset.csv", index=False)
    overall.to_csv(OUT / "adaptive_rolling_backtest_overall.csv", index=False)
    period_summary.to_csv(OUT / "adaptive_rolling_backtest_period.csv", index=False)
    payload = {
        "answer_files_used": False,
        "design": "Monday 1-4 business-day pseudo-F3 tasks; inputs are truncated at each synthetic origin",
        "source_policy": "one coherent public unit per dataset; no cross-unit panel merge",
        "panel_sources": {str(config["name"]): str(config["unit"]) for config in CONFIGS},
        "datasets": len(CONFIGS),
        "forecast_rows": int(len(frame)),
        "origin_dataset_pairs": int(frame[["dataset", "origin"]].drop_duplicates().shape[0]),
        "overall": overall.to_dict(orient="records"),
        "period": period_summary.to_dict(orient="records"),
    }
    (OUT / "adaptive_rolling_backtest.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    print("\nOverall:\n", overall.to_string(index=False))
    print("\nBy period:\n", period_summary.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
