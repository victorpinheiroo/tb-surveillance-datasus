"""
Transformação bronze -> silver: SINAN-TB.

Aplica, nesta ordem, todas as decisões já documentadas nas ADRs do projeto:
  - ADR-001: descarte das 3 colunas legadas de 2015; preserva
    `_status_maturidade_estimado` vindo do bronze.
  - ADR-002: deduplicação via NDUPLIC_N == '2'; métrica de diagnóstico de
    quase-identificador calculada mas NUNCA usada como filtro.
  - ADR-003: join com população IBGE, incluindo `_status_fonte_populacao`;
    ausência de população (ex.: Boa Esperança do Norte/MT em 2022-2023)
    fica nula e explícita, nunca descartada ou zerada silenciosamente.
  - Decodificação de SITUA_ENCE contra o dicionário oficial confirmado
    (ver ADR-002 / investigação de schema).

IMPORTANTE — ponto de validação antes de rodar:
As colunas de `bronze/ibge_population/*/data.parquet` vêm cruas da API
SIDRA (biblioteca sidrapy) e NUNCA tiveram o `head()` inspecionado neste
projeto — só o `shape`. Os nomes abaixo (`D1C`, `V`, etc.) são o padrão
conhecido de retorno bruto da API SIDRA, não uma confirmação empírica
deste projeto. `validate_population_schema()` deve ser rodado primeiro;
se os nomes não baterem, ajuste as constantes no topo do arquivo antes de
prosseguir — não adivinhe em produção.

Uso:
    python transformation/bronze_to_silver/transform_sinan_tb.py --validate-only
    python transformation/bronze_to_silver/transform_sinan_tb.py --years 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024
"""

import argparse
from pathlib import Path

import pandas as pd

from quality_report import QualityLog

BRONZE_SINAN = Path("bronze/sinan_tb")
BRONZE_POPULATION = Path("bronze/ibge_population")
SILVER_ROOT = Path("silver/stg_sinan__tuberculose")

LEGACY_2015_COLUMNS = ["AGRAVOUTDE", "EXTRAPUL_O", "OUTRAS_DES"]

DATE_COLUMNS = [
    "DT_NOTIFIC", "DT_DIAG", "DT_DIGITA", "DT_TRANSUS", "DT_TRANSDM",
    "DT_TRANSSM", "DT_TRANSRM", "DT_TRANSRS", "DT_TRANSSE", "DT_INIC_TR",
    "DT_NOTI_AT", "DT_MUDANCA", "DT_ENCERRA",
]

SITUA_ENCE_MAP = {
    "1": "Cura",
    "2": "Abandono",
    "3": "Óbito por Tuberculose",
    "4": "Óbito por outras causas",
    "5": "Transferência",
    "6": "Mudança de Diagnóstico",
    "7": "TB-DR",
    "8": "Mudança de Esquema",
    "9": "Falência",
    "10": "Abandono Primário",
}

# Chave composta usada SÓ como diagnóstico de possível colisão de
# quase-identificador (ADR-002) — nunca como filtro de deduplicação real.
QUASI_ID_COLUMNS = ["ID_MN_RESI", "DT_NOTIFIC", "ANO_NASC", "CS_SEXO"]

# Nomes de coluna esperados no retorno bruto da API SIDRA — CONFIRMAR
# contra dado real antes de confiar (ver validate_population_schema).
POP_MUNICIPIO_COL_CANDIDATES = ["D1C"]
POP_VALUE_COL_CANDIDATES = ["V"]


def load_bronze_years(years) -> pd.DataFrame:
    frames = []
    for year in years:
        path = BRONZE_SINAN / f"ano={year}" / "data.parquet"
        if not path.exists():
            print(f"  [aviso] {path} não encontrado, pulando {year}")
            continue
        df = pd.read_parquet(path)
        frames.append(df)
    combined = pd.concat(frames, ignore_index=True, sort=False)
    return combined


def drop_legacy_2015_columns(df: pd.DataFrame, log: QualityLog) -> pd.DataFrame:
    before = len(df)
    present = [c for c in LEGACY_2015_COLUMNS if c in df.columns]
    detail = {}
    for col in present:
        non_null = df[col].astype(str).str.strip().replace({"nan": ""}).ne("").sum()
        detail[f"{col}_valores_descartados"] = int(non_null)
    df = df.drop(columns=present, errors="ignore")
    log.record("drop_legacy_2015_columns", before, len(df), detail)
    return df


