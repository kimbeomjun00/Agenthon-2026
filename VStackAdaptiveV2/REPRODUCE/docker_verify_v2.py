"""Verify a built VStack Short V2 image on all 22 official practice cards."""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time
import tomllib
from typing import Any

import pandas as pd


ROOT = pathlib.Path(__file__).resolve().parents[1]
HERE = pathlib.Path(__file__).resolve().parent
OFFICIAL_ROOT = ROOT / "official-track2"
UNIT_ROOT = OFFICIAL_ROOT / "units"
ANSWER_ROOT = OFFICIAL_ROOT / "practice-answers"
DIRECT_ROOT = HERE / "outputs" / "vstack_short_v2" / "seed-42"
VERIFY_ROOT = HERE / "docker-verification"
INPUT_ROOT = VERIFY_ROOT / "inputs"
OUTPUT_ROOT = VERIFY_ROOT / "outputs"
DOCKER = pathlib.Path(r"C:\Program Files\Docker\Docker\resources\bin\docker.exe")
IMAGE = "agenthon-vstack-short-v2:research"
MODE: str | None = None
SEED = 42


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def load_card(path: pathlib.Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def stage_unit(unit_dir: pathlib.Path) -> pathlib.Path:
    destination = INPUT_ROOT / unit_dir.name
    panels = destination / "panels"
    panels.mkdir(parents=True, exist_ok=True)
    for source in unit_dir.iterdir():
        if source.is_file() and source.suffix != ".parquet":
            shutil.copy2(source, destination / source.name)
    shutil.copytree(unit_dir / "text", destination / "text", dirs_exist_ok=True)
    for source in unit_dir.glob("*.parquet"):
        shutil.copy2(source, panels / source.name)
    return destination


def container_path(path: pathlib.Path) -> str:
    return "/repo/" + path.resolve().relative_to(ROOT.resolve()).as_posix()


def verify_pair(
    card_path: pathlib.Path,
    forecast_path: pathlib.Path,
    direct_path: pathlib.Path,
    answer_path: pathlib.Path,
) -> dict[str, Any]:
    completed = subprocess.run(
        [
            str(DOCKER),
            "run",
            "--rm",
            "--user",
            "0:0",
            "--mount",
            f"type=bind,source={ROOT},target=/repo,readonly",
            "-w",
            "/repo",
            IMAGE,
            "python",
            "/repo/candidate-ps1-eval/verify_forecast_pair.py",
            "--card",
            container_path(card_path),
            "--forecast",
            container_path(forecast_path),
            "--direct",
            container_path(direct_path),
            "--answer",
            container_path(answer_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(f"container verification failed:\n{completed.stdout}\n{completed.stderr}")
    return json.loads(completed.stdout)


def run_one(unit_dir: pathlib.Path, staged: pathlib.Path) -> dict[str, Any]:
    card = load_card(unit_dir / "card.toml")
    unit_id = unit_dir.name
    out_dir = OUTPUT_ROOT / unit_id
    out_dir.mkdir(parents=True, exist_ok=True)
    command = [
        str(DOCKER),
        "run",
        "--rm",
        "--network",
        "none",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,size=536870912",
        "--cpus",
        "4",
        "--memory",
        "4g",
        "--mount",
        f"type=bind,source={staged},target=/input,readonly",
        "--mount",
        f"type=bind,source={out_dir},target=/output",
        "-e",
        f"QFBENCH_SEED={SEED}",
        IMAGE,
        "forecast",
        "--panels",
        "/input/panels",
        "--text",
        "/input/text",
        "--asof",
        str(card["provenance"]["data_cutoff"]),
        "--out",
        "/output/forecast.parquet",
    ]
    if MODE is not None:
        command.extend(["--mode", MODE])
    env = os.environ.copy()
    env["PATH"] = f"{DOCKER.parent}{os.pathsep}{env.get('PATH', '')}"
    started = time.monotonic()
    completed = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"Docker failed:\n{completed.stdout}\n{completed.stderr}")
    docker_forecast = out_dir / "forecast.parquet"
    direct_forecast = DIRECT_ROOT / unit_id / "forecast.parquet"
    answer = ANSWER_ROOT / f"{unit_id}.parquet"
    comparison = verify_pair(unit_dir / "card.toml", docker_forecast, direct_forecast, answer)
    docker_score = comparison["docker_score"]
    direct_score = comparison["direct_score"]
    score_fields = ("marginal_crps", "joint_variogram", "tail_penalty", "composite_score")
    maximum_score_difference = max(
        abs(float(docker_score[field]) - float(direct_score[field])) for field in score_fields
    )
    meta = json.loads((out_dir / "forecast_meta.json").read_text(encoding="utf-8"))
    return {
        "unit_id": unit_id,
        "family": str(card["metadata"]["category"]),
        "panel": str(card["metadata"].get("asset_panel", "")),
        "engine": str(meta["vnext"]["numeric"]["engine"]),
        "route": str(meta["vnext"]["numeric"].get("short_horizon_route", "")),
        "n_draws": int(docker_score["n_draws"]),
        "admissible": bool(docker_score["admissible"]),
        "gates_all_pass": all(value == "pass" for value in docker_score["gates"].values()),
        "docker_sha256": sha256(docker_forecast),
        "direct_sha256": sha256(direct_forecast),
        "byte_identical": sha256(docker_forecast) == sha256(direct_forecast),
        "max_value_abs_difference": float(comparison["max_value_abs_difference"]),
        "max_official_score_abs_difference": maximum_score_difference,
        "reasoning_applied": bool(meta.get("reasoning_applied", False)),
        "runtime_seconds": time.monotonic() - started,
    }


def image_identity() -> dict[str, Any]:
    completed = subprocess.run(
        [str(DOCKER), "image", "inspect", IMAGE], capture_output=True, text=True, check=True
    )
    data = json.loads(completed.stdout)[0]
    return {
        "id": data.get("Id"),
        "repo_digests": data.get("RepoDigests", []),
        "architecture": data.get("Architecture"),
        "os": data.get("Os"),
        "size": data.get("Size"),
    }


def main() -> int:
    global IMAGE, MODE, DIRECT_ROOT, VERIFY_ROOT, INPUT_ROOT, OUTPUT_ROOT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default=IMAGE)
    parser.add_argument("--mode")
    parser.add_argument("--direct-candidate", default="vstack_short_v2")
    parser.add_argument("--verify-name", default="docker-verification")
    args = parser.parse_args()
    IMAGE = args.image
    MODE = args.mode
    DIRECT_ROOT = HERE / "outputs" / args.direct_candidate / f"seed-{SEED}"
    VERIFY_ROOT = HERE / args.verify_name
    INPUT_ROOT = VERIFY_ROOT / "inputs"
    OUTPUT_ROOT = VERIFY_ROOT / "outputs"
    if not DIRECT_ROOT.is_dir():
        raise RuntimeError(f"direct forecast root not found: {DIRECT_ROOT}")
    VERIFY_ROOT.mkdir(parents=True, exist_ok=True)
    units = sorted(path.parent for path in UNIT_ROOT.glob("*-ps1/card.toml"))
    if len(units) != 22:
        raise AssertionError(f"expected 22 cards, found {len(units)}")
    staged = {unit.name: stage_unit(unit) for unit in units}
    results: list[dict[str, Any]] = []
    failures: list[str] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        future_map = {pool.submit(run_one, unit, staged[unit.name]): unit.name for unit in units}
        for count, future in enumerate(concurrent.futures.as_completed(future_map), start=1):
            unit_id = future_map[future]
            try:
                row = future.result()
                results.append(row)
                passed = (
                    row["admissible"]
                    and row["gates_all_pass"]
                    and row["max_official_score_abs_difference"] <= 1e-12
                    and row["max_value_abs_difference"] <= 1e-12
                )
                print(f"[{count:02d}/22] {'PASS' if passed else 'MISMATCH'} {unit_id}", flush=True)
            except Exception as exc:
                failures.append(f"{unit_id}: {exc}")
                print(f"[{count:02d}/22] ERROR {unit_id}: {exc}", flush=True)
    frame = pd.DataFrame(results).sort_values("unit_id").reset_index(drop=True)
    frame.to_csv(VERIFY_ROOT / "docker_verification.csv", index=False)
    summary = {
        "image": IMAGE,
        "mode_override": MODE,
        "direct_candidate": args.direct_candidate,
        "image_identity": image_identity(),
        "seed": SEED,
        "cards_expected": 22,
        "cards_completed": int(len(frame)),
        "failures": failures,
        "all_admissible": bool(len(frame) == 22 and frame["admissible"].all()),
        "all_official_gates_passed": bool(len(frame) == 22 and frame["gates_all_pass"].all()),
        "byte_identical_cards": int(frame["byte_identical"].sum()) if len(frame) else 0,
        "max_value_abs_difference": float(frame["max_value_abs_difference"].max()) if len(frame) else None,
        "max_official_score_abs_difference": (
            float(frame["max_official_score_abs_difference"].max()) if len(frame) else None
        ),
        "all_reasoning_offline": bool((~frame["reasoning_applied"]).all()) if len(frame) else False,
    }
    (VERIFY_ROOT / "docker_verification.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False), flush=True)
    ok = (
        not failures
        and summary["all_admissible"]
        and summary["all_official_gates_passed"]
        and summary["max_value_abs_difference"] <= 1e-12
        and summary["max_official_score_abs_difference"] <= 1e-12
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
