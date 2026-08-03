"""
Transformação bronze -> silver: SIM (óbitos de TB).

Achados do levantamento de schema (docs/schema-reference-sim.md) que
motivam as etapas abaixo:
  - `CODMUNRES` tem 6 dígitos, diferente dos 7 dígitos usados em
    `ID_MN_RESI` (SINAN-TB) e `codigo_municipio` (população IBGE/dim
    município) — convenção DATASUS de omitir o dígito verificador.
    Precisa de normalização antes de qualquer join geográfico.
  - `DTOBITO` vem em `DDMMAAAA`, diferente do `AAAAMMDD` do SINAN-TB.
  - Não existe campo análogo a `NDUPLIC_N` no SIM — `CONTADOR` é
    candidato a identificador mas não teve unicidade confirmada entre
    arquivos (UF/ano) diferentes. Tratado como diagnóstico, não como
    identificador de fato (mesmo princípio da ADR-002 para o SINAN-TB).
  - `CAUSABAS` confirmado como CID-10 completo (ex. `A162`), já usado
    corretamente no filtro de extração — nenhuma ação adicional aqui.

IMPORTANTE — validar antes de rodar em escala:
A hipótese de que `CODMUNRES` (6 dígitos) = primeiros 6 dígitos do código
IBGE de 7 dígitos (removendo o dígito verificador) é a convenção conhecida
do DATASUS, mas não foi empiricamente confirmada neste projeto ainda.
`--validate-only` testa essa hipótese contra a dimensão de município real
antes de aplicar em escala.

Uso:
    python transformation/bronze_to_silver/transform_sim.py --validate-only
    python transformation/bronze_to_silver/transform_sim.py --years 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024
"""

import argparse
from pathlib import Path

import pandas as pd

from quality_report import QualityLog

BRONZE_ROOT = Path("bronze/sim_tb_deaths")
DIM_MUNICIPIO = Path("silver/dim_municipio/data.parquet")
SILVER_ROOT = Path("silver/stg_sim__obitos_tb")

ALL_UFS = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
    "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
    "SP", "SE", "TO",
]


def load_bronze(years, ufs) -> pd.DataFrame:
    frames = []
    for year in years:
        for uf in ufs:
            path = BRONZE_ROOT / f"uf={uf}" / f"ano={year}" / "data.parquet"
            if not path.exists():
                continue  # gaps conhecidos (ADR-001) — ausência esperada, não erro
            df = pd.read_parquet(path)
            df["_ano"] = year
            df["_uf"] = uf
            frames.append(df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True, sort=False)


def validate_municipio_code_mapping():
    """Testa a hipótese: CODMUNRES (6 dígitos) == primeiros 6 dígitos do
    código IBGE de 7 dígitos, contra a dimensão de município real."""
    sample_path = BRONZE_ROOT / "uf=SP" / "ano=2022" / "data.parquet"
    if not sample_path.exists():
        print(f"Amostra {sample_path} não encontrada, tente outro UF/ano.")
        return
    df = pd.read_parquet(sample_path)
    dim = pd.read_parquet(DIM_MUNICIPIO)

    dim["codigo_6dig"] = dim["codigo_municipio"].astype(str).str[:6]
    codigos_dim_6dig = set(dim["codigo_6dig"])

    codmunres_unicos = set(df["CODMUNRES"].astype(str).str.strip())
    match = codmunres_unicos & codigos_dim_6dig
    sem_match = codmunres_unicos - codigos_dim_6dig

    print(f"CODMUNRES únicos na amostra: {len(codmunres_unicos)}")
    print(f"Com correspondência em codigo_municipio[:6]: {len(match)}")
    print(f"Sem correspondência: {len(sem_match)}")
    if sem_match:
        print(f"Exemplos sem match: {sorted(sem_match)[:10]}")
    taxa = len(match) / len(codmunres_unicos) * 100 if codmunres_unicos else 0
    print(f"\nTaxa de correspondência: {taxa:.1f}%")
    print("Se a taxa não estiver perto de 100%, NÃO prossiga sem investigar os casos sem match.")


