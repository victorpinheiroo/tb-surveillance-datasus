---
artifact: adr
version: "2.0"
created: 2026-08-03
status: accepted
---

# ADR-002: Case identity and deduplication in SINAN-TB

## Status

Accepted

**Date:** 2026-08-03
**Deciders:** Victor Pinheiro

## Context

The real schema survey of SINAN-TB (`docs/schema-reference-sinan-tb.md`, generated from `bronze/sinan_tb/ano=2023/data.parquet`, 109,854 records) confirmed that **the public export via PySUS contains no column with cardinality consistent with a unique case/notification identifier**. The highest-cardinality column among the 94 source columns (`ID_MN_RESI`) has only 4,268 distinct values for 109,854 rows — orders of magnitude below what unique identification would require.

The source provides `NDUPLIC_N`, a SINAN system field that flags notifications suspected of being duplicates (89.87% null — presumably populated only once the source system has already detected and marked a duplicate), but this is not a case identifier; it's a duplicate flag already resolved by the source.

This requires an explicit decision before designing the bronze→silver transformation: how to treat case identity, and how to handle case reopening/updates over time, when no reliable native key is available.

## Decision

Two deliberately separate lines of treatment:

1. **Count notification events, not unique patients.** Each SINAN-TB row is treated as a notification event. `NDUPLIC_N` is used to remove duplicates already confirmed by the source itself — no custom deduplication heuristic is applied to remove rows.

2. **A composite key (`ID_MN_RESI` + `DT_NOTIFIC` + `ANO_NASC` + `CS_SEXO`) is computed only as a data quality diagnostic, never as a filter.** Silver publishes the percentage of records sharing this combination, as an estimated upper bound on possible duplication not captured by `NDUPLIC_N` — without dropping, merging, or altering any row based on it.

There is no attempt to track the same patient across multiple notifications/years (record linkage). This is out of scope both because no reliable identifier exists and because of the project's prior decision not to employ probabilistic matching techniques (outside the declared scope of "engineering without predictive modeling").

## Consequences

### Positive

- Avoids the main identified risk: using a composite key as a de facto identifier would generate silent collisions in large municipalities (two distinct patients, same birth year, sex, and municipality, notified on the same day — statistically common, not a rare edge case), underestimating incidence with no signal that it happened.
- The separation between "what is removed" (duplicates confirmed by the source via `NDUPLIC_N`) and "what is only measured" (quasi-identifier collision) is auditable: anyone can reproduce the published percentage and understand exactly what it does and doesn't mean.
- Consistent with ADR-001: measure and state a data quality limitation explicitly, rather than masking it with a fix that looks more rigorous than it is.

### Negative

- The project cannot answer questions that would require patient identity over time (e.g., true individual re-treatment rate) — this needs to be stated as out of scope in public documentation, not left implicit.
- The "quasi-identifier collision percentage" metric is an estimated upper bound, not an exact measure of real duplication — it needs to be presented with that caveat, so it isn't read as a confirmed duplication rate.
- `NDUPLIC_N = 0`/blank means "not evaluated for duplication," not "confirmed not a duplicate" — filtering only on `= 2` captures duplicates already confirmed by the source, but doesn't guarantee the absence of unevaluated duplication. This needs to be explicit in any quality report that cites this deduplication step.

## Alternatives Considered

### Composite key as a de facto identifier (filter-based deduplication)

Rejected. Combines fields with insufficient cardinality in large municipalities; would generate systematic, silent false positives (distinct patients treated as duplicates), distorting the project's central metric (incidence per 100,000 inhabitants).

### Probabilistic record linkage across notifications (e.g., `recordlinkage`, `splink`)

Rejected for this project. Would technically address part of the patient-identity-over-time problem, but falls outside the scope declared from the start ("engineering without predictive modeling/ML") and would add complexity disproportionate to the analytical gain for the defined business questions.

### Ignore the problem (row = event, no diagnostic metric)

Considered, but rejected as less rigorous than the adopted decision: computing and publishing the quasi-identifier collision metric as a diagnostic costs very little.

## Revision History

- **2026-08-03** — `NDUPLIC_N` decoded against the SINAN data dictionary (a system field common to all conditions, internal name `tp_duplicidade`): `0`/blank = "not identified" (not evaluated), `1` = "not a duplicate" (evaluated and valid), `2` = "duplicate (do not count)". Filter rule adopted: drop only rows with `NDUPLIC_N = 2` — the only category representing a duplicate confirmed by the source itself; `0` and `1` are kept.
  **Provenance note**: this decoding comes from indexed text (Google search) of two official SINAN portal PDFs, corroborated by a peer-reviewed article (SciELO) citing the same use of the field — the `portalsinan.saude.gov.br` server did not respond when direct PDF access was attempted. Reasonable confidence (two convergent independent sources plus documented use in the literature), but weaker provenance than the `SITUA_ENCE` decoding below (confirmed by direct reading of the official PDF). Worth confirming by direct reading if the portal becomes reachable again.
- **2026-08-03** — `SITUA_ENCE` (case closure status, used both for the abandonment-rate numerator and for the SINAN×SIM reconciliation) was initially decoded for codes 1–7 only, leaving 24,251 records (2.5% of the dataset) unmapped, including codes `8`, `9`, `10`, and an isolated zero-padding artifact (`'03'`/`'04'` appearing only in 2018). Two secondary sources suggested an alternative ordering that inserted an "Abandono primário" category early in the sequence, which would have shifted codes 3–7 and meant a large share of records classified as "Óbito por Tuberculose" were actually miscategorized. This hypothesis was tested against a primary source — a direct read of `DICI_DADOS_NET_Tuberculose_23_07_2020.pdf` (Ministry of Health, SINAN Net v5.0 data dictionary), located after three earlier attempts to reach official SINAN documentation had failed. The primary source confirmed the original 1–7 mapping was correct as committed, simply incomplete: it was extended with `8 = Mudança de Esquema`, `9 = Falência`, `10 = Abandono Primário`. The `'03'`/`'04'` zero-padding was normalized to `'3'`/`'4'` before mapping. After the extension, unmapped records dropped from 24,251 to 8,358 — the remainder is entirely the `'0'` sentinel value, left intentionally unmapped (no confirmed meaning; not a data error, consistent with the "not identified" pattern seen elsewhere in this source).

## References

- `docs/schema-reference-sinan-tb.md` — schema survey that motivated this decision.
- ADR-001 — precedent for treating a data quality limitation as a documented decision rather than a silent fix (right-censoring, irregular SIM coverage).
