"""Paired validation of the F3-only volatility-adaptive Short V2 candidate."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
BASELINE = (
    ROOT
    / "delivery"
    / "VStack_Short_V2_Research_2026-10-20"
    / "RESULTS"
    / "candidate_results.csv"
)
ADAPTIVE = ROOT / "adaptive_f3_candidate_results.csv"
SOURCE_WINNER = "vstack_short_v2_adaptive_f3"
RELEASE_WINNER = "vstack_short_v2_adaptive"
COMPONENTS = ["marginal_normalized", "joint_normalized", "tail_normalized", "normalized_score"]


def summarize(frame: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    rows = []
    for values, group in frame.groupby(keys, sort=False):
        if not isinstance(values, tuple):
            values = (values,)
        row = dict(zip(keys, values))
        row.update(
            observations=int(len(group)),
            cards=int(group["unit_id"].nunique()),
            seeds=int(group["seed"].nunique()),
            v2_score=float(group["v2_score"].mean()),
            adaptive_score=float(group["adaptive_score"].mean()),
            m0_score=float(group["m0_normalized"].mean()),
            delta_adaptive_vs_v2=float(group["delta_adaptive_vs_v2"].mean()),
            improvement_vs_v2_pct=float(
                -100 * group["delta_adaptive_vs_v2"].mean() / group["v2_score"].mean()
            ),
            improvement_vs_m0_pct=float(
                100 * (group["m0_normalized"].mean() - group["adaptive_score"].mean())
                / group["m0_normalized"].mean()
            ),
            paired_win_rate=float((group["delta_adaptive_vs_v2"] < 0).mean()),
        )
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> int:
    baseline = pd.read_csv(BASELINE)
    baseline = baseline[baseline["candidate"] == "vstack_short_v2"].copy()
    adaptive = pd.read_csv(ADAPTIVE)
    adaptive = adaptive[adaptive["candidate"] == SOURCE_WINNER].copy()
    keys = ["unit_id", "seed"]
    keep = keys + ["asof", "family", "group", "m0_normalized", *COMPONENTS]
    merged = baseline[keep].merge(
        adaptive[keys + COMPONENTS], on=keys, suffixes=("_v2", "_adaptive"), validate="one_to_one"
    )
    if len(merged) != 110:
        raise RuntimeError(f"expected 110 paired rows, found {len(merged)}")
    merged["year"] = pd.to_datetime(merged["asof"]).dt.year
    merged["period"] = np.where(merged["year"] >= 2018, "2018-2022", "2009-2017")
    merged["v2_score"] = merged["normalized_score_v2"]
    merged["adaptive_score"] = merged["normalized_score_adaptive"]
    merged["delta_adaptive_vs_v2"] = merged["adaptive_score"] - merged["v2_score"]

    overall = summarize(merged.assign(scope="all"), ["scope"])
    by_seed = summarize(merged, ["seed"])
    by_family = summarize(merged, ["family"])
    by_group = summarize(merged, ["group"])
    by_period = summarize(merged, ["period"])

    card = (
        merged.groupby(["unit_id", "asof", "family", "group"], as_index=False)
        .agg(
            v2_score=("v2_score", "mean"),
            adaptive_score=("adaptive_score", "mean"),
            m0_score=("m0_normalized", "mean"),
            delta_adaptive_vs_v2=("delta_adaptive_vs_v2", "mean"),
        )
        .sort_values("delta_adaptive_vs_v2")
    )
    card["improvement_vs_v2_pct"] = -100 * card["delta_adaptive_vs_v2"] / card["v2_score"]
    card["changed"] = card["delta_adaptive_vs_v2"].abs() > 1e-12
    card["adaptive_wins"] = card["delta_adaptive_vs_v2"] < 0

    rng = np.random.default_rng(20261020)
    card_delta = card["delta_adaptive_vs_v2"].to_numpy(float)
    bootstrap = rng.choice(card_delta, size=(50000, len(card_delta)), replace=True).mean(axis=1)
    ci = np.quantile(bootstrap, [0.025, 0.975])
    loo = np.array([np.delete(card_delta, i).mean() for i in range(len(card_delta))])

    component_delta = {
        component: float(
            (merged[f"{component}_adaptive"] - merged[f"{component}_v2"]).mean()
        )
        for component in COMPONENTS
    }
    non_f3 = merged[merged["family"] != "T2-F3"]
    unchanged_non_f3 = bool(
        np.allclose(non_f3["adaptive_score"], non_f3["v2_score"], rtol=0, atol=0)
    )
    payload = {
        "winner": RELEASE_WINNER,
        "rows": int(len(merged)),
        "cards": int(merged["unit_id"].nunique()),
        "seeds": sorted(map(int, merged["seed"].unique())),
        "overall": overall.iloc[0].to_dict(),
        "component_mean_delta_adaptive_minus_v2": component_delta,
        "card_level": {
            "changed_cards": int(card["changed"].sum()),
            "wins_on_changed_cards": int((card["changed"] & card["adaptive_wins"]).sum()),
            "losses_on_changed_cards": int((card["changed"] & ~card["adaptive_wins"]).sum()),
            "bootstrap_mean_delta_95pct": list(map(float, ci)),
            "leave_one_card_out_mean_delta_range": [float(loo.min()), float(loo.max())],
        },
        "non_f3_outputs_score_identical": unchanged_non_f3,
        "limitations": [
            "The 22 published practice cards are a small public tuning set, not the ranked Final.",
            "Only five cards are F3, so the incremental gain has substantial selection uncertainty.",
            "House reasoning is disabled in this offline comparison.",
        ],
    }

    merged.to_csv(ROOT / "adaptive_paired_rows.csv", index=False)
    overall.to_csv(ROOT / "adaptive_comparison_overall.csv", index=False)
    by_seed.to_csv(ROOT / "adaptive_comparison_seed.csv", index=False)
    by_family.to_csv(ROOT / "adaptive_comparison_family.csv", index=False)
    by_group.to_csv(ROOT / "adaptive_comparison_group.csv", index=False)
    by_period.to_csv(ROOT / "adaptive_comparison_period.csv", index=False)
    card.to_csv(ROOT / "adaptive_comparison_card.csv", index=False)
    (ROOT / "adaptive_validation.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(overall.to_string(index=False))
    print("\nBy seed:\n", by_seed.to_string(index=False))
    print("\nBy family:\n", by_family.to_string(index=False))
    print("\nBy period:\n", by_period.to_string(index=False))
    print("\nValidation:\n", json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
