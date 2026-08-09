# Schema Reference — SINAN-TB (bronze)

Real schema survey of SINAN-TB, generated from data already extracted in
`bronze/sinan_tb/ano=2023/data.parquet` — not from hypothesis or third-party
documentation. Serves as a reference for designing the bronze→silver
transformation with confirmed field names.

**Source:** `bronze/sinan_tb/ano=2023/data.parquet`
**Why 2023:** most recent year of the "closed" batch (see ADR-001 —
right-censoring empirically validated), and the most stable schema — avoids
the 3 legacy columns present in 2015-2018, absent from 2019 onward
(`AGRAVOUTDE`, `EXTRAPUL_O`, `OUTRAS_DES`; confirmed by real inspection of
all 10 years of bronze, not just the original spike's 2015/2019/2023
sample).
**Rows:** 109,854
**Total columns:** 97 (94 from the original source schema + 3 provenance
columns added by the ingestion script)

**"% Null" methodology:** same logic already validated in the `DT_ENCERRA`
spike (see ADR-001) — an empty string after `strip()` counts as missing, not
just `NaN`. SINAN-TB's entire schema is `dtype=object` (text), so this
distinction matters for practically every column, not just date fields.

## Key fields identified

### Unique notification/case identifier

**Not found.** No column comes close to being unique per row — with 109,854
records, the highest cardinality among all 94 source columns is
`ID_MN_RESI` (municipality of residence), with only 4,268 distinct values.
There's no `NU_NOTIFIC`-like field in this export. `NDUPLIC_N` (89.87% null,
values `0`/`1`/`2`) appears to be a duplicate-notification *flag*, not an
identifier.

**Implication for silver:** either (a) generate a surrogate row key at
ingestion/bronze→silver, explicitly documenting it as synthetic and not
sourced, or (b) investigate whether the original SINAN/DBF has an internal
record number that PySUS discards during Parquet conversion — requires an
explicit decision before designing joins or dedup logic in silver.

### Municipality of notification

**`ID_MUNICIP`** — IBGE code (7 digits), 0% null, 3,968 unique values.
Examples: `3509601`, `3505708`, `3513801`, `4118204`, `3515707` (the first 2
digits match `SG_UF_NOT`: `35`=SP, `41`=PR).

There is also `ID_MUNIC_A` (0.29% null, 3,980 unique) — same code pattern,
appears to be the "updated" notification municipality (post-transfer within
the same record); and `ID_MUNIC_2` (23.56% null) and `MUN_TRANSF` (95.10%
null), tied to case-transfer workflows. Only `ID_MUNICIP` is needed for the
project's business question (incidence by municipality/state); the rest are
candidates to leave out of silver or become audit metadata, not analytical
data.

### Patient's municipality of residence

**`ID_MN_RESI`** — IBGE code (7 digits), 0% null, 4,268 unique values (more
granular than `ID_MUNICIP`, expected — more people reside outside where they
were notified than the reverse). This is the relevant field for SINAN×SIM
geographic reconciliation (SIM deaths are also attributed to municipality of
residence).

### Case closure status

**`SITUA_ENCE`** — 4.30% null (2023 sample), up to 10 distinct numerically
coded values across the 10 years (2015-2024). It's the field paired with
`DT_ENCERRA` (already validated in the spike): `DT_ENCERRA` says *when* the
case was closed, `SITUA_ENCE` says *how* (cure, abandonment, death, etc.).

**Domain dictionary confirmed (2026-08-03, direct reading of the official
Ministry of Health PDF — SINAN Net v5.0 data dictionary, field 62; see
`docs/known-issues.md` for the exact reference and the difficulty accessing
it):**

| Code | Meaning |
|---|---|
| 1 | Cure |
| 2 | Abandonment |
| 3 | Death from Tuberculosis |
| 4 | Death from other causes |
| 5 | Transfer |
| 6 | Change of Diagnosis |
| 7 | Drug-resistant TB (TB-DR) |
| 8 | Regimen Change |
| 9 | Treatment Failure |
| 10 | Primary Abandonment |

