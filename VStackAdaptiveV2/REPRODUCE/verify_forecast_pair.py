"""Container-side official scoring and value comparison for two forecasts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCORER = ROOT / "official-track2" / "scoring" / "scoring.py"


def score(card: Path, forecast: Path, answer: Path) -> dict[str, object]:
    completed = subprocess.run(
        [
            sys.executable,
            str(SCORER),
            "score",
            "--card",
            str(card),
            "--forecast",
            str(forecast),
            "--realized",
            str(answer),
        ],
        cwd=SCORER.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(completed.stdout + "\n" + completed.stderr)
    return json.loads(completed.stdout)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--card", type=Path, required=True)
    parser.add_argument("--forecast", type=Path, required=True)
    parser.add_argument("--direct", type=Path, required=True)
    parser.add_argument("--answer", type=Path, required=True)
    args = parser.parse_args()
    left = pd.read_parquet(args.forecast).sort_values(
        ["draw", "asset", "horizon"]
    ).reset_index(drop=True)
    right = pd.read_parquet(args.direct).sort_values(
        ["draw", "asset", "horizon"]
    ).reset_index(drop=True)
    keys = ["draw", "asset", "horizon"]
    if len(left) != len(right) or not left[keys].equals(right[keys]):
        raise AssertionError("Docker/direct forecast keys differ")
    payload = {
        "docker_score": score(args.card, args.forecast, args.answer),
        "direct_score": score(args.card, args.direct, args.answer),
        "max_value_abs_difference": float((left["value"] - right["value"]).abs().max()),
    }
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
