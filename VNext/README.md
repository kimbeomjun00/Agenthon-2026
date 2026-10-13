## Executive summary (read this first)

VNext is a research candidate extending the reconstructed V11 checkpoint. It handles gaps,
models FX in proportional changes, adds trends to monthly macro forecasts and chooses numeric
mixture weights using only the current task's resolved historical observations. The same model
and scenario are shared across assets and horizons within a joint draw.

Read the Korean report in the outer bundle before choosing a submission. Local improvements are
not an official leaderboard result. No submission descriptor or Codabench upload archive is included.

### Running locally

Build from this directory:

```powershell
docker build --platform linux/amd64 -t agenthon-vnext:research .
```

Mount one existing public unit as `/input` and an empty output folder as `/output`:

```powershell
docker run --rm --network=none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=512m `
  --mount "type=bind,source=C:\absolute\unit-folder,target=/input,readonly" `
  --mount "type=bind,source=C:\absolute\output-folder,target=/output" `
  agenthon-vnext:research forecast --panels /input/panels --text /input/text `
  --asof YYYY-MM-DD --out /output/forecast.parquet
```

The harness calls `forecast` as its first command. The image has no ENTRYPOINT.
It writes `forecast.parquet`, `forecast_meta.json`, and `forecast_rationale.md` only.
`QFBENCH_SEED` takes precedence over `--seed`. The default ensemble is 2,000 draws.

### Research switches

- `--mode adaptive`: default past-only mixture of numerical candidates.
- `--mode v11_safe`: V11-like absolute-change sampler with the gap correction.
- `--mode fhs60`: causal volatility filtering and joint residual resampling.
- `--mode direct`: contiguous historical paths scaled by their prior volatility.
- `--mode block5`: stationary blocks with mean length five; never bridge source gaps.
- `--text-policy guarded`: default; exact supplied document IDs and confidence attenuate shifts.
- `--text-policy v11`: the previous scenario cleaning policy, for later House ablation.
- `--text-policy off`: numeric-only experiments.

The candidate names are local implementation choices, not additional competition families.
Output families remain T2-F1 through T2-F4. Authored horizon keys remain unchanged.
Monthly step counts use the supplied observation periods and each asset's last observed month.
Malformed monthly metadata raises an error rather than turning a business-day label into months.

### Numerical method

For each target asset the current unit alone supplies its history. Changes spanning a long gap
are discarded before alignment. FX and wholly positive macro-index groups can use log changes;
rates and mixed macro groups use absolute changes. Cumulative factor returns use log(1+r).

The daily candidate pool contains a V11-like model, filtered historical simulations at three
volatility half-lives, a historical path model and a five-step block model. Monthly candidates
are a no-drift comparator, local trends over 12 and 36 observations and an autoregressive
change model. No fitted artifact from the benchmark is packaged.

Eight non-overlapping, already resolved blocks from the supplied history score the candidates
with the shared toolkit's marginal CRPS. A soft weighting rule limits selection noise.
This local selector is a surrogate objective, not the official normalized CRPS composite.
One candidate is assigned to the complete asset/horizon grid of each Monte Carlo draw.

If an FX target's last usable change is over 180 days old, an optional regression path uses
contemporaneous G10 proxies. Its coefficients use only overlapping historical dates. Half the
draws retain the stale target model to reflect transfer uncertainty. Synthetic gap experiments
do not establish performance on the contest's actual emerging-market cards.

### House text path

The organizer's endpoint, model alias, proxy and token are read at runtime. No participant API
key is packaged. The inherited V11 House client calls the organizer route once per unit.
The latest ten cutoff-valid indexed documents feed the V11 scenario representation.
Probabilities, centre shifts and uncertainty scales affect whole joint draws.

The guarded policy accepts only exact document IDs in a comma-separated citation list. Confidence
shrinks unsupported certainty; a directional shift cannot simultaneously narrow the distribution.
For monthly targets the shift uses actual monthly steps, including publication lag. A missing
or invalid House reply leaves the numeric forecast unchanged.

Local tests use mocked responses. They establish the data flow and gates; they do not establish
the accuracy of the actual House model or the text policy. The forthcoming submission should
compare guarded and V11 text policies before claiming text uplift.

### Provenance and licences

The numeric code was written for this project on 2026-10-13. The `v11_new` directory is the user's
uploaded reconstruction, preserved from commit `24aaeb7daaf2283695c1e4a20aa8a145bf52fc56`.
It is not claimed to be identical to the source of the original submitted V11 image.
The official helper package is copied without edits from Track 2 commit
`a2c93e7b66b8c6a6c429fda81d6bc7873b7c5dec` under the MIT licence.
The common toolkit is v2.6.0 at `bd01548e34d21fd660d88fd06157078fb25ece4e`, licensed CC BY-NC 4.0.
Their licence texts are included. Benchmarks read public panels locally but none are in this image.

The House identity and training-cutoff disclosure must follow the organizer's current guide when
we later prepare submission metadata. This research bundle contains no descriptor or team secret.
