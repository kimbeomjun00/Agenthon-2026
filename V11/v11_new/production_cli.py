"""Agenthon 2026 Track 2 — V11 final candidate.

V11 = E2 90/10 numeric backbone + V8 scenario-mixture text representation.

Daily numeric engine
--------------------
* aligned absolute daily changes for level targets; aligned daily log returns for log-return targets;
* full-history standardization of complete cross-asset rows;
* current variance = 0.90 * EWMA(HL=60) variance + 0.10 * full-history variance;
* iid sampling of complete standardized cross-asset rows, one row per simulated day;
* one nested path shared by all authored horizons.

Text engine
-----------
* reads only cutoff-valid corpus documents;
* asks House for 1-4 plausible forward scenarios;
* each scenario has a probability, per-asset centre shift (SD units at max horizon), and vol scale;
* one scenario is assigned to an entire joint Monte-Carlo draw;
* short-horizon centre shifts scale linearly by h/max_h;
* invalid/unavailable House => continuation scenario (shift=0, vol=1), leaving numeric forecast unchanged.

Explicit monthly cards use the official reference monthly generator as the numeric backbone before
applying the same scenario transform.

This repository copy was reconstructed from the archived V10 submitted numeric source, V8 champion
scenario source, the V11 validation scripts, and the V11 retrospective. See V11_PROVENANCE.md.
"""
from __future__ import annotations

import argparse
import base64
import http.client
import json
import math
import os
import pathlib
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import unquote, urlsplit

import numpy as np
import pandas as pd

from qfbench2_track_forecasting.cli import (
    _draw as _reference_draw,
    _monthly_inputs,
    _read_panels,
    _series,
)
from qfbench2_track_forecasting.horizons import HorizonMetadataError
from qfbench2_track_forecasting.limits import ParseLimits
from qfbench2_track_forecasting.targets import log_return_steps

_DEFAULT_DRAWS = 1000
_EWMA_HALF_LIFE = 60.0
_EWMA_WEIGHT = 0.90
_MAX_DOCS = 10
_MAX_DOC_CHARS = 7000
_MAX_SCENARIOS = 4
_HOUSE_OUTPUT_TOKENS = 4000
_RESPONSE_BYTES = 1024 * 1024
_TIMEOUT_SEC = 60
_RATIONALE_NAME = "forecast_rationale.md"
_FAMILIES = {"T2-F1", "T2-F2", "T2-F3", "T2-F4"}

_FAMILY_GUIDANCE = {
    "T2-F1": (
        "Continuation-with-context: numbers already carry most of the signal. Text should make "
        "incremental centre/width changes; avoid aggressive regime shifts without strong evidence."
    ),
    "T2-F2": (
        "Text-cued regime shift: text may signal a transition before the panel. Scenario weights "
        "and directional shifts may move materially when evidence is strong."
    ),
    "T2-F3": (
        "Cross-asset reasoning: preserve joint moves. Express a coherent scenario across all target "
        "assets; do not reason about each margin independently."
    ),
    "T2-F4": (
        "Tail/shock-from-text: represent a plausible shock as a distinct scenario with honest "
        "probability and wider uncertainty rather than only inflating every draw."
    ),
}


def _family(card: dict[str, Any]) -> str:
    fam = str(card.get("metadata", {}).get("category", "T2-F1"))
    return fam if fam in _FAMILIES else "T2-F1"


def read_corpus(text_dir: pathlib.Path, asof: str) -> tuple[list[dict[str, Any]], int, int]:
    index_path = text_dir / "corpus_index.json"
    if not index_path.is_file():
        return [], 0, 0
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [], 0, 0

    kept: list[dict[str, Any]] = []
    excluded = 0
    for doc in index.get("documents", []):
        ts = str(doc.get("timestamp", ""))[:10]
        if not ts or ts > asof:
            excluded += 1
            continue
        path = text_dir / str(doc.get("file", ""))
        if not path.is_file():
            excluded += 1
            continue
        try:
            body = path.read_text(encoding="utf-8", errors="replace")[:_MAX_DOC_CHARS]
        except OSError:
            excluded += 1
            continue
        kept.append({
            "doc_id": str(doc.get("doc_id", path.name)),
            "timestamp": ts,
            "doc_type": str(doc.get("doc_type", "")),
            "source": str(doc.get("source", "")),
            "text": body,
        })
    kept.sort(key=lambda d: (d["timestamp"], d["doc_id"]), reverse=True)
    truncated = max(0, len(kept) - _MAX_DOCS)
    return kept[:_MAX_DOCS], excluded, truncated