def normalize_municipio_code(df: pd.DataFrame, log: QualityLog) -> pd.DataFrame:
    before = len(df)
    df["codigo_municipio_residencia"] = df["CODMUNRES"].astype(str).str.strip()
    # Mantém o código de 6 dígitos como está — o join com outras fontes
    # (silver/dim_municipio) deve truncar o lado de 7 dígitos, não o
    # contrário, para não perder informação por padding incorreto.
    is_ignorado = df["codigo_municipio_residencia"].str.match(r"^\d{2}0000$")
    df["municipio_residencia_ignorado"] = is_ignorado
    log.record("normalize_municipio_code", before, len(df), {
        "nota": "codigo mantido em 6 dígitos (padrão DATASUS); join deve truncar o lado IBGE de 7 dígitos",
        "municipio_residencia_ignorado_count": int(is_ignorado.sum()),
        "municipio_residencia_ignorado_pct": f"{is_ignorado.mean()*100:.2f}%",
    })
    return df


def cast_dates(df: pd.DataFrame, log: QualityLog) -> pd.DataFrame:
    before = len(df)
    df["data_obito"] = pd.to_datetime(
        df["DTOBITO"].astype(str).str.strip(),
        format="%d%m%Y",
        errors="coerce",
    )
    falhas = df["data_obito"].isna().sum()
    log.record("cast_dates", before, len(df), {"datas_invalidas_dtobito": int(falhas)})
    return df


def diagnostic_duplicate_check(df: pd.DataFrame, log: QualityLog) -> pd.DataFrame:
    """CONTADOR não teve unicidade entre arquivos confirmada — trata como
    diagnóstico, não filtro (mesmo princípio da ADR-002)."""
    before = len(df)
    if "CONTADOR" in df.columns:
        dupes_contador = df.duplicated(subset=["CONTADOR"], keep=False).sum()
    else:
        dupes_contador = None

    quasi_cols = [c for c in ["codigo_municipio_residencia", "data_obito", "CAUSABAS"] if c in df.columns]
    dupes_quasi = df.duplicated(subset=quasi_cols, keep=False).sum() if len(quasi_cols) == len(["codigo_municipio_residencia", "data_obito", "CAUSABAS"]) else None

    log.record("diagnostic_duplicate_check", before, len(df), {
        "contador_duplicado_entre_arquivos": int(dupes_contador) if dupes_contador is not None else "coluna ausente",
        "colisao_quase_identificador_municipio_data_causa": int(dupes_quasi) if dupes_quasi is not None else "n/a",
        "nota": "diagnóstico apenas — nenhuma linha removida por duplicidade não confirmada",
    })
    return df


def write_silver(df: pd.DataFrame, years, ufs):
    for year in years:
        year_df = df[df["_ano"] == year] if "_ano" in df.columns else df
        if year_df.empty:
            continue
        out_dir = SILVER_ROOT / f"ano={year}"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "data.parquet"
        year_df.to_parquet(out_path, compression="zstd")
        print(f"  -> {out_path} ({len(year_df):,} óbitos)")


def main():
    parser = argparse.ArgumentParser(description="Transformação bronze->silver SIM (óbitos TB)")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--years", type=int, nargs="+", default=list(range(2015, 2025)))
    parser.add_argument("--ufs", type=str, nargs="+", default=ALL_UFS)
    args = parser.parse_args()

    if args.validate_only:
        validate_municipio_code_mapping()
        return

    log = QualityLog(pipeline_name="bronze_to_silver_sim")

    print("Carregando bronze...")
    df = load_bronze(args.years, args.ufs)
    log.record("load_bronze", 0, len(df))

    df = normalize_municipio_code(df, log)
    df = cast_dates(df, log)
    df = diagnostic_duplicate_check(df, log)

    print("\nGravando silver...")
    write_silver(df, args.years, args.ufs)

    log.write(Path("quality/logs/bronze_to_silver_sim_last_run.json"))


if __name__ == "__main__":
    main()
