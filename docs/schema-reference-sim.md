# Schema Reference — SIM TB deaths (bronze)

Real schema survey of SIM (deaths with a basic cause in TB), generated from
data already extracted in `bronze/sim_tb_deaths/uf=SP/ano=2022/data.parquet`
— not from hypothesis or third-party documentation. Same process already
applied to SINAN-TB (`docs/schema-reference-sinan-tb.md`), serves as a
reference for designing the SIM bronze→silver transformation with confirmed
field names.

**Source:** `bronze/sim_tb_deaths/uf=SP/ano=2022/data.parquet`
**Why SP/2022:** highest volume available among the 251 files in the SIM
bronze layer (confirmed by file size before choosing — SP/2022 is the
largest; SP/2023, which would be the most recent year/state, is one of the
19 coverage gaps already documented in ADR-001, so it doesn't exist in
bronze).
**Rows:** 1,283
**Total columns:** 90 (87 from the original source schema + 3 provenance
columns added by the ingestion script)

**"% Null" methodology:** same logic already used for SINAN-TB — an empty
string after `strip()` counts as missing, not just `NaN`. SIM's entire schema
is also `dtype=object` (text).

## Key fields identified

### Deceased's municipality of residence

**`CODMUNRES`** — 0.00% null, 215 unique values in the sample. Examples:
`354890`, `350710`, `355030`, `353060`, `354630`.

