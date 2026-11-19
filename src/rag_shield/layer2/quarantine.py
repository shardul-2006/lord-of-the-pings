"""Reversible sentence quarantine. Nothing is deleted: records change status and every change
is appended to the result's event log (who, what, when, policy version)."""

from __future__ import annotations

from datetime import datetime, timezone

from rag_shield.models import QuarantineRecord, ScanStatus, ScreenedChunk, ScreenResult, Sentence

QUARANTINED = "quarantined"
REVIEW_REQUIRED = "review_required"
RELEASED = "released"
WITHHELD = (QUARANTINED, REVIEW_REQUIRED)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_chunks(
    sentences: list[Sentence], withheld: set[str], doc_id: str, max_chars: int
) -> list[ScreenedChunk]:
    """Pack permitted sentences into chunks. A withheld sentence always ends a chunk."""
    chunks: list[ScreenedChunk] = []
    cur: list[Sentence] = []

    def flush() -> None:
        if cur:
            spans: list[str] = []
            for s in cur:
                spans.extend(x for x in s.source_span_ids if x not in spans)
            chunks.append(ScreenedChunk(
                chunk_id=f"{doc_id[:12]}-c{len(chunks) + 1}",
                permitted_sentence_ids=[s.sentence_id for s in cur],
                source_span_ids=spans,
                text=" ".join(s.text for s in cur),
            ))
            cur.clear()

    for s in sentences:
        if s.sentence_id in withheld:
            flush()
            continue
        if cur and len(" ".join(x.text for x in cur)) + 1 + len(s.text) > max_chars:
            flush()
        cur.append(s)
    flush()
    return chunks


def doc_status(records: list[QuarantineRecord]) -> ScanStatus:
    statuses = {r.status for r in records}
    if QUARANTINED in statuses:
        return ScanStatus.FLAGGED
    if REVIEW_REQUIRED in statuses:
        return ScanStatus.REVIEW_REQUIRED
    return ScanStatus.CLEAN


class QuarantineManager:
    """Release / re-quarantine sentences of one ScreenResult and keep chunks consistent."""

    def __init__(self, result: ScreenResult, max_chars: int = 300) -> None:
        self.result = result
        self.max_chars = max_chars

    def _record(self, sentence_id: str) -> QuarantineRecord:
        for r in self.result.quarantine:
            if r.sentence_id == sentence_id:
                return r
        raise KeyError(f"no quarantine record for {sentence_id}")

    def _rebuild(self) -> None:
        withheld = {r.sentence_id for r in self.result.quarantine if r.status in WITHHELD}
        self.result.screened_chunks = build_chunks(
            self.result.sentences, withheld, self.result.document.doc_id, self.max_chars
        )
        if self.result.status not in (ScanStatus.UNSUPPORTED, ScanStatus.SCAN_FAILED):
            self.result.status = doc_status(self.result.quarantine)

    def _log(self, action: str, rec: QuarantineRecord, actor: str, reason: str) -> dict:
        event = {
            "action": action, "sentence_id": rec.sentence_id, "by": actor, "at": now(),
            "reason": reason, "policy_version": self.result.policy_version,
        }
        self.result.events.append(event)
        return event

    def release(self, sentence_id: str, reviewer: str, reason: str = "false positive") -> dict:
        if not reviewer:
            raise ValueError("a release must name the reviewer")
        rec = self._record(sentence_id)
        if rec.status not in WITHHELD:
            raise ValueError(f"{sentence_id} is not withheld (status {rec.status})")
        rec.status = RELEASED
        rec.reviewed_by = reviewer
        rec.timestamps["released_at"] = now()
        self._rebuild()
        return self._log("release", rec, reviewer, reason)

    def requarantine(self, sentence_id: str, reviewer: str, reason: str = "re-quarantined") -> dict:
        rec = self._record(sentence_id)
        rec.status = QUARANTINED
        rec.reviewed_by = reviewer
        rec.timestamps["requarantined_at"] = now()
        self._rebuild()
        return self._log("requarantine", rec, reviewer, reason)
