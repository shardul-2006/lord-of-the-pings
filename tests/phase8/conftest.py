import pytest
from fastapi.testclient import TestClient

from app.api import create_app


@pytest.fixture
def uploads(tmp_path):
    return tmp_path / "uploads"


@pytest.fixture
def client(tmp_path, uploads):
    app = create_app(home=tmp_path / "home", upload_root=uploads)
    with TestClient(app) as c:
        yield c
    app.state.shield.close()


@pytest.fixture
def upload(client, fixtures_dir):
    def do(name: str, as_name: str | None = None):
        with open(fixtures_dir / name, "rb") as fh:
            return client.post("/ingest", files={"file": (as_name or name, fh)})

    return do
