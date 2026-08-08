# TB Surveillance in Brazil — SINAN × SIM × IBGE

End-to-end data engineering pipeline over real Brazilian public health data, built as technical proof for international remote Data Engineering roles — not as an epidemiological study.

**[→ Interactive dashboard](https://victorpinheiroo.github.io/tb-surveillance-datasus/)**

## Scope

This project uses real Brazilian public health surveillance data — SINAN-TB case notifications, SIM mortality records, and IBGE population estimates — rather than a pre-cleaned dataset. The data carries genuine cross-source inconsistency, undocumented sentinel values for missing data, and irregular coverage between sources, which the pipeline treats as engineering problems to be identified and documented, not edge cases to smooth over silently.

The scope is data engineering: ingestion, schema validation across sources, deduplication, structured quality logging, and orchestration. The analytical layer — incidence rates, treatment outcomes, cross-source reconciliation — uses descriptive statistics only, no predictive modeling.

## What the pipeline answers

1. **Tuberculosis incidence** per 100,000 inhabitants, by municipality/state/year (SINAN-TB × IBGE population).
2. **Treatment abandonment rate**, by state/year — a serious clinical indicator, associated with disease progression and drug resistance.
3. **Estimated underreporting**, cross-referencing TB deaths notified in SINAN against TB deaths registered in SIM — two independent sources of the same event.

## Architecture

Medallion (bronze / silver / gold), with decisions documented in [ADRs](docs/adrs/):

```
Sources (PySUS, SIDRA/IBGE API)
        ↓
    BRONZE   — faithful copy of the source, immutable, with provenance metadata
        ↓
    SILVER   — typed, deduplicated, decoded, with an SCD2 municipality dimension
        ↓
    GOLD     — aggregates: incidence, abandonment, SINAN×SIM reconciliation
        ↓
  GitHub Pages (dashboard, DuckDB-WASM reading Parquet directly from the repo)
```

Orchestrated via GitHub Actions (monthly + manual trigger), 100% free infrastructure — no payment method on file for any continuously-running service (see [ADR-001](docs/adrs/ADR-001-scope-source-infrastructure.md)).

## Data sources

| Source | Content | Window | Access |
|---|---|---|---|
| SINAN-TB | Tuberculosis case notifications | 2015–2024 | PySUS |
| SIM | Deaths (filtered to ICD-10 A15-A19) | 2015–2024, 251/270 state×year combinations | PySUS |
| IBGE/SIDRA | Resident population by municipality | 2015–2024 | SIDRA API |

## Engineering decisions

Six ADRs document context, alternatives considered, and trade-offs for each decision:

- **[ADR-001](docs/adrs/ADR-001-scope-source-infrastructure.md)** — source selection, right-censoring empirically validated (2024 data still consolidating), irregular SIM coverage (7% gaps, no single pattern), SCD2 kept by design even without observed need in the current window.
- **[ADR-002](docs/adrs/ADR-002-case-identity-deduplication.md)** — SINAN-TB has no unique case identifier; deliberate decision not to build a synthetic key (a quasi-identifier collision approach was tested and rejected for producing false positives in large municipalities).
- **[ADR-003](docs/adrs/ADR-003-population-source-ibge.md)** — 2022/2023 had no population estimate table available; the solution replicates the logic IBGE itself used publicly (2022 Census as proxy), not an invented interpolation.
- **[ADR-004](docs/adrs/ADR-004-orchestration.md)** — orchestration uses a fixed year window (does not auto-extend), because every new year investigated in this project surfaced a quirk that only human investigation caught.

## Data quality findings

- **Metadata bug in PySUS's remote catalog**: `TUBEBR16.parquet` existed but returned empty — root cause identified (a null `group_id` silently excluding the file from filtered queries), documented in [`docs/known-issues.md`](docs/known-issues.md).
- **Three sources, three different conventions for "missing value"**: SINAN-TB uses `"0"`, IBGE/SIDRA uses `"..."`, SIM uses `UF+0000` — same semantic idea, incompatible syntax, each identified and handled explicitly.
- **A hypothesis tested and partially refuted, reported as such**: an attempt to explain 4 anomalous cases in the SINAN×SIM reconciliation by SIM maturity lag did not hold up against the data — reported as-is, not forced to fit a clean narrative.
- **Official data dictionary (`SITUA_ENCE`) confirmed by direct reading of a Ministry of Health PDF**, after two secondary sources disagreed with each other on the correct category ordering.

See [`docs/known-issues.md`](docs/known-issues.md) for the full list.

## Stack

Python 3.13 · pandas/pyarrow · PySUS · sidrapy (SIDRA API) · Parquet (zstd) · GitHub Actions · DuckDB-WASM · Azure (Bicep, one-time demonstration — see `infra/`)

## Running it

```bash
pip install -r requirements.txt
python pipeline/run_pipeline.py --stage all      # full bronze -> silver -> gold
python pipeline/run_pipeline.py --stage bronze   # ingestion only
```

## Repository structure

```
ingestion/               # bronze extraction (SINAN-TB, SIM, IBGE)
transformation/
  bronze_to_silver/      # cleaning, deduplication, SCD2
  silver_to_gold/        # analytical aggregates
pipeline/                # orchestrator
docs/adrs/                    # Architecture Decision Records
docs/known-issues.md          # data quality findings
docs/schema-reference-*.md    # real schema documented per source
quality/logs/             # structured log per execution
infra/                    # Azure IaC (one-time demonstration)
```

## Known limitations

- Case identity is per notification event, not per unique patient (see ADR-002).
- 7% of SIM state×year combinations have no data available from the source (not backfilled from an alternative source — see ADR-001).
- Municipality-level abandonment rate is statistically unstable for ~90% of municipalities (small sample); state-level is the recommended view.
- 4 residual cases in the SINAN×SIM reconciliation remain without a complete explanation.

---

Victor Pinheiro — [linkedin.com/in/victorpinheiroo](https://linkedin.com/in/victorpinheiroo) · [github.com/victorpinheiroo](https://github.com/victorpinheiroo)

*[Versão em português](README.pt-BR.md)*
