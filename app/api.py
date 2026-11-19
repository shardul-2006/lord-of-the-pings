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
from fastapi.responses import Response
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
    max_bytes = (guard_config or GuardConfig()).max_bytes
    upload_dir = Path(upload_root) if upload_root else None
    if upload_dir:
        upload_dir.mkdir(parents=True, exist_ok=True)
    api = FastAPI(title="RAG-Shield", version=__version__)
    api.state.shield = shield

    def _doc(doc_id: str) -> dict[str, Any]:
        doc = shield.ledger.get_document(doc_id)
        if doc is None:
            raise HTTPException(404, f"unknown document {doc_id}")
        return doc

    @api.get("/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "version": __version__,
                "policy_version": shield.policy["version"], "tier": shield.policy["tier"],
                "guard": shield.guard.model_id,
                "real_llm_configured": bool(os.environ.get("RAG_SHIELD_LLM"))}

    @api.post("/ingest")
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

    @api.post("/dataset")
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

    @api.get("/findings/{doc_id}")
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

    @api.get("/review")
    def review() -> dict[str, Any]:
        return {"items": shield.review_items()}

    @api.post("/release/{sentence_id}")
    def release(sentence_id: str, body: ReleaseRequest) -> dict[str, Any]:
        out = shield.release(sentence_id, body.reviewer)
        if not out["released"]:
            raise HTTPException(409, out.get("reason", "not released"))
        return out

    @api.post("/requarantine/{sentence_id}")
    def requarantine(sentence_id: str, body: ReleaseRequest) -> dict[str, Any]:
        return shield.requarantine(sentence_id, body.reviewer)

    @api.get("/overlay/{doc_id}/{page}")
    def overlay(doc_id: str, page: int) -> Response:
        _doc(doc_id)
        try:
            png = shield.overlay(doc_id, page)
        except (ValueError, FileNotFoundError) as e:
            raise HTTPException(400, str(e)) from e
        return Response(content=png, media_type="image/png")

    @api.post("/ask")
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

    @api.post("/integrity")
    def integrity(body: IntegrityRequest) -> dict[str, Any]:
        doc = _doc(body.doc_id)
        if not doc["forensic_path"]:
            raise HTTPException(400, "no stored original for this document")
        return integrity_check(body.task, doc["forensic_path"], get_llm(body.llm),
                               runs=body.runs).to_dict()

    return api
