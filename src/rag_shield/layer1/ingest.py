"""Layer 1 ingest: guard -> parse -> Unicode clean -> provenance map -> signals.

Status after Layer 1 (Layer 2 `screen()` sets the final disposition):
- unsupported / scan_failed: the guard or parser failed; never indexed.
- review_required: completed, at least one HIDING signal is present.
- clean: completed, no hiding signals (carrier signals such as metadata may still exist).
Any exception during parsing is reported as scan_failed, never as clean.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pdfplumber

from rag_shield.layer1 import markup, metadata, pdf_signals
from rag_shield.layer1.provenance import ExtractedText, ProvenanceMap
from rag_shield.layer1.unicode_clean import clean_text
from rag_shield.models import Document, IngestResult, ScanStatus, Signal
from rag_shield.scanner_guard import (
    GuardConfig,
    ScanTimeout,
    check_file,
    guarded_copy,
    media_type_for,
    run_with_timeout,
)

HIDING_SIGNALS = frozenset({
    "tiny_font", "low_contrast", "off_page", "unicode_tag", "bidi_control", "zero_width_run",
    "hidden_comment", "hidden_element",
})
CARRIER_SIGNALS = frozenset({"metadata", "alt_text"})
UNICODE_SIGNAL_KINDS = frozenset({"unicode_tag", "bidi_control", "zero_width_run"})


def _sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _parse(path: Path, media: str, doc_id: str) -> tuple[ExtractedText, list[Signal], dict]:
    ex = ExtractedText()
    if media == "application/pdf":
        with pdfplumber.open(str(path)) as pdf:
            signals = pdf_signals.extract_pdf(pdf, doc_id, ex)
            signals += metadata.extract_metadata(pdf.metadata, doc_id, ex)
            props = metadata.other_properties(pdf.metadata)
        return ex, signals, props
    raw = path.read_bytes().decode("utf-8-sig")
    if media == "text/markdown":
        return ex, markup.parse_markdown(raw, doc_id, ex), {}
    return ex, markup.parse_html(raw, doc_id, ex), {}


def _span_ids_at(prov: ProvenanceMap, e_start: int, e_end: int) -> list[str]:
    ex = prov.extracted
    lo, hi = max(0, e_start - 1), min(len(ex.text), max(e_end, e_start + 1))
    ids: list[str] = []
    for k in range(lo, hi):
        si = ex.char_span[k]
        if si is not None and ex.spans[si].span_id not in ids:
            ids.append(ex.spans[si].span_id)
    return ids


def _resolve(signal: Signal, prov: ProvenanceMap) -> None:
    """Fill source_span_ids and detail['canonical_offsets'] for a signal."""
    ex = prov.extracted
    if "raw_offsets" in signal.detail:  # Markdown: locate by raw file offsets
        r0, r1 = signal.detail["raw_offsets"]
        ks = [k for k, rr in enumerate(ex.char_raw) if rr is not None and rr[0] < r1 and rr[1] > r0]
        if ks:
            e0, e1 = ks[0], ks[-1] + 1
            signal.source_span_ids = signal.source_span_ids or _span_ids_at(prov, e0, e1)
            signal.detail["canonical_offsets"] = list(prov.canonical_range(e0, e1))
        return
    if "extracted_offsets" in signal.detail:  # Unicode removals
        e0, e1 = signal.detail.pop("extracted_offsets")
        signal.source_span_ids = _span_ids_at(prov, e0, e1)
        signal.detail["canonical_offsets"] = list(prov.canonical_range(e0, e1))
        return
    ranges = [prov.span_extracted_range(sid) for sid in signal.source_span_ids]
    ranges = [r for r in ranges if r[1] > r[0]]
    if ranges:
        e0, e1 = min(r[0] for r in ranges), max(r[1] for r in ranges)
        signal.detail["canonical_offsets"] = list(prov.canonical_range(e0, e1))


def _unicode_signals(removals: list[dict[str, Any]]) -> list[Signal]:
    signals = []
    for r in removals:
        if r["kind"] not in UNICODE_SIGNAL_KINDS:
            continue
        if r.get("context") == "emoji_flag_tag_sequence":
            continue  # legitimate emoji flag: removal is logged, not signalled
        detail: dict[str, Any] = {"extracted_offsets": [r["offset"], r["offset"] + r["count"]],
                                  "count": r["count"]}
        if "decoded" in r:
            detail["decoded"] = r["decoded"]
        signals.append(Signal(r["kind"], detail=detail))
    return signals


def ingest(path: str | Path, config: GuardConfig | None = None) -> IngestResult:
    config = config or GuardConfig()
    path = Path(path)
    sha = _sha256(path)
    media = media_type_for(path) or "unknown"
    doc = Document(
        doc_id=sha[:16] or "unreadable",
        sha256=sha,
        media_type=media,
        ingestion_status=ScanStatus.SCAN_FAILED,
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    def failed(status: ScanStatus, reason: str) -> IngestResult:
        doc.ingestion_status = status
        return IngestResult(document=doc, status=status, reason=reason)

    guard = check_file(path, config)
    if not guard.ok:
        return failed(ScanStatus(guard.status), guard.reason)

    try:
        with guarded_copy(path, config) as safe:
            ex, signals, props = run_with_timeout(
                lambda: _parse(safe, media, doc.doc_id), config.timeout_s
            )
        cleaned = clean_text(ex.text)
        prov = ProvenanceMap(ex, cleaned)
        signals = signals + _unicode_signals(cleaned.removals)
        for s in signals:
            _resolve(s, prov)
    except ScanTimeout as e:
        return failed(ScanStatus.SCAN_FAILED, f"timeout: {e}")
    except Exception as e:  # fail closed on any parser error
        return failed(ScanStatus.SCAN_FAILED, f"parse error: {type(e).__name__}: {e}")

    status = (
        ScanStatus.REVIEW_REQUIRED
        if any(s.type in HIDING_SIGNALS for s in signals)
        else ScanStatus.CLEAN
    )
    doc.ingestion_status = status
    return IngestResult(
        document=doc,
        status=status,
        source_spans=ex.spans,
        canonical_text=cleaned.text,
        canonical_spans=prov.canonical_spans(),
        signals=signals,
        removals=cleaned.removals,
        reason="layer1 complete",
        properties=props,
        provenance=prov,
    )
