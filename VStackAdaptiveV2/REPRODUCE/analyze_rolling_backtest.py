"""Paired uncertainty checks for the answer-free volatility rolling backtest."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
COMPONENTS = ("marginal", "joint", "tail")
WEIGHTS = {"marginal": 0.5, "joint": 0.3, "tail": 0.2}
POWERS = (0.50, 0.75, 1.00)
BOOTSTRAPS = 20_000
RNG_SEED = 20261020


def paired_deltas(frame: pd.DataFrame, power: float) -> pd.DataFrame:
    """Return paired normalized composite deltas for one adaptive power."""
    selected = frame[frame["power"].isin([0.0, power])].copy()
    reference = selected[selected["power"] == 0.0]
    scales = {component: float(reference[component].mean()) for component in COMPONENTS}
    selected["relative_score"] = sum(
        WEIGHTS[component] * selected[component] / scales[component]
        for component in COMPONENTS
    )
    paired = selected.pivot(
        index=["dataset", "origin", "period"], columns="power", values="relative_score"
    ).reset_index()
    if 0.0 not in paired or power not in paired:
        raise ValueError(f"missing paired rows for power={power}")
    paired["delta"] = paired[power] - paired[0.0]
    return paired


def summarize(frame: pd.DataFrame, power: float, label: str) -> dict[str, object]:
    paired = paired_deltas(frame, power)
    # Several datasets can share the same date. Cluster on date so a common market
    # shock is resampled once rather than treated as independent evidence.
    date_delta = paired.groupby("origin", as_index=False)["delta"].mean()["delta"].to_numpy()
    rng = np.random.default_rng(RNG_SEED + int(power * 1000) + len(date_delta))
    draws = rng.choice(date_delta, size=(BOOTSTRAPS, len(date_delta)), replace=True).mean(axis=1)
    mean_delta = float(date_delta.mean())
    return {
        "scope": label,
        "power": float(power),
        "origin_dataset_pairs": int(len(paired)),
        "date_clusters": int(len(date_delta)),
        "mean_relative_delta": mean_delta,
        "improvement_pct": float(-100.0 * mean_delta),
        "date_win_rate": float(np.mean(date_delta < 0)),
        "pair_win_rate": float(np.mean(paired["delta"].to_numpy() < 0)),
        "bootstrap_ci_low": float(np.quantile(draws, 0.025)),
        "bootstrap_ci_high": float(np.quantile(draws, 0.975)),
        "bootstrap_probability_improvement": float(np.mean(draws < 0)),
    }


def main() -> int:
    frame = pd.read_csv(HERE / "adaptive_rolling_backtest_rows.csv")
    rows: list[dict[str, object]] = []
    for power in POWERS:
        rows.append(summarize(frame, power, "all_2012_2024"))
        for period in ("2012-2017", "2018-2024"):
            rows.append(summarize(frame[frame["period"] == period], power, period))
        if power == 1.0:
            for dataset in sorted(frame["dataset"].unique()):
                subset = frame[frame["dataset"] != dataset]
                rows.append(summarize(subset, power, f"leave_out_{dataset}"))

    summary = pd.DataFrame(rows)
    summary.to_csv(HERE / "adaptive_rolling_validation.csv", index=False)
    payload = {
        "answer_files_used": False,
        "bootstrap_unit": "origin date cluster",
        "bootstrap_draws": BOOTSTRAPS,
        "rng_seed": RNG_SEED,
        "score": "0.5 marginal ratio + 0.3 joint ratio + 0.2 tail ratio",
        "rows": summary.to_dict(orient="records"),
    }
    (HERE / "adaptive_rolling_validation.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    print(summary.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
