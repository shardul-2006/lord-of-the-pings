from pathlib import Path

import pytest

from scripts.make_fixtures import main as make_fixtures

FIXTURES = Path(__file__).resolve().parents[1] / "data" / "fixtures"


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    make_fixtures(["--out", str(FIXTURES)])
    return FIXTURES
