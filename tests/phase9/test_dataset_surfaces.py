"""The Dataset Gate is reachable from the API and the Streamlit tab."""

from pathlib import Path

from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

from app.api import create_app

APP = str(Path(__file__).resolve().parents[2] / "app" / "streamlit_app.py")


def test_api_dataset_route(dataset, tmp_path):
    path, planted = dataset
    uploads = tmp_path / "up"
    app = create_app(home=tmp_path / "home", upload_root=uploads)
    with TestClient(app) as c, open(path, "rb") as fh:
        r = c.post("/dataset", files={"file": ("poisoned.jsonl", fh)})
        bad = c.post("/dataset", files={"file": ("x.txt", b"hello")})
    app.state.shield.close()
    d = r.json()
    assert r.status_code == 200
    assert planted["trigger_token"] in d["summary"]["trigger_tokens"]
    assert len(d["screened"]) + len(d["quarantined"]) == 1000
    assert bad.status_code == 415
    assert list(uploads.iterdir()) == []  # nothing kept on the server


def test_streamlit_dataset_tab(dataset):
    at = AppTest.from_file(APP).run(timeout=60)
    at.button(key="demo_dataset").click().run(timeout=120)
    assert not at.exception
    assert any(m.label == "Rows" and m.value == "1000" for m in at.metric)
    assert any("cf-zeta-7" in m.value for m in at.markdown)
