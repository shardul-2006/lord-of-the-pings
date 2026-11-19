from fastapi.testclient import TestClient

from app.api import create_app
from rag_shield.scanner_guard import GuardConfig


def test_upload_dir_empty_after_requests(client, upload, uploads):
    upload("smoke_poisoned.pdf")
    upload("not_a_pdf.pdf")
    upload("hidden_comment.md")
    assert uploads.is_dir() and list(uploads.iterdir()) == []


def test_upload_dir_empty_after_oversize(tmp_path, fixtures_dir):
    uploads = tmp_path / "up"
    app = create_app(home=tmp_path / "home", upload_root=uploads,
                     guard_config=GuardConfig(max_bytes=100))
    with TestClient(app) as c, open(fixtures_dir / "smoke_poisoned.pdf", "rb") as fh:
        d = c.post("/ingest", files={"file": ("big.pdf", fh)}).json()
    app.state.shield.close()
    assert d["status"] == "unsupported" and d["indexed"] is False
    assert list(uploads.iterdir()) == []


def test_unsafe_filename_not_used_on_disk(client, upload, uploads):
    d = upload("smoke_poisoned.pdf", "../../etc/evil name.pdf").json()
    assert d["status"] == "flagged"
    assert list(uploads.iterdir()) == []
