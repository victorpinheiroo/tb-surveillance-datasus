"""
Transformação bronze -> silver: População IBGE (município/ano).

Aplica as decisões já documentadas:
  - ADR-003: proxy censitário para 2022/2023 (`_status_fonte_populacao`
    já vem do bronze, só é preservado e renomeado aqui).
  - Filtro da linha de rótulo da API SIDRA (mesmo bug já corrigido no
    `transform_sinan_tb.py` — aqui é a versão "oficial" desse tratamento,
    silver de população própria, não só um lookup auxiliar).

IMPORTANTE — mesma ressalva do transform_sinan_tb.py: os nomes de coluna
brutos do SIDRA (`D1C`, `V`, etc.) foram confirmados empiricamente contra
uma amostra (ver validação anterior), não são hardcoded às cegas — mas
`validate_schema()` está aqui de novo por segurança, caso o formato mude
entre anos ou APIs.

Uso:
    python transformation/bronze_to_silver/transform_population.py --validate-only
    python transformation/bronze_to_silver/transform_population.py --years 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024
"""

import argparse
from pathlib import Path

import pandas as pd

from quality_report import QualityLog

BRONZE_ROOT = Path("bronze/ibge_population")
SILVER_ROOT = Path("silver/stg_ibge__populacao_municipio")

# Confirmados empiricamente contra amostra real (ver validação anterior no
# transform_sinan_tb.py) — não são palpite.
COL_MUNICIPIO = "D1C"
COL_NOME_MUNICIPIO = "D1N"
COL_VALOR = "V"
COL_STATUS_FONTE = "_status_fonte_populacao"


def validate_schema():
    sample_path = next(BRONZE_ROOT.glob("ano=*/data.parquet"), None)
    if sample_path is None:
        print("Nenhum arquivo de população encontrado.")
        return
    df = pd.read_parquet(sample_path)
    print(f"Amostra: {sample_path}")
    print(f"Colunas reais: {list(df.columns)}")
    faltando = [c for c in [COL_MUNICIPIO, COL_NOME_MUNICIPIO, COL_VALOR, COL_STATUS_FONTE] if c not in df.columns]
    if faltando:
        print(f"AVISO: colunas esperadas ausentes: {faltando} — ajuste as constantes antes de prosseguir.")
    else:
        print("Todas as colunas esperadas estão presentes.")


def load_bronze_years(years) -> pd.DataFrame:
    frames = []
    for year in years:
        path = BRONZE_ROOT / f"ano={year}" / "data.parquet"
        if not path.exists():
            print(f"  [aviso] {path} não encontrado, pulando {year}")
            continue
        df = pd.read_parquet(path)
        df["_ano"] = year
        frames.append(df)
    return pd.concat(frames, ignore_index=True, sort=False)


def filter_header_row(df: pd.DataFrame, log: QualityLog) -> pd.DataFrame:
    before = len(df)
    is_valid_code = pd.to_numeric(df[COL_MUNICIPIO], errors="coerce").notna()
    removidas_por_ano = (
        df.loc[~is_valid_code].groupby("_ano").size().to_dict()
    )
    df = df.loc[is_valid_code].copy()
    log.record("filter_header_row", before, len(df), {"removidas_por_ano": removidas_por_ano})
    return df


def standardize_columns(df: pd.DataFrame, log: QualityLog) -> pd.DataFrame:
    before = len(df)
    df = df.rename(columns={
        COL_MUNICIPIO: "codigo_municipio",
        COL_NOME_MUNICIPIO: "nome_municipio",
        COL_VALOR: "populacao",
        COL_STATUS_FONTE: "status_fonte_populacao",
        "_ano": "ano",
    })
    df["codigo_municipio"] = df["codigo_municipio"].astype(str).str.strip()
    df["populacao"] = pd.to_numeric(df["populacao"], errors="coerce").astype("Int64")
    pop_nula = df["populacao"].isna().sum()

    df = df[["ano", "codigo_municipio", "nome_municipio", "populacao", "status_fonte_populacao"]]
    log.record("standardize_columns", before, len(df), {"populacao_nao_numerica": int(pop_nula)})
    return df


def validate_uniqueness(df: pd.DataFrame, log: QualityLog) -> pd.DataFrame:
    before = len(df)
    dupes = df.duplicated(subset=["ano", "codigo_municipio"], keep=False)
    detail = {"linhas_duplicadas_ano_municipio": int(dupes.sum())}
    if dupes.sum() > 0:
        # Não descarta silenciosamente — sinaliza para investigação manual,
        # já que (ano, código_município) deveria ser sempre único.
        detail["aviso"] = "duplicidade inesperada em (ano, codigo_municipio) — investigar antes de usar em produção"
    log.record("validate_uniqueness", before, len(df), detail)
    return df


def write_silver(df: pd.DataFrame, years):
    for year in years:
        year_df = df[df["ano"] == year]
        if year_df.empty:
            continue
        out_dir = SILVER_ROOT / f"ano={year}"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "data.parquet"
        year_df.to_parquet(out_path, compression="zstd")
        print(f"  -> {out_path} ({len(year_df):,} municípios)")


def main():
    parser = argparse.ArgumentParser(description="Transformação bronze->silver população IBGE")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--years", type=int, nargs="+", default=list(range(2015, 2025)))
    args = parser.parse_args()

    if args.validate_only:
        validate_schema()
        return

    log = QualityLog(pipeline_name="bronze_to_silver_ibge_population")

    print("Carregando bronze...")
    df = load_bronze_years(args.years)
    log.record("load_bronze_years", 0, len(df))

    df = filter_header_row(df, log)
    df = standardize_columns(df, log)
    df = validate_uniqueness(df, log)

    print("\nGravando silver...")
    write_silver(df, args.years)

    log.write(Path("quality/logs/bronze_to_silver_ibge_population_last_run.json"))


if __name__ == "__main__":
    main()
