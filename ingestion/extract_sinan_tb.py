"""
Ingestão bronze — SINAN-TB (notificações de tuberculose).

Referência: ADR-001 (docs/adrs/ADR-001-escopo-fonte-infraestrutura.md)

Comportamento:
- Baixa um arquivo nacional por ano via PySUS (`sinan(disease="tube", year=Y)`).
- Não aplica NENHUMA transformação de conteúdo — bronze é cópia fiel da fonte.
- Adiciona apenas colunas de proveniência (fonte, timestamp de extração,
  dataset), nunca altera ou remove colunas originais.
- Particiona em disco por `ano` (não por UF — o SINAN entrega um arquivo
  nacional por ano, diferente do SIM).
- Marca anos >= PROVISIONAL_FROM_YEAR com uma flag de proveniência
  `_status_maturidade_estimado`, que é só um sinal de bronze; o cálculo
  definitivo de maturidade (com base em DT_ENCERRA) é responsabilidade
  do silver, não do bronze.

Uso:
    python ingestion/extract_sinan_tb.py --years 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024
"""

import argparse
import asyncio
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from pysus import sinan
from pysus.api.client import PySUS

DISEASE_CODE = "tube"
BRONZE_ROOT = Path("bronze/sinan_tb")

# Ano a partir do qual o dado é estruturalmente sujeito a right-censoring
# significativo, conforme validado empiricamente no spike (ADR-001).
# Isso é só uma flag informativa no bronze — não filtra nem descarta nada.
PROVISIONAL_FROM_YEAR = 2024


def checksum_dataframe(df) -> str:
    """Hash determinístico do conteúdo, para rastreabilidade em auditoria."""
    return hashlib.sha256(
        df.to_csv(index=False).encode("utf-8")
    ).hexdigest()[:16]


def _fetch_without_group_filter(year: int) -> pd.DataFrame:
    """Contorna bug de metadado do catálogo PySUS onde alguns arquivos SINAN
    têm group_id nulo, fazendo sinan(..., group=<disease>) excluí-los
    silenciosamente mesmo quando o arquivo existe e está saudável.

    Consulta o dataset sinan sem filtro de group e filtra no lado do
    cliente pelo nome do arquivo (ex: TUBEBR16.parquet).
    """
    file_prefix = f"{DISEASE_CODE.upper()}BR{str(year)[-2:]}"

    async def _run() -> pd.DataFrame:
        async with PySUS() as p:
            files = await p.query(dataset="sinan")
            matches = [f for f in files if file_prefix in str(f.path)]
            if not matches:
                return pd.DataFrame()

            paths = [str((await p.download(f)).path) for f in matches]
            return p.read_parquet(paths).df()

    return asyncio.run(_run())


def extract_year(year: int) -> Path:
    print(f"Baixando SINAN-TB {year}...")
    df = sinan(disease=DISEASE_CODE, year=year, as_dataframe=True)
    extraction_method = "normal"

    if df.empty:
        print(
            f"  aviso: sinan() retornou vazio para {year} "
            f"(possível bug de metadado no catálogo); tentando fallback..."
        )
        df = _fetch_without_group_filter(year)
        extraction_method = "fallback_no_group_filter"

        if df.empty:
            raise RuntimeError(
                f"SINAN-TB {year}: nenhum dado disponível no catálogo PySUS "
                f"mesmo sem filtro de group — ano genuinamente sem arquivo."
            )

    ingested_at = datetime.now(timezone.utc).isoformat()
    df["_source_dataset"] = f"SINAN-TUBE-{year}"
    df["_ingested_at"] = ingested_at
    df["_status_maturidade_estimado"] = (
        "provisorio" if year >= PROVISIONAL_FROM_YEAR else "fechado"
    )

    out_dir = BRONZE_ROOT / f"ano={year}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "data.parquet"

    df.to_parquet(out_path, compression="zstd")

    checksum = checksum_dataframe(df)
    meta_path = out_dir / "_metadata.txt"
    meta_lines = (
        f"source=PySUS sinan(disease='{DISEASE_CODE}', year={year})\n"
        f"ingested_at={ingested_at}\n"
        f"rows={len(df)}\n"
        f"columns={len(df.columns)}\n"
        f"checksum_sha256_16={checksum}\n"
    )
    if extraction_method == "fallback_no_group_filter":
        meta_lines += "extraction_method=fallback_no_group_filter\n"
    meta_path.write_text(meta_lines)

    print(f"  -> {out_path} ({len(df):,} linhas, checksum={checksum})")
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Ingestão bronze do SINAN-TB")
    parser.add_argument(
        "--years", type=int, nargs="+", required=True,
        help="Anos a extrair, ex: --years 2015 2016 2017"
    )
    args = parser.parse_args()

    for year in args.years:
        extract_year(year)


if __name__ == "__main__":
    main()
