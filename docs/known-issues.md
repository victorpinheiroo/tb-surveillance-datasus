# Known Issues

Known issues in third-party dependencies/sources used in this project,
documented here instead of being left implicit in scattered code comments.
See also `docs/adrs/` for decisions derived from these issues.

## PySUS: `sinan()` returns an empty DataFrame for `TUBEBR16.parquet` (SINAN-TB, year 2016)

**Status:** worked around in `ingestion/extract_sinan_tb.py`.

### Symptom

`sinan(disease="tube", year=2016, as_dataframe=True)` returns an empty
`pandas.DataFrame` (`shape == (0, 0)`), without raising an exception — the
same silent pattern already seen for the SIM coverage gap (see ADR-001), but
with a completely different cause: here the file **exists and has healthy
data** in PySUS's remote catalog; the problem is only in the metadata used to
filter it.

### Investigated root cause

The file `TUBEBR16.parquet` (SINAN, condition `TUBE`, year 2016) is present
in PySUS's remote catalog, but with a null `group_id` field in that specific
record's metadata. The call `sinan(disease="tube", year=2016)` internally
does `PySUS.query(dataset="sinan", group="TUBE", year=2016)`, which filters
by `group` — since this file's `group_id` is null in the catalog, the filter
excludes the file from the result list before it's ever downloaded. The
result is an empty `DataFrame`, indistinguishable at first glance from "no
data for this year" (a real, expected situation in other cases, e.g. SIM
coverage gaps).

All other SINAN-TB years (2015, 2017–2024) have a present and correct
`group_id` in the catalog; 2016 is an isolated case.

### Applied workaround

In `ingestion/extract_sinan_tb.py`, the `extract_year()` function detects
when `sinan()` returns an empty DataFrame and, in that case, calls
`_fetch_without_group_filter()` as a fallback: this function queries the
catalog via `PySUS.query(dataset="sinan")` **without** the `group` filter,
filters the results client-side by filename (prefix `TUBEBR16`), and
downloads and reads the matching file(s) directly.

If nothing is found even then, the function raises an explicit
`RuntimeError` — the same principle already applied to the SIM coverage gap
in `extract_sim_tb_deaths.py`: an empty DataFrame is never treated as "no
data" by default, only after confirming there really is no file at all, with
or without the metadata filter.

The `_metadata.txt` generated for the 2016 bronze partition records
`extraction_method=fallback_no_group_filter`, so the use of the workaround is
traceable in the provenance trail, not hidden in the code.

Result after the fix: `bronze/sinan_tb/ano=2016/` with 86,210 rows and 100
columns — same order of magnitude as neighboring years (85,462 in 2015,
90,295 in 2017), confirming the year's data was healthy all along; only the
filter metadata was broken.

## SINAN Net's official data dictionary (TB) — hard to access directly

**Status:** reference recorded, to avoid repeating the search effort.

Confirming SINAN-TB's coded fields (`NDUPLIC_N`, `SITUA_ENCE`) against the
primary source (not indexed/summarized search text) proved repeatedly
difficult in this project: direct `WebFetch` attempts against
`portalsinan.saude.gov.br`, `sitetb.saude.gov.br`, and a UFSC mirror failed
(timeout, connection refused, or a scanned/binary PDF with no extractable
text) on at least 3 separate occasions.

The document that finally allowed direct confirmation (field 62, the
complete `SITUA_ENCE` domain with all 10 codes) was:

- **`DICI_DADOS_NET_Tuberculose_23_07_2020.pdf`** — SINAN Net data dictionary,
  form version 5.0, Ministry of Health.
- Found and read directly by the project's owner (outside this session); the
  exact URL it was downloaded from wasn't captured here — if available, it's
  worth adding to this record for direct access in the future, instead of
  relying on search again.

Before assuming a SINAN field code is undocumented, or trying to decode it
from indexed search alone, it's worth searching specifically for this
filename pattern (`DICI_DADOS_NET_*`) — it's SINAN Net's official naming
convention for per-condition data dictionaries.

## SIM: `XX0000` sentinel in `CODMUNRES` = residence municipality not identified

**Status:** identified and handled explicitly in `transform_sim.py`, not dropped.

### Context

