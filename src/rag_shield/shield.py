"""Shield: the library facade (Spec C).

ingest(path): scanner guard -> Layer 1 -> Layer 2 -> trust ledger -> defended index.
Only screened chunks are indexed. unsupported / scan_failed documents are never indexed, and
a failed rescan removes any chunks the document had before (fail closed).
"""

from __future__ import annotations

import json
import os
import shutil
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rag_shield import timing
from rag_shield.adapters import apply_domain, get_adapter
from rag_shield.dataset_gate.screen import screen_dataset as _screen_dataset
from rag_shield.layer1.ingest import ingest as _ingest
from rag_shield.layer2 import screen as _screen
from rag_shield.layer2 import screen_report
from rag_shield.layer2.guard import Guard, make_guard
from rag_shield.layer3.spotlight import spotlight
from rag_shield.layer3.trust_tiers import apply_tier
from rag_shield.layer4 import validate_output
from rag_shield.layer4.canary import make_canary, system_line
from rag_shield.ledger.overlay import highlights_from_findings, render_overlay
from rag_shield.ledger.store import Ledger
from rag_shield.models import (
    DatasetReport,
    OutputCheck,
    ScanStatus,
    ScreenedChunk,
    ScreenResult,
)
from rag_shield.policy import load_policy
from rag_shield.rag.embedder import Embedder
from rag_shield.rag.index_sync import DefendedIndex
from rag_shield.scanner_guard import GuardConfig

BLOCKED = (ScanStatus.UNSUPPORTED, ScanStatus.SCAN_FAILED)
OWASP_TAG = "OWASP LLM01: Prompt Injection"
ATLAS_TAG = "MITRE ATLAS AML.T0051.001: Indirect Prompt Injection"


def default_home() -> Path:
    return Path(os.environ.get("RAG_SHIELD_HOME") or Path.home() / ".rag_shield")


@dataclass
class ShieldIngest:
    status: ScanStatus
    doc_id: str
    indexed: bool
    index_version: int
    screen: ScreenResult
    alerts: list[dict[str, Any]] = field(default_factory=list)
    reason: str = ""

    @property
    def clean_chunks(self) -> list[ScreenedChunk]:
        return self.screen.screened_chunks if self.indexed else []

    @property
    def quarantined_ids(self) -> list[str]:
        return [r.sentence_id for r in self.screen.quarantine if r.status == "quarantined"]

    def to_dict(self) -> dict[str, Any]:
        report = screen_report(self.screen)
        return {
            "status": self.status.value,
            "doc_id": self.doc_id,
            "indexed": self.indexed,
            "index_version": self.index_version,
            "reason": self.reason,
            "quarantined_ids": self.quarantined_ids,
            "review_ids": [r.sentence_id for r in self.screen.quarantine
                           if r.status == "review_required"],
            "alerts": self.alerts,
            "screened_chunk_ids": [c.chunk_id for c in self.clean_chunks],
            "screened_text": report["screened_text"] if self.indexed else "",
            "policy_version": self.screen.policy_version,
        }


