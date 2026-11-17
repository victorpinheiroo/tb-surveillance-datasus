"""
Testes das guardas criadas após o incidente 2026-10 (docs/known-issues.md).

Fixtures são recortes do dado REAL de AC/2015 e SP/2015: a versão
contaminada (execução de 2026-11-01, PySUS 2.11.7) e a validada (cdfcd29).
Colunas mantidas: CONTADOR, CODMUNRES, _source_dataset.
"""

import pandas as pd
import pytest

import extract_sim_tb_deaths as extract
import transform_sim
from conftest import FIXTURES
from quality_report import QualityLog


@pytest.fixture
def contaminated():
    return pd.read_parquet(FIXTURES / "sim_bronze_2015_AC_SP_contaminated.parquet")


@pytest.fixture
def validated():
    return pd.read_parquet(FIXTURES / "sim_bronze_2015_AC_SP_validated.parquet")


def _file(df, state):
    return df[df["_source_dataset"] == f"SIM-{state}-2015"]


# --- guarda de conteúdo: residência na própria UF ---------------------------

@pytest.mark.parametrize("state", ["AC", "SP"])
def test_residence_guard_accepts_validated_state_file(validated, state):
    extract.assert_rows_belong_to_state(_file(validated, state), state, 2015)


@pytest.mark.parametrize("state", ["AC", "SP"])
def test_residence_guard_rejects_file_with_national_rows(contaminated, state):
    with pytest.raises(RuntimeError, match="residência"):
        extract.assert_rows_belong_to_state(_file(contaminated, state), state, 2015)


# --- guarda de catálogo: só arquivos da UF pedida ---------------------------

def _catalog(*rows):
    return pd.DataFrame([{"name": n, "state": s} for n, s in rows])


def test_catalog_guard_accepts_state_only_catalog(monkeypatch):
    monkeypatch.setattr(extract, "list_files", lambda *a, **k: _catalog(("DOAC2015.parquet", "AC")))
    assert list(extract.catalog_files_for("AC", 2015)["name"]) == ["DOAC2015.parquet"]


def test_catalog_guard_accepts_empty_catalog_as_coverage_gap(monkeypatch):
    monkeypatch.setattr(extract, "list_files", lambda *a, **k: pd.DataFrame(columns=["name", "state"]))
    assert len(extract.catalog_files_for("SP", 2021)) == 0


def test_catalog_guard_rejects_national_file_with_null_state(monkeypatch):
    # Saída real de list_files("SIM", state="AC", year=2015) no PySUS 2.11.7.
    monkeypatch.setattr(extract, "list_files", lambda *a, **k: _catalog(
        ("DOAC2015.parquet", "AC"),
        ("Mortalidade_Geral_2015.parquet", None),
    ))
    with pytest.raises(RuntimeError, match="outra UF ou sem UF"):
        extract.catalog_files_for("AC", 2015)


# --- teto de duplicidade de CONTADOR no silver -------------------------------

def test_duplicate_ceiling_accepts_validated_data(validated):
    transform_sim.diagnostic_duplicate_check(validated, QualityLog("test"))


def test_duplicate_ceiling_rejects_same_deaths_in_multiple_states(contaminated):
    with pytest.raises(RuntimeError, match="CONTADOR duplicado"):
        transform_sim.diagnostic_duplicate_check(contaminated, QualityLog("test"))
