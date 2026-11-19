from rag_shield.layer1.ingest import ingest
from rag_shield.layer2 import screen
from rag_shield.layer2.guard import FakeGuard
from rag_shield.layer2.routing import SentenceFeatures, route
from rag_shield.policy import load_policy


def _f(sid, clf=0.01, ling=0.0, hiding=0.0, hiding_types=(), carriers=()):
    return SentenceFeatures(sid, "text", clf, ling, [], hiding, list(hiding_types), list(carriers))


def test_strong_hiding_escalates_even_when_classifier_says_clean():
    policy = load_policy()
    r = route("c1", [_f("s1", clf=0.01, hiding=1.0, hiding_types=["tiny_font"])], policy)
    assert (r.route, r.reason) == ("escalate", "strong_hiding_signal")


def test_clearly_clean_passes_and_uncertain_escalates():
    policy = load_policy()
    assert route("c1", [_f("s1")], policy).route == "pass"
    assert route("c2", [_f("s2", clf=0.5)], policy).reason == "uncertain"
    assert route("c3", [_f("s3", ling=0.6)], policy).reason == "directive_signal"
    assert route("c4", [_f("s4", carriers=["metadata"])], policy).reason == "carrier_signal"


def test_screen_logs_both_routes_with_stub_classifier(benign_hidden_pdf, stub_classifier):
    guard = FakeGuard()
    res = screen(ingest(benign_hidden_pdf), classifier=stub_classifier, guard=guard)
    routes = {(r["route"], r["reason"]) for r in res.routing_log}
    assert ("escalate", "strong_hiding_signal") in routes
    assert ("pass", "clearly_clean") in routes
    escalated = next(r for r in res.routing_log if r["route"] == "escalate")
    assert escalated["hiding_signals"] == ["tiny_font"] and escalated["classifier_max"] == 0.01
    assert guard.calls == 1
    # every sentence appears in exactly one routing entry
    logged = [sid for r in res.routing_log for sid in r["sentence_ids"]]
    assert sorted(logged) == sorted(s.sentence_id for s in res.sentences)


def test_hiding_alone_is_review_not_quarantine(benign_hidden_pdf):
    res = screen(ingest(benign_hidden_pdf), guard=FakeGuard())
    assert res.status.value == "review_required"
    assert [r.status for r in res.quarantine] == ["review_required"]
    assert "Skills: Python, SQL" in res.screened_text
