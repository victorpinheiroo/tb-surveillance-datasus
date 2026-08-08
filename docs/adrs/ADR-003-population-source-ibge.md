---
artifact: adr
version: "2.0"
created: 2026-08-03
status: accepted
---

# ADR-003: Population source for incidence normalization (IBGE)

## Status

Accepted

**Date:** 2026-08-03
**Deciders:** Victor Pinheiro

## Context

Calculating incidence per 100,000 inhabitants requires a population source by municipality/year. SIDRA table 6579 (population estimates for municipalities) was chosen as the primary source, but empirical validation (a real per-year download test, not just reading declared metadata) found two years missing within the project's window (2015–2024):

- **2022**: a Census year — IBGE removed the 2022 Estimates from the SIDRA calendar, replacing them with Census results (table 4714).
- **2023**: no equivalent SIDRA table. IBGE itself published the 2023 reference population using 2022 Census results, updated only for territorial boundary changes through April 30, 2023, via the Federal Official Gazette — not as a separate annual SIDRA table.

This did not surface from the table's declared metadata (which listed a nominal 2001–2025 range); it only appeared when testing a real per-year download — reinforcing the pattern already established in this project (ADR-001, ADR-002) of never trusting declared coverage without empirical testing.

## Decision

For 2022 and 2023, use the **2022 Census** value (table 4714, variable 93) as the population source — the same value for both years. This replicates the logic IBGE itself applied publicly for 2023 (2022 Census as the base, no new demographic estimate), rather than the project constructing its own interpolation or extrapolation.

Each population record carries a `_status_fonte_populacao` column (`estimativa_direta` / `proxy_censo_2022`), so any downstream analysis knows, per year, whether the population denominator came from the annual estimates series or the census proxy.

Explicitly rejected: sourcing the specific Federal Official Gazette publication with the boundary-corrected 2023 population. The precision gain (the difference between the raw Census figure and the boundary-corrected version) is marginal for a rate per 100,000 inhabitants, and the engineering cost (parsing an unstructured government gazette publication, no API) is disproportionate to the gain — the same pattern already applied to the SIM coverage gap (not chasing an alternative source to close a small gap).

Also rejected: any custom interpolation/extrapolation of 2023 population (e.g., projecting a growth trend between 2021 and 2024). This would mean the project inventing a value the source didn't provide, contrary to the decision declared from the project's start not to employ custom estimation/modeling.

## Consequences

### Positive

- The decision replicates IBGE's own public logic for 2023 rather than substituting a custom criterion.
- `_status_fonte_populacao` makes the limitation auditable by anyone consuming the gold layer, without needing to read this ADR to discover that 2022 and 2023 share the same population base.
- Consistent with the pattern already established in the project: measure and state a source limitation, rather than masking it with disproportionate refinement.

### Negative

- Any real population growth between 2022 and 2023 (even if small, given the short interval) is not captured — the 2023 incidence rate uses a denominator that is, in practice, the 2022 figure.
- If the exact precision of the 2023 boundary correction becomes relevant in the future (e.g., for a municipality that had a boundary change in that specific period), the decision would need revisiting — it was not investigated in depth, it was consciously set aside as disproportionate effort.

## Alternatives Considered

### Sourcing the Federal Official Gazette publication with the boundary-corrected 2023 population

Rejected due to the mismatch between engineering effort (scraping an unstructured source) and precision gain (marginal for this project's metric).

### Custom interpolation/extrapolation of 2023 population

Rejected for contradicting the project's decision, declared from the start, not to employ custom estimation or modeling — the project uses official data as available, rather than substituting the source with its own inference.

### Excluding 2022 and 2023 from population-normalized metrics

Considered, but rejected: 2022 and 2023 fall within the `fechado` (closed/mature) batch (ADR-001, right-censoring validated), with mature notification data — excluding population normalization for these two years would discard mature, relevant information rather than handling it with a stated limitation.

## Revision History

- **2026-08-03** — Municipality count validation found a discrepancy of exactly one code between the two sources: the estimates series lists 5,571 municipalities (2021) vs. 5,570 in the 2022 Census. Root cause: **Boa Esperança do Norte (MT), IBGE code `5101837`**, was legally created in 2000, but its emancipation was only confirmed by Brazil's Supreme Court in October 2023, with formal installation in January 2025 — during 2022 Census data collection (Aug 2022–May 2023) it did not yet exist as a separate entity (its population was counted within Sorriso/Nova Ubiratã). IBGE had already reserved the code in the territorial base used by the estimates series, but the Census did not count it separately. Decision: no special handling is built for this single case (e.g., inheriting proportional population from the origin municipalities) — the same disproportionate-effort standard applied to the Gazette boundary correction. In silver, the join between SINAN-TB notifications and population must treat `5101837`'s absence in 2022/2023 as null, explicitly flagged population — not zero, and without dropping the corresponding notification row if one exists.
- **2026-08-03** — The population bronze→silver transformation (`transform_population.py`) found 8 records with a non-numeric population value after conversion. Investigation confirmed all 8 are the same municipality (`5101837`) across 2015–2021 and 2024 (absent from 2022/2023 for the reason above), with a raw value of `"..."` — SIDRA's standard convention for "value not available." Consistent with the root cause already on record: IBGE reserves the code in the estimates base since 2015 but never published an estimated population for it while the municipality had no separate administrative status. No code change was needed — `pd.to_numeric(errors="coerce")` already converts `"..."` to `NaN`, producing the correct behavior (explicit null population) without additional handling.

## References

- SIDRA table 6579 (IBGE) — Population estimates for municipalities.
- SIDRA table 4714 (IBGE) — 2022 Demographic Census, resident population by municipality.
- ADR-001, ADR-002 — precedents for treating a source limitation as a documented decision.
