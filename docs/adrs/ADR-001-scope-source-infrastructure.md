---
artifact: adr
version: "2.0"
created: 2026-07-29
status: accepted
---

# ADR-001: Project scope, data source, and execution infrastructure

## Status

Accepted — empirically validated 2026-08-02 via `00_explore_assumptions.py`. See Revision History for the amendment trail.

**Date:** 2026-07-29
**Deciders:** Victor Pinheiro

## Context

The goal of this project is to build a public, end-to-end data engineering pipeline over Brazilian health data, as technical proof for international remote Data Engineering roles. The declared scope is engineering — ingestion, handling of inconsistent data, quality, and governance — not data science; the project includes no predictive modeling.

Two concrete constraints shaped this decision:

1. The dataset cannot be generic or tutorial-grade (e.g., Titanic). It needs real complexity — dirty data, underreporting, and cross-source inconsistency — defensible in a technical interview.
2. The project cannot generate infrastructure cost or unexpected billing risk. This rules out any "always-on" cloud service billed by reserved capacity or uptime, and reduces tolerance for any configuration that depends on staying within a free-tier quota without constant supervision.

## Decision

The project uses **tuberculosis notification data from SINAN Net, cross-referenced against SIM (Mortality Information System)**, over the window **2015–2023**. The window start was set to 2015 to avoid mixing a 2014 notification form version with the schema used from 2015 onward. The window end respects a consolidation margin of roughly two to three years before the project's execution date (see Revision History for the empirical basis).

Years outside this window (2024 onward) are not silently dropped: the gold layer carries a `status_maturidade` column (`fechado` / `provisorio`) per year, computed from the consolidation rule above. This allows extending the analysis to more recent years later, with an explicit flag that the data is still consolidating, rather than treating the cutoff as if those years didn't exist.