def _house_reply(endpoint: str, token: str, body: bytes) -> Any:
    target = urlsplit(endpoint)
    proxy = urlsplit(os.environ.get("http_proxy", os.environ.get("HTTP_PROXY", "")))
    if (
        target.scheme != "http" or not target.hostname
        or target.username is not None or target.password is not None
        or target.path.rstrip("/") not in ("", "/v1")
        or target.query or target.fragment
        or proxy.scheme != "http" or not proxy.hostname or not proxy.port
        or proxy.path not in ("", "/") or proxy.query or proxy.fragment
        or not proxy.username or not proxy.password or not token
        or any(ord(c) < 33 or ord(c) > 126 for c in token)
    ):
        raise ValueError("invalid House model or proxy configuration")
    credentials = unquote(proxy.username) + ":" + unquote(proxy.password)
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + token,
        "Proxy-Authorization": "Basic " + base64.b64encode(credentials.encode()).decode(),
    }
    conn = http.client.HTTPConnection(proxy.hostname, proxy.port, timeout=_TIMEOUT_SEC)
    try:
        conn.request(
            "POST",
            target.scheme + "://" + target.netloc + "/v1/chat/completions",
            body,
            headers,
        )
        response = conn.getresponse()
        if response.status != 200:
            raise ValueError("House model request was refused")
        raw = response.read(_RESPONSE_BYTES + 1)
        if len(raw) > _RESPONSE_BYTES:
            raise ValueError("House response too large")
        return json.loads(raw)
    finally:
        conn.close()


