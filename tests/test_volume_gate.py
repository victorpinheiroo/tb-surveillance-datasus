"""
Testes do gate de volume entre execuções (pipeline/volume_gate.py).

Fixtures: quality logs reais do SIM e da reconciliação nos commits cdfcd29
(execução validada) e f48a95b (execução contaminada de 2026-11-01).
"""

import copy
import json

import volume_gate
from conftest import FIXTURES

LOGS = ["bronze_to_silver_sim", "gold_fct_reconciliacao_sinan_sim"]


def _logs(ref):
    return {
        f"{name}_last_run.json": json.loads((FIXTURES / f"{name}_{ref}.json").read_text(encoding="utf-8"))
        for name in LOGS
    }


def _scaled(logs, factor):
    """Mesmos logs, com todas as contagens multiplicadas e um novo completed_at."""
    out = copy.deepcopy(logs)
    for log in out.values():
        log["completed_at"] = "2099-01-01T00:00:00+00:00"
        for step in log["steps"]:
            step["rows_before"] = round(step["rows_before"] * factor)
            step["rows_after"] = round(step["rows_after"] * factor)
    return out


def test_gate_rejects_the_real_incident():
    violations = volume_gate.compare(_logs("cdfcd29"), _logs("f48a95b"))
    assert any("bronze_to_silver_sim" in v and "40,205 -> 1,419,740" in v for v in violations)


def test_gate_accepts_normal_monthly_consolidation():
    good = _logs("cdfcd29")
    assert volume_gate.compare(good, _scaled(good, 1.01)) == []


def test_gate_accepts_a_new_partition_adding_a_few_percent():
    # Caso DOSP2021: uma partição que não existia soma alguns % ao TOTAL da
    # etapa. O gate compara totais por etapa, não partição a partição.
    good = _logs("cdfcd29")
    assert volume_gate.compare(good, _scaled(good, 1.06)) == []


def test_gate_ignores_counts_that_were_zero_before():
    good = _logs("cdfcd29")
    current = _scaled(good, 1.0)
    current["bronze_to_silver_sim_last_run.json"]["steps"].append(
        {"step": "nova_etapa", "rows_before": 0, "rows_after": 500}
    )
    assert volume_gate.compare(good, current) == []


def test_gate_skips_logs_not_rewritten_in_this_run():
    # mesmo completed_at = log não foi reescrito (ex.: --stage parcial), então
    # nem o salto de 35x é comparado — o gate só julga o que esta execução gerou.
    same_timestamp = _logs("f48a95b")
    for name, log in same_timestamp.items():
        log["completed_at"] = _logs("cdfcd29")[name]["completed_at"]
    assert volume_gate.compare(_logs("cdfcd29"), same_timestamp) == []
