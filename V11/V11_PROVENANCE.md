# V11 preservation / provenance note

The final V11 archive existed in the prior research workspace as `V11_E2_V8_SCENARIO_BUNDLE.zip`. In this chat
session its indexed record was readable, but its raw ZIP bytes were not authorized for direct materialization into
the working container. To avoid losing the final model when preparing the GitHub-ready repository, the V11 code in
`v11_new/production_cli.py` was reconstructed from the archived source components that *were* readable:

1. `V10_SUBMITTED_PRODUCTION_CLI.py` — exact E2 90/10 numeric backbone definitions and helper conventions.
2. `V8_CHAMPION_PRODUCTION_CLI.py` — exact scenario prompt/schema, scenario cleaning rules, and centre/width transform.
3. `V11_LEVEL_REPRESENTATION_SCREEN.py` — archived V11 validation script importing the V11 numeric constants/helpers.
4. `MAKE_V11_SUBMISSION_DESCRIPTOR.py` — archived V11 descriptor generator.
5. `Agenthon_T2_V11_E2_V8_Scenario_Mixture_Retrospective_2026-10-11.pdf` — final architecture, validation and sealed-result record.

The reconstructed implementation preserves the documented V11 mechanism:

- E2 empirical joint-row daily sampler;
- EWMA60/full variance mix of 90/10;
- absolute daily-change representation for level cards;
- nested horizons;
- official reference monthly fallback;
- V8 1-4 scenario representation;
- scenario probability + per-asset `shift_sd` + `vol_scale`;
- one scenario per entire joint draw;
- short-horizon shift scaling by `h/max_h`;
- continuation fallback if House is unavailable/invalid.

Because the raw original V11 bundle could not be byte-copied in this session, this file intentionally does **not** claim
that `v11_new/production_cli.py` is byte-for-byte identical to the submitted image source. The archived submission
metadata and score remain the authoritative record of the original sealed V11.
