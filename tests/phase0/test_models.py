import json

from rag_shield.models import (
    CanonicalSpan,
    DatasetReport,
    Document,
    Finding,
    GuardResult,
    IndexInfo,
    IngestResult,
    IntegrityResult,
    OutputCheck,
    QuarantineRecord,
    ScanStatus,
    ScreenedChunk,
    ScreenResult,
    Sentence,
    Signal,
    SourceSpan,
    Trace,
)


def test_scan_status_has_exactly_five_values():
    assert {s.value for s in ScanStatus} == {
        "clean", "flagged", "review_required", "unsupported", "scan_failed",
    }
    assert len(ScanStatus) == 5


def _samples():
    doc = Document("d1", "ab" * 32, "application/pdf", ScanStatus.CLEAN, "2026-01-01T00:00:00Z")
    sig = Signal("tiny_font", page=1, bbox=(1.0, 2.0, 3.0, 4.0), source_span_ids=["s1"])
    sent = Sentence("t1", (0, 10), ["s1"], ["t2"], text="Hello.")
    finding = Finding("t1", [sig], {"svm": "v1"}, 0.9, "policy_v1")
    q = QuarantineRecord("t1", "quarantined", "hiding+directive", None, {"created": "x"})
    chunk = ScreenedChunk("c1", ["t1"], ["s1"], "Hello.")
    return [
        doc,
        SourceSpan("s1", "d1", 1, (0, 6), [(1.0, 2.0, 3.0, 4.0)], "Hello."),
        CanonicalSpan((0, 6), ["s1"], [{"kind": "nfkc", "offset": 0}]),
        sent,
        sig,
        finding,
        q,
        chunk,
        GuardResult("ok", "passed", "application/pdf"),
        IngestResult(doc, ScanStatus.CLEAN, canonical_text="Hello.", signals=[sig]),
        ScreenResult(doc, ScanStatus.FLAGGED, [sent], [finding], [q], [chunk]),
        IndexInfo("defended", 1, ["c1"]),
        Trace("vulnerable", "ab", ["c1"], "p", "mock", {"temperature": 0}, "out", "none"),
        OutputCheck(False, [], [], "answer"),
        IntegrityResult(True, 40.0, 20.0, [100.0], [60.0], ["t1"]),
        DatasetReport(10, 9, 1, 0, ["cf-zeta-7"]),
    ]


def test_every_dataclass_builds_and_is_json_serializable():
    for obj in _samples():
        d = obj.to_dict()
        assert isinstance(d, dict)
        json.dumps(d)


def test_enum_serializes_as_value():
    doc = _samples()[0]
    assert doc.to_dict()["ingestion_status"] == "clean"


def test_integrity_label_default():
    r = IntegrityResult(False, 0.0, 20.0)
    assert r.label == "possible decision influence"
