from __future__ import annotations

"""Small local smoke for the archived V11 candidate.

Runs one practice unit twice: numeric fallback and a deterministic mock House scenario.
It checks required outputs and verifies that mock text changes the distribution.
"""

import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tomllib

import numpy as np
import pandas as pd


def _pick(units: pathlib.Path, family: str | None) -> pathlib.Path:
    for d in sorted(units.iterdir()):
        p = d / "card.toml"
        if not d.is_dir() or not p.is_file():
            continue
        with p.open("rb") as f:
            card = tomllib.load(f)
        if str(card.get("task", {}).get("id", "")).startswith("t2-EXAMPLE"):
            continue
        fam = str(card.get("metadata", {}).get("category", ""))
        if family is None or fam == family:
            return d
    raise SystemExit("no matching practice unit")


def _run(unit: pathlib.Path, out: pathlib.Path, mock: str | None, seed: int) -> tuple[pd.DataFrame, dict]:
    with (unit / "card.toml").open("rb") as f:
        card = tomllib.load(f)
    asof = str(card["provenance"]["data_cutoff"])
    panels = unit / "panels" if (unit / "panels").exists() else unit
    text = unit / "text" if (unit / "text").exists() else unit
    out.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["QFBENCH_SEED"] = str(seed)
    env.pop("MODEL_ENDPOINT", None)
    env.pop("MODEL_NAME", None)
    env.pop("V11_MOCK_HOUSE_JSON", None)
    if mock is not None:
        env["V11_MOCK_HOUSE_JSON"] = mock
    cmd = [
        sys.executable, "-m", "v11_new.production_cli",
        "--panels", str(panels), "--text", str(text), "--asof", asof,
        "--out", str(out / "forecast.parquet"), "--card", str(unit / "card.toml"),
        "--seed", str(seed),
    ]
    p = subprocess.run(cmd, text=True, capture_output=True, env=env)
    if p.returncode != 0:
        raise SystemExit(p.stderr or p.stdout)
    df = pd.read_parquet(out / "forecast.parquet")
    meta = json.loads((out / "forecast_meta.json").read_text(encoding="utf-8"))
    if not (out / "forecast_rationale.md").is_file():
        raise SystemExit("missing rationale")
    if not np.isfinite(pd.to_numeric(df["value"], errors="coerce").to_numpy(float)).all():
        raise SystemExit("non-finite output")
    return df, meta


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--units", default="units")
    ap.add_argument("--family", default="T2-F3")
    ap.add_argument("--out", default="v11_smoke_out")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()

    unit = _pick(pathlib.Path(a.units), a.family or None)
    root = pathlib.Path(a.out)
    if root.exists(): shutil.rmtree(root)

    with (unit / "card.toml").open("rb") as f:
        card = tomllib.load(f)
    assets = [str(x) for x in card["targets"]["asset_ids"]]
    spec = {x: {"shift_sd": 0.35, "vol_scale": 1.20, "because": "local-smoke"} for x in assets}
    mock = json.dumps({
        "state": {"label": "transition", "confidence": 1.0},
        "scenarios": [{"name": "mock-transition", "prob": 1.0, "assets": spec}],
    })

    off, moff = _run(unit, root / "off", None, a.seed)
    on, mon = _run(unit, root / "mock", mock, a.seed)
    same = np.array_equal(off["value"].to_numpy(), on["value"].to_numpy())

    print("unit:", card["task"]["id"])
    print("numeric engine:", moff.get("v11", {}).get("numeric", {}).get("engine"))
    print("off reasoning:", moff.get("reasoning_applied"))
    print("mock reasoning:", mon.get("reasoning_applied"))
    print("off/mock identical:", same)
    if same:
        raise SystemExit("mock scenario did not change forecast")
    print("=== V11 LOCAL SMOKE PASS ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
