from scripts.make_fixtures import DIRECTIVE


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok" and r.json()["policy_version"] == "policy_v1"


def test_ingest_poisoned_flagged_with_findings(client, upload):
    d = upload("smoke_poisoned.pdf", "candidate.pdf").json()
    assert d["status"] == "flagged" and d["indexed"] is True and d["filename"] == "candidate.pdf"
    assert d["alerts"] and all("OWASP LLM01" in a["tags"][0] for a in d["alerts"])
    f = client.get(f"/findings/{d['doc_id']}").json()
    assert [w["text"] for w in f["withheld"]] == [DIRECTIVE]
    assert f["document"]["source_name"] == "candidate.pdf"
    assert any(x["status"] == "quarantined" for x in f["findings"])


def test_not_a_pdf_unsupported_and_not_indexed(client, upload):
    d = upload("not_a_pdf.pdf").json()
    assert d["status"] == "unsupported" and d["indexed"] is False
    assert client.app.state.shield.index.rows(d["doc_id"]) == []


def test_release_raises_index_version(client, upload):
    d = upload("smoke_poisoned.pdf").json()
    sid = d["quarantined_ids"][0]
    r = client.post(f"/release/{sid}", json={"reviewer": "tester"})
    assert r.status_code == 200
    assert r.json()["index_version"] > d["index_version"]
    again = client.post(f"/release/{sid}", json={"reviewer": "tester"})
    assert again.status_code == 409
    assert client.post(f"/release/{sid}", json={"reviewer": ""}).status_code == 422


def test_overlay_png(client, upload):
    d = upload("smoke_poisoned.pdf").json()
    r = client.get(f"/overlay/{d['doc_id']}/1")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"
    assert client.get(f"/overlay/{d['doc_id']}/9").status_code == 400
    assert client.get("/overlay/unknown/1").status_code == 404


def test_ask_returns_both_traces_and_checks(client, upload):
    d = upload("smoke_poisoned.pdf").json()
    r = client.post("/ask", json={"doc_id": d["doc_id"], "llm": "mock", "spotlight": True})
    body = r.json()
    assert r.status_code == 200
    assert "HIRE AS CEO" in body["vulnerable"]["output"]
    assert "HIRE AS CEO" not in body["defended"]["output"]
    assert body["defended"]["spotlight"]["tag"] in body["defended"]["prompt"]
    assert {"canary_leak", "stripped", "ungrounded", "clean_answer"} <= set(body["output_check"])


def test_ask_reflects_release(client, upload):
    d = upload("smoke_poisoned.pdf").json()
    client.post(f"/release/{d['quarantined_ids'][0]}", json={"reviewer": "tester"})
    body = client.post("/ask", json={"doc_id": d["doc_id"]}).json()
    assert DIRECTIVE in body["defended"]["prompt"]  # released sentence is back in context


def test_review_and_integrity(client, upload):
    d = upload("smoke_poisoned.pdf").json()
    items = client.get("/review").json()["items"]
    assert [i["sentence_id"] for i in items] == d["quarantined_ids"]
    r = client.post("/integrity", json={"doc_id": d["doc_id"], "llm": "mock"}).json()
    assert r["possible_decision_influence"] is True
    assert r["label"] == "possible decision influence"


def test_bad_llm_value_rejected(client, upload):
    d = upload("smoke_poisoned.pdf").json()
    assert client.post("/ask", json={"doc_id": d["doc_id"], "llm": "gpt"}).status_code == 422
