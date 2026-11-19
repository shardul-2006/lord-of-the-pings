import pytest

from rag_shield.rag.compare import compare
from rag_shield.rag.llm import MockLLM


@pytest.fixture(scope="session")
def poisoned_traces(fixtures_dir):
    return compare(fixtures_dir / "smoke_poisoned.pdf", MockLLM())


@pytest.fixture(scope="session")
def clean_traces(fixtures_dir):
    return compare(fixtures_dir / "smoke_clean.pdf", MockLLM())
