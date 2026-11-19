"""API smoke test with FastAPI's TestClient (no server, MockLLM, temporary home).

upload poisoned fixture -> findings -> overlay -> release -> ask -> upload not_a_pdf.
Exits non-zero on any wrong status.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from fastapi.testclient import TestClient  # noqa: E402

from app.api import create_app  # noqa: E402

FIX = REPO / "data" / "fixtures"


def expect(cond: bool, msg: str) -> None:
    if not cond:
        print(f"API SMOKE FAILED: {msg}")
        sys.exit(1)
    print(f"ok: {msg}")


def main() -> int:
    with tempfile.TemporaryDirectory() as home:
        app = create_app(home=home, upload_root=Path(home) / "uploads")
        with TestClient(app) as client:
            expect(client.get("/health").status_code == 200, "health 200")

            with open(FIX / "smoke_poisoned.pdf", "rb") as fh:
                r = client.post("/ingest", files={"file": ("resume.pdf", fh, "application/pdf")})
            d = r.json()
            expect(r.status_code == 200 and d["status"] == "flagged", "poisoned upload flagged")
            doc_id, sid = d["doc_id"], d["quarantined_ids"][0]

            f = client.get(f"/findings/{doc_id}").json()
            expect(any(w["sentence_id"] == sid for w in f["withheld"]), "finding listed")

            ov = client.get(f"/overlay/{doc_id}/1")
            expect(ov.status_code == 200 and ov.headers["content-type"] == "image/png",
                   "overlay png")

            rel = client.post(f"/release/{sid}", json={"reviewer": "smoke"}).json()
            expect(rel["released"] is True and rel["index_version"] >= 2, "release bumps index")

            ask = client.post("/ask", json={"doc_id": doc_id, "llm": "mock"}).json()
            expect({"vulnerable", "defended", "output_check"} <= set(ask), "ask returns both")

            with open(FIX / "not_a_pdf.pdf", "rb") as fh:
                bad = client.post("/ingest", files={"file": ("x.pdf", fh, "application/pdf")})
            b = bad.json()
            expect(b["status"] == "unsupported" and b["indexed"] is False, "not_a_pdf blocked")
        app.state.shield.close()
    print("API SMOKE: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