def cast_types(df: pd.DataFrame, log: QualityLog) -> pd.DataFrame:
    before = len(df)
    for col in DATE_COLUMNS:
        if col not in df.columns:
            continue
        df[col] = pd.to_datetime(
            df[col].astype(str).str.strip(),
            format="%Y%m%d",
            errors="coerce",
        )
    if "ANO_NASC" in df.columns:
        df["ANO_NASC"] = pd.to_numeric(df["ANO_NASC"], errors="coerce").astype("Int64")
    if "NU_ANO" in df.columns:
        df["NU_ANO"] = pd.to_numeric(df["NU_ANO"], errors="coerce").astype("Int64")
    log.record("cast_types", before, len(df), {"date_columns_cast": len(DATE_COLUMNS)})
    return df


def decode_situa_ence(df: pd.DataFrame, log: QualityLog) -> pd.DataFrame:
    before = len(df)
    if "SITUA_ENCE" in df.columns:
        raw = df["SITUA_ENCE"].astype(str).str.strip()
        # Normaliza zero-padding inconsistente (ex.: "03"/"04" só em 2018) antes
        # do mapeamento — é o mesmo código que "3"/"4" nos demais anos, não uma
        # categoria nova. "10" não é afetado (sem zero à esquerda).
        normalizado = raw.str.lstrip("0")
        df["situacao_encerramento_desc"] = normalizado.map(SITUA_ENCE_MAP)
        nao_mapeado = df["SITUA_ENCE"].notna() & df["situacao_encerramento_desc"].isna() \
            & raw.ne("")
        detail = {"codigos_nao_mapeados": int(nao_mapeado.sum())}
        if nao_mapeado.sum() > 0:
            detail["valores_nao_mapeados_exemplo"] = sorted(
                df.loc[nao_mapeado, "SITUA_ENCE"].astype(str).unique().tolist()
            )[:10]
    else:
        detail = {"aviso": "coluna SITUA_ENCE não encontrada"}
    log.record("decode_situa_ence", before, len(df), detail)
    return df


def deduplicate(df: pd.DataFrame, log: QualityLog) -> pd.DataFrame:
    before = len(df)

    # Diagnóstico de colisão de quase-identificador — SÓ MEDIÇÃO, nunca filtro.
    available_quasi_cols = [c for c in QUASI_ID_COLUMNS if c in df.columns]
    if len(available_quasi_cols) == len(QUASI_ID_COLUMNS):
        dupe_mask = df.duplicated(subset=available_quasi_cols, keep=False)
        pct_colisao = dupe_mask.mean() * 100
    else:
        pct_colisao = None

    # Filtro real: só remove duplicata confirmada pela própria fonte.
    if "NDUPLIC_N" in df.columns:
        is_confirmed_dupe = df["NDUPLIC_N"].astype(str).str.strip() == "2"
        removed = int(is_confirmed_dupe.sum())
        df = df.loc[~is_confirmed_dupe].copy()
    else:
        removed = 0

    detail = {"ndupli_n_2_removidos": removed}
    if pct_colisao is not None:
        detail["pct_colisao_quase_identificador_diagnostico"] = f"{pct_colisao:.2f}%"
    log.record("deduplicate", before, len(df), detail)
    return df


def validate_population_schema():
    """Inspeciona a primeira partição de população e reporta as colunas
    reais, para confirmar (ou corrigir) as constantes de nome de coluna
    antes de rodar o join em escala."""
    sample_path = next(BRONZE_POPULATION.glob("ano=*/data.parquet"), None)
    if sample_path is None:
        print("Nenhum arquivo de população encontrado em bronze/ibge_population/")
        return
    df = pd.read_parquet(sample_path)
    print(f"Amostra: {sample_path}")
    print(f"Colunas reais: {list(df.columns)}")
    print(df.head(3).to_string())
    print(f"\nCandidatos de coluna de município configurados: {POP_MUNICIPIO_COL_CANDIDATES}")
    print(f"Candidatos de coluna de valor configurados: {POP_VALUE_COL_CANDIDATES}")
    found_muni = [c for c in POP_MUNICIPIO_COL_CANDIDATES if c in df.columns]
    found_val = [c for c in POP_VALUE_COL_CANDIDATES if c in df.columns]
    print(f"Encontrados -> município: {found_muni or 'NENHUM — ajustar constantes'}, "
          f"valor: {found_val or 'NENHUM — ajustar constantes'}")


