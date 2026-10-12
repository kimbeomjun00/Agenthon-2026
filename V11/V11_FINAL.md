# V11 FINAL — Agenthon 2026 Track 2

This folder/repository snapshot preserves the final champion used at the end of the Track-2 research cycle.

## Champion

- **Candidate:** V11 — E2 90/10 numeric backbone + V8 text scenario mixture
- **Development submission score:** **-2.2219**
- **Submission ID:** `977123`
- **Submitted archive:** `submission_v11_e2_v8_01.zip`
- **Image repository:** `kbj710211/agenthon-t2-v11`
- **Image digest:** `sha256:6b10442fe81b10461ce56066ea573238842ff66bed9bce83faa5e35c05d68bc6`
- **Status:** frozen champion; later V13/WIDTH085 and Gaussian WIDTH090 experiments did not replace it.

The public leaderboard snapshot recorded around the same time displayed `lifeisluck` at `-2.2172`; the
submission-row score above is the comparison reference used in the research record.

## Architecture

```text
cutoff-valid panel history
        |
        v
E2 empirical joint-row sampler
full-history z standardization
current var = 0.90*EWMA60 + 0.10*full
nested multi-horizon path
        |
        +-------------------------------+
        |                               |
        |                     cutoff-valid text corpus
        |                               |
        |                               v
        |                     House: 1-4 scenarios
        |                     prob + shift_sd + vol_scale
        |                               |
        +---------------+---------------+
                        v
            one scenario per joint draw
            centre + width transform
                        |
                        v
                forecast.parquet
```

Important design choice: text is **not** compressed to a single direction label. It changes scenario
probability, centre and width jointly. If House fails, the continuation scenario leaves the numeric forecast unchanged.

## Files added to the official public repository

- `v11_new/production_cli.py` — self-contained V11 implementation for future inspection/work.
- `Dockerfile.v11` — image definition that exposes the V11 `forecast` verb.
- `V11_SMOKE.py` — local OFF vs mock-scenario plumbing smoke.
- `V11_BATCH_VALIDATE.py` — structural all-practice-unit validator.
- `V11_LEVEL_REPRESENTATION_SCREEN.py` — archived V11 ABS-vs-REL level representation screen.
- `MAKE_V11_SUBMISSION_DESCRIPTOR.py` — archived V11 Development descriptor generator.
- `docs/v11/Agenthon_T2_V11_Retrospective_2026-10-11.pdf` — final research record.
- `V11_PROVENANCE.md` — preservation/reconstruction notes.

## Local use

From the repository root:

```powershell
python .\V11_SMOKE.py --family T2-F3
python .\V11_BATCH_VALIDATE.py
```

Direct forecast invocation:

```powershell
python -m v11_new.production_cli `
  --panels units\<UNIT>\panels `
  --text units\<UNIT>\text `
  --asof YYYY-MM-DD `
  --card units\<UNIT>\card.toml `
  --out out\forecast.parquet
```

Docker:

```powershell
docker build --platform linux/amd64 -f .\Dockerfile.v11 -t agenthon-t2-v11:local .
```

## Research status

Treat V11 as a **frozen comparison checkpoint**. The point of preserving it here is to let another GPT/app inspect,
explain, refactor, reproduce, or extend the final working architecture without needing the old chat history.