class Shield:
    def __init__(
        self,
        domain: str = "hr",
        source_tier: str = "external_upload",
        *,
        home: str | Path | None = None,
        db_path: str | Path | None = None,
        keep_forensic: bool = True,
        policy: dict[str, Any] | None = None,
        guard: Guard | None = None,
        classifier: Any = None,
        embedder: Embedder | None = None,
        guard_config: GuardConfig | None = None,
    ) -> None:
        self.domain = domain
        self.adapter = get_adapter(domain)  # config only: tiers, sensitive actions, cues
        self.source_tier = source_tier
        self.home = Path(home) if home else default_home()
        base = load_policy(overrides=policy) if policy else load_policy()
        self.policy = apply_tier(apply_domain(base, domain), source_tier)
        self.canary = make_canary()
        in_memory = str(db_path) == ":memory:"
        self.ledger = Ledger(db_path or self.home / "ledger.db")
        self.keep_forensic = keep_forensic and not in_memory
        self.index = DefendedIndex(self.ledger, embedder)
        self.guard = guard or make_guard(self.policy["guard"]["kind"], self.policy)
        self.classifier = classifier
        self.guard_config = guard_config

    def close(self) -> None:
        self.ledger.close()

    # --- ingestion ----------------------------------------------------------------------------
    def _forensic_copy(self, path: Path, sha: str) -> str:
        if not self.keep_forensic or not sha:
            return ""
        dest = self.home / "forensic" / f"{sha}{path.suffix.lower()}"
        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, dest)
            os.chmod(dest, stat.S_IREAD)  # immutable original
        return str(dest)

    def ingest(self, path: str | Path, source_name: str | None = None) -> ShieldIngest:
        """`source_name`: the user-facing file name when `path` is a temp upload."""
        path = Path(path)
        with timing.stage("shield_ingest"):
            ing = _ingest(path, self.guard_config)
            scr = _screen(ing, self.policy, classifier=self.classifier, guard=self.guard)
            highlights = self._highlights(ing, scr)
            forensic = self._forensic_copy(path, ing.document.sha256)
            indexed = scr.status not in BLOCKED
            doc_id = ing.document.doc_id
            with self.ledger.transaction() as conn:
                if ing.document.sha256:
                    self.ledger.record_scan(conn, ing, scr, highlights, source_name or path.name,
                                            forensic)
                # screened chunks only; blocked scans leave the document with NO chunks
                chunks = scr.screened_chunks if indexed else []
                version = self.index.write_document(conn, doc_id, chunks, scr.policy_version)
        return ShieldIngest(
            status=scr.status, doc_id=doc_id, indexed=indexed, index_version=version,
            screen=scr, alerts=self._alerts(scr), reason=scr.reason,
        )

    @staticmethod
    def _highlights(ing: Any, scr: ScreenResult) -> dict[str, list]:
        prov = ing.provenance
        if prov is None:
            return {}
        out: dict[str, list] = {}
        for s in scr.sentences:
            a, b = s.canonical_offsets
            out[s.sentence_id] = [[p, list(bb)] for p, bb in prov.highlight_boxes(a, b)
                                  if p is not None]
        return out

    @staticmethod
    def _alerts(scr: ScreenResult) -> list[dict[str, Any]]:
        report = screen_report(scr)
        alerts = []
        for item in report["quarantined"] + report["review_required"]:
            alerts.append({**item, "tags": [OWASP_TAG, ATLAS_TAG]})
        return alerts

    # --- query time ---------------------------------------------------------------------------
    def chunks_for(self, doc_id: str) -> list[ScreenedChunk]:
        """The document's chunks in the CURRENT defended index (reflects releases)."""
        return [ScreenedChunk(r["chunk_id"], json.loads(r["permitted_sentence_ids"]),
                              json.loads(r["source_span_ids"]), r["text"])
                for r in self.index.rows(doc_id)]

    def query(self, question: str, k: int = 4):
        return self.index.query(question, k)

    def filter(self, chunks: list[ScreenedChunk]) -> list[ScreenedChunk]:
        """Keep only chunks that are in the CURRENT defended index with identical text.
        Unknown or stale chunks are dropped (fail closed)."""
        self.index.ensure_current()
        current = {r["chunk_id"]: r["text"] for r in self.index.rows()}
        return [c for c in chunks if current.get(c.chunk_id) == c.text]

    # --- review -------------------------------------------------------------------------------
    def review_items(self) -> list[dict[str, Any]]:
        return self.ledger.review_items()

    def release(self, sentence_id: str, reviewer: str) -> dict[str, Any]:
        return self.ledger.release(sentence_id, reviewer, self.index,
                                   int(self.policy["chunk_max_chars"]))

    def requarantine(self, sentence_id: str, reviewer: str) -> dict[str, Any]:
        return self.ledger.requarantine(sentence_id, reviewer, self.index,
                                        int(self.policy["chunk_max_chars"]))

    def overlay(self, doc_id: str, page: int, source: str | Path | None = None) -> bytes:
        doc = self.ledger.get_document(doc_id)
        if doc is None:
            raise KeyError(f"document {doc_id} is not in the ledger")
        if doc["media_type"] != "application/pdf":
            raise ValueError("overlay is available for PDF documents only")
        pdf = doc["forensic_path"] or (str(source) if source else "")
        if not pdf:
            raise FileNotFoundError("no forensic copy and no source file given")
        return render_overlay(pdf, page, highlights_from_findings(
            self.ledger.findings_for(doc_id), page))

    # --- Layers 3 and 4 ------------------------------------------------------------------------
    def spotlight(self, chunks: list[ScreenedChunk]):
        return spotlight(chunks, self.source_tier, self.policy)

    def system_prompt_line(self) -> str:
        """Add this to the system prompt so validate_output can detect prompt leaks."""
        return system_line(self.canary)

    def validate_output(self, answer: str, chunks: list[ScreenedChunk]) -> OutputCheck:
        out = self.policy.get("output", {})
        return validate_output(
            answer, [c.chunk_id for c in chunks], canary=self.canary,
            allowed_domains=out.get("allowed_domains", []),
            require_citations=out.get("require_citations", True),
        )

    # --- later phases -------------------------------------------------------------------------

    def screen_dataset(self, path: str | Path, out_dir: str | Path = ".") -> DatasetReport:
        return _screen_dataset(path, out_dir, guard=self.guard)
