"""
Ingestão bronze — SIM (óbitos), filtrado para causas relacionadas a
tuberculose, para uso na reconciliação SINAN x SIM (ver ADR-001).

IMPORTANTE — validar antes de rodar em escala:
O nome da coluna de causa básica de óbito (`CAUSA_COL` abaixo) e os
prefixos CID-10 de tuberculose (A15-A19) precisam ser confirmados contra
uma amostra real antes de rodar para todos os 27 estados x 9 anos — do
mesmo jeito que "DT_ENCERRA" só foi confirmado no SINAN depois de inspeção
manual. Rode primeiro `validate_sim_schema()` para um único estado/ano
antes de decidir se o filtro está certo.

Comportamento:
- Baixa um arquivo por (UF, ano) via PySUS (`sim(state=UF, year=Y)`).
- Filtra somente óbitos cuja causa básica começa com A15-A19 (CID-10,
  tuberculose) — o filtro é a única transformação aplicada aqui, e ainda
  assim é registrado explicitamise como decisão de ingestão, não fica
  implícito.
- Particiona em disco por `uf/ano` (diferente do SINAN-TB, que é só por
  ano — o SIM é entregue pela fonte por estado).
- Adiciona colunas de proveniência, igual ao script do SINAN.

Uso:
    python ingestion/extract_sim_tb_deaths.py --validate-only --state SP --year 2023
    python ingestion/extract_sim_tb_deaths.py --years 2015 2019 2023 --states SP RJ MG
"""

import argparse
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from pysus import list_files, sim

BRONZE_ROOT = Path("bronze/sim_tb_deaths")

# CID-10: A15-A19 cobre tuberculose respiratória e de outros órgãos.
TB_ICD10_PREFIXES = ("A15", "A16", "A17", "A18", "A19")

# Nome candidato da coluna de causa básica no SIM — CONFIRMAR antes de usar
# em escala. Se `validate_sim_schema` não encontrar essa coluna, ajuste aqui.
CAUSA_COL_CANDIDATES = ["CAUSABAS", "CAUSABAS_O"]

ALL_UFS = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
    "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
    "SP", "SE", "TO",
]


def checksum_dataframe(df) -> str:
    return hashlib.sha256(df.to_csv(index=False).encode("utf-8")).hexdigest()[:16]


def validate_sim_schema(state: str, year: int):
    """Roda isso primeiro, para UM estado/ano, antes de qualquer extração em escala."""
    print(f"Validando schema do SIM para {state}/{year}...")
    df = sim(state=state, year=year, as_dataframe=True)
    found = [c for c in CAUSA_COL_CANDIDATES if c in df.columns]
    print(f"  Colunas candidatas encontradas: {found or 'NENHUMA — ver df.columns abaixo'}")
    if not found:
        print(f"  Colunas disponíveis: {sorted(df.columns)}")
        return
    col = found[0]
    sample = df[col].dropna().astype(str).str[:3].value_counts().head(10)
    print(f"  Amostra de prefixos CID-10 em '{col}':\n{sample}")
    tb_count = df[col].astype(str).str.startswith(TB_ICD10_PREFIXES).sum()
    print(f"  Registros que bateriam com o filtro de TB (A15-A19): {tb_count} de {len(df)}")


def build_coverage_report(states: list[str], years: list[int]) -> pd.DataFrame:
    """Consulta o catálogo do SIM (sem baixar nenhum dado) para cada combinação
    UF x ano e monta uma matriz de disponibilidade.

    O SIM tem gaps de publicação irregulares por UF — confirmado empiricamente
    para SP (sem arquivo para 2021, 2023 e 2024 no catálogo espelhado pelo
    PySUS, mesmo com outros estados já tendo 2024 disponível). Não é seguro
    assumir cobertura uniforme UF x ano. Rode isso ANTES de qualquer extração
    em escala, para saber de antemão quais combinações vão falhar.
    """
    rows = []
    for state in states:
        row = {"state": state}
        for year in years:
            matches = list_files("SIM", state=state, year=year)
            row[year] = bool(len(matches))
        rows.append(row)

    report = pd.DataFrame(rows).set_index("state")

    print("\n--- Relatório de cobertura SIM (UF x ano) ---")
    print(report.replace({True: "OK", False: "AUSENTE"}).to_string())

    missing = [
        (state, year)
        for state in states
        for year in years
        if not report.loc[state, year]
    ]
    if missing:
        print(f"\n{len(missing)} combinação(ões) UF x ano sem arquivo no catálogo:")
        for state, year in missing:
            print(f"  - {state}/{year}")
    else:
        print("\nTodas as combinações UF x ano têm arquivo no catálogo.")

    return report


