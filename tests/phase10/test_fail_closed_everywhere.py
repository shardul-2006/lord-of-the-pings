"""Fail-closed audit: five bad inputs through every entry point. None may come out `clean`
and none may reach the defended index (documents) or the screened output (datasets)."""

import json
import time

import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.uploads import ingest_bytes, screen_dataset_bytes
from rag_shield.cli import main as cli_main
from rag_shield.dataset_gate import screen as gate_mod
from rag_shield.dataset_gate.screen import screen_dataset
from rag_shield.layer1 import ingest as ingest_mod
from rag_shield.shield import Shield

BAD = ("malformed", "encrypted", "oversize", "timeout", "empty")
BLOCKED = {"unsupported", "scan_failed"}


def _slow(*args, **kwargs):
    time.sleep(1.5)
    raise RuntimeError("should have timed out first")


@pytest.fixture
def bad_document(request, fixtures_dir, tmp_path, monkeypatch):
    """Returns (name, bytes) for the requested bad document and sets the matching limits."""
    kind = request.param
    if kind == "malformed":
        return "broken.pdf", b"%PDF-1.4\n%this is not a real PDF body\n"
    if kind == "encrypted":
        return "encrypted.pdf", (fixtures_dir / "encrypted.pdf").read_bytes()
    if kind == "oversize":
        monkeypatch.setenv("RAG_SHIELD_MAX_BYTES", "200")
        return "big.pdf", (fixtures_dir / "smoke_poisoned.pdf").read_bytes()
    if kind == "timeout":
        monkeypatch.setenv("RAG_SHIELD_SCAN_TIMEOUT", "0.2")
        monkeypatch.setattr(ingest_mod, "_parse", _slow)
        return "slow.pdf", (fixtures_dir / "smoke_poisoned.pdf").read_bytes()
    return "empty.pdf", b""


@pytest.mark.parametrize("bad_document", BAD, indirect=True)
def test_cli(bad_document, tmp_path, capsys):
    name, data = bad_document
    path = tmp_path / name
    path.write_bytes(data)
    db = tmp_path / "ledger.db"
    assert cli_main(["shield-run", str(path), "--db", str(db), "--json"]) == 0
    d = json.loads(capsys.readouterr().out)
    assert d["status"] in BLOCKED and d["indexed"] is False
    s = Shield(db_path=db)
    try:
        assert s.index.rows() == []
    finally:
        s.close()


@pytest.mark.parametrize("bad_document", BAD, indirect=True)
def test_api(bad_document, tmp_path):
    name, data = bad_document
    app = create_app(home=tmp_path / "home", upload_root=tmp_path / "up")
    try:
        with TestClient(app) as c:
            d = c.post("/ingest", files={"file": (name, data)}).json()
        assert d["status"] in BLOCKED and d["indexed"] is False
        assert app.state.shield.index.rows() == []
    finally:
        app.state.shield.close()


@pytest.mark.parametrize("bad_document", BAD, indirect=True)
def test_streamlit_upload(bad_document, tmp_path):
    name, data = bad_document
    shield = Shield(home=tmp_path / "home")
    try:
        d = ingest_bytes(shield, name, data)
        assert d["status"] in BLOCKED and d["indexed"] is False
        assert shield.index.rows() == []
    finally:
        shield.close()


@pytest.fixture
def bad_dataset(request, tmp_path, monkeypatch):
    kind = request.param
    good = "\n".join(json.dumps({"id": f"r{i}", "text": f"Review number {i} is fine.",
                                 "label": "positive"}) for i in range(20)) + "\n"
    if kind == "malformed":
        return "bad.jsonl", b'{"text": "unterminated\n'
    if kind == "encrypted":
        return "cipher.jsonl", bytes(range(256)) * 8  # opaque binary, not UTF-8 text
    if kind == "oversize":
        monkeypatch.setenv("RAG_SHIELD_MAX_BYTES", "100")
        return "big.jsonl", good.encode()
    if kind == "timeout":
        monkeypatch.setenv("RAG_SHIELD_DATASET_TIMEOUT", "0.2")
        monkeypatch.setattr(gate_mod, "_analyse", _slow)
        return "slow.jsonl", good.encode()
    return "empty.jsonl", b""


@pytest.mark.parametrize("bad_dataset", BAD, indirect=True)
def test_dataset_gate_library_and_cli(bad_dataset, tmp_path, capsys):
    name, data = bad_dataset
    path = tmp_path / name
    path.write_bytes(data)
    rep = screen_dataset(path, tmp_path / "out_lib")
    assert rep.status in BLOCKED and rep.screened == 0
    assert not (tmp_path / "out_lib" / "screened.jsonl").exists()
    cli_main(["dataset-gate", "screen", str(path), "--out", str(tmp_path / "out_cli"), "--json"])
    d = json.loads(capsys.readouterr().out)
    assert d["status"] in BLOCKED and d["screened"] == 0
    assert not (tmp_path / "out_cli" / "screened.jsonl").exists()


@pytest.mark.parametrize("bad_dataset", BAD, indirect=True)
def test_dataset_gate_api_and_ui(bad_dataset, tmp_path):
    name, data = bad_dataset
    app = create_app(home=tmp_path / "home", upload_root=tmp_path / "up")
    try:
        with TestClient(app) as c:
            r = c.post("/dataset", files={"file": (name, data)})
        if r.status_code == 200:
            d = r.json()
            assert d["summary"]["status"] in BLOCKED and d["screened"] == []
        else:
            assert r.status_code in (413, 415)  # refused before screening
        ui = screen_dataset_bytes(app.state.shield, name, data)
        assert ui["summary"]["status"] in BLOCKED and ui["screened"] == ""
    finally:
        app.state.shield.close()