**Questions the pipeline answers:**
- Epidemiological: what is TB incidence and treatment abandonment rate, by municipality/state, over time?
- Meta-question (the project's differentiator): what is the difference between TB cases closed as deaths in SINAN and TB deaths registered in SIM, by region — an estimate of underreporting via reconciliation of two independent sources.

Extraction via the `PySUS` library (SINAN and SIM).

**Execution infrastructure is split into two categories:**

- **What runs permanently (the portfolio's actual production)**: 100% GitHub-native. Data (bronze/silver/gold, as Parquet) is versioned directly in the Git repository — validated real volume (~25 MB for 9 years of SINAN-TB) is far below any threshold that would justify Git LFS or GitHub Releases, so those tools were rejected as unnecessary, not unavailable. Orchestration via scheduled GitHub Actions; the final dashboard is published as a static site via GitHub Pages. None of these components has a cost, and none requires a payment method on file.
- **What demonstrates cloud competency (Azure)**: a reference architecture (ADLS Gen2 + Synapse Serverless SQL + Microsoft Purview) written as Infrastructure as Code (Bicep) and versioned in the repository, but not kept running continuously. Validating that the IaC works happens once — stand up the resources, run the pipeline against them, capture evidence (screenshots/short video), and tear the resources down (`az group delete`) immediately after. Cost exposure is one-time, brief, and directly controlled — never a forgotten running service.

## Consequences

### Positive

- Choosing TB with SINAN/SIM reconciliation gives the project a data quality problem that is citable and documented in Brazilian public health literature, not a generic "dirty data" claim.
- Reconciling two independent sources (SINAN and SIM) is a real MDM/record-linkage exercise, directly aligned with prior MDM and governance experience — stronger evidence of competence than handling a single source.
- Infrastructure cost is guaranteed zero for the component permanently visible to recruiters (GitHub), removing the risk of unexpected billing.
- Separating "what runs continuously" (GitHub) from "what demonstrates cloud" (Azure, one-time exposure) allows claiming real Azure experience without taking on continuous financial risk.

### Negative

- At a real volume of ~25 MB, the full Medallion architecture (bronze/silver/gold) is disproportionate to the data volume itself; this needs to be stated explicitly in the project's public documentation — the architecture demonstrates engineering practice, not a scale requirement — so it isn't read as over-engineering by a technical reviewer.
- The Azure demonstration is not always-on: a reviewer cannot access the cloud architecture at any time, only recorded evidence that it worked. This is weaker proof than a permanently accessible environment, and needs to be offset by good execution evidence (video/screenshots).
- Git LFS and GitHub Releases have size limits (1 GB and 2 GB per file, respectively); if raw data volume for the chosen window ever exceeds that, sampling or aggregation before versioning would need to be an explicit, documented decision — not a silent cutoff.

### Neutral

- The decision to exclude predictive modeling is maintained; the final analysis layer uses descriptive statistics only (rates per 100,000 inhabitants, cross-source comparison).

## Alternatives Considered

### SINAN Dengue/Chikungunya as the primary source

Considered initially for well-documented data quality issues and topical relevance (climate change, recurring epidemics). Rejected in favor of TB because dengue's underreporting problem is mostly field-completeness within a single source, while TB allows reconciliation between two independent sources (SINAN × SIM) — a richer engineering problem, and a better match for an MDM-focused profile.

### Pre-aggregated sources (WHO, Our World in Data)

Rejected for leaving little real engineering work — cleaning and reconciliation are already done by a third party, weakening the competence this project is meant to demonstrate.

### Always-on cloud infrastructure (Synapse dedicated pool, Fabric capacity, a permanent Spark cluster)

Rejected for generating fixed cost regardless of usage, incompatible with the zero-cost constraint. Also rejected: keeping serverless resources (e.g., Synapse Serverless, Blob Storage within free tier) running continuously without supervision, because sources disagree on Azure's billing behavior when a free-tier quota is exceeded, and the cost of being wrong is financial — not worth gambling for a portfolio project.

## Revision History

- **2026-07-29** — Original window (2014–2023) revised to 2015–2023 after identifying that 2015 introduced a notification form update (SINAN Net v5.0) that 2014 predates, and that SIM-style sources carry a multi-year consolidation lag affecting the most recent years.
- **2026-08-02** — Empirical validation (`00_explore_assumptions.py` spike, run against real PySUS data) confirmed right-censoring: `DT_ENCERRA` fill rate was 95.9% (2015), 97.0% (2019), 95.3% (2023), and 85.9% (2024). The drop concentrates in 2024 (2 years old) while 2023 (3 years old) is already mature — enough to validate 2015–2023 as `fechado` and any year ≥2024 as `provisorio`, though not enough to pin the exact threshold between 2 and 3 years.
- **2026-08-02** — Real compressed volume (Parquet, zstd) measured at ~2–3 MB/year, ~25 MB for the full 2015–2023 window — well under Git LFS or GitHub Releases thresholds, eliminating the need for either.
- **2026-08-02** — SIM coverage gaps discovered: 19 of 270 state×year combinations (7%) have no file available in the PySUS catalog, spread across 8 states with no single pattern (rules out a state-specific cause such as an alternate mortality data pipeline for São Paulo). Decision: gaps are not backfilled from an alternative source; a `status_cobertura_sim` column is carried through silver/gold, and any national aggregate must state the coverage percentage it's based on. A separate PySUS metadata bug was found and documented in `docs/known-issues.md` (a null `group_id` on one 2016 file silently excluded it from filtered queries) — a third-party dependency issue, distinct from SIM's coverage gaps.
- **2026-08-03** — Corrected an earlier, factually wrong claim in this ADR that the legacy columns `AGRAVOUTDE`, `EXTRAPUL_O`, `OUTRAS_DES` were exclusive to 2015. They are present 2015–2018 and absent from 2019 onward; the original spike sampled only 2015, 2019, and 2023, missing the intermediate years. The decision to drop these columns in silver stands regardless (none are needed for the project's business questions).
- **2026-08-03** — SCD Type 2 for the municipality dimension was originally justified by general domain knowledge (IBGE codes change over time), not by evidence in this project's data. Empirical validation against 10 years of SINAN-TB and both IBGE population sources found zero municipality code changes within the 2015–2024 window, beyond the already-documented Boa Esperança do Norte case (a new municipality being recognized, not a recode — see ADR-003). SCD2 is kept, re-justified on different grounds: the pipeline is designed to be re-run as future years are published, and municipality recoding is a real, decades-documented phenomenon in Brazil — simply not observed in this specific sample.
- **2026-08-03** — SIM maturity hypothesis tested and not confirmed. `status_maturidade_sim` was added (a conservative rule, the same ~2-year criterion already used for SINAN-TB) to test whether 4 cases where SINAN > SIM in the reconciliation (out of 251 state×year combinations with coverage) were explained by SIM's own consolidation lag. Result: only 1 of the 4 cases (PB/2024) falls in a provisional year; the other 3 (AL/2018, AP/2023, MS/2023) persist even in years classified as `fechado` by that rule — the maturity hypothesis does not explain most of the reversed cases. Magnitude is small in all 4 cases (-2 to -12 deaths), with no clear geographic or temporal pattern identified. Treated as an unresolved residual statistical anomaly, documented explicitly — not investigated further beyond this point, given the disproportion between additional effort and the volume involved (4 of 251 combinations, 1.6%). `status_maturidade_sim` remains in the gold table as useful information, even though it does not fully explain the finding.

## References

- Pinheiro RS, Andrade VL, Oliveira GP. "Subnotificação da tuberculose no Sistema de Informação de Agravos de Notificação (SINAN)." Cad Saúde Pública 2012; 28:1559-68.
- "Sistema de Informação de Agravos de Notificação (Sinan): principais características da notificação e da análise de dados relacionada à tuberculose." Epidemiol. Serv. Saude, Brasília, 29(1):e2019017, 2020 — reference for the 2015 schema update (version 5.0).
- Portal de Dados Abertos do Estado de Minas Gerais, "Dados de Tuberculose" dataset — reference for SIM's ~2-year consolidation lag.
- PySUS library (AlertaDengue/Fiocruz) — github.com/AlertaDengue/PySUS
- Azure free tier documentation (verify current limits before any cloud execution, as terms change frequently)