def call_house(prompt: str) -> tuple[dict[str, Any] | None, str]:
    # Local smoke compatibility. V11_MOCK_HOUSE_JSON is the preferred name; the V8 alias is
    # also accepted because V11 deliberately reuses the V8 scenario representation.
    mock = os.environ.get("V11_MOCK_HOUSE_JSON", "").strip() or os.environ.get(
        "V8_MOCK_HOUSE_JSON", ""
    ).strip()
    if mock:
        try:
            parsed = json.loads(mock)
            return (parsed if isinstance(parsed, dict) else None), ""
        except ValueError:
            return None, "mock House JSON did not parse"

    endpoint = os.environ.get("MODEL_ENDPOINT", "").strip()
    model = os.environ.get("MODEL_NAME", "").strip()
    if not endpoint:
        return None, "MODEL_ENDPOINT is unset"
    if not model:
        return None, "MODEL_NAME is unset"

    try:
        max_tokens = min(
            _HOUSE_OUTPUT_TOKENS,
            max(1, int(os.environ.get("MODEL_MAX_TOKENS", "3200"))),
        )
    except ValueError:
        return None, "MODEL_MAX_TOKENS is not an integer"

    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": max_tokens,
        "chat_template_kwargs": {"enable_thinking": False},
    }).encode("utf-8")

    try:
        if "MODEL_TOKEN" in os.environ:
            payload = _house_reply(endpoint, os.environ["MODEL_TOKEN"], body)
        else:
            ep = endpoint.rstrip("/")
            url = ep + ("/chat/completions" if ep.endswith("/v1") else "/v1/chat/completions")
            req = urllib.request.Request(
                url,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            local_key = os.environ.get("MODEL_API_KEY", "").strip()
            if local_key:
                req.add_header("Authorization", f"Bearer {local_key}")
            with urllib.request.urlopen(req, timeout=_TIMEOUT_SEC) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
    except (
        urllib.error.URLError,
        TimeoutError,
        ValueError,
        OSError,
        http.client.HTTPException,
    ) as exc:
        return None, f"House request failed ({type(exc).__name__})"

    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return None, "House reply had no choices[0].message.content"
    if not isinstance(content, str):
        return None, "House content was not a string"
    start, end = content.find("{"), content.rfind("}")
    if start < 0 or end <= start:
        return None, "House reply contained no JSON object"
    try:
        parsed = json.loads(content[start : end + 1])
    except ValueError:
        return None, "House reply JSON did not parse"
    return (parsed if isinstance(parsed, dict) else None), ""


def _common_level_frame(
    panels: dict[str, pd.DataFrame], assets: list[str], asof: str
) -> pd.DataFrame:
    cols = {}
    for asset in assets:
        s = _series(panels, asset, asof).astype(float)
        s.index = pd.to_datetime(s.index)
        cols[asset] = s
    return (
        pd.DataFrame(cols)
        .sort_index()
        .replace([np.inf, -np.inf], np.nan)
        .dropna()
    )


def _common_return_frame(
    panels: dict[str, pd.DataFrame], assets: list[str], asof: str
) -> pd.DataFrame:
    cols = {}
    for asset in assets:
        s = _series(panels, asset, asof).astype(float)
        s.index = pd.to_datetime(s.index)
        cols[asset] = pd.Series(log_return_steps(s), index=s.index, dtype=float)
    return (
        pd.DataFrame(cols)
        .sort_index()
        .replace([np.inf, -np.inf], np.nan)
        .dropna()
    )


def _ewma_variance(x: np.ndarray, half_life: float) -> np.ndarray:
    n = len(x)
    age = np.arange(n - 1, -1, -1, dtype=float)
    w = 0.5 ** (age / half_life)
    w /= w.sum()
    mu = np.sum(x * w[:, None], axis=0)
    var = np.sum(((x - mu[None, :]) ** 2) * w[:, None], axis=0)
    return np.maximum(var, 1e-16)


def _daily_e2_draws(
    panels: dict[str, pd.DataFrame],
    assets: list[str],
    horizons: list[int],
    asof: str,
    target_type: str,
    n_draws: int,
    seed: int,
) -> tuple[np.ndarray, dict[str, Any], pd.DataFrame, np.ndarray, np.ndarray]:
    """Return draws [draw, horizon, asset], metadata, steps, anchor and current daily SD."""
    if target_type == "log_return":
        steps_df = _common_return_frame(panels, assets, asof)
        anchor = np.zeros(len(assets), dtype=float)
        daily_mu = steps_df.to_numpy(dtype=float).mean(axis=0)
    else:
        levels = _common_level_frame(panels, assets, asof)
        if len(levels) < 3:
            raise ValueError("insufficient common level history")
        anchor = levels.iloc[-1].to_numpy(dtype=float)
        steps_df = levels.diff().dropna()
        daily_mu = np.zeros(len(assets), dtype=float)

    train = steps_df.to_numpy(dtype=float)
    if len(train) < 100:
        raise ValueError(f"insufficient common daily history ({len(train)} rows)")

    full_mu = np.mean(train, axis=0)
    full_sd = np.std(train, axis=0, ddof=1)
    full_sd = np.where(np.isfinite(full_sd) & (full_sd > 1e-12), full_sd, 1e-12)
    zpool = (train - full_mu[None, :]) / full_sd[None, :]

    ewma_var = _ewma_variance(train, _EWMA_HALF_LIFE)
    current_sd = np.sqrt(
        _EWMA_WEIGHT * ewma_var + (1.0 - _EWMA_WEIGHT) * (full_sd ** 2)
    )

    max_h = max(horizons)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(zpool), size=(n_draws, max_h))
    z = zpool[idx]
    daily = daily_mu[None, None, :] + z * current_sd[None, None, :]
    cumulative = np.cumsum(daily, axis=1)
    out = np.stack([cumulative[:, h - 1, :] for h in horizons], axis=1)
    if target_type != "log_return":
        out = out + anchor[None, None, :]

    meta = {
        "engine": "e2_empirical_joint_iid",
        "step_unit": "business_day",
        "n_history_rows": int(len(train)),
        "ewma_half_life": _EWMA_HALF_LIFE,
        "ewma_variance_weight": _EWMA_WEIGHT,
        "full_variance_weight": 1.0 - _EWMA_WEIGHT,
        "historical_pool": "all standardized common joint rows, uniform sampling",
        "serial_policy": "iid historical joint rows; one common row per simulated day",
        "horizon_policy": "nested cumulative path shared across authored horizons",
        "anchor": {asset: float(anchor[i]) for i, asset in enumerate(assets)},
        "current_daily_sd": {asset: float(current_sd[i]) for i, asset in enumerate(assets)},
        "daily_drift": {asset: float(daily_mu[i]) for i, asset in enumerate(assets)},
    }
    return out, meta, steps_df, anchor, current_sd


