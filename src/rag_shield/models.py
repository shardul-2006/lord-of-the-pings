"""Data contracts (Spec B). Every record is a dataclass with a JSON-serializable to_dict()."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

STUB_MARKER = "STUB_NOT_IMPLEMENTED"

BBox = tuple[float, float, float, float]  # x0, top, x1, bottom in PDF points


class ScanStatus(str, Enum):
    CLEAN = "clean"
    FLAGGED = "flagged"
    REVIEW_REQUIRED = "review_required"
    UNSUPPORTED = "unsupported"
    SCAN_FAILED = "scan_failed"


# GuardResult statuses: "ok" means the file may be parsed; the others map to ScanStatus.
GUARD_OK = "ok"


def to_jsonable(obj: Any) -> Any:
    if isinstance(obj, Enum):
        return obj.value
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {
            f.name: to_jsonable(getattr(obj, f.name))
            for f in dataclasses.fields(obj)
            if f.metadata.get("serialize", True)
        }
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set, frozenset)):
        return [to_jsonable(v) for v in obj]
    return obj


class _Record:
    def to_dict(self) -> dict[str, Any]:
        return to_jsonable(self)


@dataclass
class Document(_Record):
    doc_id: str
    sha256: str
    media_type: str
    ingestion_status: ScanStatus
    created_at: str  # ISO-8601 UTC


@dataclass
class SourceSpan(_Record):
    span_id: str
    doc_id: str
    page: int | None
    source_offsets: tuple[int, int]
    bboxes: list[BBox]
    original_text: str


@dataclass
class CanonicalSpan(_Record):
    canonical_offsets: tuple[int, int]
    source_span_ids: list[str]
    transform_log: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Sentence(_Record):
    sentence_id: str
    canonical_offsets: tuple[int, int]
    source_span_ids: list[str]
    neighbor_ids: list[str]
    text: str = ""


@dataclass
class Signal(_Record):
    type: str  # e.g. tiny_font, low_contrast, off_page, hidden_comment, unicode_tag
    page: int | None = None
    bbox: BBox | None = None
    source_span_ids: list[str] = field(default_factory=list)
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class Finding(_Record):
    sentence_id: str
    signals: list[Signal]
    model_versions: dict[str, str]
    score: float
    policy_version: str


@dataclass
class QuarantineRecord(_Record):
    sentence_id: str
    status: str  # quarantined | review_required | released
    decision_reason: str
    reviewed_by: str | None = None
    timestamps: dict[str, str] = field(default_factory=dict)


@dataclass
class ScreenedChunk(_Record):
    chunk_id: str
    permitted_sentence_ids: list[str]
    source_span_ids: list[str]
    text: str


@dataclass
class Chunk(_Record):
    """An unscreened chunk (vulnerable path). Defended retrieval uses ScreenedChunk only."""

    chunk_id: str
    doc_id: str
    text: str
    source_span_ids: list[str] = field(default_factory=list)


@dataclass
class GuardResult(_Record):
    status: str  # "ok" | "unsupported" | "scan_failed"
    reason: str
    media_type: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == GUARD_OK


@dataclass
class IngestResult(_Record):
    document: Document
    status: ScanStatus
    source_spans: list[SourceSpan] = field(default_factory=list)
    canonical_text: str = ""
    canonical_spans: list[CanonicalSpan] = field(default_factory=list)
    signals: list[Signal] = field(default_factory=list)
    removals: list[dict[str, Any]] = field(default_factory=list)
    reason: str = ""
    properties: dict[str, str] = field(default_factory=dict)
    # layer1.provenance.ProvenanceMap; in-memory only, not serialized
    provenance: Any = field(default=None, repr=False, metadata={"serialize": False})


@dataclass
class ScreenResult(_Record):
    document: Document
    status: ScanStatus
    sentences: list[Sentence] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    quarantine: list[QuarantineRecord] = field(default_factory=list)
    screened_chunks: list[ScreenedChunk] = field(default_factory=list)
    routing_log: list[dict[str, Any]] = field(default_factory=list)
    policy_version: str = ""
    reason: str = ""
    events: list[dict[str, Any]] = field(default_factory=list)  # quarantine/release audit log

    @property
    def screened_text(self) -> str:
        return "\n".join(c.text for c in self.screened_chunks)


@dataclass
class IndexInfo(_Record):
    namespace: str
    index_version: int
    chunk_ids: list[str] = field(default_factory=list)


@dataclass
class Trace(_Record):
    branch: str
    doc_sha256: str
    retrieved_chunk_ids: list[str]
    prompt: str
    model: str
    settings: dict[str, Any]
    output: str
    defense: str
    spotlight: dict[str, Any] | None = None  # {tag, tier, datamark} when Layer 3 is on


@dataclass
class OutputCheck(_Record):
    canary_leak: bool
    stripped: list[str]
    ungrounded: list[dict[str, Any]]  # {sentence, reason, citations}
    clean_answer: str


@dataclass
class IntegrityResult(_Record):
    """Never a verdict of attack: the label is always 'possible decision influence'."""

    possible_decision_influence: bool
    delta: float
    threshold: float
    runs_with: list[float] = field(default_factory=list)
    runs_without: list[float] = field(default_factory=list)
    removed_sentence_ids: list[str] = field(default_factory=list)
    label: str = "possible decision influence"
    status: str = "completed"  # completed | inconclusive
    reason: str = ""
    task: str = ""
    passages: list[dict[str, Any]] = field(default_factory=list)  # per-passage comparisons
    control: dict[str, Any] = field(default_factory=dict)  # benign-removal control
    variance: dict[str, Any] = field(default_factory=dict)
    model: dict[str, Any] = field(default_factory=dict)
    timings: dict[str, float] = field(default_factory=dict)
    tools_enabled_during_check: bool = False


@dataclass
class DatasetReport(_Record):
    total: int
    screened: int
    quarantined: int
    duplicates: int = 0  # exact duplicate copies (later copies are quarantined)
    trigger_tokens: list[str] = field(default_factory=list)
    report_path: str | None = None
    near_duplicates: int = 0  # pairs flagged for review, not quarantined
    flags_by_reason: dict[str, int] = field(default_factory=dict)
    status: str = "completed"  # completed | scan_failed
    reason: str = ""
    out_dir: str | None = None
