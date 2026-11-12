"""分层依赖边界测试（AC-1）。

api/ 不直连 agent/；agent/ 不 import 数据库驱动。
"""
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ALGORITHM = Path(__file__).resolve().parents[2] / "algorithm"


def _grep(pattern: str, path: Path) -> list[str]:
    result = subprocess.run(
        [sys.executable, "-c",
         f"import re, pathlib; "
         f"[print(str(p)) for p in pathlib.Path(r'{path}').rglob('*.py') "
         f"if re.search(r'{pattern}', p.read_text(encoding='utf-8', errors='ignore'))]"],
        capture_output=True, text=True,
    )
    return [l for l in result.stdout.splitlines() if l.strip()]


def test_api_does_not_import_agent():
    """api/ 路由文件不直接 import algorithm。"""
    api_dir = BACKEND / "app" / "api"
    for py in api_dir.rglob("*.py"):
        text = py.read_text(encoding="utf-8", errors="ignore")
        assert "from algorithm" not in text and "import algorithm" not in text, (
            f"{py} 不应直接 import algorithm"
        )


def test_algorithm_has_no_db_driver():
    """algorithm/ 不 import psycopg/sqlalchemy。"""
    for py in ALGORITHM.rglob("*.py"):
        if "test" in str(py):
            continue
        text = py.read_text(encoding="utf-8", errors="ignore")
        assert "psycopg" not in text, f"{py} 不应 import psycopg"
        assert "sqlalchemy" not in text.lower(), f"{py} 不应 import sqlalchemy"


def test_services_is_only_agent_caller():
    """只有 services/ 调 algorithm。"""
    for py in (BACKEND / "app").rglob("*.py"):
        if "services" in str(py):
            continue
        text = py.read_text(encoding="utf-8", errors="ignore")
        assert "from algorithm" not in text and "import algorithm" not in text, (
            f"{py} 不应直接 import algorithm（只有 services/ 可以）"
        )
