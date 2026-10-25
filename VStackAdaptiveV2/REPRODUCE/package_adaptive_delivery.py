"""Package the two validated Short V2 candidates as research, not submission."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile


ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
NAME = "VStack_Short_and_Adaptive_V2_Research_2026-10-21"
DELIVERY = HERE / "delivery" / NAME
ZIP_PATH = HERE / f"{NAME}.zip"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest().upper()


def copy(source: Path, relative: str) -> None:
    destination = DELIVERY / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def main() -> int:
    if DELIVERY.exists() or ZIP_PATH.exists():
        raise FileExistsError("delivery already exists; preserve it and choose a new name")
    DELIVERY.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        HERE / "VStackDevelop",
        DELIVERY / "MODEL",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"),
    )

    for name in (
        "ADAPTIVE_V2_RESULTS_KR.md",
        "RESULTS_KR.md",
        "FINAL_TWO_CANDIDATES.csv",
        "VSTACK_SHORT_V2_ANALYSIS.ipynb",
        "VSTACK_SHORT_V2_ANALYSIS.html",
        "score_improvement_vs_m0.png",
    ):
        copy(HERE / name, f"REPORTS/{name}")

    result_names = (
        "candidate_results.csv",
        "candidate_summary.csv",
        "candidate_group_summary.csv",
        "candidate_family_summary.csv",
        "candidate_summary.json",
        "adaptive_comparison_overall.csv",
        "adaptive_comparison_seed.csv",
        "adaptive_comparison_group.csv",
        "adaptive_comparison_family.csv",
        "adaptive_comparison_period.csv",
        "adaptive_comparison_card.csv",
        "adaptive_validation.json",
        "adaptive_rolling_backtest_overall.csv",
        "adaptive_rolling_backtest_period.csv",
        "adaptive_rolling_backtest_dataset.csv",
        "adaptive_rolling_backtest_rows.csv",
        "adaptive_rolling_backtest.json",
        "adaptive_rolling_validation.csv",
        "adaptive_rolling_validation.json",
        "panel_unit_inventory.csv",
    )
    for name in result_names:
        copy(HERE / name, f"RESULTS/{name}")

    for folder in ("docker-verification-short-v2-final", "docker-verification-adaptive"):
        for name in ("docker_verification.csv", "docker_verification.json"):
            copy(HERE / folder / name, f"DOCKER_VERIFICATION/{folder}/{name}")

    for name in (
        "run_candidate_screen.py",
        "analyze_adaptive.py",
        "backtest_volatility_adaptation.py",
        "analyze_rolling_backtest.py",
        "inspect_panel_units.py",
        "docker_verify_v2.py",
        "verify_forecast_pair.py",
        "package_adaptive_delivery.py",
    ):
        copy(HERE / name, f"REPRODUCE/{name}")

    git_result = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={(ROOT / 'official-track2').as_posix()}",
            "-C",
            str(ROOT / "official-track2"),
            "rev-parse",
            "HEAD",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    short_verify = json.loads(
        (HERE / "docker-verification-short-v2-final" / "docker_verification.json").read_text(
            encoding="utf-8"
        )
    )
    adaptive_verify = json.loads(
        (HERE / "docker-verification-adaptive" / "docker_verification.json").read_text(
            encoding="utf-8"
        )
    )
    files = sorted(path for path in DELIVERY.rglob("*") if path.is_file())
    manifest = {
        "bundle": NAME,
        "purpose": "research and reproducibility; not a Codabench submission archive",
        "created_date": "2026-10-21",
        "official_repo_commit": git_result.stdout.strip() if git_result.returncode == 0 else "unknown",
        "practice_cards": 22,
        "evaluation_seeds": [0, 1, 42, 2026, 314159],
        "models": {
            "short_v2": short_verify,
            "volatility_adaptive_v2": adaptive_verify,
        },
        "team_key_included": False,
        "submission_descriptor_included": False,
        "files": [
            {
                "path": path.relative_to(DELIVERY).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": digest(path),
            }
            for path in files
        ],
    }
    (DELIVERY / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(item for item in DELIVERY.rglob("*") if item.is_file()):
            archive.write(path, arcname=f"{NAME}/{path.relative_to(DELIVERY).as_posix()}")

    receipt = {
        "bundle_directory": str(DELIVERY),
        "zip_path": str(ZIP_PATH),
        "zip_bytes": ZIP_PATH.stat().st_size,
        "zip_sha256": digest(ZIP_PATH),
        "files": len([path for path in DELIVERY.rglob("*") if path.is_file()]),
    }
    (HERE / "ADAPTIVE_DELIVERY_RECEIPT.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
