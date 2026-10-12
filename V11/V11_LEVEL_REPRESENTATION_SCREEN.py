from __future__ import annotations

import argparse
import json
import math
import tomllib
import zlib
from pathlib import Path

import numpy as np
import pandas as pd

from v11_new.production_cli import (
    _EWMA_HALF_LIFE,
    _EWMA_WEIGHT,
    _common_level_frame,
    _ewma_variance,
    _monthly_inputs,
    _read_panels,
)
from qfbench2_track_forecasting.horizons import HorizonMetadataError


def _safe_sd(x: np.ndarray) -> np.ndarray:
    sd = np.std(x, axis=0, ddof=1)
    return np.where(np.isfinite(sd) & (sd > 1e-12), sd, 1e-12)


def _e2_components(train: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    full_mu = np.mean(train, axis=0)
    full_sd = _safe_sd(train)
    zpool = (train - full_mu[None, :]) / full_sd[None, :]

    ewma_var = _ewma_variance(train, _EWMA_HALF_LIFE)
    current_sd = np.sqrt(
        _EWMA_WEIGHT * ewma_var
        + (1.0 - _EWMA_WEIGHT) * (full_sd ** 2)
    )
    return zpool, current_sd


def _draw_abs(
    levels_train: pd.DataFrame,
    horizons: list[int],
    idx: np.ndarray,
) -> np.ndarray:
    """Current V11 level representation: absolute daily changes ΔP."""
    train = levels_train.diff().dropna().to_numpy(dtype=float)
    zpool, current_sd = _e2_components(train)

    daily = zpool[idx] * current_sd[None, None, :]
    cumulative = np.cumsum(daily, axis=1)
    anchor = levels_train.iloc[-1].to_numpy(dtype=float)

    return np.stack(
        [anchor[None, :] + cumulative[:, h - 1, :] for h in horizons],
        axis=1,
    )


def _draw_rel(
    levels_train: pd.DataFrame,
    horizons: list[int],
    idx: np.ndarray,
) -> np.ndarray:
    """
    Alternative representation: daily log-level changes.

    Everything else stays E2-identical:
      full-history standardization,
      EWMA60 90/10 current variance,
      iid historical joint rows,
      same random historical-row indices,
      nested horizons,
      zero numeric drift for level targets.
    """
    x = levels_train.to_numpy(dtype=float)

    if not np.isfinite(x).all() or np.any(x <= 0):
        raise ValueError("REL requires strictly positive historical levels")

    log_levels = np.log(x)
    train = np.diff(log_levels, axis=0)
    zpool, current_sd = _e2_components(train)

    daily_log = zpool[idx] * current_sd[None, None, :]
    cumulative_log = np.cumsum(daily_log, axis=1)

    # Protect the screen from pathological near-zero historical levels.
    cumulative_log = np.clip(cumulative_log, -20.0, 20.0)

    anchor = x[-1]

    return np.stack(
        [anchor[None, :] * np.exp(cumulative_log[:, h - 1, :]) for h in horizons],
        axis=1,
    )


def _crps_1d(draws: np.ndarray, y: float) -> float:
    x = np.sort(np.asarray(draws, dtype=float))
    n = len(x)
    if n == 0:
        return math.nan

    first = float(np.mean(np.abs(x - y)))
    coeff = 2.0 * np.arange(1, n + 1, dtype=float) - n - 1.0
    half_pair = float(np.sum(coeff * x) / (n * n))
    return first - half_pair


def _interval_score_90(draws: np.ndarray, y: float) -> float:
    alpha = 0.10
    lo, hi = np.quantile(draws, [alpha / 2.0, 1.0 - alpha / 2.0])
    score = float(hi - lo)
    if y < lo:
        score += (2.0 / alpha) * float(lo - y)
    elif y > hi:
        score += (2.0 / alpha) * float(y - hi)
    return score


def _variogram_score(
    draws: np.ndarray,
    truth: np.ndarray,
    baseline_scale: np.ndarray,
    p: float = 0.5,
) -> float:
    """
    Dimensionless variogram proxy.

    draws: [draw, horizon, asset]
    truth: [horizon, asset]

    Uses the ABS forecast's cellwise SD as a common scale for BOTH models, so
    the representation comparison is not contaminated by different units.
    """
    n = draws.shape[0]
    flat = draws.reshape(n, -1)
    y = truth.reshape(-1)
    s = baseline_scale.reshape(-1)

    good = np.isfinite(s) & (s > 1e-12)
    if good.sum() < 2:
        return 0.0

    flat = flat[:, good] / s[good][None, :]
    y = y[good] / s[good]

    m = flat.shape[1]
    total = 0.0
    count = 0

    for i in range(m):
        for j in range(i + 1, m):
            obs = abs(float(y[i] - y[j])) ** p
            pred = float(np.mean(np.abs(flat[:, i] - flat[:, j]) ** p))
            total += (obs - pred) ** 2
            count += 1

    return total / max(count, 1)


def _fold_metrics(
    abs_draws: np.ndarray,
    rel_draws: np.ndarray,
    truth: np.ndarray,
) -> dict[str, float]:
    # Use ABS forecast scale as a common unit normalization.
    scale = np.std(abs_draws, axis=0, ddof=1)
    scale = np.where(np.isfinite(scale) & (scale > 1e-12), scale, 1e-12)

    abs_crps = []
    rel_crps = []
    abs_tail = []
    rel_tail = []

    for hi in range(truth.shape[0]):
        for ai in range(truth.shape[1]):
            y = float(truth[hi, ai])
            s = float(scale[hi, ai])

            abs_crps.append(_crps_1d(abs_draws[:, hi, ai], y) / s)
            rel_crps.append(_crps_1d(rel_draws[:, hi, ai], y) / s)

            abs_tail.append(_interval_score_90(abs_draws[:, hi, ai], y) / s)
            rel_tail.append(_interval_score_90(rel_draws[:, hi, ai], y) / s)

    abs_crps_loss = float(np.mean(abs_crps))
    rel_crps_loss = float(np.mean(rel_crps))
    abs_tail_loss = float(np.mean(abs_tail))
    rel_tail_loss = float(np.mean(rel_tail))

    abs_vario = _variogram_score(abs_draws, truth, scale)
    rel_vario = _variogram_score(rel_draws, truth, scale)

    eps = 1e-12
    crps_ratio = rel_crps_loss / max(abs_crps_loss, eps)
    tail_ratio = rel_tail_loss / max(abs_tail_loss, eps)

    # If the unit has only one scored cell, variogram has no pair and is neutral.
    if truth.size < 2 or abs_vario <= eps:
        vario_ratio = 1.0
    else:
        vario_ratio = rel_vario / max(abs_vario, eps)

    proxy = (
        0.50 * crps_ratio
        + 0.30 * vario_ratio
        + 0.20 * tail_ratio
    )

    return {
        "crps_ratio": crps_ratio,
        "variogram_ratio": vario_ratio,
        "tail90_ratio": tail_ratio,
        "proxy_composite_ratio": proxy,
    }


def _choose_cut_indices(
    n_levels: int,
    max_h: int,
    min_train_steps: int,
    n_folds: int,
) -> list[int]:
    # cut_idx is the last observed level row in a pseudo-OOS training sample.
    first = min_train_steps
    last = n_levels - max_h - 1

    if last < first:
        return []

    if n_folds <= 1:
        return [last]

    raw = np.linspace(first, last, n_folds)
    cuts = sorted(set(int(round(x)) for x in raw))

    return [c for c in cuts if c >= first and c <= last]


def _family(card: dict) -> str:
    return str(card.get("metadata", {}).get("category", "UNKNOWN"))


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Pseudo-OOS representation screen for V11 level targets: "
            "ABS daily changes (current) vs REL daily log-level changes."
        )
    )
    ap.add_argument("--units", default="units")
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--draws", type=int, default=500)
    ap.add_argument("--min-train", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="v11_level_representation_screen.csv")
    args = ap.parse_args()

    root = Path.cwd()
    units_root = root / args.units

    if not units_root.is_dir():
        raise SystemExit(f"units directory not found: {units_root}")
    if not (root / "v11_new" / "production_cli.py").is_file():
        raise SystemExit(
            "Run from repo root after unpacking V11; "
            "v11_new/production_cli.py not found."
        )

    rows: list[dict] = []
    skipped: list[dict] = []

    for unit in sorted(units_root.iterdir()):
        card_path = unit / "card.toml"
        if not unit.is_dir() or not card_path.is_file():
            continue

        with card_path.open("rb") as f:
            card = tomllib.load(f)

        unit_id = str(card.get("task", {}).get("id", unit.name))
        if unit_id.startswith("t2-EXAMPLE"):
            continue

        tgt = card.get("targets", {})
        target_type = str(tgt.get("target_type", "level"))

        # This screen asks only how LEVEL targets should be represented.
        if target_type != "level":
            skipped.append(
                {"unit_id": unit_id, "reason": f"target_type={target_type}"}
            )
            continue

        assets = [str(x) for x in tgt.get("asset_ids", [])]
        horizons = [int(x) for x in tgt.get("horizons", [])]
        if not assets or not horizons:
            skipped.append({"unit_id": unit_id, "reason": "missing assets/horizons"})
            continue

        asof = str(card.get("provenance", {}).get("data_cutoff", ""))

        try:
            panels = _read_panels(unit)
        except Exception as exc:
            skipped.append(
                {"unit_id": unit_id, "reason": f"read_panels: {type(exc).__name__}"}
            )
            continue

        # Monthly authored horizons are not part of the daily representation question.
        try:
            panel_steps = _monthly_inputs(panels, card, card_path, asof)
        except HorizonMetadataError:
            panel_steps = None

        if panel_steps is not None:
            skipped.append({"unit_id": unit_id, "reason": "explicit monthly card"})
            continue

        try:
            full_levels = _common_level_frame(panels, assets, asof)
        except Exception as exc:
            skipped.append(
                {"unit_id": unit_id, "reason": f"common levels: {type(exc).__name__}"}
            )
            continue

        max_h = max(horizons)
        cuts = _choose_cut_indices(
            len(full_levels),
            max_h,
            args.min_train,
            args.folds,
        )

        if not cuts:
            skipped.append(
                {
                    "unit_id": unit_id,
                    "reason": (
                        f"insufficient history n={len(full_levels)} "
                        f"for min_train={args.min_train}, max_h={max_h}"
                    ),
                }
            )
            continue

        unit_fold_rows = []

        for fold_no, cut_idx in enumerate(cuts, start=1):
            train_levels = full_levels.iloc[: cut_idx + 1].copy()

            # REL is only defined cleanly for strictly positive levels.
            arr = train_levels.to_numpy(dtype=float)
            if (
                not np.isfinite(arr).all()
                or np.any(arr <= 0)
                or np.min(arr) < 1e-8
            ):
                continue

            # Both representations have exactly n_levels - 1 historical step rows,
            # so one common index matrix gives near-common-random-number comparison.
            n_steps = len(train_levels) - 1
            if n_steps < args.min_train:
                continue

            unit_seed = (
                args.seed
                + zlib.crc32(unit_id.encode("utf-8"))
                + 1009 * fold_no
            ) & 0xFFFFFFFF

            rng = np.random.default_rng(unit_seed)
            idx = rng.integers(
                0,
                n_steps,
                size=(args.draws, max_h),
            )

            try:
                abs_draws = _draw_abs(train_levels, horizons, idx)
                rel_draws = _draw_rel(train_levels, horizons, idx)
            except Exception:
                continue

            truth = np.stack(
                [
                    full_levels.iloc[cut_idx + h].to_numpy(dtype=float)
                    for h in horizons
                ],
                axis=0,
            )

            if (
                not np.isfinite(abs_draws).all()
                or not np.isfinite(rel_draws).all()
                or not np.isfinite(truth).all()
            ):
                continue

            met = _fold_metrics(abs_draws, rel_draws, truth)

            rec = {
                "unit_id": unit_id,
                "family": _family(card),
                "fold": fold_no,
                "cutoff": str(full_levels.index[cut_idx].date()),
                "n_assets": len(assets),
                "n_horizons": len(horizons),
                "history_steps": n_steps,
                **met,
            }

            rows.append(rec)
            unit_fold_rows.append(rec)

        if unit_fold_rows:
            med = np.median(
                [r["proxy_composite_ratio"] for r in unit_fold_rows]
            )
            print(
                f"{unit_id:42s} "
                f"{_family(card):5s} "
                f"folds={len(unit_fold_rows)} "
                f"REL/ABS proxy median={med:.4f}"
            )

    if not rows:
        raise SystemExit(
            "No valid level-target folds. "
            "Check repo root, history length, or positivity constraints."
        )

    df = pd.DataFrame(rows)
    df.to_csv(args.out, index=False, encoding="utf-8-sig")

    unit = (
        df.groupby(["unit_id", "family"], as_index=False)
        .agg(
            folds=("fold", "count"),
            crps_ratio=("crps_ratio", "median"),
            variogram_ratio=("variogram_ratio", "median"),
            tail90_ratio=("tail90_ratio", "median"),
            proxy_composite_ratio=("proxy_composite_ratio", "median"),
        )
    )

    unit_out = str(Path(args.out).with_name(
        Path(args.out).stem + "_units.csv"
    ))
    unit.to_csv(unit_out, index=False, encoding="utf-8-sig")

    skip_out = str(Path(args.out).with_name(
        Path(args.out).stem + "_skipped.csv"
    ))
    pd.DataFrame(skipped).to_csv(skip_out, index=False, encoding="utf-8-sig")

    print()
    print("=" * 88)
    print("V11 LEVEL REPRESENTATION SCREEN — REL / ABS")
    print("=" * 88)
    print(f"Valid folds          : {len(df)}")
    print(f"Valid units          : {len(unit)}")
    print(f"Median unit CRPS     : {unit['crps_ratio'].median():.4f}")
    print(f"Median unit Variogram: {unit['variogram_ratio'].median():.4f}")
    print(f"Median unit Tail90   : {unit['tail90_ratio'].median():.4f}")
    print(
        "Median unit Proxy   : "
        f"{unit['proxy_composite_ratio'].median():.4f}"
    )
    print(
        "Unit win rate REL   : "
        f"{(unit['proxy_composite_ratio'] < 1.0).mean():.1%}"
    )
    print(
        "Strong REL units    : "
        f"{(unit['proxy_composite_ratio'] <= 0.95).sum()}/{len(unit)}"
    )
    print()

    print("By family:")
    for fam, g in unit.groupby("family"):
        print(
            f"  {fam}: n={len(g):2d} "
            f"| proxy={g['proxy_composite_ratio'].median():.4f} "
            f"| CRPS={g['crps_ratio'].median():.4f} "
            f"| VAR={g['variogram_ratio'].median():.4f} "
            f"| TAIL={g['tail90_ratio'].median():.4f} "
            f"| win={(g['proxy_composite_ratio'] < 1.0).mean():.1%}"
        )

    overall = float(unit["proxy_composite_ratio"].median())
    win = float((unit["proxy_composite_ratio"] < 1.0).mean())

    print()
    print("Decision rule:")
    if overall <= 0.95 and win >= 2.0 / 3.0:
        print(
            "  REL PROMISING: material broad improvement. "
            "Only then consider a REL V11 production branch."
        )
    elif overall < 0.99 and win >= 0.60:
        print(
            "  HOLD: modest/broad REL edge, but below our ~5% promotion threshold. "
            "Keep current ABS production unless family evidence is unusually clean."
        )
    else:
        print(
            "  KEEP ABS: no material broad REL advantage. "
            "Do not change the frozen V11 numeric representation."
        )

    print()
    print("Important:")
    print("  - This is a pseudo-OOS proxy screen, not the official sealed score.")
    print("  - It compares only DAILY LEVEL cards.")
    print("  - Original log_return cards are intentionally excluded.")
    print("  - Raw historical LEVEL sampling is NOT tested; the comparator is log change.")
    print()
    print("Fold CSV :", args.out)
    print("Unit CSV :", unit_out)
    print("Skipped  :", skip_out)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())