Values `03`/`04` observed only in 2018 are zero-padding of the same code
`3`/`4`, not new categories (normalized in silver via `lstrip('0')`). Value
`0` (present only in 2015-2017, 8,358 records) is not part of this confirmed
domain and remains unmapped — not decoded from memory.

Two similar-looking fields that are **not** the final closure field — kept
out of that role:
- `SITUA_9_M` (99.98% null) and `SITUA_12_M` (100.00% null, with very rare
  exceptions) — follow-up status at fixed treatment checkpoints (9 and 12
  months), not the case's final outcome.
- There is no `TPCASO` column in this schema.

## Full table — source columns (94)

| Column | Type (dtype) | % Null | Unique values (sample) |
|---|---|---|---|
| `TP_NOT` | object | 0.00% | `2` |
| `ID_AGRAVO` | object | 0.00% | `A169` |
| `DT_NOTIFIC` | object | 0.00% | `20230516`, `20230317`, `20230619`, `20231208`, `20230807` |
| `NU_ANO` | object | 0.00% | `2023`, `2024`, `2025` |
| `SG_UF_NOT` | object | 0.00% | `35`, `41`, `29`, `15`, `23` |
| `ID_MUNICIP` | object | 0.00% | `3509601`, `3505708`, `3513801`, `4118204`, `3515707` |
| `ID_REGIONA` | object | 40.69% | `135`, `140`, `148`, `152`, `153` |
| `DT_DIAG` | object | 0.00% | `20230512`, `20230316`, `20230619`, `20231206`, `20230804` |
| `ANO_NASC` | object | 0.43% | `1963`, `1965`, `1984`, `1961`, `2001` |
| `NU_IDADE_N` | object | 0.04% | `4059`, `4057`, `4038`, `4062`, `4022` |
| `CS_SEXO` | object | 0.00% | `M`, `F`, `I` |
| `CS_GESTANT` | object | 0.01% | `6`, `5`, `9`, `4`, `1` |
| `CS_RACA` | object | 1.68% | `4`, `1`, `5`, `9`, `2` |
| `CS_ESCOL_N` | object | 7.55% | `9`, `7`, `5`, `1`, `3` |
| `SG_UF` | object | 0.00% | `35`, `41`, `29`, `15`, `23` |
| `ID_MN_RESI` | object | 0.00% | `3509601`, `3505708`, `3513801`, `4118204`, `3515707` |
| `ID_RG_RESI` | object | 41.03% | `135`, `140`, `148`, `152`, `154` |
| `ID_PAIS` | object | 22.72% | `1`, `68`, `138`, `126`, `199` |
| `NDUPLIC_N` | object | 89.87% | `1`, `0`, `2` |
| `IN_VINCULA` | object | 90.31% | `1`, `0` |
| `DT_DIGITA` | object | 22.72% | `20231208`, `20230310`, `20230607`, `20230717`, `20230726` |
| `DT_TRANSUS` | object | 93.88% | `20231208`, `20230820`, `20240110`, `20230523`, `20230927` |
| `DT_TRANSDM` | object | 99.06% | `20240410`, `20230502`, `20230426`, `20240417`, `20240209` |
| `DT_TRANSSM` | object | 43.58% | `20230321`, `20240216`, `20230801`, `20240126`, `20230814` |
| `DT_TRANSRM` | object | 100.00% | *(no values — 100% null)* |
| `DT_TRANSRS` | object | 98.46% | `20230727`, `20230510`, `20230426`, `20240119`, `20230616` |
| `DT_TRANSSE` | object | 64.38% | `20240520`, `20240822`, `20240815`, `20231027`, `20250604` |
| `CS_FLXRET` | object | 100.00% | *(no values — 100% null)* |
| `FLXRECEBI` | object | 100.00% | *(no values — 100% null)* |
| `MIGRADO_W` | object | 100.00% | *(no values — 100% null)* |
| `ID_OCUPA_N` | object | 100.00% | *(no values — 100% null)* |
| `TRATAMENTO` | object | 0.00% | `1`, `3`, `5`, `2`, `4` |
| `INSTITUCIO` | object | 99.98% | `9`, `1`, `2` |
| `RAIOX_TORA` | object | 1.88% | `4`, `1`, `3`, `2` |
| `TESTE_TUBE` | object | 99.98% | `4`, `3`, `1`, `2` |
| `FORMA` | object | 0.02% | `1`, `2`, `3` |
| `EXTRAPU1_N` | object | 0.00% | `.`, `1`, `3`, `8`, `4` |
| `EXTRAPU2_N` | object | 99.86% | `6`, `7`, `10`, `5`, `3` |
| `AGRAVAIDS` | object | 1.62% | `2`, `9`, `1` |
| `AGRAVALCOO` | object | 1.61% | `2`, `1`, `9` |
| `AGRAVDIABE` | object | 1.84% | `2`, `9`, `1` |
| `AGRAVDOENC` | object | 2.14% | `2`, `9`, `1` |
| `AGRAVOUTRA` | object | 32.86% | `9`, `2`, `1` |
| `BACILOSC_E` | object | 0.02% | `3`, `2`, `1`, `4` |
| `BACILOS_E2` | object | 99.98% | `2`, `3`, `1` |
| `BACILOSC_O` | object | 77.27% | `3`, `1`, `2` |
| `CULTURA_ES` | object | 0.02% | `4`, `1`, `3`, `2` |
| `CULTURA_OU` | object | 81.20% | `4`, `2`, `1`, `3` |
| `HIV` | object | 0.26% | `2`, `4`, `3`, `1` |
| `HISTOPATOL` | object | 6.97% | `5`, `2`, `1`, `4`, `3` |
| `DT_INIC_TR` | object | 4.59% | `20230516`, `20230316`, `20230619`, `20231208`, `20230807` |
| `RIFAMPICIN` | object | 99.99% | `1`, `2` |
| `ISONIAZIDA` | object | 99.99% | `1`, `2` |
| `ETAMBUTOL` | object | 99.99% | `2`, `1` |
| `ESTREPTOMI` | object | 99.99% | `2` |
| `PIRAZINAMI` | object | 99.99% | `1`, `2` |
| `ETIONAMIDA` | object | 99.99% | `1`, `2` |
| `OUTRAS` | object | 99.99% | `2`, `1` |
| `TRAT_SUPER` | object | 77.25% | `1`, `9`, `2` |
| `NU_CONTATO` | object | 3.52% | `1`, `0`, `3`, `4`, `9` |
| `DOENCA_TRA` | object | 99.98% | `2` |
| `SG_UF_AT` | object | 0.29% | `35`, `41`, `29`, `15`, `23` |
| `ID_MUNIC_A` | object | 0.29% | `3509601`, `3505708`, `3513801`, `4118204`, `3515707` |
| `DT_NOTI_AT` | object | 23.00% | `20231208`, `20230304`, `20230603`, `20230710`, `20230721` |
| `SG_UF_2` | object | 23.31% | `41`, `29`, `15`, `23`, `27` |
| `ID_MUNIC_2` | object | 23.56% | `4118204`, `2902708`, `1502608`, `2306108`, `2703809` |
| `BACILOSC_1` | object | 23.64% | `1`, `2`, `3`, `4` |
| `BACILOSC_2` | object | 28.49% | `1`, `2`, `3`, `4` |
| `BACILOSC_3` | object | 31.79% | `2`, `3`, `4`, `1` |
| `BACILOSC_4` | object | 34.94% | `3`, `2`, `4`, `1` |
| `BACILOSC_5` | object | 37.60% | `3`, `2`, `4`, `1` |
| `BACILOSC_6` | object | 40.55% | `3`, `2`, `4`, `1` |
| `TRATSUP_AT` | object | 21.32% | `2`, `1`, `9` |
| `DT_MUDANCA` | object | ~100.00% | `18991230`, `20231227` *(≈2 non-empty values in 109,854 rows)* |
| `NU_COMU_EX` | object | 16.34% | `1`, `0`, `2`, `4`, `3` |
| `SITUA_9_M` | object | 99.98% | `12`, `2`, `5`, `1`, `3` |
| `SITUA_12_M` | object | ~100.00% | `5`, `11`, `1` |
| `SITUA_ENCE` | object | 4.30% | `1`, `5`, `3`, `7`, `4` |
| `DT_ENCERRA` | object | 4.73% | `20240115`, `20240109`, `20240415`, `20240207`, `20230310` |
| `TPUNINOT` | object | 25.40% | `36`, `5`, `2`, `4`, `39` |
| `POP_LIBER` | object | 1.90% | `2`, `9`, `1` |
| `POP_RUA` | object | 2.20% | `2`, `1`, `9` |
| `POP_SAUDE` | object | 2.25% | `3`, `2`, `9`, `1` |
| `POP_IMIG` | object | 2.44% | `2`, `1`, `9`, `3` |
| `BENEF_GOV` | object | 26.89% | `2`, `9`, `1` |
| `AGRAVDROGA` | object | 2.03% | `2`, `9`, `1` |
| `AGRAVTABAC` | object | 2.12% | `1`, `2`, `9` |
| `TEST_MOLEC` | object | 5.23% | `1`, `5`, `2`, `3`, `4` |
| `TEST_SENSI` | object | 44.71% | `5`, `7`, `3`, `6`, `1` |
| `ANT_RETRO` | object | 75.34% | `2`, `1`, `9` |
| `BAC_APOS_6` | object | 70.12% | `3`, `4`, `2`, `1`, `6` |
| `TRANSF` | object | 91.97% | `3`, `2`, `1`, `9`, `4` |
| `UF_TRANSF` | object | 94.78% | `42`, `29`, `27`, `35`, `43` |
| `MUN_TRANSF` | object | 95.10% | `42`, `29`, `27`, `35`, `43` |

