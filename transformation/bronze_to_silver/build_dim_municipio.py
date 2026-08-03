"""
Dimensão de município — SCD Type 2 (versão mínima).

Referência: adendo de validação empírica na ADR-001. A janela observada
(2015-2024) não mostrou nenhuma mudança real de código/identidade de
município — a estrutura SCD2 é implementada porque o pipeline é projetado
para rodar continuamente (novos anos entrarão no futuro), não porque esta
janela específica precisou dela.

Distinção deliberada, para não repetir o erro já visto no projeto (confundir
"ausente de uma fonte num ano" com "mudança de identidade"):

  - MUDANÇA DE ATRIBUTO (gera nova versão SCD2 de verdade): o mesmo código
    de município aparece com `nome_municipio` diferente em anos diferentes.
  - GAP DE COBERTURA (não gera nova versão, só uma flag diagnóstica): o
    código está ausente de um ano específico por limitação da fonte (ex.:
    Boa Esperança do Norte ausente do Censo 2022/2023 — ADR-003). Isso não
    significa que o município deixou de existir ou mudou de identidade.

Fonte: `silver/stg_ibge__populacao_municipio/` (já limpo, sem linha de
rótulo da API, sem duplicidade) — usado como registro de referência de
município, não o SINAN-TB (que é dado de evento, não de cadastro).

Uso:
    python transformation/bronze_to_silver/build_dim_municipio.py --years 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024
"""

import argparse
from pathlib import Path

import pandas as pd

from quality_report import QualityLog

SILVER_POPULATION = Path("silver/stg_ibge__populacao_municipio")
SILVER_ROOT = Path("silver/dim_municipio")


def load_population_silver(years) -> pd.DataFrame:
    frames = []
    for year in years:
        path = SILVER_POPULATION / f"ano={year}" / "data.parquet"
        if not path.exists():
            print(f"  [aviso] {path} não encontrado, pulando {year}")
            continue
        df = pd.read_parquet(path)
        frames.append(df[["ano", "codigo_municipio", "nome_municipio"]])
    return pd.concat(frames, ignore_index=True)


def detect_coverage_gaps(df: pd.DataFrame, years, log: QualityLog) -> pd.DataFrame:
    """Para cada código de município, identifica em quais anos da janela ele
    está ausente da fonte — diagnóstico, não muda a identidade do município."""
    before = len(df)
    all_codes = df["codigo_municipio"].unique()
    presence = df.groupby("codigo_municipio")["ano"].apply(set).to_dict()

    gap_records = []
    for code, anos_presentes in presence.items():
        anos_ausentes = sorted(set(years) - anos_presentes)
        if anos_ausentes:
            gap_records.append({"codigo_municipio": code, "anos_ausentes": anos_ausentes})

    gaps_df = pd.DataFrame(gap_records)
    log.record("detect_coverage_gaps", before, len(df), {
        "municipios_com_gap": len(gap_records),
        "exemplo": gap_records[:3] if gap_records else [],
    })
    return gaps_df


def build_scd2(df: pd.DataFrame, gaps_df: pd.DataFrame, log: QualityLog) -> pd.DataFrame:
    """Constrói a dimensão SCD2: uma linha por versão distinta de atributos
    (nome_municipio) por código de município, ordenada por ano."""
    before = len(df)

    df_sorted = df.sort_values(["codigo_municipio", "ano"])
    versions = []
    version_change_count = 0

    for code, group in df_sorted.groupby("codigo_municipio"):
        group = group.drop_duplicates(subset=["ano"]).sort_values("ano")
        current_nome = None
        current_valid_from = None

        for _, row in group.iterrows():
            if row["nome_municipio"] != current_nome:
                if current_nome is not None:
                    # Fecha a versão anterior (mudança real de atributo detectada)
                    versions.append({
                        "codigo_municipio": code,
                        "nome_municipio": current_nome,
                        "valid_from": current_valid_from,
                        "valid_to": row["ano"] - 1,
                        "is_current": False,
                    })
                    version_change_count += 1
                current_nome = row["nome_municipio"]
                current_valid_from = row["ano"]

        # Última versão observada, ainda vigente
        versions.append({
            "codigo_municipio": code,
            "nome_municipio": current_nome,
            "valid_from": current_valid_from,
            "valid_to": None,
            "is_current": True,
        })

    dim = pd.DataFrame(versions)
    dim = dim.merge(gaps_df, on="codigo_municipio", how="left")
    dim["anos_ausentes"] = dim["anos_ausentes"].apply(lambda x: x if isinstance(x, list) else [])

    log.record("build_scd2", before, len(dim), {
        "municipios_unicos": df["codigo_municipio"].nunique(),
        "versoes_totais": len(dim),
        "mudancas_de_atributo_reais_detectadas": version_change_count,
    })
    return dim


def write_silver(df: pd.DataFrame):
    SILVER_ROOT.mkdir(parents=True, exist_ok=True)
    out_path = SILVER_ROOT / "data.parquet"
    df.to_parquet(out_path, compression="zstd")
    print(f"  -> {out_path} ({len(df):,} versões de município)")


def main():
    parser = argparse.ArgumentParser(description="Construção da dimensão SCD2 de município")
    parser.add_argument("--years", type=int, nargs="+", default=list(range(2015, 2025)))
    args = parser.parse_args()

    log = QualityLog(pipeline_name="build_dim_municipio_scd2")

    print("Carregando silver de população...")
    df = load_population_silver(args.years)
    log.record("load_population_silver", 0, len(df))

    gaps_df = detect_coverage_gaps(df, args.years, log)
    dim = build_scd2(df, gaps_df, log)

    print("\nGravando dimensão...")
    write_silver(dim)

    log.write(Path("quality/logs/build_dim_municipio_last_run.json"))


if __name__ == "__main__":
    main()
