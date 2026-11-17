"""
Quality gate de variação de volume ENTRE execuções.

Motivação (incidente 2026-10, ver docs/known-issues.md): uma execução mensal
automática fez o SIM saltar de 40.205 para 1.419.740 linhas (~35x) por
mudança de comportamento do PySUS. Os logs de qualidade registraram tudo —
inclusive 100% de CONTADOR duplicado — mas cada log só olhava para a própria
execução, e nada comparava com a anterior. O pipeline terminou com sucesso e
o commit automático publicou o número errado no dashboard.

Como funciona:
- Antes de rodar, `snapshot()` lê os `quality/logs/*_last_run.json` atuais
  (no GitHub Actions, são os da última execução commitada).
- Depois de rodar, `compare()` confronta, para cada log reescrito, as
  contagens `rows_before`/`rows_after` de cada etapa com as da execução
  anterior. Variação relativa acima do limite reprova o pipeline (exit != 0),
  o que impede o commit automático no workflow.

Limite padrão de 25%: a consolidação mensal normal mexe ~1% (SINAN
2026-08 -> 2026-10: 951.035 -> 950.825). Mudança legítima maior (ex.:
estender a janela de anos, ADR-004) é decisão manual — rode com
`--accept-volume-change` e documente.

Uso isolado (compara dois commits, útil para auditoria):
    python pipeline/volume_gate.py --from-ref cdfcd29 --to-ref f48a95b
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

LOG_DIR = Path("quality/logs")
DEFAULT_MAX_RELATIVE_CHANGE = 0.25


def _read_log_text(text: str) -> dict:
    return json.loads(text)


def snapshot(repo_root: Path) -> dict[str, dict]:
    logs = {}
    for path in sorted((repo_root / LOG_DIR).glob("*_last_run.json")):
        logs[path.name] = _read_log_text(path.read_text(encoding="utf-8"))
    return logs


def snapshot_from_git(repo_root: Path, ref: str) -> dict[str, dict]:
    names = subprocess.run(
        ["git", "ls-tree", "--name-only", f"{ref}:{LOG_DIR.as_posix()}"],
        cwd=repo_root, capture_output=True, text=True, check=True,
    ).stdout.split()
    logs = {}
    for name in names:
        if name.endswith("_last_run.json"):
            text = subprocess.run(
                ["git", "show", f"{ref}:{LOG_DIR.as_posix()}/{name}"],
                cwd=repo_root, capture_output=True, text=True, check=True, encoding="utf-8",
            ).stdout
            logs[name] = _read_log_text(text)
    return logs


def _step_counts(log: dict) -> dict[tuple[str, str], int]:
    counts = {}
    for step in log.get("steps", []):
        for field in ("rows_before", "rows_after"):
            value = step.get(field)
            if isinstance(value, int) and value > 0:
                counts[(step["step"], field)] = value
    return counts


def compare(previous: dict[str, dict], current: dict[str, dict],
            max_relative_change: float = DEFAULT_MAX_RELATIVE_CHANGE) -> list[str]:
    """Retorna a lista de violações (vazia = aprovado)."""
    violations = []
    for name, cur_log in sorted(current.items()):
        prev_log = previous.get(name)
        if prev_log is None:
            print(f"  [volume_gate] {name}: sem execução anterior — primeira execução, não comparado")
            continue
        if prev_log.get("completed_at") == cur_log.get("completed_at"):
            continue  # log não foi reescrito nesta execução (ex.: --stage parcial)
        prev_counts = _step_counts(prev_log)
        for key, cur_value in _step_counts(cur_log).items():
            prev_value = prev_counts.get(key)
            if prev_value is None:
                continue
            change = (cur_value - prev_value) / prev_value
            if abs(change) > max_relative_change:
                violations.append(
                    f"{name} :: {key[0]}.{key[1]}: {prev_value:,} -> {cur_value:,} "
                    f"({change:+.1%}, limite ±{max_relative_change:.0%})"
                )
    return violations


def report(violations: list[str], max_relative_change: float) -> bool:
    if not violations:
        print(f"\n[volume_gate] OK — nenhuma contagem variou mais de ±{max_relative_change:.0%} "
              f"em relação à execução anterior.")
        return True
    print(f"\n!!! [volume_gate] REPROVADO — {len(violations)} contagem(ns) variaram mais de "
          f"±{max_relative_change:.0%} em relação à execução anterior:")
    for v in violations:
        print(f"    - {v}")
    print("    Investigue antes de publicar. Se a mudança for intencional (ex.: janela de anos "
          "estendida), rode com --accept-volume-change e documente o motivo.")
    return False


def main():
    parser = argparse.ArgumentParser(description="Compara volumes de quality logs entre dois commits")
    parser.add_argument("--from-ref", required=True)
    parser.add_argument("--to-ref", default="HEAD")
    parser.add_argument("--max-relative-change", type=float, default=DEFAULT_MAX_RELATIVE_CHANGE)
    args = parser.parse_args()

    repo_root = Path(__file__).parent.parent
    violations = compare(
        snapshot_from_git(repo_root, args.from_ref),
        snapshot_from_git(repo_root, args.to_ref),
        args.max_relative_change,
    )
    sys.exit(0 if report(violations, args.max_relative_change) else 1)


if __name__ == "__main__":
    main()
