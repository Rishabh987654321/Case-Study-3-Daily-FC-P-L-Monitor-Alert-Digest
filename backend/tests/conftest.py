import os
import tempfile
from pathlib import Path

# Must run before any `app.*` import: app.db creates its engine (and hence
# reads DATABASE_URL) at module import time, so env vars have to land first.
# Uses a fresh OS temp dir (portable across machines) rather than anything
# under the project tree, so test runs never touch real app data.
_SCRATCH = Path(tempfile.mkdtemp(prefix="pnl_monitor_test_"))

os.environ["INSIGHT_MODE"] = "rule"
os.environ["DATABASE_URL"] = f"sqlite:///{_SCRATCH / 'test_pnl_monitor.db'}"
os.environ["UPLOAD_DIR"] = str(_SCRATCH / "uploads")
os.environ["NOTIFY_CHANNEL"] = "file"

import pytest  # noqa: E402

from app.config import Settings  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_XLSX = PROJECT_ROOT / "sample_data" / "input" / "fc_daily_data.xlsx"


@pytest.fixture(scope="session")
def sample_xlsx_path() -> Path:
    return SAMPLE_XLSX


@pytest.fixture
def settings_rule(tmp_path) -> Settings:
    """Settings with INSIGHT_MODE=rule so tests never depend on Ollama."""
    return Settings(insight_mode="rule", _env_file=None)


@pytest.fixture
def settings_default() -> Settings:
    return Settings(_env_file=None)
