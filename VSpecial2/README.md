## Executive summary (read this first)

VSpecial2 audits the submitted VSpecial and adds optional numerical research candidates.
Default `price` repairs input handling and House context, keeping ordinary numeric forecasts.
No submitted ZIP, image digest or Codabench entry is changed by this research package.

### Build and use

```powershell
docker build --platform linux/amd64 -t agenthon-vspecial2:research .
docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=512m `
  --mount "type=bind,source=C:\absolute\unit,target=/input,readonly" `
  --mount "type=bind,source=C:\absolute\empty-output,target=/output" `
  agenthon-vspecial2:research forecast --panels /input/panels --text /input/text `
  --asof YYYY-MM-DD --out /output/forecast.parquet
```

First command is forecast; no ENTRYPOINT. Exactly three forecast files, 2,000 default draws.
Monthly output keys remain unchanged and explicit observation periods determine actual steps.

### Accepted repairs

- Apply the source-date cutoff before aligning monthly observations by calendar month.
- Refuse duplicate observations in one month at the numerical helper level too. The existing
  official CLI already rejected this ambiguity; it was not a newly discovered intake failure.
- Remove long jumps across internal daily gaps even when the latest observation is fresh.
  Preserve individual current anchors and the first valid factor-return row.
- Use exact calendar continuity and actual per-asset step counts in monthly historical folds.
- Give House actual observed anchors, real recent/full volatility, units, baseline intervals
  and historical cross-asset correlation. Real House accuracy remains untested.
- Neutral text is exact identity. A extreme affine text shift crossing zero on known positive
  FX/price targets uses a positive log-space fallback with the same scenario assignments.

### Optional research modes

- `--mode cpi_soft`: mix inflation candidates only for CPI_ALL; other series remain on repaired
  VSpecial. Positive primary results did not reproduce on every horizon grid. Research only.
- `--mode soft`: inflation mixture for all four price indices; PCE losses increased.
- `--mode calibrated`: rolling past-fold predictive-width calibration of that mixture.
- `--mode term`: daily variance gradually returns to its historical longer-run level.
- `--mode daily_calibrated`: past-fold scale/drift menu with conservative wins/gain guards.
- `--mode geometric`: proportional CPI/PCE growth using the same historical trend menu.
- Prior research modes and the previous VNext `adaptive` mode remain available.

Weights, regression parameters and calibration fit only this task's supplied history. No saved
benchmark losses or target tables enter inference. The selector and local reference expectation
are research surrogates, not the official M0 scale or Codabench score.

The House client still makes at most one organizer-routed call. `--text-policy guarded` is the
default; `v11` and `off` remain available. Mock tests establish plumbing, not text uplift.

### Provenance and limits

The baseline source matches submitted immutable digest
68d85e885da895a9559996675a44f5bbae289538dd03be1ecc0f97e959d6e821.
Official helpers and v11_new are unchanged. MIT and common CC BY-NC 4.0 licences are included.
One revised macro vintage and already-explored 2020-2024 data bound the claims. GDP is still
not supplied for accuracy tests. Read the outer Korean result tables before choosing a mode.
This package contains research only, without a submission descriptor or team claim.