## Provenance columns (added by ingestion, not part of the source schema)

| Column | Type (dtype) | % Null | Unique values (sample) |
|---|---|---|---|
| `_source_dataset` | object | 0.00% | `SINAN-TUBE-2023` |
| `_ingested_at` | object | 0.00% | `2026-08-03T00:30:20.345312+00:` |
| `_status_maturidade_estimado` | object | 0.00% | `fechado` |

## General observations

- **The entire schema is `dtype=object`** (text) — including numeric and
  date fields (`YYYYMMDD` as a string). Type conversion is silver's explicit
  responsibility, not something that comes pre-done from bronze.
- Columns that are 100% (or nearly 100%) null in this year (`DT_TRANSRM`,
  `CS_FLXRET`, `FLXRECEBI`, `MIGRADO_W`, `ID_OCUPA_N`, `DT_MUDANCA`,
  `SITUA_12_M`) are candidates for dropping in silver, but that wasn't
  decided here — this document is only a survey; the decision on which
  columns enter silver is separate (see ADR-001 for the precedent of
  documented column dropping, applied to the 3 legacy columns present in
  2015-2018 and absent from 2019 onward).
- Several distinct `SG_UF_*` / `ID_MUNIC_*` pairs (`_NOT`, `_AT`, `_2`,
  `_TRANSF`) suggest SINAN tracks case transfers between notifying units —
  worth designing silver assuming only the "original notification" pair
  (`ID_MUNICIP`/`SG_UF_NOT`) and the "residence" pair (`ID_MN_RESI`/`SG_UF`)
  are needed for the project's business questions, unless an explicit
  decision expands that scope.
