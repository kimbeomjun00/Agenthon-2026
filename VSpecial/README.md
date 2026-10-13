## Executive summary (read this first)

VSpecial tests each available financial series and defaults to inflation specialists plus V11
for the other series. Runtime parameters and choices use the current task's history only.
The outer Korean report gives measured gains, rejected candidates and limitations.

### Build and run

```powershell
docker build --platform linux/amd64 -t agenthon-vspecial:research .
docker run --rm --network=none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=512m `
  --mount "type=bind,source=C:\absolute\unit-folder,target=/input,readonly" `
  --mount "type=bind,source=C:\absolute\output-folder,target=/output" `
  agenthon-vspecial:research forecast --panels /input/panels --text /input/text `
  --asof YYYY-MM-DD --out /output/forecast.parquet
```

`forecast` is the first command; no ENTRYPOINT is set. Outputs are exactly forecast.parquet,
forecast_meta.json and forecast_rationale.md. Default: 2,000 draws. QFBENCH_SEED overrides --seed.
Monthly horizon keys remain authored keys; actual steps come from observation periods and lag.

### Tested engines

- `--mode price` (default): CPI_ALL, CPI_CORE, PCE_ALL, PCE_CORE use 8 trend specifications ×
  4 trend-uncertainty strengths. Resolved local folds pick each asset's specification. Require
  >=3% past-fold gain and >=half of folds won, else baseline. Fifteen percent of entire draws
  retain baseline. Joint Gaussian innovations couple assets/months; a common historical
  rolling-trend vector adds uncertainty about inflation regimes. Other series retain V11.
- `--mode conservative`: Phase 1 restricted asset specialist menu from development.
- `--mode specialists`: Phase 1 unrestricted asset selector, 15 daily and 14 monthly candidates.
  Models share historical shock rows and nested paths. This is an exploratory comparator.
- `--mode adaptive`: prior VNext joint mixture, retained for comparison.
- Other inherited fixed modes: v11_safe, fhs60, direct, block5, trend12, trend36, ar1.
- `crossasset.py`: researched ridge VAR, smoothed lags and PCA level mean reversion. It is not
  selected by the production router. PCA is applicable to level targets, not factor returns.

The Phase 1 menu and the final price-only support decision are documented separately. Neither
loads benchmark losses or fitted policy weights at inference. The local selector objective is
a CRPS/pinball surrogate, not the official normalized composite.

### Gaps, House and limitations

Changes crossing large gaps are excluded. A stale FX history may use a 50/50 target/proxy path
mixture fitted on overlap dates only. Synthetic G10 gap tests do not prove actual EM accuracy.

The V11 House client makes at most one organizer-routed call per unit. `--text-policy guarded`
is the default, `v11` retains prior cleaning, and `off` disables text. Guarded responses must cite
supplied document IDs; confidence attenuates shifts. Actual monthly steps control shifts.
Real House accuracy/text uplift has not been tested; mocks test plumbing only.

28 contiguous series are available in the supplied panels. GDP has no supplied continuous
history. Unknown monthly names retain the baseline; no GDP accuracy claim is made.
Macro backtests use one revised vintage, not a historical real-time release-vintage database.
2020-2024 was already explored in earlier VNext work. Results are exploratory, not a pristine
holdout or a Codabench score. Read coverage, joint and tail diagnostics alongside marginal CRPS.

### Provenance

The uploaded V11 is reconstructed source, not byte-identical to its earlier submitted image.
`v11_new` is preserved from user commit 24aaeb7daaf2283695c1e4a20aa8a145bf52fc56.
Unmodified official T2 helpers: a2c93e7b66b8c6a6c429fda81d6bc7873b7c5dec (MIT).
Common toolkit: v2.6.0, bd01548e34d21fd660d88fd06157078fb25ece4e (CC BY-NC 4.0).
Licences and pinned dependencies are included. No raw panels, neural checkpoints, credentials,
submission descriptor or registry publication are included in this research bundle.
