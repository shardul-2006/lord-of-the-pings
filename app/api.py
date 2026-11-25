"""RAG-Shield REST API (FastAPI).

Run:  uvicorn app.api:create_app --factory --port 8000   (needs `pip install uvicorn`)
LLM:  requests choose "mock" (default) or "real" (env RAG_SHIELD_LLM / RAG_SHIELD_LLM_MODEL,
      e.g. ollama + llama3.1:8b).

Uploads go through the scanner guard in a private temp directory that is deleted after the
request; only the ledger's forensic copy (needed for the evidence overlay) is kept.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from rag_shield import __version__
from rag_shield.integrity.decision_check import check as integrity_check
from rag_shield.layer2.guard import Guard
from rag_shield.rag.compare import answer_both
from rag_shield.rag.llm import get_llm
from rag_shield.rag.pipeline import DEFAULT_QUESTION
from rag_shield.scanner_guard import GuardConfig
from rag_shield.shield import ATLAS_TAG, OWASP_TAG, Shield

UPLOAD_PREFIX = "rag_shield_upload_"
CHUNK = 1 << 16

REPO = Path(__file__).resolve().parent.parent
FIXTURES = REPO / "data" / "fixtures"
DEMO_DATASET = REPO / "data" / "synthetic_dataset" / "poisoned.jsonl"
FRONTEND_DIST = REPO / "frontend" / "dist"

SAMPLES: dict[str, dict[str, Any]] = {
    "smoke_poisoned.pdf": {
        "label": "Poisoned resume: hidden 0.5 pt white text",
        "file": "smoke_poisoned.pdf",
        "title": "Sub-Point White Text",
        "tag": "Physical Hiding",
        "badge_color": "#ef4444",
        "vector": "0.5 pt white font hidden on white page directing the LLM to recommend candidate as CEO.",
        "layer": "Layer 1 + 2",
    },
    "visible_injection.pdf": {
        "label": "Visible injected instruction",
        "file": "visible_injection.pdf",
        "title": "Visible Directive Override",
        "tag": "Direct Instruction",
        "badge_color": "#dc2626",
        "vector": "Unhidden prompt injection directive overriding evaluation rubric and hiring decision.",
        "layer": "Layer 2",
    },
    "off_page.pdf": {
        "label": "Text placed off the page",
        "file": "off_page.pdf",
        "title": "Off-Canvas Text",
        "tag": "Layout Anomaly",
        "badge_color": "#f59e0b",
        "vector": "Malicious payload placed outside printable canvas coordinates [x < 0 or y > page].",
        "layer": "Layer 1",
    },
    "metadata_payload.pdf": {
        "label": "Instruction in PDF metadata",
        "file": "metadata_payload.pdf",
        "title": "Carrier Metadata Injection",
        "tag": "Metadata Carrier",
        "badge_color": "#8b5cf6",
        "vector": "Injection hidden inside PDF document metadata attributes (/Title, /Subject, /Author).",
        "layer": "Layer 1 + 2",
    },
    "hidden_comment.md": {
        "label": "Hidden comment in Markdown",
        "file": "hidden_comment.md",
        "title": "Markdown HTML Comment",
        "tag": "Concealed Markup",
        "badge_color": "#ec4899",
        "vector": "Instruction disguised inside HTML comment tags <!-- SYSTEM: ... --> in Markdown.",
        "layer": "Layer 1",
    },
    "smoke_trigger_words.pdf": {
        "label": "Clean resume with trigger words (system override...)",
        "file": "smoke_trigger_words.pdf",
        "title": "Clean Resume (Trigger Words)",
        "tag": "False Positive Baseline",
        "badge_color": "#10b981",
        "vector": "Legitimate engineering resume containing trigger words ('override', 'system prompt').",
        "layer": "Safe Pass",
    },
    "smoke_clean.pdf": {
        "label": "Clean resume",
        "file": "smoke_clean.pdf",
        "title": "Clean Resume",
        "tag": "Pure Baseline",
        "badge_color": "#059669",
        "vector": "Standard authentic software engineer resume with normal layout and verified facts.",
        "layer": "Safe Pass",
    },
    "encrypted.pdf": {
        "label": "Encrypted PDF (blocked)",
        "file": "encrypted.pdf",
        "title": "Encrypted / Password-Protected",
        "tag": "Fail-Closed Guard",
        "badge_color": "#64748b",
        "vector": "Encrypted PDF file; scanner guard blocks from ingestion to prevent un-scanned bypass.",
        "layer": "Scanner Guard",
    },
    "not_a_pdf.pdf": {
        "label": "Text file named .pdf (blocked)",
        "file": "not_a_pdf.pdf",
        "title": "Spoofed Extension (.pdf)",
        "tag": "Magic-Byte Verification",
        "badge_color": "#64748b",
        "vector": "Plain text renamed to .pdf; fails binary magic-byte verification.",
        "layer": "Scanner Guard",
    },
}


class AskRequest(BaseModel):
    doc_id: str
    question: str = DEFAULT_QUESTION
    llm: str = Field(default="mock", pattern="^(mock|real)$")
    spotlight: bool = False


class ReleaseRequest(BaseModel):
    reviewer: str = Field(min_length=1)


class IntegrityRequest(BaseModel):
    doc_id: str
    task: str = "Score this candidate for a software engineer role"
    llm: str = Field(default="mock", pattern="^(mock|real)$")
    runs: int | None = Field(default=None, ge=1, le=10)


def _safe_suffix(name: str) -> str:
    suffix = Path(name or "").suffix.lower()
    return suffix if re.fullmatch(r"\.[a-z0-9]{1,8}", suffix) else ""


def create_app(
    home: str | Path | None = None,
    upload_root: str | Path | None = None,
    guard: Guard | None = None,
    guard_config: GuardConfig | None = None,
) -> FastAPI:
    shield = Shield(home=home, guard=guard, guard_config=guard_config)
    guard_config = guard_config or GuardConfig.from_env()
    max_bytes = guard_config.max_bytes
    upload_dir = Path(upload_root) if upload_root else None
    if upload_dir:
        upload_dir.mkdir(parents=True, exist_ok=True)
    api = FastAPI(title="RAG-Shield", version=__version__)
    api.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    api.state.shield = shield

    def route_get(path: str, **kwargs):
        def dec(fn):
            api.get(path, **kwargs)(fn)
            api.get(f"/api{path}", include_in_schema=False, **kwargs)(fn)
            return fn
        return dec

    def route_post(path: str, **kwargs):
        def dec(fn):
            api.post(path, **kwargs)(fn)
            api.post(f"/api{path}", include_in_schema=False, **kwargs)(fn)
            return fn
        return dec

    def _doc(doc_id: str) -> dict[str, Any]:
        doc = shield.ledger.get_document(doc_id)
        if doc is None:
            raise HTTPException(404, f"unknown document {doc_id}")
        return doc

    @route_get("/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "version": __version__,
                "policy_version": shield.policy["version"], "tier": shield.policy["tier"],
                "guard": shield.guard.model_id,
                "real_llm_configured": bool(os.environ.get("RAG_SHIELD_LLM"))}

    @route_get("/samples")
    def list_samples() -> list[dict[str, Any]]:
        return list(SAMPLES.values())

    @route_post("/samples/{sample_name}/ingest")
    def ingest_sample(sample_name: str) -> dict[str, Any]:
        if sample_name not in SAMPLES:
            raise HTTPException(404, f"unknown sample fixture {sample_name}")
        path = FIXTURES / sample_name
        if not path.exists():
            raise HTTPException(404, f"fixture file missing on disk: {sample_name}")
        result = shield.ingest(path, source_name=path.name)
        return {**result.to_dict(), "filename": path.name}

    @route_post("/demo-dataset/screen")
    def screen_demo_dataset() -> dict[str, Any]:
        if not DEMO_DATASET.exists():
            raise HTTPException(404, "demo dataset missing: run python scripts/make_poisoned_dataset.py")
        tmp = Path(tempfile.mkdtemp(prefix="rag_shield_demo_ds_"))
        try:
            rep = shield.screen_dataset(DEMO_DATASET, tmp / "out")
            summary = {k: v for k, v in rep.to_dict().items() if k not in ("report_path", "out_dir")}
            if rep.status != "completed":
                return {"summary": summary, "report": None, "screened": [], "quarantined": []}
            out = tmp / "out"
            return {
                "summary": summary,
                "report": json.loads((out / "report.json").read_text(encoding="utf-8")),
                "screened": [json.loads(x) for x in (out / "screened.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()],
                "quarantined": [json.loads(x) for x in (out / "quarantined.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()],
            }
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    @route_post("/ingest")
    async def ingest(file: Annotated[UploadFile, File()]) -> dict[str, Any]:
        tmp = Path(tempfile.mkdtemp(prefix=UPLOAD_PREFIX, dir=upload_dir))
        try:
            dest = tmp / f"upload{_safe_suffix(file.filename or '')}"
            written = 0
            with open(dest, "wb") as fh:
                while chunk := await file.read(CHUNK):
                    written += len(chunk)
                    if written > max_bytes:  # stop reading; the guard reports oversize
                        break
                    fh.write(chunk)
            if written > max_bytes:
                return {"status": "unsupported", "indexed": False, "doc_id": None,
                        "reason": f"oversize (> {max_bytes} bytes)", "filename": file.filename}
            result = shield.ingest(dest, source_name=file.filename or dest.name)
            return {**result.to_dict(), "filename": file.filename}
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    @route_post("/dataset")
    async def dataset(file: Annotated[UploadFile, File()]) -> dict[str, Any]:
        """Screen an uploaded CSV/JSONL dataset; returns the report and the screened rows.
        Nothing is kept on the server after the request."""
        suffix = _safe_suffix(file.filename or "")
        if suffix not in (".csv", ".jsonl"):
            raise HTTPException(415, "dataset must be .csv or .jsonl")
        tmp = Path(tempfile.mkdtemp(prefix=UPLOAD_PREFIX, dir=upload_dir))
        try:
            dest = tmp / f"dataset{suffix}"
            written = 0
            with open(dest, "wb") as fh:
                while chunk := await file.read(CHUNK):
                    written += len(chunk)
                    if written > max_bytes:
                        raise HTTPException(413, f"dataset larger than {max_bytes} bytes")
                    fh.write(chunk)
            rep = shield.screen_dataset(dest, tmp / "out")
            summary = {k: v for k, v in rep.to_dict().items() if k not in ("report_path",
                                                                             "out_dir")}
            if rep.status != "completed":
                return {"summary": summary, "report": None, "screened": [], "quarantined": []}
            out = tmp / "out"
            return {
                "summary": summary,
                "report": json.loads((out / "report.json").read_text(encoding="utf-8")),
                "screened": [json.loads(x) for x in (out / "screened.jsonl")
                             .read_text(encoding="utf-8").splitlines() if x.strip()],
                "quarantined": [json.loads(x) for x in (out / "quarantined.jsonl")
                                .read_text(encoding="utf-8").splitlines() if x.strip()],
            }
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    @route_get("/findings/{doc_id}")
    def findings(doc_id: str) -> dict[str, Any]:
        doc = _doc(doc_id)
        items = [i for i in shield.review_items() if i["doc_id"] == doc_id]
        return {
            "document": doc,
            "findings": shield.ledger.findings_for(doc_id),
            "withheld": items,
            "tags": [OWASP_TAG, ATLAS_TAG],
            "events": shield.ledger.events(doc_id),
        }

    @route_get("/review")
    def review() -> dict[str, Any]:
        return {"items": shield.review_items()}

    @route_post("/release/{sentence_id}")
    def release(sentence_id: str, body: ReleaseRequest) -> dict[str, Any]:
        out = shield.release(sentence_id, body.reviewer)
        if not out["released"]:
            raise HTTPException(409, out.get("reason", "not released"))
        return out

    @route_post("/requarantine/{sentence_id}")
    def requarantine(sentence_id: str, body: ReleaseRequest) -> dict[str, Any]:
        return shield.requarantine(sentence_id, body.reviewer)

    @route_get("/overlay/{doc_id}/{page}")
    def overlay(doc_id: str, page: int) -> Response:
        _doc(doc_id)
        try:
            png = shield.overlay(doc_id, page)
        except (ValueError, FileNotFoundError) as e:
            raise HTTPException(400, str(e)) from e
        return Response(content=png, media_type="image/png")

    @route_post("/ask")
    def ask(body: AskRequest) -> dict[str, Any]:
        doc = _doc(body.doc_id)
        if not doc["forensic_path"]:
            raise HTTPException(400, "no stored original for this document")
        llm = get_llm(body.llm)
        chunks = shield.chunks_for(body.doc_id)  # current defended index (reflects releases)
        traces = answer_both(doc["forensic_path"], chunks, f"shield:{shield.policy['version']}",
                             llm, body.question,
                             shield.source_tier if body.spotlight else None)
        retrieved = [c for c in chunks if c.chunk_id in traces["defended"].retrieved_chunk_ids]
        check = shield.validate_output(traces["defended"].output, retrieved)
        return {
            "status": doc["final_status"],
            "vulnerable": traces["vulnerable"].to_dict(),
            "defended": traces["defended"].to_dict(),
            "output_check": check.to_dict(),
        }

    @route_post("/integrity")
    def integrity(body: IntegrityRequest) -> dict[str, Any]:
        doc = _doc(body.doc_id)
        if not doc["forensic_path"]:
            raise HTTPException(400, "no stored original for this document")
        return integrity_check(body.task, doc["forensic_path"], get_llm(body.llm),
                               runs=body.runs).to_dict()

    if FRONTEND_DIST.exists():
        api.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

        @api.get("/", include_in_schema=False)
        def index():
            return FileResponse(FRONTEND_DIST / "index.html")

        @api.get("/{full_path:path}", include_in_schema=False)
        def spa_fallback(full_path: str):
            if full_path.startswith("api/"):
                raise HTTPException(404, f"API endpoint not found: /{full_path}")
            candidate = FRONTEND_DIST / full_path
            if candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(FRONTEND_DIST / "index.html")

    return api
