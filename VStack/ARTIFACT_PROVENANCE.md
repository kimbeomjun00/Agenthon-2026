## Executive summary (read this first)

This research image contains pure numerical source and no packaged fitted model, winner
table, numerical checkpoint, target answer, raw historical panel or retrieval database.
All statistical parameters and expert weights fit from this unit's supplied cutoff-valid
history, in memory. Historical fold outcomes are resolved earlier rows of the same input.

### Numerical code and runtime fitting

The pinned Dockerfile/requirements.lock declare Python, numpy, pandas, scipy, pyarrow and
qfbench2-common versions. Official Track 2 scoring helpers are copied unmodified from
a2c93e7b66b8c6a6c429fda81d6bc7873b7c5dec; common is v2.6.0,
bd01548e34d21fd660d88fd06157078fb25ece4e. Licences are preserved.

experts.py is a source implementation of linear/state-space, empirical residual,
conditional-variance and curve-factor algorithms. portfolio.py is code for cross-domain
trajectory coupling and a past-fold guard. Immutable code checksums are in the outer
MANIFEST.json and frozen study records; the local research Docker digest is in provenance.
They are not neural checkpoints or serialized fitted regressions.

VStack adds stacking.py (empirical-mixture CRPS weights with chronological validation)
and optimized.py (the globally development-selected stack50 dispatcher). The four new
integration designs were fixed before their purged 2006-2019 comparison. Any development
origin whose target window reaches 2020 was removed. stack50 was then frozen before
this round's 2020-2024 evaluation. This does NOT create a pristine holdout: the same
period and the price-anchor architecture were explored in preceding research. Architecture
selection therefore uses public history through 2024; per-unit fitted parameters do not.

Training mixture moments use empirical (biased-estimator) CRPS; guard and reported
evaluation use the official fair ensemble estimator. Official score implementations and
their denominators are not altered. Local reference scaling is not official M0 scaling.

The final stable.py composition was chosen AFTER this comparison showed mixed/regressive
optimization results. It calls previous fast_price exactly for pure known domains and
the safe joint baseline for mixed/unknown inputs. This is explicitly post-comparison
release selection, not a new held-out success. The optimized design and its failed cells
remain in the source and research evidence. Direct sample-equivalence checks and a fresh
final-image validation support the integration, not a claim of independent accuracy.

Covariates come from supplied same-domain histories only. Source dates are cut before
monthly alignment. Regressions, means, variance states, filtering parameters, residual
pools, return hedge ratios and selector weights use only that unit's current input rows.
There are no historical event-date branches or stored per-unit decisions at inference.
Unknown/insufficient/stale histories preserve the safe baseline and existing transfer code.

### House and eligibility

The inherited client permits only the organizer endpoint. No participant vendor key,
language-model weights, adapters or model server are included. House is optional during
local numeric tests, and those tests do not establish real House accuracy. Any actual
submission must preserve the current organizer House revision and training-cutoff disclosure.
No submission descriptor or team claim is included in this research ZIP.

The supplied macro benchmark is one revised vintage. Research results do not certify
historical first-availability or a real-time release-vintage backtest. Inference never imports
later public panels or uses another unit to obtain a specific target answer.
Read the official docs/ARTIFACT-POLICY.md before producing a future submission descriptor.
