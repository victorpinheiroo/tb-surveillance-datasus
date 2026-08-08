---
artifact: adr
version: "1.1"
created: 2026-08-03
status: accepted
---

# ADR-004: Pipeline orchestration (GitHub Actions)

## Status

Accepted

**Date:** 2026-08-03
**Deciders:** Victor Pinheiro

## Context

The pipeline (11 scripts, 3 stages: bronze/silver/gold) had, up to this point, been run manually, script by script, with human validation at each step — deliberate, since every source and every year surfaced a particularity that required investigation (a PySUS metadata bug in 2016, legacy columns from 2015, "not identified" sentinels across three different sources, irregular SIM coverage). ADR-001 had already decided on GitHub Actions as the orchestrator (zero-cost infrastructure), but the concrete design — what to automate, at what frequency, and with what limits — had not been specified.

## Decision

**Frequency**: monthly (1st of the month, 06:00 UTC), plus on-demand manual execution (`workflow_dispatch`). Epidemiological surveillance data doesn't change on a day-to-day scale; monthly is enough to capture case consolidation without spending GitHub Actions minutes for no gain.

**Fixed, non-dynamic year window**: the automated pipeline reprocesses the same already-validated window (2015–2024), defined as a constant in `pipeline/run_pipeline.py` — it does not compute "current year" and try to extend on its own. The value of periodic execution isn't discovering new years automatically; it's **capturing consolidation of data that already exists** (2024 cases marked `provisorio` will close over time; periodically reprocessing the same window reflects that evolution without manual intervention). Extending the window to include new years (2025+) is a deliberate manual decision, subject to the same investigation applied to every new year so far — not something the cron does on its own.

**Automatic commit of artifacts**: the workflow commits `bronze/`, `silver/`, `gold/`, and `quality/logs/` back to the repository at the end of every successful run, using the `github-actions[bot]` identity (not the author's personal identity) — keeps the repository as the single source of truth for the data, consistent with ADR-001's decision to store Parquet directly in Git (validated volume ~66 MB total, well under any limit).

**Fail-fast between stages**: `pipeline/run_pipeline.py` stops execution at the first script that fails, without letting subsequent stages run on incomplete data. A bronze error should not let silver/gold run on broken bronze.

**No automated regression check in this version**: the workflow does not compare row counts between runs to detect anomalous drops (e.g., a year suddenly arriving with far fewer records than history). Considered, but deferred — see Alternatives.

## Consequences

### Positive

- Periodic reprocessing captures data consolidation (`status_maturidade` evolving from `provisorio` to `fechado`) without manual intervention, which is genuinely useful given the right-censoring pattern already documented in ADR-001.
- A fixed window avoids the risk of the automated pipeline processing a new year with an undiscovered particularity (the same pattern seen in every year investigated so far) and silently publishing an incorrect result.
- Fail-fast between stages is cheap to implement and avoids the most expensive class of error (silver/gold consuming corrupted bronze).

### Negative

- Extending the year window requires manual action — the project doesn't stay "always current" with the latest year automatically; this is a deliberate choice of safety over full automation.
- Without automated regression checking, a subtle source failure (e.g., DATASUS publishing a corrupted file for an already-validated year) would go unnoticed until a manual inspection of the quality logs.
- Automatic bot commits can add noise to the repository history (one commit per month, even when no data changed — mitigated by `git diff --staged --quiet`, which skips the commit if nothing changed).

## Alternatives Considered

### Automatically extending the year window (computing the current year)

Rejected for safety: every new year investigated in this project surfaced a particularity that only human investigation caught. Automating the extension would risk publishing undetected-problem data, contradicting the validation discipline applied throughout.

### Automated regression validation (comparing counts between runs)

Considered, but deferred to a future iteration — would add real complexity (defining "anomalous drop" thresholds per source, deciding what to do when triggered) without being strictly necessary for the first working version of orchestration. Can be revisited as an incremental improvement.

### Daily or weekly execution

Rejected as disproportionate: Brazilian epidemiological surveillance data isn't updated by the source at that cadence; more frequent execution would spend CI minutes for no information gain.

## Revision History

- **2026-08-03** — The initial `timeout-minutes: 45` was an unvalidated estimate. The first real execution on GitHub Actions was auto-cancelled by GitHub mid-run after exceeding it, partway through the SIM download stage (251 files). No partial commit resulted — the workflow's final "commit and push" step had not yet run when the cancellation occurred, so the failure mode was safe. Timeout increased to 150 minutes, based on the observed runtime, with margin. No cost impact either way — GitHub Actions minutes are free and unlimited on public repositories regardless of run duration.

## References

- ADR-001 — original decision to use GitHub Actions as a zero-cost orchestrator.
- `pipeline/run_pipeline.py`, `.github/workflows/pipeline.yml`.
