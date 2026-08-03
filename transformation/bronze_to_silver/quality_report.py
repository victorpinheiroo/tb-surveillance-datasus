"""
Log estruturado de qualidade para transformações bronze->silver.

Formato baseado no padrão de logging estruturado de pipeline (ver
docs/adrs — decisão de nunca deixar transformação silenciosa). Cada
execução produz um JSON com contagens antes/depois por regra aplicada,
não só um "OK" final.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class QualityLog:
    pipeline_name: str
    steps: list = field(default_factory=list)
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def record(self, step_name: str, rows_before: int, rows_after: int, detail: dict = None):
        self.steps.append({
            "step": step_name,
            "rows_before": rows_before,
            "rows_after": rows_after,
            "rows_changed": rows_before - rows_after,
            "detail": detail or {},
        })
        change_note = f" ({rows_before - rows_after:+d})" if rows_before != rows_after else ""
        print(f"  [{step_name}] {rows_before:,} -> {rows_after:,}{change_note}")
        if detail:
            for k, v in detail.items():
                print(f"      {k}: {v}")

    def write(self, out_path: Path):
        payload = {
            "pipeline_name": self.pipeline_name,
            "started_at": self.started_at,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "steps": self.steps,
        }
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nLog de qualidade salvo em {out_path}")
