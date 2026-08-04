"""
Gold: fct_taxa_abandono — taxa de abandono de tratamento de TB,
por município/UF/ano.

Decisão confirmada (2026-08-03): anos provisórios (2024+) NÃO são
excluídos — abandono é indicador clínico sério (associado a agravamento
e resistência bacteriana), relevante mesmo em dado ainda em consolidação.
Salvaguarda: `n_casos_encerrados` (denominador) é exposto junto com a
taxa, para que instabilidade estatística em anos com poucos casos
encerrados fique visível na própria tabela, não escondida atrás de um
percentual isolado.

Regras:
  - Denominador: só casos com desfecho conhecido (situacao_encerramento_desc
    não nulo) — não o total de notificações.
  - Numerador: Abandono + Abandono Primário.
  - `status_maturidade` propagado como coluna informativa.

Uso:
    python transformation/silver_to_gold/build_fct_taxa_abandono.py --years 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "bronze_to_silver"))
from quality_report import QualityLog

SILVER_SINAN = Path("silver/stg_sinan__tuberculose")
GOLD_ROOT = Path("gold/fct_taxa_abandono")
GOLD_ROOT_UF = Path("gold/fct_taxa_abandono_uf")

ABANDONO_CATEGORIAS = ["Abandono", "Abandono Primário"]


def load_silver_sinan(years) -> pd.DataFrame:
    frames = []
    for year in years:
        path = SILVER_SINAN / f"ano={year}" / "data.parquet"
        if not path.exists():
            continue
        frames.append(pd.read_parquet(path))
    return pd.concat(frames, ignore_index=True)


def filter_encerrados(df: pd.DataFrame, log: QualityLog) -> pd.DataFrame:
    before = len(df)
    df_enc = df[df["situacao_encerramento_desc"].notna()].copy()
    log.record("filter_encerrados", before, len(df_enc), {
        "nota": "denominador é só casos com desfecho conhecido, não o total de notificações",
    })
    return df_enc


def aggregate_abandono(df: pd.DataFrame, log: QualityLog) -> pd.DataFrame:
    before = len(df)
    df["is_abandono"] = df["situacao_encerramento_desc"].isin(ABANDONO_CATEGORIAS)

    agg = df.groupby(["ID_MN_RESI", "NU_ANO"]).agg(
        n_casos_encerrados=("situacao_encerramento_desc", "size"),
        n_abandono=("is_abandono", "sum"),
        status_maturidade=("_status_maturidade_estimado", "first"),
    ).reset_index()
    agg["taxa_abandono_pct"] = (agg["n_abandono"] / agg["n_casos_encerrados"]) * 100

    log.record("aggregate_abandono", before, len(agg), {
        "granularidade": "municipio x ano",
        "categorias_numerador": ABANDONO_CATEGORIAS,
    })
    return agg


def aggregate_abandono_uf(df: pd.DataFrame, log: QualityLog) -> pd.DataFrame:
    """Rollup em nível de UF — recomendado como visão principal do
    dashboard. Achado empírico (2026-08-03): ~90% dos municípios têm
    menos de 30 casos encerrados/ano em toda a série, tornando a taxa em
    nível de município estatisticamente instável para a maioria das
    linhas. UF agrega o suficiente para ser confiável na maior parte dos
    casos (ainda vale checar n_casos_encerrados antes de citar um número).

    `SG_UF='0'` é excluído antes do agrupamento — sentinela conhecido (ver
    docs/known-issues.md), não uma UF real; sem esse filtro ele aparecia
    como uma 28ª "UF" na tabela gold."""
    before = len(df)
    valid_ufs = {"11", "12", "13", "14", "15", "16", "17", "21", "22", "23", "24", "25", "26",
                 "27", "28", "29", "31", "32", "33", "35", "41", "42", "43", "50", "51", "52", "53"}
    invalid_mask = ~df["SG_UF"].astype(str).isin(valid_ufs)
    n_invalid = int(invalid_mask.sum())
    df_valid = df.loc[~invalid_mask].copy()

    agg = df_valid.groupby(["SG_UF", "NU_ANO"]).agg(
        n_casos_encerrados=("situacao_encerramento_desc", "size"),
        n_abandono=("is_abandono", "sum"),
        status_maturidade=("_status_maturidade_estimado", "first"),
    ).reset_index()
    agg["taxa_abandono_pct"] = (agg["n_abandono"] / agg["n_casos_encerrados"]) * 100
    agg = agg.rename(columns={"SG_UF": "uf_codigo", "NU_ANO": "ano"})
    log.record("aggregate_abandono_uf", before, len(agg), {
        "granularidade": "UF x ano",
        "linhas_uf_invalida_excluidas": n_invalid,
        "nota": "SG_UF='0' é sentinela conhecido (padrão consistente com SITUA_ENCE='0', IBGE '...', SIM XX0000); "
                "hipótese não confirmada contra fonte primária por desproporção de esforço vs. volume (0,012%)",
    })
    return agg


def write_gold(df: pd.DataFrame, years):
    for year in years:
        year_df = df[df["NU_ANO"] == year]
        if year_df.empty:
            continue
        out_dir = GOLD_ROOT / f"ano={year}"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "data.parquet"
        year_df.to_parquet(out_path, compression="zstd")
        pequenos = year_df[year_df["n_casos_encerrados"] < 30]
        aviso = f" [aviso: {len(pequenos)} municípios com <30 casos encerrados]" if len(pequenos) else ""
        print(f"  -> {out_path} ({len(year_df):,} municípios){aviso}")


def write_gold_uf(df: pd.DataFrame, years):
    for year in years:
        year_df = df[df["ano"] == year]
        if year_df.empty:
            continue
        out_dir = GOLD_ROOT_UF / f"ano={year}"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "data.parquet"
        year_df.to_parquet(out_path, compression="zstd")
        print(f"  -> {out_path} ({len(year_df):,} UFs)")


def main():
    parser = argparse.ArgumentParser(description="Gold: taxa de abandono de tratamento de TB")
    parser.add_argument("--years", type=int, nargs="+", default=list(range(2015, 2025)))
    args = parser.parse_args()

    log = QualityLog(pipeline_name="gold_fct_taxa_abandono")

    print("Carregando silver...")
    sinan = load_silver_sinan(args.years)
    log.record("load_silver", 0, len(sinan))

    df_enc = filter_encerrados(sinan, log)
    result = aggregate_abandono(df_enc, log)
    result_uf = aggregate_abandono_uf(df_enc, log)

    print("\nGravando gold (município)...")
    write_gold(result, args.years)

    print("\nGravando gold (UF — visão principal recomendada)...")
    write_gold_uf(result_uf, args.years)

    log.write(Path("quality/logs/gold_fct_taxa_abandono_last_run.json"))


if __name__ == "__main__":
    main()
