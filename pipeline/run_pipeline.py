"""
Orquestrador do pipeline completo — bronze -> silver -> gold.

Referência: ADR-004 (orquestração). Roda os 11 scripts do projeto em
ordem, parando no primeiro erro (fail-fast) — um estágio quebrado não deve
deixar estágios seguintes rodarem sobre dado incompleto/inconsistente.

Janela de anos é FIXA e validada (2015-2024) — não é calculada
dinamicamente a partir do ano atual. Estender a janela é uma decisão
manual deliberada (ver ADR-004), não algo que este orquestrador faz
sozinho, porque todo ano novo até agora trouxe uma particularidade que
exigiu investigação humana antes de confiar no dado.

Uso:
    python pipeline/run_pipeline.py
    python pipeline/run_pipeline.py --stage bronze   # só ingestão
    python pipeline/run_pipeline.py --stage silver   # só bronze->silver
    python pipeline/run_pipeline.py --stage gold     # só silver->gold
"""

import argparse
import subprocess
import sys
from pathlib import Path

YEARS = [str(y) for y in range(2015, 2025)]  # fixo — ver docstring acima

REPO_ROOT = Path(__file__).parent.parent

# extract_sim_tb_deaths.py roda um ano por chamada de subprocesso (não um
# --years com os 10 juntos) — motivo: retenção de memória confirmada
# empiricamente dentro de chamadas repetidas a sim() (PySUS), crescimento
# acelerado e não coletável via gc.collect() (medido: ~1.7GB -> ~7.6GB em
# 80 iterações de um total de ~270). Isolar cada ano em subprocesso
# separado deixa o SO liberar toda a memória entre um ano e outro, sem
# depender de entender/corrigir a causa raiz dentro da lib de terceiros.
SINAN_STEPS = [
    ("ingestion/extract_sinan_tb.py", ["--years"] + YEARS),
]

SIM_STEPS = [
    ("ingestion/extract_sim_tb_deaths.py", ["--years", year])
    for year in YEARS
]

POPULATION_STEPS = [
    ("ingestion/extract_ibge_population.py", ["--years"] + YEARS),
]

BRONZE_STEPS = SINAN_STEPS + SIM_STEPS + POPULATION_STEPS

SILVER_STEPS = [
    ("transformation/bronze_to_silver/transform_sinan_tb.py", ["--years"] + YEARS),
    ("transformation/bronze_to_silver/transform_population.py", ["--years"] + YEARS),
    ("transformation/bronze_to_silver/build_dim_municipio.py", ["--years"] + YEARS),
    ("transformation/bronze_to_silver/transform_sim.py", ["--years"] + YEARS),
]

GOLD_STEPS = [
    ("transformation/silver_to_gold/dim_uf.py", []),
    ("transformation/silver_to_gold/build_fct_incidencia.py", ["--years"] + YEARS),
    ("transformation/silver_to_gold/build_fct_taxa_abandono.py", ["--years"] + YEARS),
    ("transformation/silver_to_gold/build_fct_reconciliacao_sinan_sim.py", ["--years"] + YEARS),
]


def run_step(script_path: str, args: list) -> bool:
    full_path = REPO_ROOT / script_path
    print(f"\n{'=' * 70}\n>>> {script_path} {' '.join(args)}\n{'=' * 70}")
    result = subprocess.run(
        [sys.executable, str(full_path)] + args,
        cwd=str(REPO_ROOT),
    )
    if result.returncode != 0:
        print(f"\n!!! FALHA em {script_path} (exit code {result.returncode}) — pipeline interrompido.")
        return False
    return True


def run_stage(steps, stage_name: str) -> bool:
    print(f"\n########## ESTÁGIO: {stage_name.upper()} ##########")
    for script_path, args in steps:
        if not run_step(script_path, args):
            return False
    return True


def main():
    parser = argparse.ArgumentParser(description="Orquestrador do pipeline TB-DATASUS")
    parser.add_argument("--stage", choices=["bronze", "silver", "gold", "all"], default="all")
    args = parser.parse_args()

    stages = {
        "bronze": [(BRONZE_STEPS, "bronze")],
        "silver": [(SILVER_STEPS, "silver")],
        "gold": [(GOLD_STEPS, "gold")],
        "all": [(BRONZE_STEPS, "bronze"), (SILVER_STEPS, "silver"), (GOLD_STEPS, "gold")],
    }[args.stage]

    for steps, name in stages:
        if not run_stage(steps, name):
            print(f"\nPipeline abortado no estágio '{name}'.")
            sys.exit(1)

    print("\n\nPipeline completo executado com sucesso.")


if __name__ == "__main__":
    main()