**Note — format mismatch with SINAN-TB, relevant to the requested geographic
reconciliation:** the code here has **6 digits**, not 7. This is DATASUS's
classic convention of omitting the check digit from the 7-digit IBGE code
(e.g., `355030` = São Paulo, whose full IBGE code is `3550308`). SINAN-TB
(`ID_MN_RESI`) and IBGE population (`D1C`, see `transform_population.py`)
use the full 7 digits. **A direct join between SIM and SINAN-TB/population
will silently fail or produce zero matches without normalizing this first**
— it requires an explicit decision in the transformation (most likely:
appending the check digit to SIM's `CODMUNRES`, or truncating the other
sources' codes to 6 digits; the first option is safer but requires
implementing or importing IBGE's check-digit algorithm). This isn't a data
problem, it's a transformation decision to be made — only flagged here, not
resolved.

There is also `CODMUNOCOR` (0.00% null, municipality of **occurrence** of the
death — where the death happened, not where the deceased resided) and
`CODMUNNATU` (4.29% null, municipality of **birth**). Only `CODMUNRES` is the
field relevant to the project's business question (mortality by municipality
of residence, comparable to SINAN-TB's incidence by `ID_MN_RESI`).

### Date of death

**`DTOBITO`** — 0.00% null, 353 unique values in the sample. Examples:
`16062022`, `06062022`, `19052022`, `24062022`, `31012022`.

**Note — different format from SINAN-TB:** here the format is `DDMMYYYY`
(day-month-year), not `YYYYMMDD` (year-month-day) like `DT_NOTIFIC`/
`DT_ENCERRA` in SINAN-TB. E.g., `16062022` = 06/16/2022, not "1606-02-2" nor
year 1606. Date parsing in silver needs to handle the two formats
differently — the same parse function from `transform_sinan_tb.py` can't be
reused without adjustment.

There is also `DTATESTADO` (0.08% null, the date the death certificate was
filled out — almost always the same as `DTOBITO`) and `DTCADASTRO`/
`DTRECEBIM`/`DTRECORIGA` (SIM's own administrative workflow dates, 0.00% null
each, same `DDMMYYYY` format).

### Quality/duplicate field analogous to `NDUPLIC_N`

**Not found.** None of the 87 source columns has "DUPLIC" in its name, and
there's no field equivalent to a duplicate-record flag already resolved by
the source, as exists in SINAN-TB. This is a real difference between the two
sources, not a gap in the search — it needs to be explicitly documented if
the project decides to report mortality without this kind of quality signal.

Two fields that are **not** this, to avoid confusion:
- **`TIPOBITO`** — death type classification (fetal/non-fetal), not
  duplication. In this sample it's `2` (non-fetal) in 100% of rows —
  expected, since a fetal death wouldn't have TB as an attributable basic
  cause in the same way.
- **`CONTADOR`** — 0.00% null, and **unique across the 1,283 rows in this
  sample** (1,283 distinct values for 1,283 rows). It's a candidate for a
  record identifier, but with a caveat: it wasn't confirmed whether it's
  unique *globally* (across states/years) or just a sequential counter reset
  per DATASUS extraction batch/file — would need to check for `CONTADOR`
  collisions between two different `uf=X/ano=Y` files before treating it as
  a key. Not tested here (out of scope for this survey, which covers a
  single file).

### `CAUSABAS` — value format

**Confirmed: full ICD-10 (category + subcategory digit), not just the
category.** Examples: `A162`, `A153`, `A150`, `A159`, `A169` — never a "bare"
`A15` without the fourth character. 0.00% null, 30 unique values in the
sample, all within the `A15`-`A19` range expected by the extraction filter
(confirmed by the provenance column `_filter_applied` itself: `"CAUSABAS
startswith ('A15', 'A16', 'A17', 'A18', 'A19')"`).

There is also `CAUSABAS_O` ("original" basic cause, before any recoding
rules; 0.00% null, 72 unique values) which **sometimes has only 3
characters** (e.g., `J18`, no subcategory digit) — the two fields aren't
interchangeable; `CAUSABAS` is the column already used in the extraction
filter and should remain the source of truth for "is a TB death," `CAUSABAS_O`
is auxiliary/audit.

## Full table — source columns (87)

| Column | Type (dtype) | % Null | Unique values (sample) |
|---|---|---|---|
| `ORIGEM` | object | 0.00% | `1` |
| `TIPOBITO` | object | 0.00% | `2` |
| `DTOBITO` | object | 0.00% | `16062022`, `06062022`, `19052022`, `24062022`, `31012022` |
| `HORAOBITO` | object | 4.99% | `2316`, `1510`, `2124`, `1300`, `2055` |
| `NATURAL` | object | 2.10% | `829`, `850`, `835`, `826`, `825` |
| `CODMUNNATU` | object | 4.29% | `291480`, `500620`, `355250`, `355080`, `260540` |
| `DTNASC` | object | 0.62% | `10091967`, `29061981`, `23031959`, `22061994`, `27061940` |
| `IDADE` | object | 0.00% | `454`, `440`, `463`, `428`, `481` |
| `SEXO` | object | 0.00% | `1`, `2` |
| `RACACOR` | object | 0.94% | `1`, `2`, `4`, `3`, `5` |
| `ESTCIV` | object | 2.03% | `9`, `1`, `2`, `3`, `4` |
| `ESC` | object | 3.04% | `9`, `4`, `1`, `3`, `2` |
| `ESC2010` | object | 3.04% | `9`, `3`, `0`, `1`, `2` |
| `SERIESCFAL` | object | 60.41% | `1`, `4`, `3`, `8`, `5` |
| `OCUP` | object | 14.58% | `998999`, `514210`, `521125`, `999993`, `782510` |
| `CODMUNRES` | object | 0.00% | `354890`, `350710`, `355030`, `353060`, `354630` |
| `LOCOCOR` | object | 0.00% | `1`, `5`, `2`, `3`, `4` |
| `CODESTAB` | object | 14.19% | `2080931`, `2081407`, `4050169`, `2080052`, `2080745` |
| `ESTABDESCR` | object | 100.00% | *(no values — 100% null)* |
| `CODMUNOCOR` | object | 0.00% | `354890`, `352520`, `355030`, `353060`, `354630` |
| `IDADEMAE` | object | 100.00% | *(no values — 100% null)* |
| `ESCMAE` | object | 100.00% | *(no values — 100% null)* |
| `ESCMAE2010` | object | 100.00% | *(no values — 100% null)* |
| `SERIESCMAE` | object | 100.00% | *(no values — 100% null)* |
| `OCUPMAE` | object | 100.00% | *(no values — 100% null)* |
| `QTDFILVIVO` | object | 100.00% | *(no values — 100% null)* |
| `QTDFILMORT` | object | 100.00% | *(no values — 100% null)* |
| `GRAVIDEZ` | object | 100.00% | *(no values — 100% null)* |
| `SEMAGESTAC` | object | 100.00% | *(no values — 100% null)* |
| `GESTACAO` | object | 100.00% | *(no values — 100% null)* |
| `PARTO` | object | 100.00% | *(no values — 100% null)* |
| `OBITOPARTO` | object | 100.00% | *(no values — 100% null)* |
| `PESO` | object | 100.00% | *(no values — 100% null)* |
| `TPMORTEOCO` | object | 92.28% | `8`, `9`, `5` |
| `OBITOGRAV` | object | 92.28% | `2`, `9` |
| `OBITOPUERP` | object | 92.28% | `3`, `9`, `2` |
| `ASSISTMED` | object | 33.52% | `1`, `2`, `9` |
| `EXAME` | object | 100.00% | *(no values — 100% null)* |
| `CIRURGIA` | object | 100.00% | *(no values — 100% null)* |
| `NECROPSIA` | object | 30.24% | `1`, `2`, `9` |
| `LINHAA` | object | 1.64% | `*A419`, `*J969`, `*R688`, `*J960`, `*J189` |
| `LINHAB` | object | 19.10% | `*A162`, `*J180`, `*J690`, `*A150`, `*J189` |
| `LINHAC` | object | 48.56% | `*J449`, `*J159`, `*A169`, `*A159`, `*A162` |
| `LINHAD` | object | 80.28% | `*A150`, `*F172`, `*J189`, `*A198`, `*A159` |
| `LINHAII` | object | 53.78% | `*R64X*F199`, `*K746*A153`, `*A162*K746`, `*E149*A162`, `*J449` |
| `CAUSABAS` | object | 0.00% | `A162`, `A153`, `A150`, `A159`, `A169` |
| `CB_PRE` | object | 100.00% | *(no values — 100% null)* |
| `COMUNSVOIM` | object | 75.68% | `354140`, `351880`, `355280`, `355030`, `353440` |
| `DTATESTADO` | object | 0.08% | `16062022`, `07062022`, `19052022`, `24062022`, `31012022` |
| `CIRCOBITO` | object | 100.00% | *(no values — 100% null)* |
| `ACIDTRAB` | object | 100.00% | *(no values — 100% null)* |
| `FONTE` | object | 100.00% | *(no values — 100% null)* |
| `NUMEROLOTE` | object | 0.00% | `20220043`, `20220039`, `20220228`, `20220129`, `20220003` |
| `TPPOS` | object | 43.96% | `N`, `S` |
| `DTINVESTIG` | object | 80.20% | `19082022`, `07022022`, `05042022`, `13072022`, `29072022` |
| `CAUSABAS_O` | object | 0.00% | `A162`, `A153`, `J18`, `A159`, `A169` |
| `DTCADASTRO` | object | 0.00% | `24062022`, `14062022`, `29062022`, `30062022`, `07022022` |
| `ATESTANTE` | object | 7.87% | `2`, `5`, `4`, `1`, `3` |
| `STCODIFICA` | object | 0.00% | `S` |
| `CODIFICADO` | object | 0.00% | `S` |
| `VERSAOSIST` | object | 0.00% | `3.2.30`, `3.2.00`, `3.2.02` |
| `VERSAOSCB` | object | 0.31% | `3.4`, `3.2`, `3.3` |
| `FONTEINV` | object | 80.12% | `3`, `8`, `1`, `7`, `6` |
| `DTRECEBIM` | object | 0.00% | `03082022`, `15062022`, `01122022`, `24082022`, `12022022` |
| `ATESTADO` | object | 0.00% | `A419/A162*R64 F199`, `A419/J180*K746 A153`, `J969/J690*A162 K746`, `J969/A150`, `A419/J189/J449/A150` |
| `DTRECORIGA` | object | 0.00% | `29062022`, `15062022`, `01122022`, `01072022`, `12022022` |
| `CAUSAMAT` | object | 100.00% | *(no values — 100% null)* |
| `ESCMAEAGR1` | object | 100.00% | *(no values — 100% null)* |
| `ESCFALAGR1` | object | 3.04% | `09`, `05`, `00`, `12`, `02` |
| `STDOEPIDEM` | object | 0.00% | `0` |
| `STDONOVA` | object | 0.00% | `1` |
| `DIFDATA` | object | 0.00% | `048`, `009`, `196`, `061`, `012` |
| `NUDIASOBCO` | object | 93.06% | `64`, `128`, `95`, `68`, `56` |
| `NUDIASOBIN` | object | 100.00% | *(no values — 100% null)* |
| `DTCADINV` | object | 92.91% | `19072022`, `07092022`, `27062022`, `06012023`, `31052022` |
| `TPOBITOCOR` | object | 92.91% | `9`, `6`, `8` |
| `DTCONINV` | object | 93.06% | `13072022`, `07092022`, `27062022`, `01062022`, `31052022` |
| `FONTES` | object | 100.00% | *(no values — 100% null)* |
| `TPRESGINFO` | object | 99.84% | `1`, `2` |
| `TPNIVELINV` | object | 92.91% | `M`, `R` |
| `NUDIASINF` | object | 100.00% | *(no values — 100% null)* |
| `DTCADINF` | object | 100.00% | *(no values — 100% null)* |
| `MORTEPARTO` | object | 100.00% | *(no values — 100% null)* |
| `DTCONCASO` | object | 100.00% | *(no values — 100% null)* |
| `FONTESINF` | object | 100.00% | *(no values — 100% null)* |
| `ALTCAUSA` | object | 100.00% | *(no values — 100% null)* |
| `CONTADOR` | object | 0.00% | `727`, `953`, `1437`, `1630`, `2820` |

## Provenance columns (added by ingestion, not part of the source schema)

| Column | Type (dtype) | % Null | Unique values (sample) |
|---|---|---|---|
| `_source_dataset` | object | 0.00% | `SIM-SP-2022` |
| `_ingested_at` | object | 0.00% | `2026-08-03T01:48:41.647585+00:00` |
| `_filter_applied` | object | 0.00% | `CAUSABAS startswith ('A15', 'A16', 'A17', 'A18', 'A19')` |

## General observations

- **The entire schema is `dtype=object`** (text), same pattern as SINAN-TB —
  type conversion is silver's responsibility.
- Large number of 100%-null columns in this sample (`ESTABDESCR`,
  `IDADEMAE`, `ESCMAE*`, `SERIESCMAE`, `OCUPMAE`, `QTDFIL*`, `GRAVIDEZ`,
  `SEMAGESTAC`, `GESTACAO`, `PARTO`, `OBITOPARTO`, `PESO`, `EXAME`,
  `CIRURGIA`, `CB_PRE`, `CIRCOBITO`, `ACIDTRAB`, `FONTE`, `CAUSAMAT`,
  `ESCMAEAGR1`, `NUDIASOBIN`, `FONTES`, `NUDIASINF`, `DTCADINF`,
  `MORTEPARTO`, `DTCONCASO`, `FONTESINF`, `ALTCAUSA`) — most are
  fetal/maternal death fields (`*MAE*`, `GRAVIDEZ`, `PARTO`, `PESO`,
  `CAUSAMAT`, `MORTEPARTO`), expectedly irrelevant to adult TB deaths;
  candidates for dropping in silver, decision not made here.
- Several epidemiological investigation fields (`DTINVESTIG`, `FONTEINV`,
  `DTCADINV`, `TPOBITOCOR`, `DTCONINV`, `TPRESGINFO`, `TPNIVELINV`) are
  80-99% null — appear to be populated only when the death underwent formal
  investigation, not for every record.
- `LINHAA`-`LINHAD` and `LINHAII` are the death certificate's lines (Part I:
  direct cause → basic cause; Part II: contributing causes) — raw input from
  which `CAUSABAS` is derived via ICD-10's basic-cause selection rules, not
  used directly in the project's business question.
- No `TPCASO`/`SITUA_ENCE`-like field: SIM has no concept of case closure
  like SINAN — each row is, by definition, already a death (a terminal
  event), not a case under follow-up.
