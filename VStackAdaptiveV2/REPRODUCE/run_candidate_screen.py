"""## Executive summary (read this first)

Compare the preserved Agenthon Track 2 model candidates on the official 22-card
short-horizon practice set.  Every candidate sees the same card inputs, seed and
official scorer.  Scores are normalized by the published M0 Gaussian reference;
lower values are better.

This script never writes to the public benchmark checkout.  Outputs and results
stay in the sibling ``candidate-ps1-eval`` research directory.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


ROOT = pathlib.Path(__file__).resolve().parents[1]
EVAL_ROOT = pathlib.Path(__file__).resolve().parent
OFFICIAL_ROOT = ROOT / "official-track2"
UNIT_ROOT = OFFICIAL_ROOT / "units"
ANSWER_ROOT = OFFICIAL_ROOT / "practice-answers"
OUTPUT_ROOT = EVAL_ROOT / "outputs"


def load_base_module():
    path = ROOT / "vstack-ps1-eval" / "run_evaluation.py"
    spec = importlib.util.spec_from_file_location("vstack_ps1_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load evaluation helpers from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


BASE = load_base_module()


@dataclass(frozen=True)
class Candidate:
    name: str
    model_root: pathlib.Path
    module: str
    mode: str | None
    description: str


CANDIDATES: dict[str, Candidate] = {
    "v11": Candidate(
        "v11",
        ROOT / "agenthon-v11-work" / "V11",
        "v11_new.production_cli",
        None,
        "V11 E2+V8 scenario-mixture candidate",
    ),
    "vnext": Candidate(
        "vnext",
        ROOT / "agenthon-v11-work" / "VNext",
        "vnext.cli",
        "adaptive",
        "VNext adaptive historical selector",
    ),
    "vspecial": Candidate(
        "vspecial",
        ROOT / "agenthon-v11-work" / "VSpecial",
        "vnext.cli",
        "price",
        "VSpecial production default",
    ),
    "vspecial2": Candidate(
        "vspecial2",
        ROOT / "agenthon-v11-work" / "VSpecial2",
        "vnext.cli",
        "price",
        "VSpecial2 repaired production default",
    ),
    "vexpert": Candidate(
        "vexpert",
        ROOT / "agenthon-v11-work" / "VExpert",
        "vnext.cli",
        "expert",
        "VExpert guarded domain selector",
    ),
    "vexpert_fast": Candidate(
        "vexpert_fast",
        ROOT / "agenthon-v11-work" / "VExpert",
        "vnext.cli",
        "fast_price",
        "VExpert post-comparison fast-price integration",
    ),
    "vstack_stable": Candidate(
        "vstack_stable",
        ROOT / "vstack-final-image",
        "vnext.cli",
        "stable",
        "exact frozen source extracted from the submitted VStack image",
    ),
    "vstack_optimized": Candidate(
        "vstack_optimized",
        ROOT / "agenthon-v11-work" / "VStack",
        "vnext.cli",
        "optimized",
        "VStack stack50 research router",
    ),
    "vstack_expert": Candidate(
        "vstack_expert",
        ROOT / "agenthon-v11-work" / "VStack",
        "vnext.cli",
        "expert",
        "VStack source with VExpert router",
    ),
    "vstack_fast": Candidate(
        "vstack_fast",
        ROOT / "agenthon-v11-work" / "VStack",
        "vnext.cli",
        "fast_price",
        "VStack source with fast-price daily router",
    ),
    "vstack_develop_stable": Candidate(
        "vstack_develop_stable",
        ROOT / "candidate-ps1-eval" / "VStackDevelop",
        "vnext.cli",
        "stable",
        "VStack with the new bill tenors and EM currencies enabled in its domain router",
    ),
    "vstack_develop_expert": Candidate(
        "vstack_develop_expert",
        ROOT / "candidate-ps1-eval" / "VStackDevelop",
        "vnext.cli",
        "expert",
        "VExpert with the new bill tenors and EM currencies enabled",
    ),
    "vstack_develop_optimized": Candidate(
        "vstack_develop_optimized",
        ROOT / "candidate-ps1-eval" / "VStackDevelop",
        "vnext.cli",
        "optimized",
        "VStack optimized router with the new bill tenors and EM currencies enabled",
    ),
    "vstack_reference": Candidate(
        "vstack_reference",
        ROOT / "candidate-ps1-eval" / "VStackDevelop",
        "vnext.cli",
        "reference",
        "Cutoff-local 300-observation joint Gaussian random walk",
    ),
    "vstack_short_safe": Candidate(
        "vstack_short_safe",
        ROOT / "candidate-ps1-eval" / "VStackDevelop",
        "vnext.cli",
        "short_safe",
        "Conservative short-horizon router: established rates F1/F2, Gaussian otherwise",
    ),
    "vstack_short_v2": Candidate(
        "vstack_short_v2",
        ROOT / "candidate-ps1-eval" / "VStackDevelop",
        "vnext.cli",
        "short_v2",
        "Short-safe router plus contiguous joint paths for cross-asset FX cards",
    ),
    "vstack_short_v2_adaptive": Candidate(
        "vstack_short_v2_adaptive",
        ROOT / "candidate-ps1-eval" / "VStackDevelop",
        "vnext.cli",
        "short_v2_adaptive",
        "Short V2 plus full cutoff-local fast/slow volatility adaptation restricted to F3",
    ),
    "vstack_short_v2_adaptive_global25": Candidate(
        "vstack_short_v2_adaptive_global25",
        ROOT / "candidate-ps1-eval" / "VStackDevelop",
        "vnext.cli",
        "short_v2_adaptive_global25",
        "Diagnostic: Short V2 global volatility adaptation with 25% regime response",
    ),
    "vstack_short_v2_adaptive_global50": Candidate(
        "vstack_short_v2_adaptive_global50",
        ROOT / "candidate-ps1-eval" / "VStackDevelop",
        "vnext.cli",
        "short_v2_adaptive_global50",
        "Diagnostic: Short V2 global volatility adaptation with 50% regime response",
    ),
    "vstack_short_v2_adaptive_global75": Candidate(
        "vstack_short_v2_adaptive_global75",
        ROOT / "candidate-ps1-eval" / "VStackDevelop",
        "vnext.cli",
        "short_v2_adaptive_global75",
        "Diagnostic: Short V2 global volatility adaptation with 75% regime response",
    ),
    "vstack_short_v2_adaptive_global100": Candidate(
        "vstack_short_v2_adaptive_global100",
        ROOT / "candidate-ps1-eval" / "VStackDevelop",
        "vnext.cli",
        "short_v2_adaptive_global100",
        "Diagnostic: Short V2 global volatility adaptation with full regime response",
    ),
    "vstack_short_v2_adaptive_f3_50": Candidate(
        "vstack_short_v2_adaptive_f3_50",
        ROOT / "candidate-ps1-eval" / "VStackDevelop",
        "vnext.cli",
        "short_v2_adaptive_f3_50",
        "Short V2 with 50% volatility-regime response restricted to F3",
    ),
    "vstack_short_v2_adaptive_f3_75": Candidate(
        "vstack_short_v2_adaptive_f3_75",
        ROOT / "candidate-ps1-eval" / "VStackDevelop",
        "vnext.cli",
        "short_v2_adaptive_f3_75",
        "Short V2 with 75% volatility-regime response restricted to F3",
    ),
    "vstack_v11_safe": Candidate(
        "vstack_v11_safe",
        ROOT / "candidate-ps1-eval" / "VStackDevelop",
        "vnext.cli",
        "v11_safe",
        "Fixed empirical V11-like absolute-change sampler",
    ),
    "vstack_fhs60": Candidate(
        "vstack_fhs60",
        ROOT / "candidate-ps1-eval" / "VStackDevelop",
        "vnext.cli",
        "fhs60",
        "Filtered historical simulation with 60-day volatility half-life",
    ),
    "vstack_direct": Candidate(
        "vstack_direct",
        ROOT / "candidate-ps1-eval" / "VStackDevelop",
        "vnext.cli",
        "direct",
        "Volatility-scaled contiguous historical paths",
    ),
    "vstack_block5": Candidate(
        "vstack_block5",
        ROOT / "candidate-ps1-eval" / "VStackDevelop",
        "vnext.cli",
        "block5",
        "Five-step stationary block bootstrap",
    ),
    "vstack_daily_calibrated": Candidate(
        "vstack_daily_calibrated",
        ROOT / "candidate-ps1-eval" / "VStackDevelop",
        "vnext.cli",
        "daily_calibrated",
        "Past-fold daily scale and drift calibration",
    ),
    "vstack_term": Candidate(
        "vstack_term",
        ROOT / "candidate-ps1-eval" / "VStackDevelop",
        "vnext.cli",
        "term",
        "Daily variance term-structure refinement",
    ),
}


def run_model(
    python: pathlib.Path,
    candidate: Candidate,
    unit_dir: pathlib.Path,
    card: dict[str, Any],
    seed: int,
    out_dir: pathlib.Path,
    force: bool,
) -> tuple[str, float]:
    forecast = out_dir / "forecast.parquet"
    if forecast.is_file() and not force:
        return "cached", 0.0
    out_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    for key in (
        "MODEL_ENDPOINT",
        "MODEL_NAME",
        "MODEL_MAX_TOKENS",
        "MODEL_TOKEN",
        "MODEL_API_KEY",
        "V11_MOCK_HOUSE_JSON",
        "V8_MOCK_HOUSE_JSON",
    ):
        env.pop(key, None)
    env["QFBENCH_SEED"] = str(seed)
    prior_path = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(candidate.model_root) + (os.pathsep + prior_path if prior_path else "")
    command = [
        str(python),
        "-m",
        candidate.module,
        "--panels",
        str(unit_dir),
        "--text",
        str(unit_dir / "text"),
        "--asof",
        str(card["provenance"]["data_cutoff"]),
        "--out",
        str(forecast),
    ]
    if candidate.mode is not None:
        command.extend(["--mode", candidate.mode])
    started = time.monotonic()
    completed = subprocess.run(
        command,
        cwd=candidate.model_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    elapsed = time.monotonic() - started
    if completed.returncode != 0:
        raise RuntimeError(
            f"{candidate.name} failed for {card['task']['id']} seed={seed}:\n"
            f"{completed.stdout}\n{completed.stderr}"
        )
    return completed.stdout.strip(), elapsed


def numeric_engine(meta: dict[str, Any], candidate: Candidate) -> str:
    if candidate.name == "v11":
        return "v11_e2_v8"
    numeric = meta.get("vnext", {}).get("numeric", {})
    engine = numeric.get("engine")
    if engine:
        return str(engine)
    return candidate.mode or candidate.name


def build_references(python: pathlib.Path):
    integrity = BASE.verify_answer_hashes()
    exemplar = BASE.validate_exemplar_scale()
    if not integrity["ok"]:
        raise RuntimeError(f"answer integrity failed: {integrity}")
    if not exemplar["ok"]:
        raise RuntimeError(f"M0 scale check failed: {exemplar}")
    references: dict[str, dict[str, Any]] = {}
    unit_dirs = sorted(path.parent for path in UNIT_ROOT.glob("*-ps1/card.toml"))
    if len(unit_dirs) != 22:
        raise RuntimeError(f"expected 22 practice cards, found {len(unit_dirs)}")
    for unit_dir in unit_dirs:
        card_path = unit_dir / "card.toml"
        card = BASE.load_card(card_path)
        unit_id = str(card["task"]["id"])
        answer_path = ANSWER_ROOT / f"{unit_id}.parquet"
        answer = pd.read_parquet(answer_path)
        dist = BASE.build_m0(unit_dir, card, answer)
        m0_dir = ROOT / "vstack-ps1-eval" / "m0_outputs" / unit_id
        if not (m0_dir / "forecast.parquet").is_file():
            BASE.write_m0_output(m0_dir, card, dist)
        m0_score = BASE.official_score(python, card_path, m0_dir / "forecast.parquet", answer_path)
        if not m0_score["admissible"]:
            raise RuntimeError(f"M0 is inadmissible for {unit_id}")
        references[unit_id] = {
            "unit_dir": unit_dir,
            "card_path": card_path,
            "card": card,
            "answer_path": answer_path,
            "dist": dist,
            "m0_score": m0_score,
            "m0_norm": BASE.normalized(m0_score, dist.scales, len(dist.cells)),
        }
    return unit_dirs, references, integrity, exemplar


def evaluate_one(
    python: pathlib.Path,
    candidate: Candidate,
    seed: int,
    ref: dict[str, Any],
    force: bool,
) -> dict[str, Any]:
    card = ref["card"]
    unit_id = str(card["task"]["id"])
    out_dir = OUTPUT_ROOT / candidate.name / f"seed-{seed}" / unit_id
    message, elapsed = run_model(python, candidate, ref["unit_dir"], card, seed, out_dir, force)
    score = BASE.official_score(python, ref["card_path"], out_dir / "forecast.parquet", ref["answer_path"])
    norm = BASE.normalized(score, ref["dist"].scales, int(score["cell_count"]))
    meta = json.loads((out_dir / "forecast_meta.json").read_text(encoding="utf-8"))
    m0_norm = ref["m0_norm"]
    delta = float(norm["composite"] - m0_norm["composite"])
    return {
        "candidate": candidate.name,
        "description": candidate.description,
        "unit_id": unit_id,
        "seed": int(seed),
        "asof": str(card["provenance"]["data_cutoff"]),
        "family": str(card["metadata"]["category"]),
        "group": BASE.card_group(card),
        "panel": str(card["metadata"].get("asset_panel", "")),
        "assets": "|".join(str(x) for x in card["targets"]["asset_ids"]),
        "horizons": "|".join(str(x) for x in card["targets"]["horizons"]),
        "cell_count": int(score["cell_count"]),
        "admissible": bool(score["admissible"]),
        "marginal_normalized": float(norm["marginal"]),
        "joint_normalized": float(norm["joint"]),
        "tail_normalized": float(norm["tail"]),
        "normalized_score": float(norm["composite"]),
        "m0_normalized": float(m0_norm["composite"]),
        "delta_vs_m0": delta,
        "relative_improvement_pct": float(-100.0 * delta / m0_norm["composite"]),
        "beats_m0": bool(norm["composite"] < m0_norm["composite"]),
        "engine": numeric_engine(meta, candidate),
        "reasoning_applied": bool(meta.get("reasoning_applied", False)),
        "n_draws": int(score["n_draws"]),
        "runtime_seconds": float(elapsed),
        "run_message": message,
    }


def make_summaries(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    overall = (
        frame.groupby(["candidate", "description"], sort=False)
        .agg(
            observations=("unit_id", "size"),
            cards=("unit_id", "nunique"),
            seeds=("seed", "nunique"),
            score=("normalized_score", "mean"),
            m0_score=("m0_normalized", "mean"),
            delta_vs_m0=("delta_vs_m0", "mean"),
            win_rate=("beats_m0", "mean"),
            admissible_rate=("admissible", "mean"),
            runtime_seconds=("runtime_seconds", "sum"),
        )
        .reset_index()
    )
    overall["improvement_vs_m0_pct"] = -100.0 * overall["delta_vs_m0"] / overall["m0_score"]
    overall = overall.sort_values(["score", "candidate"]).reset_index(drop=True)
    overall.insert(0, "rank", np.arange(1, len(overall) + 1))
    by_group = (
        frame.groupby(["candidate", "group"], sort=False)
        .agg(
            observations=("unit_id", "size"),
            cards=("unit_id", "nunique"),
            score=("normalized_score", "mean"),
            m0_score=("m0_normalized", "mean"),
            delta_vs_m0=("delta_vs_m0", "mean"),
            win_rate=("beats_m0", "mean"),
        )
        .reset_index()
    )
    by_group["improvement_vs_m0_pct"] = -100.0 * by_group["delta_vs_m0"] / by_group["m0_score"]
    by_family = (
        frame.groupby(["candidate", "family"], sort=False)
        .agg(
            observations=("unit_id", "size"),
            cards=("unit_id", "nunique"),
            score=("normalized_score", "mean"),
            m0_score=("m0_normalized", "mean"),
            delta_vs_m0=("delta_vs_m0", "mean"),
            win_rate=("beats_m0", "mean"),
        )
        .reset_index()
    )
    by_family["improvement_vs_m0_pct"] = -100.0 * by_family["delta_vs_m0"] / by_family["m0_score"]
    return overall, by_group, by_family


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--python",
        type=pathlib.Path,
        default=ROOT / ".venv-vstack313" / "Scripts" / "python.exe",
    )
    parser.add_argument("--candidates", nargs="+", choices=sorted(CANDIDATES), default=list(CANDIDATES))
    parser.add_argument("--seeds", type=int, nargs="+", default=[42])
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    python = args.python.resolve()
    if not python.is_file():
        raise SystemExit(f"Python executable not found: {python}")
    selected = [CANDIDATES[name] for name in args.candidates]
    for candidate in selected:
        if not candidate.model_root.is_dir():
            raise RuntimeError(f"candidate root not found: {candidate.model_root}")

    EVAL_ROOT.mkdir(parents=True, exist_ok=True)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    unit_dirs, refs, integrity, exemplar = build_references(python)
    tasks = [
        (candidate, seed, refs[str(BASE.load_card(unit_dir / "card.toml")["task"]["id"])])
        for candidate in selected
        for seed in args.seeds
        for unit_dir in unit_dirs
    ]
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    total = len(tasks)
    completed_count = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        future_map = {
            pool.submit(evaluate_one, python, candidate, seed, ref, args.force):
            (candidate.name, seed, str(ref["card"]["task"]["id"]))
            for candidate, seed, ref in tasks
        }
        for future in concurrent.futures.as_completed(future_map):
            candidate_name, seed, unit_id = future_map[future]
            completed_count += 1
            try:
                row = future.result()
                rows.append(row)
                print(
                    f"[{completed_count:03d}/{total}] {candidate_name} seed={seed} {unit_id}: "
                    f"score={row['normalized_score']:.4f} delta={row['delta_vs_m0']:+.4f} "
                    f"engine={row['engine']}",
                    flush=True,
                )
            except Exception as exc:  # keep the screen running so one candidate cannot hide the others
                errors.append(
                    {"candidate": candidate_name, "seed": str(seed), "unit_id": unit_id, "error": str(exc)}
                )
                print(f"[ERROR {completed_count:03d}/{total}] {candidate_name} {unit_id}: {exc}", flush=True)

    if not rows:
        raise RuntimeError(f"all candidate runs failed: {errors}")
    frame = pd.DataFrame(rows).sort_values(["candidate", "seed", "group", "unit_id"]).reset_index(drop=True)
    frame.to_csv(EVAL_ROOT / "candidate_results.csv", index=False)
    overall, by_group, by_family = make_summaries(frame)
    overall.to_csv(EVAL_ROOT / "candidate_summary.csv", index=False)
    by_group.to_csv(EVAL_ROOT / "candidate_group_summary.csv", index=False)
    by_family.to_csv(EVAL_ROOT / "candidate_family_summary.csv", index=False)
    payload = {
        "method": {
            "cards": len(unit_dirs),
            "seeds": list(args.seeds),
            "candidate_names": [c.name for c in selected],
            "score_direction": "lower_is_better",
            "house_api": "disabled; numerical fallback only",
            "answer_integrity": integrity,
            "m0_exemplar_check": exemplar,
        },
        "overall": overall.to_dict(orient="records"),
        "by_group": by_group.to_dict(orient="records"),
        "by_family": by_family.to_dict(orient="records"),
        "errors": errors,
    }
    (EVAL_ROOT / "candidate_summary.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print("\n=== OVERALL (lower is better) ===", flush=True)
    print(overall.to_string(index=False), flush=True)
    if errors:
        print(f"\nCompleted with {len(errors)} errors; see candidate_summary.json", flush=True)
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