def _prompt_stats(
    steps_df: pd.DataFrame,
    assets: list[str],
    horizons: list[int],
    anchor: np.ndarray,
    current_sd: np.ndarray,
) -> tuple[dict[str, float], dict[str, dict[str, float]]]:
    arr = steps_df.to_numpy(dtype=float)
    recent = arr[-min(252, len(arr)) :]
    max_h = max(horizons)
    anchors = {a: float(anchor[i]) for i, a in enumerate(assets)}
    stats: dict[str, dict[str, float]] = {}
    for i, a in enumerate(assets):
        full_sd = float(np.std(arr[:, i], ddof=1)) if len(arr) > 1 else 0.0
        recent_sd = float(np.std(recent[:, i], ddof=1)) if len(recent) > 1 else full_sd
        stats[a] = {
            "daily_sd_full": max(full_sd, 1e-12),
            "daily_sd_recent": max(recent_sd, 1e-12),
            "horizon_sd": max(float(current_sd[i]) * math.sqrt(max_h), 1e-12),
        }
    return anchors, stats


def build_prompt(
    family: str,
    assets: list[str],
    horizons: list[int],
    target_type: str,
    asof: str,
    anchors: dict[str, float],
    stats: dict[str, dict[str, float]],
    docs: list[dict[str, Any]],
) -> str:
    lines = [
        "You are the text-state module inside a probabilistic financial forecasting system.",
        f"As-of date: {asof}. Use only the dated documents below; nothing later is known.",
        f"Card family: {family}. {_FAMILY_GUIDANCE.get(family, '')}",
        f"Target type: {target_type}; horizons (business days): {horizons}.",
        "",
        "The numerical engine has generated an E2 joint empirical distribution from cutoff-valid",
        "panel history. Your job is only to describe 1-4 plausible forward scenarios supported by",
        "the corpus. One scenario will be selected for an entire Monte-Carlo draw, so cross-asset",
        "directions must be coherent.",
        "",
        "Per asset numerical scale at the LONGEST horizon:",
    ]
    for a in assets:
        s = stats[a]
        lines.append(
            f"  {a}: anchor={anchors[a]:.8g}, horizon_sd≈{s['horizon_sd']:.8g}, "
            f"recent/full daily sd ratio≈{s['daily_sd_recent']/max(s['daily_sd_full'],1e-12):.3f}"
        )
    lines += ["", f"Documents ({len(docs)}), newest first:"]
    for d in docs:
        lines += [
            f"--- {d['doc_id']} ({d['timestamp']}, {d['doc_type']}) ---",
            d["text"],
            "",
        ]
    lines += [
        "Return JSON only with this schema:",
        "{",
        '  "state": {"label": "continuation|transition|shock", "confidence": 0.0},',
        '  "scenarios": [',
        "    {",
        '      "name": "short label", "prob": 0.0,',
        '      "assets": {',
        '        "<asset>": {"shift_sd": 0.0, "vol_scale": 1.0, "because": "doc_id(s)"}',
        "      }",
        "    }",
        "  ]",
        "}",
        "",
        "Definitions and hard rules:",
        "- probabilities across scenarios must sum to 1; use 1-4 scenarios.",
        "- shift_sd is the centre shift at the LONGEST horizon measured in that asset's horizon sd.",
        "  Positive means upward target value; negative means downward. Keep it in [-2.5, +2.5].",
        "- vol_scale is scenario-specific uncertainty, keep it in [0.65, 2.5].",
        "- At shorter horizons the engine scales shift_sd linearly with horizon/max_horizon.",
        "- If evidence is weak, include a high-probability continuation scenario near shift_sd=0.",
        "- Do not narrow uncertainty merely because you infer a direction from tone.",
        "- For F3, scenario directions across assets must represent one coherent joint market state.",
        "- For F4, if the text supports a tail event, represent it as a distinct lower-probability",
        "  shock scenario with wider vol, not as a guaranteed outcome.",
        "- because must cite only document ids shown above.",
    ]
    return "\n".join(lines)


