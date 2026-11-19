from pathlib import Path

import pytest

from rag_shield.rag.compare import compare
from rag_shield.rag.llm import MockLLM
from scripts.make_fixtures import main as make_fixtures

FIXTURES = Path(__file__).resolve().parents[2] / "data" / "fixtures"


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    make_fixtures(["--out", str(FIXTURES)])
    return FIXTURES


@pytest.fixture(scope="session")
def poisoned_traces(fixtures_dir):
    return compare(fixtures_dir / "smoke_poisoned.pdf", MockLLM())


@pytest.fixture(scope="session")
def clean_traces(fixtures_dir):
    return compare(fixtures_dir / "smoke_clean.pdf", MockLLM())
