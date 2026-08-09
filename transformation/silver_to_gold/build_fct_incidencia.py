"""
Gold: fct_incidencia_tb — incidência de TB por 100 mil habitantes,
por município/UF/ano.

Regras já decididas:
  - Numerador: TODAS as notificações do ano (não filtra por status_maturidade
    — incidência é sobre volume notificado, right-censoring afeta desfecho,
    não a notificação em si).
  - Denominador: população de silver/stg_ibge__populacao_municipio, join
    direto por código IBGE de 7 dígitos (SINAN-TB já usa 7 dígitos nativamente,
    diferente do SIM, que precisou de truncamento).
  - Ausência de população (ex.: Boa Esperança do Norte) resulta em
    incidência nula e explícita, nunca zero.
  - `status_maturidade` e `status_fonte_populacao` propagados como colunas
    informativas, nunca usados para filtrar linha.

Uso:
    python transformation/silver_to_gold/build_fct_incidencia.py --years 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "bronze_to_silver"))
from quality_report import QualityLog

SILVER_SINAN = Path("silver/stg_sinan__tuberculose")
SILVER_POPULATION = Path("silver/stg_ibge__populacao_municipio")
DIM_MUNICIPIO = Path("silver/dim_municipio/data.parquet")
GOLD_ROOT = Path("gold/fct_incidencia_tb")


def load_dim_municipio() -> pd.DataFrame:
    return pd.read_parquet(DIM_MUNICIPIO)


def load_silver_sinan(years) -> pd.DataFrame:
    frames = []
    for year in years:
        path = SILVER_SINAN / f"ano={year}" / "data.parquet"
        if not path.exists():
            continue
        frames.append(pd.read_parquet(path))
    return pd.concat(frames, ignore_index=True)


def load_silver_population(years) -> pd.DataFrame:
    frames = []
    for year in years:
        path = SILVER_POPULATION / f"ano={year}" / "data.parquet"
        if not path.exists():
            continue
        frames.append(pd.read_parquet(path))
    return pd.concat(frames, ignore_index=True)


def aggregate_casos(df: pd.DataFrame, log: QualityLog) -> pd.DataFrame:
    before = len(df)
    agg = df.groupby(["ID_MN_RESI", "NU_ANO"]).agg(
        casos=("ID_MN_RESI", "size"),
        status_maturidade=("_status_maturidade_estimado", "first"),
    ).reset_index()
    log.record("aggregate_casos", before, len(agg), {"granularidade": "municipio x ano"})
    return agg


def join_population(agg: pd.DataFrame, pop: pd.DataFrame, log: QualityLog) -> pd.DataFrame:
    before = len(agg)
    df = agg.merge(
        pop[["ano", "codigo_municipio", "populacao", "status_fonte_populacao"]],
        left_on=["ID_MN_RESI", "NU_ANO"],
        right_on=["codigo_municipio", "ano"],
        how="left",
    )
    sem_pop = df["populacao"].isna().sum()
    df["incidencia_por_100k"] = (df["casos"] / df["populacao"]) * 100_000
    df = df.drop(columns=["codigo_municipio", "ano"], errors="ignore")
    log.record("join_population", before, len(df), {
        "linhas_sem_populacao": int(sem_pop),
        "nota": "incidência fica nula quando população ausente (ex. Boa Esperança do Norte); não zerar",
    })
    return df


def join_municipio_nome(df: pd.DataFrame, dim_municipio: pd.DataFrame, log: QualityLog) -> pd.DataFrame:
    """Traz nome_municipio via join com dim_municipio (mesmo padrão de
    uf_sigla em build_fct_taxa_abandono.py) — código IBGE cru não é
    legível no dashboard; ID_MN_RESI é mantido, não removido."""
    before = len(df)
    df = df.merge(
        dim_municipio[["codigo_municipio", "nome_municipio"]],
        left_on="ID_MN_RESI", right_on="codigo_municipio", how="left",
    )
    df = df.drop(columns=["codigo_municipio"])
    sem_nome = df["nome_municipio"].isna().sum()
    log.record("join_municipio_nome", before, len(df), {
        "linhas_sem_nome_municipio": int(sem_nome),
    })
    return df


def write_gold(df: pd.DataFrame, years):
    for year in years:
        year_df = df[df["NU_ANO"] == year]
        if year_df.empty:
            continue
        out_dir = GOLD_ROOT / f"ano={year}"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "data.parquet"
        year_df.to_parquet(out_path, compression="zstd")
        print(f"  -> {out_path} ({len(year_df):,} municípios com caso)")


def main():
    parser = argparse.ArgumentParser(description="Gold: incidência de TB por 100k")
    parser.add_argument("--years", type=int, nargs="+", default=list(range(2015, 2025)))
    args = parser.parse_args()

    log = QualityLog(pipeline_name="gold_fct_incidencia_tb")

    print("Carregando silver...")
    sinan = load_silver_sinan(args.years)
    pop = load_silver_population(args.years)
    dim_municipio = load_dim_municipio()
    log.record("load_silver", 0, len(sinan), {"populacao_linhas": len(pop), "dim_municipio_linhas": len(dim_municipio)})

    agg = aggregate_casos(sinan, log)
    result = join_population(agg, pop, log)
    result = join_municipio_nome(result, dim_municipio, log)

    print("\nGravando gold...")
    write_gold(result, args.years)

    log.write(Path("quality/logs/gold_fct_incidencia_tb_last_run.json"))


if __name__ == "__main__":
    main()
