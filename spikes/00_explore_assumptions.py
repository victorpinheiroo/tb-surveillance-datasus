"""
Spike de validação de premissas — referente à ADR-001.

Roda LOCALMENTE (precisa de acesso à internet ao DATASUS; este script não
funciona em ambientes com rede restrita, como o sandbox usado para gerar
os documentos deste projeto).

Objetivo: responder, com dado real, três perguntas que hoje são suposições
na ADR-001:

1. Qual é o código exato do agravo de tuberculose no catálogo do SINAN?
2. O schema (colunas) é realmente estável entre 2015 e 2023, ou existe
   diferença de campos dentro da janela escolhida?
3. Qual a taxa de preenchimento do campo de encerramento por ano — isso
   testa empiricamente a regra de "~2 anos de consolidação" usada na ADR,
   que hoje está confirmada só para o SIM, não para o SINAN-TB.
4. Qual o volume real de dado (linhas / MB) na janela 2015-2023, para
   decidir entre Git LFS (1 GB grátis) e GitHub Releases (2 GB por arquivo).

Requer: pip install pysus pandas
"""

import sys
from pysus import sinan, list_files

SAMPLE_YEARS = [2015, 2019, 2023]  # início, meio e fim da janela da ADR-001
CLOSURE_CANDIDATE_COLS = ["DT_ENCERRA", "SITUA_ENCE"]


def find_tb_code():
    """Lista arquivos do catálogo SINAN cujo nome sugere tuberculose.

    O código usado nas outras funções (DISEASE_CODE) deve ser conferido
    manualmente contra esta saída antes de seguir — não assuma que 'tube'
    está certo sem checar aqui primeiro.
    """
    print("Procurando arquivos de tuberculose no catálogo SINAN...\n")
    files = list_files("SINAN")  # DataFrame: iterar direto nele dá os nomes das colunas, não as linhas
    names = files["name"].astype(str)
    # "TB" solto dá falso positivo: o sufixo padrão dos arquivos é sempre "BR<ano>",
    # então qualquer código de agravo terminado em T (DIFT, HANT, ...) já contém "TB"
    # na junção com o sufixo. TUBE/TUBERC é o padrão real do agravo de tuberculose.
    is_tb = names.str.upper().str.contains("TUBE") | names.str.upper().str.contains("TUBERC")
    tb_files = names[is_tb].tolist()
    for f in tb_files[:20]:
        print(" -", f)
    if not tb_files:
        print("Nenhum arquivo encontrado automaticamente.")
        print("Rode list_files('SINAN') manualmente e procure na lista completa.")
    return tb_files


def check_schema_stability(disease_code, years):
    print("\n--- Estabilidade de schema ---")
    schemas = {}
    for year in years:
        df = sinan(disease=disease_code, year=year, as_dataframe=True)
        schemas[year] = set(df.columns)
        print(f"{year}: {len(df):,} registros, {len(df.columns)} colunas")

    base_year = years[0]
    for year in years[1:]:
        only_in_base = schemas[base_year] - schemas[year]
        only_in_other = schemas[year] - schemas[base_year]
        if only_in_base or only_in_other:
            print(f"\nDiferença de schema entre {base_year} e {year}:")
            print("  Só em", base_year, "->", only_in_base)
            print("  Só em", year, "->", only_in_other)
        else:
            print(f"\n{base_year} e {year}: mesmo conjunto de colunas.")
    return schemas


def check_closure_rate(disease_code, years):
    print("\n--- Taxa de encerramento por ano (teste do right-censoring) ---")
    for year in years:
        df = sinan(disease=disease_code, year=year, as_dataframe=True)
        found_col = next((c for c in CLOSURE_CANDIDATE_COLS if c in df.columns), None)
        if found_col:
            # No SINAN-TB, ausência de valor em DT_ENCERRA vem como string vazia
            # ('') e não como NaN — .notna() sozinho não pega isso e sempre dava
            # ~100%, mascarando o right-censoring que esta função deveria medir.
            raw = df[found_col]
            is_missing = raw.isna() | (raw.astype(str).str.strip() == "")
            filled = 1 - is_missing.mean()
            print(f"  {year}: {filled:.1%} dos casos com '{found_col}' preenchido")
        else:
            print(f"  {year}: nenhuma das colunas candidatas {CLOSURE_CANDIDATE_COLS} encontrada.")
            print(f"          Colunas disponíveis: {sorted(df.columns)}")


def estimate_volume(disease_code, years):
    print("\n--- Estimativa de volume ---")
    total_rows = 0
    for year in years:
        df = sinan(disease=disease_code, year=year, as_dataframe=True)
        rows = len(df)
        mb_in_memory = df.memory_usage(deep=True).sum() / 1e6
        total_rows += rows
        print(f"  {year}: {rows:,} linhas, ~{mb_in_memory:.1f} MB em memória (Parquet costuma ser bem menor)")
    print(f"\nTotal nos anos amostrados: {total_rows:,} linhas")
    print("Extrapole para os 9 anos da janela (2015-2023) e compare com:")
    print("  Git LFS: 1 GB grátis | GitHub Releases: 2 GB por arquivo, sem limite de número de arquivos")


if __name__ == "__main__":
    tb_files = find_tb_code()
    if not tb_files:
        sys.exit(1)

    # Ajuste este valor DEPOIS de confirmar o código correto na lista acima.
    DISEASE_CODE = "tube"

    check_schema_stability(DISEASE_CODE, SAMPLE_YEARS)
    check_closure_rate(DISEASE_CODE, SAMPLE_YEARS)
    estimate_volume(DISEASE_CODE, SAMPLE_YEARS)