`CODMUNRES` (deceased's municipality of residence, see
`docs/schema-reference-sim.md`) uses 6-digit codes (DATASUS's convention of
omitting the check digit from the 7-digit IBGE code). Empirical validation
against `silver/dim_municipio` (`transform_sim.py --validate-only`, sample
`uf=SP/ano=2022`) found a 99.5% match rate (214 of 215 unique codes) — the
one code with no match was `350000`.

### Root cause

`XX0000` (2-digit state code + 4 zeros) is DATASUS/TABMUN's documented
convention for **"residence municipality not identified"**: the death is real
and the state is known, but the municipality of residence within that state
wasn't identified when the Death Certificate was filled out. It's not a real
municipality and will never have a match in `dim_municipio` — this is
expected, not a join bug.

In the `SP/2022` sample: 9 of 1,283 rows (0.70%). At national scale
(2015-2024, all states): **266 of 40,205 rows (0.66%)** — practically the
same magnitude as the sample, confirming it isn't a São Paulo-specific
artifact.

### Applied treatment

`normalize_municipio_code()` in `transform_sim.py` detects the pattern via
the regex `^\d{2}0000$` and writes an explicit boolean column
`municipio_residencia_ignorado` in silver — **the row is kept**, not dropped:
it's a real death, just with unresolved residence geography; dropping it
would understate real mortality. Any municipality-level aggregation must
explicitly decide how to handle these 266 rows (e.g., excluding them only
from geographic aggregation while keeping them in the national total), not
silently ignore them.

The quality log (`quality/logs/bronze_to_silver_sim_last_run.json`,
`normalize_municipio_code` step) publishes the count and percentage on every
run, to detect whether the magnitude changes in future states or years.

## SINAN-TB: `SG_UF='0'` — sentinel hypothesis, not confirmed (immaterial volume)

**Status:** filtered explicitly in `build_fct_taxa_abandono.py`
(`aggregate_abandono_uf`), not investigated further against the primary source.

`SG_UF='0'` appears in 109 SINAN-TB records (2015: 50, 2016: 55, 2017: 4;
absent from 2018 onward) — without this filter, these records formed an
invalid 28th "state" in the `gold/fct_taxa_abandono_uf` rollup, with no match
in `gold/dim_uf` (27 real states).

Hypothesis: the same "ignored/not informed" sentinel pattern already
confirmed in three other sources in this project (`SITUA_ENCE='0'` in
SINAN-TB, `"..."` in IBGE/SIDRA, `CODMUNRES='XX0000'` in SIM). **Not
confirmed against SINAN's official data dictionary** — a deliberate decision
not to investigate, given the disproportion between effort and gain: volume
is 0.012% of total closed cases (109 of 911,257), the same reasoning already
applied to reject checking the 2023 Federal Gazette (see ADR-003, rejected
alternatives). Worth reopening the investigation if the volume grows in
future runs.

## SINAN-TB: `ID_MN_RESI` with no match in `dim_municipio` — 4th instance of the sentinel pattern

**Status:** identified while adding `nome_municipio` to `build_fct_incidencia.py`
(join with `silver/dim_municipio`), not filtered — rows kept, just without a
displayable name on the dashboard.

31 records (19 distinct `ID_MN_RESI` codes, spread across several years) have
no match in `dim_municipio` — the same 31 rows that already lacked
`populacao` (the same IBGE-derived reference table underlies both joins).

17 of the 19 codes follow a recognizable sentinel pattern: `UF+0000` through
`UF+0009` and `UF+99xxx` (e.g., `2400000`=RN, `5399068`=DF) — the same
"residence not identified" semantics already seen in three other sources in
this project (`SITUA_ENCE='0'` in SINAN-TB, `"..."` in IBGE/SIDRA,
`CODMUNRES='XX0000'` in SIM); they were never real IBGE codes, this isn't a
join error.

2 of the 19 codes (`5205604`, `5208202`, 1 case each) don't fit this pattern
and remain unexplained — not investigated further given immaterial volume (1
case each).

Maximum volume: 61 cases in a single year/code (`ID_MN_RESI='0'`, 2016); the
rest is 1-3 cases per row. Same effort/volume disproportion reasoning already
applied to `SG_UF='0'` above.
