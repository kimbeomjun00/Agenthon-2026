"""Inventory coherent public-unit histories for the rolling backtest."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from qfbench2_track_forecasting.cli import _read_panels

from backtest_volatility_adaptation import CONFIGS, UNIT_ROOT


def main() -> int:
    rows: list[dict[str, object]] = []
    for unit_dir in sorted(path.parent for path in UNIT_ROOT.glob("*/card.toml")):
        panels = _read_panels(unit_dir)
        for config in CONFIGS:
            panel_id = str(config["panel_id"])
            if panel_id not in panels:
                continue
            assets = list(config["assets"])
            source = panels[panel_id]
            if not set(assets).issubset(set(source["asset"].astype(str))):
                continue
            levels = (
                source[source["asset"].isin(assets)]
                .pivot_table(index="date", columns="asset", values="value", aggfunc="last")
                .reindex(columns=assets)
                .dropna()
            )
            if levels.empty:
                continue
            rows.append(
                {
                    "dataset": config["name"],
                    "unit": unit_dir.name,
                    "rows": int(len(levels)),
                    "first": str(pd.Timestamp(levels.index.min()).date()),
                    "last": str(pd.Timestamp(levels.index.max()).date()),
                }
            )
    frame = pd.DataFrame(rows).sort_values(
        ["dataset", "rows", "last"], ascending=[True, False, False]
    )
    frame.to_csv(Path(__file__).resolve().parent / "panel_unit_inventory.csv", index=False)
    for dataset, part in frame.groupby("dataset", sort=False):
        print(f"\n{dataset}\n{part.head(10).to_string(index=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