def load_population_lookup(years, log: QualityLog = None) -> pd.DataFrame:
    """Constrói uma tabela (ano, código_município) -> (população, status_fonte)."""
    frames = []
    total_before = 0
    total_after = 0
    descartadas_por_ano = {}
    for year in years:
        path = BRONZE_POPULATION / f"ano={year}" / "data.parquet"
        if not path.exists():
            continue
        df = pd.read_parquet(path)
        muni_col = next((c for c in POP_MUNICIPIO_COL_CANDIDATES if c in df.columns), None)
        val_col = next((c for c in POP_VALUE_COL_CANDIDATES if c in df.columns), None)
        if muni_col is None or val_col is None:
            raise RuntimeError(
                f"Colunas de população não identificadas em {path}. "
                f"Rode validate_population_schema() e ajuste as constantes."
            )
        total_before += len(df)

        # A API SIDRA retorna a primeira linha como rótulo de coluna (ex.: código
        # de município = "Município (Código)"), não dado real — descartar antes
        # de qualquer uso, e normalizar o código para string numérica consistente
        # com ID_MN_RESI do SINAN (ex.: "3509601", sem zero à esquerda).
        codigo_numerico = pd.to_numeric(df[muni_col], errors="coerce")
        is_valid_row = codigo_numerico.notna()
        descartadas_por_ano[year] = int((~is_valid_row).sum())
        df = df.loc[is_valid_row].copy()
        df[muni_col] = codigo_numerico.loc[is_valid_row].astype("Int64").astype(str)

        total_after += len(df)

        status_col = "_status_fonte_populacao" if "_status_fonte_populacao" in df.columns else None
        out = df[[muni_col, val_col]].rename(columns={muni_col: "codigo_municipio", val_col: "populacao"})
        out["ano"] = year
        out["status_fonte_populacao"] = df[status_col] if status_col else "desconhecido"
        frames.append(out)

    if log is not None:
        log.record(
            "load_population_lookup_filter_header_row",
            total_before,
            total_after,
            {"linhas_descartadas_por_ano": descartadas_por_ano},
        )

    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
        columns=["codigo_municipio", "populacao", "ano", "status_fonte_populacao"]
    )


def join_population(df: pd.DataFrame, years, log: QualityLog) -> pd.DataFrame:
    before = len(df)
    pop_lookup = load_population_lookup(years, log)

    if "NU_ANO" in df.columns:
        df["_ano_join"] = df["NU_ANO"]
    else:
        df["_ano_join"] = pd.NA

    df = df.merge(
        pop_lookup,
        left_on=["ID_MN_RESI", "_ano_join"],
        right_on=["codigo_municipio", "ano"],
        how="left",
    )
    sem_populacao = df["populacao"].isna().sum()
    detail = {
        "linhas_sem_populacao_correspondente": int(sem_populacao),
        "nota": "população nula é esperada e válida (ex.: Boa Esperança do Norte 2022-2023, ADR-003); não descartar linha por isso",
    }
    df = df.drop(columns=["_ano_join", "codigo_municipio", "ano"], errors="ignore")
    log.record("join_population", before, len(df), detail)
    return df


def write_silver(df: pd.DataFrame, years):
    for year in years:
        year_df = df[df["NU_ANO"] == year] if "NU_ANO" in df.columns else df
        if year_df.empty:
            continue
        out_dir = SILVER_ROOT / f"ano={year}"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "data.parquet"
        year_df.to_parquet(out_path, compression="zstd")
        print(f"  -> {out_path} ({len(year_df):,} linhas)")


def main():
    parser = argparse.ArgumentParser(description="Transformação bronze->silver SINAN-TB")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--years", type=int, nargs="+", default=list(range(2015, 2025)))
    args = parser.parse_args()

    if args.validate_only:
        validate_population_schema()
        return

    log = QualityLog(pipeline_name="bronze_to_silver_sinan_tb")

    print("Carregando bronze...")
    df = load_bronze_years(args.years)
    log.record("load_bronze_years", 0, len(df))

    df = drop_legacy_2015_columns(df, log)
    df = cast_types(df, log)
    df = decode_situa_ence(df, log)
    df = deduplicate(df, log)
    df = join_population(df, args.years, log)

    print("\nGravando silver...")
    write_silver(df, args.years)

    log.write(Path("quality/logs/bronze_to_silver_sinan_tb_last_run.json"))


if __name__ == "__main__":
    main()
