"""Trust ledger (SQLite): documents, source spans, sentences, findings, quarantine state,
audit events and the defended index (Spec B, F).

Stores (Spec F):
- forensic store: immutable original bytes under <home>/forensic/, never used as context;
- processing store: source_spans + sentences tables (canonical text with span maps);
- defended index: index_chunks rows, screened chunks only (see rag/index_sync.py).
All multi-row changes run in one transaction; on any error nothing changes.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rag_shield.models import (
    Document,
    Finding,
    IngestResult,
    QuarantineRecord,
    ScreenResult,
    Sentence,
)

WITHHELD = ("quarantined", "review_required")

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents(
  doc_id TEXT PRIMARY KEY, sha256 TEXT, media_type TEXT, ingestion_status TEXT,
  final_status TEXT, source_name TEXT, forensic_path TEXT, policy_version TEXT,
  reason TEXT, created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS source_spans(
  span_id TEXT PRIMARY KEY, doc_id TEXT, page INTEGER, start INTEGER, end INTEGER,
  bboxes TEXT, original_text TEXT);
CREATE TABLE IF NOT EXISTS sentences(
  sentence_id TEXT PRIMARY KEY, doc_id TEXT, seq INTEGER, start INTEGER, end INTEGER,
  text TEXT, source_span_ids TEXT, neighbor_ids TEXT);
CREATE TABLE IF NOT EXISTS findings(
  id INTEGER PRIMARY KEY AUTOINCREMENT, doc_id TEXT, sentence_id TEXT, score REAL,
  signals TEXT, model_versions TEXT, policy_version TEXT, highlights TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS quarantine(
  sentence_id TEXT PRIMARY KEY, doc_id TEXT, status TEXT, decision_reason TEXT,
  reviewed_by TEXT, timestamps TEXT);
CREATE TABLE IF NOT EXISTS events(
  id INTEGER PRIMARY KEY AUTOINCREMENT, doc_id TEXT, sentence_id TEXT, action TEXT,
  actor TEXT, at TEXT, reason TEXT, policy_version TEXT);
CREATE TABLE IF NOT EXISTS index_state(namespace TEXT PRIMARY KEY, index_version INTEGER);
CREATE TABLE IF NOT EXISTS index_chunks(
  namespace TEXT, chunk_id TEXT, doc_id TEXT, text TEXT, permitted_sentence_ids TEXT,
  source_span_ids TEXT, content_hash TEXT, policy_version TEXT, index_version INTEGER,
  PRIMARY KEY(namespace, chunk_id));
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _j(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)


class Ledger:
    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self.db_path = str(db_path)
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, isolation_level=None, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            yield self.conn
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise
        self.conn.execute("COMMIT")

    # --- writes -----------------------------------------------------------------------------
    def add_document(
        self, document: Document, source_name: str = "", forensic_path: str = "",
        policy_version: str = "", reason: str = "", conn: sqlite3.Connection | None = None,
    ) -> str:
        c = conn or self.conn
        c.execute(
            "INSERT INTO documents VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(doc_id) DO UPDATE SET "
            "ingestion_status=excluded.ingestion_status, final_status=excluded.final_status, "
            "source_name=excluded.source_name, forensic_path=excluded.forensic_path, "
            "policy_version=excluded.policy_version, reason=excluded.reason, "
            "updated_at=excluded.updated_at",
            (document.doc_id, document.sha256, document.media_type,
             document.ingestion_status.value, document.ingestion_status.value, source_name,
             forensic_path, policy_version, reason, document.created_at, now()),
        )
        return document.doc_id

    def add_findings(
        self, doc_id: str, findings: list[Finding],
        highlights: dict[str, list] | None = None, conn: sqlite3.Connection | None = None,
    ) -> int:
        c = conn or self.conn
        for f in findings:
            c.execute(
                "INSERT INTO findings(doc_id, sentence_id, score, signals, model_versions, "
                "policy_version, highlights, created_at) VALUES(?,?,?,?,?,?,?,?)",
                (doc_id, f.sentence_id, f.score, _j([s.to_dict() for s in f.signals]),
                 _j(f.model_versions), f.policy_version,
                 _j((highlights or {}).get(f.sentence_id, [])), now()),
            )
        return len(findings)

    def record_scan(
        self, conn: sqlite3.Connection, ing: IngestResult, scr: ScreenResult,
        highlights: dict[str, list], source_name: str, forensic_path: str,
    ) -> None:
        """Replace everything stored for this document with the new scan (a rescan)."""
        doc_id = ing.document.doc_id
        for table in ("source_spans", "sentences", "findings", "quarantine"):
            conn.execute(f"DELETE FROM {table} WHERE doc_id=?", (doc_id,))
        doc = scr.document
        doc.ingestion_status = scr.status
        self.add_document(doc, source_name, forensic_path, scr.policy_version, scr.reason, conn)
        conn.execute("UPDATE documents SET ingestion_status=? WHERE doc_id=?",
                     (ing.status.value, doc_id))
        for s in ing.source_spans:
            conn.execute(
                "INSERT OR REPLACE INTO source_spans VALUES(?,?,?,?,?,?,?)",
                (s.span_id, doc_id, s.page, s.source_offsets[0], s.source_offsets[1],
                 _j(s.bboxes), s.original_text),
            )
        for seq, s in enumerate(scr.sentences):
            conn.execute(
                "INSERT OR REPLACE INTO sentences VALUES(?,?,?,?,?,?,?,?)",
                (s.sentence_id, doc_id, seq, s.canonical_offsets[0], s.canonical_offsets[1],
                 s.text, _j(s.source_span_ids), _j(s.neighbor_ids)),
            )
        self.add_findings(doc_id, scr.findings, highlights, conn)
        for r in scr.quarantine:
            conn.execute(
                "INSERT OR REPLACE INTO quarantine VALUES(?,?,?,?,?,?)",
                (r.sentence_id, doc_id, r.status, r.decision_reason, r.reviewed_by,
                 _j(r.timestamps)),
            )
        self.log_event(conn, doc_id, None, "scan", "system", f"status={scr.status.value}",
                       scr.policy_version)

    def log_event(
        self, conn: sqlite3.Connection, doc_id: str, sentence_id: str | None, action: str,
        actor: str, reason: str, policy_version: str,
    ) -> dict[str, Any]:
        at = now()
        conn.execute(
            "INSERT INTO events(doc_id, sentence_id, action, actor, at, reason, policy_version) "
            "VALUES(?,?,?,?,?,?,?)",
            (doc_id, sentence_id, action, actor, at, reason, policy_version),
        )
        return {"doc_id": doc_id, "sentence_id": sentence_id, "action": action, "by": actor,
                "at": at, "reason": reason, "policy_version": policy_version}

    def set_quarantine_status(
        self, conn: sqlite3.Connection, sentence_id: str, status: str, reviewer: str
    ) -> QuarantineRecord:
        rec = self.get_quarantine(sentence_id, conn)
        if rec is None:
            raise KeyError(sentence_id)
        stamp = {"released": "released_at", "quarantined": "requarantined_at"}.get(status, status)
        rec.timestamps[stamp] = now()
        rec.status, rec.reviewed_by = status, reviewer
        conn.execute(
            "UPDATE quarantine SET status=?, reviewed_by=?, timestamps=? WHERE sentence_id=?",
            (status, reviewer, _j(rec.timestamps), sentence_id),
        )
        return rec

    # --- reads ------------------------------------------------------------------------------
    def get_document(self, doc_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM documents WHERE doc_id=?", (doc_id,)).fetchone()
        return dict(row) if row else None

    def find_document_by_sha(self, sha256: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM documents WHERE sha256=?", (sha256,)).fetchone()
        return dict(row) if row else None

    def get_quarantine(
        self, sentence_id: str, conn: sqlite3.Connection | None = None
    ) -> QuarantineRecord | None:
        row = (conn or self.conn).execute(
            "SELECT * FROM quarantine WHERE sentence_id=?", (sentence_id,)
        ).fetchone()
        if not row:
            return None
        return QuarantineRecord(row["sentence_id"], row["status"], row["decision_reason"],
                                row["reviewed_by"], json.loads(row["timestamps"]))

    def doc_of_sentence(self, sentence_id: str) -> str | None:
        row = self.conn.execute(
            "SELECT doc_id FROM quarantine WHERE sentence_id=?", (sentence_id,)
        ).fetchone()
        return row["doc_id"] if row else None

    def list_quarantine(self, statuses: tuple[str, ...] = WITHHELD) -> list[QuarantineRecord]:
        marks = ",".join("?" * len(statuses))
        rows = self.conn.execute(
            f"SELECT sentence_id FROM quarantine WHERE status IN ({marks}) ORDER BY doc_id, "
            "sentence_id", statuses,
        ).fetchall()
        return [r for r in (self.get_quarantine(x["sentence_id"]) for x in rows) if r]

    def review_items(self) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT q.sentence_id, q.doc_id, q.status, q.decision_reason, s.text, s.seq, "
            "d.source_name, (SELECT MAX(f.score) FROM findings f WHERE f.sentence_id = "
            "q.sentence_id) AS score FROM quarantine q JOIN sentences s USING(sentence_id) "
            "JOIN documents d ON d.doc_id = q.doc_id WHERE q.status IN (?, ?) "
            "ORDER BY q.doc_id, s.seq", WITHHELD,
        ).fetchall()
        return [dict(r) for r in rows]

    def sentences_for(self, doc_id: str, conn: sqlite3.Connection | None = None) -> list[Sentence]:
        rows = (conn or self.conn).execute(
            "SELECT * FROM sentences WHERE doc_id=? ORDER BY seq", (doc_id,)
        ).fetchall()
        return [Sentence(r["sentence_id"], (r["start"], r["end"]),
                         json.loads(r["source_span_ids"]), json.loads(r["neighbor_ids"]),
                         r["text"]) for r in rows]

    def withheld_ids(self, doc_id: str, conn: sqlite3.Connection | None = None) -> set[str]:
        rows = (conn or self.conn).execute(
            "SELECT sentence_id FROM quarantine WHERE doc_id=? AND status IN (?, ?)",
            (doc_id, *WITHHELD),
        ).fetchall()
        return {r["sentence_id"] for r in rows}

    def findings_for(self, doc_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT f.*, COALESCE(q.status, 'clean') AS status FROM findings f "
            "LEFT JOIN quarantine q USING(sentence_id) WHERE f.doc_id=?", (doc_id,),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["signals"] = json.loads(d["signals"])
            d["model_versions"] = json.loads(d["model_versions"])
            d["highlights"] = json.loads(d["highlights"])
            out.append(d)
        return out

    def events(self, doc_id: str | None = None) -> list[dict[str, Any]]:
        q = "SELECT * FROM events" + (" WHERE doc_id=?" if doc_id else "") + " ORDER BY id"
        return [dict(r) for r in self.conn.execute(q, (doc_id,) if doc_id else ()).fetchall()]

    # --- review actions (index sync is part of the same transaction) ------------------------
    def release(self, sentence_id: str, reviewer: str, index: Any = None,
                max_chars: int = 300) -> dict[str, Any]:
        return self._decide(sentence_id, reviewer, "released", index, max_chars)

    def requarantine(self, sentence_id: str, reviewer: str, index: Any = None,
                     max_chars: int = 300) -> dict[str, Any]:
        return self._decide(sentence_id, reviewer, "quarantined", index, max_chars)

    def _decide(self, sentence_id: str, reviewer: str, status: str, index: Any,
                max_chars: int) -> dict[str, Any]:
        from rag_shield.layer2.quarantine import doc_status
        from rag_shield.rag.index_sync import DefendedIndex

        result = {"released": False, "sentence_id": sentence_id, "status": None,
                  "index_version": None, "reviewer": reviewer}
        if not reviewer:
            return {**result, "reason": "a reviewer name is required"}
        rec = self.get_quarantine(sentence_id)
        if rec is None:
            return {**result, "reason": "unknown sentence"}
        if status == "released" and rec.status not in WITHHELD:
            return {**result, "status": rec.status, "reason": f"not withheld ({rec.status})"}
        doc_id = self.doc_of_sentence(sentence_id)
        index = index or DefendedIndex(self)
        doc = self.get_document(doc_id) or {}
        try:
            # Authorization and index sync commit together or not at all.
            with self.transaction() as conn:
                self.set_quarantine_status(conn, sentence_id, status, reviewer)
                version = index.rebuild_document(conn, doc_id, doc.get("policy_version", ""),
                                                 max_chars)
                rows = conn.execute("SELECT status FROM quarantine WHERE doc_id=?",
                                    (doc_id,)).fetchall()
                records = [QuarantineRecord("", r["status"], "") for r in rows]
                conn.execute("UPDATE documents SET final_status=?, updated_at=? WHERE doc_id=?",
                             (doc_status(records).value, now(), doc_id))
                event = self.log_event(conn, doc_id, sentence_id,
                                       "release" if status == "released" else "requarantine",
                                       reviewer, "", doc.get("policy_version", ""))
        except Exception as e:  # rolled back: the sentence stays withheld
            return {**result, "status": rec.status,
                    "reason": f"index sync failed, nothing changed: {type(e).__name__}: {e}"}
        return {**result, "released": status == "released", "status": status,
                "index_version": version, "event": event}
