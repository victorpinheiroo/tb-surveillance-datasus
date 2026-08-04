"""
Gold: fct_reconciliacao_sinan_sim — comparação de óbitos por TB entre
SINAN (desfecho notificado) e SIM (óbito registrado), por UF/ano.

Granularidade: UF, não município — os gaps de cobertura do SIM (ADR-001)
são documentados por UF/ano, não por município; agregar em nível
municipal criaria buracos maiores do que o dado real suporta.

A diferença entre as duas contagens NÃO é um erro a corrigir — é o
achado central do projeto (estimativa de subnotificação por reconciliação
de fontes independentes). `status_cobertura_sim` impede que um UF/ano sem
dado do SIM seja lido como "SIM = 0 óbitos" (que seria uma leitura errada:
zero é uma contagem, ausência de dado é outra coisa).

Uso:
    python transformation/silver_to_gold/build_fct_reconciliacao_sinan_sim.py --years 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "bronze_to_silver"))
from quality_report import QualityLog

SILVER_SINAN = Path("silver/stg_sinan__tuberculose")
SILVER_SIM = Path("silver/stg_sim__obitos_tb")
BRONZE_SIM = Path("bronze/sim_tb_deaths")  # usado só para checar presença de arquivo por UF/ano
DIM_UF = Path("gold/dim_uf/data.parquet")
GOLD_ROOT = Path("gold/fct_reconciliacao_sinan_sim")

ALL_UFS = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
    "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
    "SP", "SE", "TO",
]


def load_dim_uf() -> pd.DataFrame:
    return pd.read_parquet(DIM_UF)


def load_silver_sinan(years) -> pd.DataFrame:
    frames = []
    for year in years:
        path = SILVER_SINAN / f"ano={year}" / "data.parquet"
        if not path.exists():
            continue
        frames.append(pd.read_parquet(path))
    return pd.concat(frames, ignore_index=True)


def load_silver_sim(years) -> pd.DataFrame:
    frames = []
    for year in years:
        path = SILVER_SIM / f"ano={year}" / "data.parquet"
        if not path.exists():
            continue
        frames.append(pd.read_parquet(path))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def aggregate_sinan_obitos(df: pd.DataFrame, dim_uf: pd.DataFrame, log: QualityLog) -> pd.DataFrame:
    before = len(df)
    df_obito = df[df["situacao_encerramento_desc"] == "Óbito por Tuberculose"].copy()

    # Mesmo sentinela já encontrado e filtrado em build_fct_taxa_abandono.py
    # (SG_UF='0', hipótese de "UF ignorada", não confirmado contra fonte
    # primária por volume imaterial — ver known-issues.md).
    valid_codes = set(dim_uf["uf_codigo"])
    invalid_mask = ~df_obito["SG_UF"].astype(str).isin(valid_codes)
    n_invalid = int(invalid_mask.sum())
    df_obito = df_obito.loc[~invalid_mask]

    agg = df_obito.groupby(["SG_UF", "NU_ANO"]).size().reset_index(name="obitos_sinan")
    agg["SG_UF"] = agg["SG_UF"].astype(str)
    agg = agg.merge(dim_uf[["uf_codigo", "uf_sigla"]], left_on="SG_UF", right_on="uf_codigo", how="left")
    agg = agg.drop(columns=["SG_UF", "uf_codigo"]).rename(columns={"NU_ANO": "ano"})

    log.record("aggregate_sinan_obitos", before, len(agg), {
        "filtro": "situacao_encerramento_desc == 'Óbito por Tuberculose'",
        "linhas_uf_invalida_excluidas": n_invalid,
    })
    return agg


def aggregate_sim_obitos(df: pd.DataFrame, log: QualityLog) -> pd.DataFrame:
    before = len(df)
    if df.empty:
        return pd.DataFrame(columns=["_uf", "_ano", "obitos_sim"])
    agg = df.groupby(["_uf", "_ano"]).size().reset_index(name="obitos_sim")
    agg = agg.rename(columns={"_uf": "uf_sigla", "_ano": "ano"})
    log.record("aggregate_sim_obitos", before, len(agg), {})
    return agg


def build_coverage_status(years, log: QualityLog) -> pd.DataFrame:
    """Para cada UF/ano da janela, marca se existe arquivo de SIM no bronze
    — é essa checagem que determina status_cobertura_sim, não a ausência
    de linha após agregação (que poderia ser zero óbitos OU zero cobertura,
    coisas diferentes)."""
    records = []
    for uf in ALL_UFS:
        for year in years:
            existe = (BRONZE_SIM / f"uf={uf}" / f"ano={year}" / "data.parquet").exists()
            records.append({"uf_sigla": uf, "ano": year, "status_cobertura_sim": "disponivel" if existe else "ausente"})
    cov = pd.DataFrame(records)
    ausentes = (cov["status_cobertura_sim"] == "ausente").sum()
    log.record("build_coverage_status", 0, len(cov), {"combinacoes_uf_ano_ausentes": int(ausentes)})
    return cov


def reconcile(sinan_agg, sim_agg, coverage, log: QualityLog) -> pd.DataFrame:
    before = len(coverage)
    df = coverage.merge(sim_agg, on=["uf_sigla", "ano"], how="left")
    df = df.merge(sinan_agg, on=["uf_sigla", "ano"], how="left")

    df["obitos_sinan"] = df["obitos_sinan"].fillna(0).astype(int)

    # Diferença só é calculada onde há cobertura do SIM — onde não há,
    # fica nula (não zero, não descartada): ausência de dado é diferente
    # de zero óbitos.
    tem_cobertura = df["status_cobertura_sim"] == "disponivel"
    df["diferenca_sim_menos_sinan"] = pd.NA
    df.loc[tem_cobertura, "diferenca_sim_menos_sinan"] = (
        df.loc[tem_cobertura, "obitos_sim"] - df.loc[tem_cobertura, "obitos_sinan"]
    )

    # Regra dos ~2 anos já documentada na ADR-001 para o SINAN-TB (right-censoring),
    # aplicada aqui ao SIM por analogia — não validada empiricamente para o SIM
    # ainda, ver adendo da ADR-001.
    df["status_maturidade_sim"] = df["ano"].apply(lambda a: "provisorio" if a >= 2024 else "fechado")

    sem_cobertura = (~tem_cobertura).sum()
    log.record("reconcile", before, len(df), {
        "linhas_sem_cobertura_sim": int(sem_cobertura),
        "nota": "diferenca_sim_menos_sinan é nula (não zero) onde status_cobertura_sim='ausente'",
    })
    return df


def write_gold(df: pd.DataFrame, years):
    for year in years:
        year_df = df[df["ano"] == year]
        if year_df.empty:
            continue
        out_dir = GOLD_ROOT / f"ano={year}"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "data.parquet"
        year_df.to_parquet(out_path, compression="zstd")
        print(f"  -> {out_path} ({len(year_df):,} UFs)")


def main():
    parser = argparse.ArgumentParser(description="Gold: reconciliação SINAN x SIM")
    parser.add_argument("--years", type=int, nargs="+", default=list(range(2015, 2025)))
    args = parser.parse_args()

    log = QualityLog(pipeline_name="gold_fct_reconciliacao_sinan_sim")

    print("Carregando silver...")
    sinan = load_silver_sinan(args.years)
    sim = load_silver_sim(args.years)
    dim_uf = load_dim_uf()
    log.record("load_silver", 0, len(sinan), {"sim_linhas": len(sim), "dim_uf_linhas": len(dim_uf)})

    sinan_agg = aggregate_sinan_obitos(sinan, dim_uf, log)
    sim_agg = aggregate_sim_obitos(sim, log)
    coverage = build_coverage_status(args.years, log)

    result = reconcile(sinan_agg, sim_agg, coverage, log)

    print("\nGravando gold...")
    write_gold(result, args.years)

    log.write(Path("quality/logs/gold_fct_reconciliacao_sinan_sim_last_run.json"))

    amostra_cols = ["uf_sigla", "ano", "obitos_sinan", "obitos_sim", "status_cobertura_sim", "diferenca_sim_menos_sinan"]
    print("\nAmostra (5 linhas, achado central do projeto):")
    print(result[amostra_cols].sample(5, random_state=42).to_string(index=False))


if __name__ == "__main__":
    main()
