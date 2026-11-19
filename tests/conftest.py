from pathlib import Path

import pytest

from scripts.make_fixtures import main as make_fixtures

FIXTURES = Path(__file__).resolve().parents[1] / "data" / "fixtures"


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    make_fixtures(["--out", str(FIXTURES)])
    return FIXTURES


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Never let tests write a ledger or forensic copies into the real home directory."""
    home = tmp_path / "rag_shield_home"
    monkeypatch.setenv("RAG_SHIELD_HOME", str(home))
    return home
