"""
Dimensão de referência — código IBGE de UF <-> sigla.

Tabela estática e estável (padrão IBGE, 27 UFs), diferente das dimensões
de município que exigiram validação empírica extensa neste projeto — não
há histórico de mudança nesses códigos, então não é tratada como SCD2 nem
como algo a validar contra dado real.

Motivada por dois usos:
  1. Destravar o join em `build_fct_reconciliacao_sinan_sim.py` (SINAN usa
     código numérico em SG_UF, SIM usa sigla via particionamento do bronze).
  2. Permitir rollup de UF em `fct_taxa_abandono` — achado empírico mostrou
     que ~90% dos municípios têm menos de 30 casos encerrados/ano em toda
     a série (2015-2024), tornando a taxa em nível de município
     estatisticamente instável para a maior parte das linhas. Nível de UF
     agrega o suficiente para ser a visão principal recomendada.

Uso:
    python transformation/silver_to_gold/dim_uf.py
"""

from pathlib import Path

import pandas as pd

GOLD_ROOT = Path("gold/dim_uf")

# Fonte: tabela de código de UF do IBGE (padrão nacional, usado por SG_UF
# no SINAN-TB — já confirmado nos dados reais: 35=SP, 41=PR, 29=BA, 15=PA,
# 23=CE aparecem exatamente assim no schema-reference-sinan-tb.md).
UF_MAPPING = [
    ("11", "RO", "Rondônia"), ("12", "AC", "Acre"), ("13", "AM", "Amazonas"),
    ("14", "RR", "Roraima"), ("15", "PA", "Pará"), ("16", "AP", "Amapá"),
    ("17", "TO", "Tocantins"), ("21", "MA", "Maranhão"), ("22", "PI", "Piauí"),
    ("23", "CE", "Ceará"), ("24", "RN", "Rio Grande do Norte"), ("25", "PB", "Paraíba"),
    ("26", "PE", "Pernambuco"), ("27", "AL", "Alagoas"), ("28", "SE", "Sergipe"),
    ("29", "BA", "Bahia"), ("31", "MG", "Minas Gerais"), ("32", "ES", "Espírito Santo"),
    ("33", "RJ", "Rio de Janeiro"), ("35", "SP", "São Paulo"), ("41", "PR", "Paraná"),
    ("42", "SC", "Santa Catarina"), ("43", "RS", "Rio Grande do Sul"),
    ("50", "MS", "Mato Grosso do Sul"), ("51", "MT", "Mato Grosso"),
    ("52", "GO", "Goiás"), ("53", "DF", "Distrito Federal"),
]


def build() -> pd.DataFrame:
    df = pd.DataFrame(UF_MAPPING, columns=["uf_codigo", "uf_sigla", "uf_nome"])
    assert len(df) == 27, f"Esperado 27 UFs, obtido {len(df)}"
    assert df["uf_codigo"].is_unique and df["uf_sigla"].is_unique, "códigos ou siglas duplicados"
    return df


def main():
    df = build()
    GOLD_ROOT.mkdir(parents=True, exist_ok=True)
    out_path = GOLD_ROOT / "data.parquet"
    df.to_parquet(out_path)
    print(f"-> {out_path} ({len(df)} UFs)")
    print("\nValidação: confira manualmente algumas linhas contra o que já apareceu nos dados reais")
    print("(35=SP, 41=PR, 29=BA, 15=PA, 23=CE já confirmados em schema-reference-sinan-tb.md):")
    print(df[df["uf_sigla"].isin(["SP", "PR", "BA", "PA", "CE"])].to_string(index=False))


if __name__ == "__main__":
    main()
