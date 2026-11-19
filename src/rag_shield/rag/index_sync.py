"""Defended index kept consistent with the ledger (Spec F).

The defended index holds SCREENED chunks only. Its source of truth is the `index_chunks`
table; the in-memory vector store is a cache rebuilt whenever `index_version` changes.

On quarantine, release or rescan, inside ONE ledger transaction:
  1. remove the document's dependent chunk rows,
  2. rebuild its chunks from permitted sentences,
  3. bump index_version,
  4. commit. Only then can retrieval see the change.
If any step fails, the transaction rolls back: a released sentence stays unretrievable.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3

from rag_shield.layer2.quarantine import build_chunks
from rag_shield.ledger.store import Ledger
from rag_shield.models import ScreenedChunk
from rag_shield.rag.embedder import Embedder, HashEmbedder
from rag_shield.rag.store import Hit, SimpleStore, VectorStore

DEFENDED = "defended"


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class DefendedIndex:
    def __init__(
        self,
        ledger: Ledger,
        embedder: Embedder | None = None,
        store: VectorStore | None = None,
        namespace: str = DEFENDED,
    ) -> None:
        self.ledger = ledger
        self.embedder = embedder or HashEmbedder()
        self.store = store or SimpleStore()
        self.namespace = namespace
        self._loaded_version: int | None = None
        self._loaded_ids: list[str] = []

    # --- version ----------------------------------------------------------------------------
    def version(self, conn: sqlite3.Connection | None = None) -> int:
        row = (conn or self.ledger.conn).execute(
            "SELECT index_version FROM index_state WHERE namespace=?", (self.namespace,)
        ).fetchone()
        return int(row["index_version"]) if row else 0

    def _bump(self, conn: sqlite3.Connection) -> int:
        v = self.version(conn) + 1
        conn.execute(
            "INSERT INTO index_state VALUES(?, ?) ON CONFLICT(namespace) DO UPDATE SET "
            "index_version=excluded.index_version", (self.namespace, v),
        )
        return v

    # --- writes (caller owns the transaction) -----------------------------------------------
    def _insert_rows(self, conn: sqlite3.Connection, doc_id: str, chunks: list[ScreenedChunk],
                     policy_version: str, version: int) -> None:
        for c in chunks:
            conn.execute(
                "INSERT INTO index_chunks VALUES(?,?,?,?,?,?,?,?,?)",
                (self.namespace, c.chunk_id, doc_id, c.text, json.dumps(c.permitted_sentence_ids),
                 json.dumps(c.source_span_ids), content_hash(c.text), policy_version, version),
            )

    def write_document(self, conn: sqlite3.Connection, doc_id: str,
                       chunks: list[ScreenedChunk], policy_version: str) -> int:
        conn.execute("DELETE FROM index_chunks WHERE namespace=? AND doc_id=?",
                     (self.namespace, doc_id))
        version = self._bump(conn)
        self._insert_rows(conn, doc_id, chunks, policy_version, version)
        return version

    def rebuild_document(self, conn: sqlite3.Connection, doc_id: str, policy_version: str,
                         max_chars: int = 300) -> int:
        sentences = self.ledger.sentences_for(doc_id, conn)
        withheld = self.ledger.withheld_ids(doc_id, conn)
        return self.write_document(conn, doc_id, build_chunks(sentences, withheld, doc_id,
                                                              max_chars), policy_version)

    def sync_document(self, doc_id: str, chunks: list[ScreenedChunk], policy_version: str) -> int:
        with self.ledger.transaction() as conn:
            return self.write_document(conn, doc_id, chunks, policy_version)

    def remove_document(self, doc_id: str) -> int:
        return self.sync_document(doc_id, [], "")

    # --- reads ------------------------------------------------------------------------------
    def rows(self, doc_id: str | None = None) -> list[dict]:
        q = "SELECT * FROM index_chunks WHERE namespace=?"
        args: tuple = (self.namespace,)
        if doc_id:
            q += " AND doc_id=?"
            args += (doc_id,)
        return [dict(r) for r in self.ledger.conn.execute(q + " ORDER BY rowid", args)]

    def chunk_ids(self) -> list[str]:
        return [r["chunk_id"] for r in self.rows()]

    def ensure_current(self) -> int:
        """Reload the vector-store cache if the committed index_version moved."""
        v = self.version()
        if v != self._loaded_version:
            rows = self.rows()
            self.store.delete(self.namespace, self._loaded_ids)
            if rows:
                vecs = self.embedder.embed([r["text"] for r in rows])
                self.store.add(self.namespace, [r["chunk_id"] for r in rows],
                               [r["text"] for r in rows], vecs,
                               [{"doc_id": r["doc_id"]} for r in rows])
            self._loaded_ids = [r["chunk_id"] for r in rows]
            self._loaded_version = v
        return v

    def query(self, text: str, k: int = 4) -> list[Hit]:
        self.ensure_current()
        return self.store.query(self.namespace, self.embedder.embed([text])[0], k)
