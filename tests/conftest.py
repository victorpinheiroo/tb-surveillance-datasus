import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
FIXTURES = Path(__file__).parent / "fixtures"

# Os scripts do pipeline são executados como scripts (não como pacote) e
# importam vizinhos pelo diretório — replica isso para os testes.
for sub in ("ingestion", "pipeline", "transformation/bronze_to_silver"):
    sys.path.insert(0, str(REPO_ROOT / sub))
