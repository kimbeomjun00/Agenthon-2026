from __future__ import annotations

"""Structural V11 practice-unit batch validator.

Runs every non-example local practice unit once with House disabled. This is not a score study;
it checks that the archived V11 implementation produces finite schema-shaped outputs and sidecars.
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--units", default="units")
    ap.add_argument("--out", default="v11_batch_out")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()

    units = pathlib.Path(a.units)
    outroot = pathlib.Path(a.out)
    if outroot.exists(): shutil.rmtree(outroot)
    outroot.mkdir(parents=True)

    rows = []
    for d in sorted(units.iterdir()):
        cp = d / "card.toml"
        if not d.is_dir() or not cp.is_file(): continue
        with cp.open("rb") as f: card = tomllib.load(f)
        uid = str(card.get("task", {}).get("id", d.name))
        if uid.startswith("t2-EXAMPLE"): continue
        asof = str(card["provenance"]["data_cutoff"])
        assets = [str(x) for x in card["targets"]["asset_ids"]]
        horizons = [int(x) for x in card["targets"]["horizons"]]
        panels = d / "panels" if (d / "panels").exists() else d
        text = d / "text" if (d / "text").exists() else d
        od = outroot / uid
        od.mkdir(parents=True)
        fp = od / "forecast.parquet"
        env = os.environ.copy()
        env["QFBENCH_SEED"] = str(a.seed)
        for k in ("MODEL_ENDPOINT","MODEL_NAME","V11_MOCK_HOUSE_JSON","V8_MOCK_HOUSE_JSON"):
            env.pop(k, None)
        p = subprocess.run([
            sys.executable,"-m","v11_new.production_cli",
            "--panels",str(panels),"--text",str(text),"--asof",asof,
            "--out",str(fp),"--card",str(cp),"--seed",str(a.seed),
        ], text=True, capture_output=True, env=env)
        rec = {"unit":uid,"ok":False,"error":""}
        if p.returncode != 0:
            rec["error"] = (p.stderr or p.stdout)[-1000:].replace("\n"," | ")
        else:
            try:
                df = pd.read_parquet(fp)
                meta = json.loads((od/"forecast_meta.json").read_text(encoding="utf-8"))
                n = int(meta["n_draws"])
                vals = pd.to_numeric(df["value"], errors="coerce").to_numpy(float)
                rec["ok"] = bool(
                    len(df) == n*len(assets)*len(horizons)
                    and np.isfinite(vals).all()
                    and (od/"forecast_rationale.md").is_file()
                )
            except Exception as exc:
                rec["error"] = f"{type(exc).__name__}: {exc}"
        rows.append(rec)
        print(f"{uid:46s} {'PASS' if rec['ok'] else 'FAIL'}")

    df = pd.DataFrame(rows)
    df.to_csv(outroot/"v11_batch.csv", index=False, encoding="utf-8-sig")
    print("Units:", len(df), "Passed:", int(df["ok"].sum()), "Failed:", int((~df["ok"]).sum()))
    if not bool(df["ok"].all()): raise SystemExit(1)
    print("=== V11 BATCH PASS ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
