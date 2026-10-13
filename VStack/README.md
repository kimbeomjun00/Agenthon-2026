# VStack: optimized research integration

**Current release:** default `--mode stable`: pure-domain calls retain the preceding
fast_price candidate exactly, while mixed/unknown domains retain the joint baseline.
This conservative composition was chosen AFTER comparison; it is not a freshly validated
winner. The new `--mode optimized` (stack50) remains a research option because its gains
were not uniform. See RELEASE_DECISION.json in the outer research directory.

**Optimization research:** `--mode optimized` dispatches to `stack50`. The older
VExpert description below is retained as component history, not current default behavior.
Build with `docker build --platform linux/amd64 -t agenthon-vstack-stable:research .`.

One global design was selected on purged 2006-2019 development before this round's
subsequent-period evaluation. Each non-price asset fits empirical-mixture CRPS weights
plus ridge, retaining at least 50% anchor. Eight resolved folds feed a chronological guard:
each later validation fold is predicted using earlier folds only. Marginal gain/win-rate
and joint-loss gates screen changes before all resolved folds are refit.

CPI/PCE preserve the earlier fast_price composition. Other anchors use repaired VSpecial.
Mixed/unknown/stale inputs retain the joint baseline; the existing CLI stale-FX transfer
layer remains. Mixtures use whole terminal-rank-aligned paths and a common stratified
latent selector. This does not guarantee unchanged covariance. No offline fitted weights
or per-asset benchmark-winner table is loaded. Real House accuracy is untested.

The 2020-2024 period was already explored in previous rounds: new results are not an
untouched holdout. Read the outer report for comparisons, regressions and limitations.
`--mode fast_price` retains the preceding candidate; other modes are research diagnostics.
Calibration/stack70/stackcal remain research-only module options, not the release default.

## Historical VExpert component description

VExpert is a domain-specific numerical-expert integration research model. It selects
separately for each target series from resolved folds of the supplied unit history only.
No saved benchmark winner table, outcome lookup or pretrained numerical parameters load.
This is research source, not a Codabench submission; the submitted image is unchanged.

### Domain experts

- UST: yield changes, curve level/slope/curvature state, PCA change conditions,
  damped policy trend, ridge lag conditions and filtered variance.
- G10 FX: positive log prices, filtered residuals, asymmetric variance, PCA common
  currency conditions and supplied DKK/EUR spread reversion when EUR is available.
- Factors: log1p simple returns, separate MKT/BAB/QMJ mean priors; asset-role feature
  menus for HML/SMB/MOM/BAB/QMJ; lagged crash/rebound conditions; squared-return
  variance proxy and asymmetric variance. The proxy is not intraday HAR-RV.
- CPI/PCE: log growth, two-speed Kalman drift uncertainty, seasonal/persistent growth
  and cross-indicator conditions. NFP uses native employment changes/robust drift.
  UNRATE evolves in a bounded logit state. No GDP accuracy claim is made.

### Integrated selection

The fixed menus are in vnext/experts.py. Parameters, residuals and weights fit at runtime.
Six recent fully resolved nonoverlapping folds compare each expert with VSpecial.
Require >=3% loss improvement and >=60% fold wins. Retain baseline probability mass
and a leave-one-fold-out joint-loss guard. Unknown or insufficient histories return
repaired VSpecial exactly. The selector objective is not organizer M0 normalization.

Experts share empirical per-step rank innovations. In the expert branch, whole baseline
trajectories are terminal-rank aligned to the joint native random-walk reference. Marginal
values and each asset's nested trajectory remain intact. A common 20% draw mask retains
original joint baseline paths. This is approximate copula coupling, not proof that the old
covariance is unchanged. Joint and tail losses are measured separately.

### Build and use

Build a local-only image: docker build --platform linux/amd64 -t agenthon-vexpert:research .
Run the forecast command with --panels /input/panels --text /input/text --asof YYYY-MM-DD
and --out /output/forecast.parquet, using offline/read-only input/output bind mounts.
Historical --mode expert includes the joint guard. --mode expert_open is a diagnostic without
that guard. --mode price is repaired VSpecial. Prior research modes remain available.
The post-comparison --mode fast_price research composition uses kf_fast for all four
price indices, unchanged VSpecial for other macro targets, and the same domain router
for daily inputs. It was chosen after earlier comparisons; reused-period gains are not
independent confirmation. The VStack CLI default is stable as documented above.
Exactly three output files, 2000 default draws, canonical monthly keys/step matrices.

The organizer-only House client and guarded text policy are unchanged. No external market
retrieval occurs at inference. Real House accuracy is untested. Read the outer result tables
and caveats before deployment. Official scoring helpers and licences are unchanged.