def _clean_scenarios(
    parsed: dict[str, Any] | None, assets: list[str]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    fallback = {
        "name": "continuation",
        "prob": 1.0,
        "assets": {a: {"shift_sd": 0.0, "vol_scale": 1.0, "because": ""} for a in assets},
    }
    state = {"label": "continuation", "confidence": 0.0}
    if not isinstance(parsed, dict):
        return [fallback], state

    raw_state = parsed.get("state")
    if isinstance(raw_state, dict):
        label = str(raw_state.get("label", "continuation")).lower()
        if label not in {"continuation", "transition", "shock"}:
            label = "continuation"
        try:
            conf = float(raw_state.get("confidence", 0.0))
        except (TypeError, ValueError):
            conf = 0.0
        state = {"label": label, "confidence": min(max(conf, 0.0), 1.0)}

    raw = parsed.get("scenarios")
    if not isinstance(raw, list):
        return [fallback], state

    cleaned: list[dict[str, Any]] = []
    for item in raw[:_MAX_SCENARIOS]:
        if not isinstance(item, dict):
            continue
        try:
            prob = float(item.get("prob", 0.0))
        except (TypeError, ValueError):
            continue
        if not math.isfinite(prob) or prob <= 0:
            continue
        specs = item.get("assets")
        if not isinstance(specs, dict):
            continue
        out_assets: dict[str, dict[str, Any]] = {}
        valid = 0
        for a in assets:
            spec = specs.get(a, {})
            if not isinstance(spec, dict):
                spec = {}
            try:
                shift = float(spec.get("shift_sd", 0.0))
                vol = float(spec.get("vol_scale", 1.0))
            except (TypeError, ValueError):
                shift, vol = 0.0, 1.0
            if not math.isfinite(shift): shift = 0.0
            if not math.isfinite(vol): vol = 1.0
            shift = min(max(shift, -2.5), 2.5)
            vol = min(max(vol, 0.65), 2.5)
            because = str(spec.get("because", ""))[:240]
            if a in specs: valid += 1
            out_assets[a] = {"shift_sd": shift, "vol_scale": vol, "because": because}
        if valid == 0:
            continue
        cleaned.append({
            "name": str(item.get("name", f"scenario_{len(cleaned)+1}"))[:80],
            "prob": prob,
            "assets": out_assets,
        })
    if not cleaned:
        return [fallback], state
    total = sum(x["prob"] for x in cleaned)
    if not math.isfinite(total) or total <= 0:
        return [fallback], state
    for x in cleaned:
        x["prob"] /= total
    return cleaned, state


def _apply_scenarios(
    rng: np.random.Generator,
    base: np.ndarray,
    assets: list[str],
    horizons: list[int],
    scenarios: list[dict[str, Any]],
) -> tuple[np.ndarray, dict[str, Any]]:
    """Apply one common scenario to each [horizon, asset] joint draw."""
    out = np.asarray(base, dtype=float).copy()
    if out.ndim != 3 or out.shape[1:] != (len(horizons), len(assets)):
        raise ValueError(f"unexpected base draw shape {out.shape}")

    probs = np.asarray([s["prob"] for s in scenarios], dtype=float)
    probs /= probs.sum()
    scen_idx = rng.choice(len(scenarios), size=len(out), p=probs)
    max_h = max(horizons)

    for ai, asset in enumerate(assets):
        horizon_sd = float(np.std(base[:, -1, ai], ddof=1))
        if not math.isfinite(horizon_sd) or horizon_sd <= 0:
            horizon_sd = 1e-8
        for hi, h in enumerate(horizons):
            centre = float(np.mean(base[:, hi, ai]))
            for d in range(len(out)):
                spec = scenarios[int(scen_idx[d])]["assets"][asset]
                out[d, hi, ai] = centre + (base[d, hi, ai] - centre) * spec["vol_scale"]
                out[d, hi, ai] += spec["shift_sd"] * horizon_sd * (float(h) / float(max_h))

    return out, {
        "transform": "V8 scenario probability + centre shift + volatility scale",
        "scenario_counts": {
            scenarios[i]["name"]: int(np.sum(scen_idx == i)) for i in range(len(scenarios))
        },
    }


def _scenario_markdown(scenarios: list[dict[str, Any]], assets: list[str]) -> list[str]:
    lines = [
        "| scenario | probability | asset | shift_sd@maxH | vol_scale | evidence |",
        "|---|---:|---|---:|---:|---|",
    ]
    for s in scenarios:
        for a in assets:
            spec = s["assets"][a]
            lines.append(
                f"| {s['name']} | {s['prob']:.3f} | {a} | {spec['shift_sd']:+.2f} | "
                f"{spec['vol_scale']:.2f} | {spec['because']} |"
            )
    return lines


def _find_card(panels_dir: pathlib.Path, explicit: pathlib.Path | None) -> pathlib.Path:
    if explicit is not None:
        if not explicit.is_file():
            raise SystemExit(f"card.toml not found: {explicit}")
        return explicit
    for cand in (panels_dir / "card.toml", panels_dir.parent / "card.toml"):
        if cand.is_file():
            return cand
    raise SystemExit("card.toml not found; pass --card explicitly")


def main(argv: list[str] | None = None) -> int:
    import tomllib

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--panels", type=pathlib.Path, required=True)
    p.add_argument("--text", type=pathlib.Path, required=True)
    p.add_argument("--asof", required=True)
    p.add_argument("--out", type=pathlib.Path, required=True)
    p.add_argument("--card", type=pathlib.Path, default=None)
    p.add_argument("--n-draws", type=int, default=_DEFAULT_DRAWS)
    p.add_argument("--seed", type=int, default=None)
    a = p.parse_args(argv)

    card_path = _find_card(a.panels, a.card)
    card = tomllib.loads(card_path.read_text(encoding="utf-8"))
    tgt = card["targets"]
    assets = [str(x) for x in tgt["asset_ids"]]
    horizons = [int(x) for x in tgt["horizons"]]
    target_type = str(tgt.get("target_type", "level"))
    family = _family(card)
    unit_id = str(card["task"]["id"])

    limits = ParseLimits()
    n_draws = max(
        int(a.n_draws),
        int(card.get("scoring", {}).get("params", {}).get("n_draws_min", 0) or 0),
        int(limits.min_draws),
    )
    if n_draws > int(limits.max_draws):
        raise SystemExit(f"n_draws {n_draws} exceeds contract max {limits.max_draws}")
    seed = int(os.environ.get("QFBENCH_SEED", a.seed if a.seed is not None else 0))

    panels = _read_panels(a.panels)
    try:
        panel_steps = _monthly_inputs(panels, card, card_path, a.asof)
    except HorizonMetadataError:
        panel_steps = None

    if panel_steps is None:
        base, numeric_meta, steps_df, anchor, current_sd = _daily_e2_draws(
            panels, assets, horizons, a.asof, target_type, n_draws, seed
        )
        anchors, stats = _prompt_stats(steps_df, assets, horizons, anchor, current_sd)
    else:
        raw, official_meta = _reference_draw(
            panels,
            assets,
            horizons,
            a.asof,
            n_draws,
            seed,
            target_type=target_type,
            panel_steps=panel_steps,
        )
        # official shape [draw, asset, horizon] -> V11 internal [draw, horizon, asset]
        base = np.transpose(np.asarray(raw, dtype=float), (0, 2, 1))
        # Prompt scale uses the base draw distribution itself for monthly cards.
        anchor = np.zeros(len(assets), dtype=float)
        if target_type != "log_return":
            try:
                anchor = np.asarray([float(official_meta["last"][x]) for x in assets], dtype=float)
            except Exception:
                anchor = np.mean(base[:, 0, :], axis=0)
        anchors = {asset: float(anchor[i]) for i, asset in enumerate(assets)}
        stats = {}
        for ai, asset in enumerate(assets):
            hsd = float(np.std(base[:, -1, ai], ddof=1))
            stats[asset] = {
                "daily_sd_full": max(hsd / math.sqrt(max(horizons)), 1e-12),
                "daily_sd_recent": max(hsd / math.sqrt(max(horizons)), 1e-12),
                "horizon_sd": max(hsd, 1e-12),
            }
        numeric_meta = {
            "engine": "official_reference_monthly_fallback",
            "step_unit": "month",
            "reference_meta": official_meta,
        }

    docs, excluded, truncated = read_corpus(a.text, a.asof)
    parsed: dict[str, Any] | None = None
    skip_reason = ""
    if docs:
        parsed, skip_reason = call_house(
            build_prompt(family, assets, horizons, target_type, a.asof, anchors, stats, docs)
        )
    else:
        skip_reason = "no indexed corpus document at or before as-of"

    scenarios, state = _clean_scenarios(parsed, assets)
    reasoning_applied = parsed is not None and not (
        len(scenarios) == 1
        and scenarios[0]["name"] == "continuation"
        and scenarios[0]["prob"] == 1.0
        and all(
            scenarios[0]["assets"][x]["shift_sd"] == 0.0
            and scenarios[0]["assets"][x]["vol_scale"] == 1.0
            for x in assets
        )
    )

    rng = np.random.default_rng((seed + 0x11E2A8) & 0xFFFFFFFF)
    samples, scenario_meta = _apply_scenarios(rng, base, assets, horizons, scenarios)
    if not np.isfinite(samples).all():
        raise SystemExit("non-finite value generated")

    a.out.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {"draw": int(d), "asset": asset, "horizon": int(h), "value": float(samples[d, hi, ai])}
        for d in range(n_draws)
        for ai, asset in enumerate(assets)
        for hi, h in enumerate(horizons)
    ]
    pd.DataFrame(rows).to_parquet(a.out, index=False)

    meta = {
        "unit_id": unit_id,
        "asof": a.asof,
        "representation": "samples",
        "asset_ids": assets,
        "horizons": horizons,
        "n_draws": n_draws,
        "target": target_type,
        "reasoning_applied": reasoning_applied,
        "reasoning_skipped_reason": "" if reasoning_applied else skip_reason,
        "rationale": {
            "file": _RATIONALE_NAME,
            "method": "V11 E2-90/10 numeric backbone + V8 text scenario mixture",
            "family": family,
            "text_state": state,
            "documents_read": len(docs),
            "documents_excluded_by_cutoff": excluded,
            "documents_over_prompt_budget": truncated,
            "numeric_engine": numeric_meta.get("engine"),
        },
        "v11": {
            "numeric": numeric_meta,
            "scenario": scenario_meta,
            "scenarios": scenarios,
        },
    }
    (a.out.parent / "forecast_meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    rationale = [
        f"# Forecast rationale — {unit_id}",
        "",
        f"**As of {a.asof}. Family {family}. Assets: {', '.join(assets)}. Horizons: {horizons}.**",
        "",
        "## 1. Numeric backbone",
        "",
        f"Engine: **{numeric_meta.get('engine')}**.",
        "Daily cards use complete historical joint rows standardized on full history and rescaled",
        "with current variance = 0.90 × EWMA60 variance + 0.10 × full-history variance. The same",
        "simulated daily path is accumulated across all horizons. Explicit monthly cards use the",
        "official reference monthly generator.",
        "",
        "## 2. Dated text state",
        "",
        f"Documents read at/before cutoff: **{len(docs)}**; excluded/missing: **{excluded}**; "
        f"over prompt budget: **{truncated}**.",
        f"House reasoning applied: **{reasoning_applied}**.",
        *([f"Fallback reason: **{skip_reason}**."] if not reasoning_applied and skip_reason else []),
        f"Extracted state: **{state['label']}**, confidence **{state['confidence']:.2f}**.",
        "",
        "## 3. Scenario ledger",
        "",
        *_scenario_markdown(scenarios, assets),
        "",
        "One scenario is selected for the entire joint Monte-Carlo draw. Scenario probability",
        "changes the mixture weight, shift_sd changes the centre, and vol_scale expands/contracts",
        "stochastic deviations around the numeric centre. Short-horizon shifts are scaled by h/max_h.",
        "",
        "## 4. Cutoff statement",
        "",
        "Only organizer-indexed documents dated on or before the as-of date are read. No live web",
        "or external market-data retrieval is used.",
    ]
    (a.out.parent / _RATIONALE_NAME).write_text("\n".join(rationale) + "\n", encoding="utf-8")

    print(f"wrote {a.out.name} + sidecars to {a.out.parent}")
    print(f"  model=V11 E2+V8 scenario mixture · family={family} · {n_draws} draws")
    print(f"  text_docs={len(docs)} · reasoning_applied={reasoning_applied} · state={state['label']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
