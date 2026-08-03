"""
Ingestão bronze — População estimada por município (IBGE/SIDRA, tabela 6579).

Necessário para normalizar incidência de TB por 100 mil habitantes
(pergunta de negócio central do projeto — ver ADR-001).

IMPORTANTE — validar antes de rodar em escala:
2022 foi ano de Censo Demográfico, não de estimativa intercensitária. É
possível que a tabela 6579 (Estimativas) não cubra 2022 da mesma forma que
os demais anos, exigindo uma fonte complementar (tabela 4714, Censo) só
para esse ano. Rode `--validate-only` primeiro para confirmar cobertura
de período antes de baixar em escala — mesmo princípio já aplicado ao
SINAN-TB e ao SIM neste projeto (nunca assumir cobertura uniforme).

O código da variável ("9324" abaixo) é um PALPITE baseado em tabelas
semelhantes do SIDRA — não confirmado. `validate_coverage()` testa um
download real de amostra para expor isso antes da extração em escala.

Uso:
    python ingestion/extract_ibge_population.py --validate-only
    python ingestion/extract_ibge_population.py --years 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024
"""

import argparse
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import sidrapy

BRONZE_ROOT = Path("bronze/ibge_population")
TABLE_CODE = "6579"  # Estimativas de população residente para os municípios
CENSUS_TABLE_CODE = "4714"  # Censo Demográfico 2022 — usado como fonte para 2022 E 2023

# Confirmado via metadados da API (2026-08-03): tabela 6579 não tem dado para
# 2022 nem 2023 (retirada do calendário SIDRA, substituída por Censo). O
# próprio IBGE usou o Censo 2022 como base oficial também para 2023
# (atualizado só por limite territorial, publicado via DOU, fora do SIDRA).
# Decisão do projeto (ver ADR-003): replicar essa mesma lógica — usar o
# valor do Censo 2022 (tabela 4714, variável 93) para os dois anos, marcado
# explicitamente via `_status_fonte_populacao`.
CENSUS_PROXY_YEARS = (2022, 2023)


def checksum_dataframe(df) -> str:
    return hashlib.sha256(df.to_csv(index=False).encode("utf-8")).hexdigest()[:16]


def validate_coverage(years):
    """Consulta metadados da tabela 6579 (sem baixar tudo) e testa um
    download real de amostra, para confirmar período coberto e formato
    de retorno antes de rodar em escala."""
    import requests

    url = f"https://servicodados.ibge.gov.br/api/v3/agregados/{TABLE_CODE}/metadados"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    meta = resp.json()

    periodicidade = meta.get("periodicidade", {})
    print(f"Periodicidade declarada na tabela {TABLE_CODE}: {periodicidade}")
    print(f"Anos {CENSUS_PROXY_YEARS} são conhecidos como ausentes na prática "
          f"(confirmado por teste real), apesar de dentro do range nominal — "
          f"ver CENSUS_PROXY_YEARS e ADR-003.")

    print("\nTeste de download real (amostra) para validar formato de retorno...")
    sample = sidrapy.get_table(
        table_code=TABLE_CODE,
        territorial_level="6",
        ibge_territorial_code="all",
        variable="9324",
        period=str(years[0]),
    )
    print(f"  Shape: {getattr(sample, 'shape', 'N/A')}")


def _fetch_census_population():
    """Baixa a população do Censo 2022 (tabela 4714), usada como fonte para
    2022 e 2023 (ver ADR-003)."""
    df = sidrapy.get_table(
        table_code=CENSUS_TABLE_CODE,
        territorial_level="6",
        ibge_territorial_code="all",
        variable="93",
        period="2022",
    )
    return df


def extract_year(year: int) -> Path:
    if year in CENSUS_PROXY_YEARS:
        print(f"Ano {year}: usando Censo 2022 (tabela {CENSUS_TABLE_CODE}) como fonte — ver ADR-003.")
        df = _fetch_census_population()
        source_label = f"IBGE-SIDRA-{CENSUS_TABLE_CODE}-censo2022-proxy-para-{year}"
        status_fonte = "proxy_censo_2022"
    else:
        print(f"Baixando população IBGE {year} (todos os municípios)...")
        df = sidrapy.get_table(
            table_code=TABLE_CODE,
            territorial_level="6",
            ibge_territorial_code="all",
            variable="9324",
            period=str(year),
        )
        source_label = f"IBGE-SIDRA-{TABLE_CODE}-{year}"
        status_fonte = "estimativa_direta"

    ingested_at = datetime.now(timezone.utc).isoformat()
    df["_source_dataset"] = source_label
    df["_ingested_at"] = ingested_at
    df["_status_fonte_populacao"] = status_fonte

    out_dir = BRONZE_ROOT / f"ano={year}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "data.parquet"
    df.to_parquet(out_path, compression="zstd")

    checksum = checksum_dataframe(df)
    meta_path = out_dir / "_metadata.txt"
    meta_path.write_text(
        f"source={source_label}\n"
        f"status_fonte_populacao={status_fonte}\n"
        f"ingested_at={ingested_at}\n"
        f"rows={len(df)}\n"
        f"checksum_sha256_16={checksum}\n"
    )
    print(f"  -> {out_path} ({len(df):,} linhas, checksum={checksum}, status={status_fonte})")
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Ingestão bronze de população IBGE")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--years", type=int, nargs="+")
    args = parser.parse_args()

    years = args.years or list(range(2015, 2025))

    if args.validate_only:
        validate_coverage(years)
        return

    for year in years:
        extract_year(year)


if __name__ == "__main__":
    main()