def extract_state_year(state: str, year: int) -> Path | None:
    print(f"Baixando SIM {state}/{year}...")
    df = sim(state=state, year=year, as_dataframe=True)

    if df.shape == (0, 0):
        raise RuntimeError(
            f"sim(state='{state}', year={year}) não retornou nenhum arquivo do "
            f"catálogo (DataFrame vazio, 0 colunas). Isso é um gap de cobertura "
            f"conhecido do SIM (ex.: SP não tem arquivo para 2021/2023/2024), não "
            f"um erro de nome de coluna. Rode build_coverage_report(states, years) "
            f"antes da extração em escala e trate esse UF/ano explicitamente — não "
            f"deixe passar como extração silenciosamente vazia."
        )

    causa_col = next((c for c in CAUSA_COL_CANDIDATES if c in df.columns), None)
    if causa_col is None:
        raise RuntimeError(
            f"Nenhuma coluna de causa básica encontrada em {state}/{year}. "
            f"Rode validate_sim_schema primeiro. Colunas: {sorted(df.columns)}"
        )

    df_tb = df[df[causa_col].astype(str).str.startswith(TB_ICD10_PREFIXES)].copy()

    ingested_at = datetime.now(timezone.utc).isoformat()
    df_tb["_source_dataset"] = f"SIM-{state}-{year}"
    df_tb["_ingested_at"] = ingested_at
    df_tb["_filter_applied"] = f"{causa_col} startswith {TB_ICD10_PREFIXES}"

    out_dir = BRONZE_ROOT / f"uf={state}" / f"ano={year}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "data.parquet"

    if df_tb.empty:
        print(f"  -> {state}/{year}: 0 óbitos de TB encontrados (arquivo não gravado)")
        return None

    df_tb.to_parquet(out_path, compression="zstd")

    checksum = checksum_dataframe(df_tb)
    meta_path = out_dir / "_metadata.txt"
    meta_path.write_text(
        f"source=PySUS sim(state='{state}', year={year})\n"
        f"filter={causa_col} startswith {TB_ICD10_PREFIXES}\n"
        f"ingested_at={ingested_at}\n"
        f"rows_total_source={len(df)}\n"
        f"rows_filtered_tb={len(df_tb)}\n"
        f"checksum_sha256_16={checksum}\n"
    )

    print(f"  -> {out_path} ({len(df_tb):,} óbitos de TB de {len(df):,} totais)")
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Ingestão bronze do SIM, filtrado para TB")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--state", type=str, help="UF única, usado com --validate-only")
    parser.add_argument("--year", type=int, help="Ano único, usado com --validate-only")
    parser.add_argument("--years", type=int, nargs="+")
    parser.add_argument(
        "--states", type=str, nargs="+", default=ALL_UFS,
        help="Default: todas as 27 UFs. Passe uma lista menor para testes."
    )
    args = parser.parse_args()

    if args.validate_only:
        if not (args.state and args.year):
            raise SystemExit("--validate-only requer --state e --year")
        validate_sim_schema(args.state, args.year)
        return

    if not args.years:
        raise SystemExit("--years é obrigatório fora do modo --validate-only")

    report = build_coverage_report(args.states, args.years)

    for year in args.years:
        for state in args.states:
            if not report.loc[state, year]:
                print(
                    f"  pulando {state}/{year}: gap de cobertura já confirmado "
                    f"no catálogo (ver relatório acima), não é erro"
                )
                continue
            extract_state_year(state, year)


if __name__ == "__main__":
    main()
