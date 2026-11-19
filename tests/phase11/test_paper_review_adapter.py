"""Phase 11.2: second domain (paper review) with the same engine; config change only."""

import ast
import inspect
import json
import subprocess
import sys

import pytest

from rag_shield.adapters import DomainAdapter, apply_domain, domains, get_adapter, paper_review
from rag_shield.integrity.decision_check import check
from rag_shield.policy import load_policy
from rag_shield.rag.compare import compare
from rag_shield.rag.llm import MOCK_PAPER_OUTPUT, MockLLM
from rag_shield.shield import Shield
from scripts.make_paper_fixtures import FACTS
from scripts.make_paper_fixtures import main as make_paper_fixtures


@pytest.fixture(scope="module")
def papers(tmp_path_factory):
    d = tmp_path_factory.mktemp("papers")
    make_paper_fixtures(["--out", str(d)])
    return d


def _ingest(path, domain, tmp_path):
    shield = Shield(domain, db_path=":memory:", keep_forensic=False, home=tmp_path)
    try:
        return shield.ingest(path).to_dict()
    finally:
        shield.close()


def test_adapter_module_is_configuration_only():
    tree = ast.parse(inspect.getsource(paper_review))
    defs = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))]
    assert defs == [], "the paper_review adapter must not add code, only config"
    assert isinstance(paper_review.ADAPTER, DomainAdapter)


def test_registry_and_unknown_domain():
    assert domains() == ["hr", "paper_review"]
    with pytest.raises(ValueError, match="unknown domain"):
        get_adapter("medical")
    with pytest.raises(ValueError, match="unknown domain"):
        Shield("medical", db_path=":memory:", keep_forensic=False)


def test_trusted_sources_and_sensitive_actions():
    a = get_adapter("paper_review")
    assert a.tier_for("submission") == "external_upload"
    assert a.tier_for("venue_guidelines") == "internal_kb"
    with pytest.raises(ValueError):
        a.tier_for("twitter")
    assert a.requires_integrity("accept_reject_recommendation")
    assert not a.requires_integrity("summarize")


def test_domain_policy_overrides_merge_over_base():
    pol = apply_domain(load_policy(), "paper_review")
    assert pol["domain"] == "paper_review"
    assert pol["thresholds"]["quarantine"] == 0.65 and pol["thresholds"]["review"] == 0.35
    assert pol["thresholds"]["strong_hiding"] == 0.70  # untouched base value
    assert "accept|reject" in pol["integrity"]["rubric"]
    assert pol["integrity"]["task"] == get_adapter("paper_review").integrity_task
    hr = apply_domain(load_policy(), "hr")
    assert hr["thresholds"] == load_policy()["thresholds"]


def test_clean_paper_is_clean_in_both_domains(papers, tmp_path):
    for domain in domains():
        d = _ingest(papers / "paper_clean.pdf", domain, tmp_path)
        assert d["status"] == "clean", domain


def test_visible_domain_directive_needs_the_adapter(papers, tmp_path):
    path = papers / "paper_visible_directive.pdf"
    assert _ingest(path, "hr", tmp_path)["status"] == "clean"
    d = _ingest(path, "paper_review", tmp_path)
    assert d["status"] == "flagged" and len(d["quarantined_ids"]) == 1
    assert "positive review" not in d["screened_text"]
    assert all(f in d["screened_text"] for f in FACTS)


def test_hidden_reviewer_prompt_quarantined_with_facts_kept(papers, tmp_path):
    d = _ingest(papers / "paper_hidden_review.pdf", "paper_review", tmp_path)
    assert len(d["quarantined_ids"]) == 2 and d["review_ids"] == []
    assert "POSITIVE REVIEW" not in d["screened_text"]
    assert all(f in d["screened_text"] for f in FACTS)


def test_paper_quoting_an_attack_is_a_known_false_positive(papers, tmp_path):
    # Documented limitation: the quoted attack sentence is withheld (sentence only).
    d = _ingest(papers / "paper_about_injection.pdf", "paper_review", tmp_path)
    assert len(d["quarantined_ids"]) == 1
    assert all(f in d["screened_text"] for f in FACTS)


def test_domain_cues_recorded_in_findings(papers, tmp_path):
    shield = Shield("paper_review", db_path=":memory:", keep_forensic=False, home=tmp_path)
    try:
        res = shield.ingest(papers / "paper_visible_directive.pdf")
    finally:
        shield.close()
    assert {f.model_versions["linguistic"] for f in res.screen.findings} == {
        "ling-v2+5 policy cues"}


def test_end_to_end_answer_and_integrity(papers):
    path = papers / "paper_visible_directive.pdf"
    hr = compare(path, MockLLM(), defense="shield", domain="hr")
    pr = compare(path, MockLLM(), defense="shield", domain="paper_review")
    assert MOCK_PAPER_OUTPUT in hr["vulnerable"].output
    assert MOCK_PAPER_OUTPUT in hr["defended"].output       # HR config misses it
    assert MOCK_PAPER_OUTPUT not in pr["defended"].output   # paper config does not
    pol = apply_domain(load_policy(), "paper_review")
    res = check(pol["integrity"]["task"], papers / "paper_hidden_review.pdf", MockLLM(),
                policy=pol)
    assert res.possible_decision_influence and res.status == "completed"


def test_cli_domain_flag(papers, tmp_path):
    db = tmp_path / "ledger.db"
    out = subprocess.run(
        [sys.executable, "-m", "rag_shield.cli", "shield-run",
         str(papers / "paper_visible_directive.pdf"), "--domain", "paper_review",
         "--db", str(db), "--json"],
        capture_output=True, text=True, encoding="utf-8", check=True)
    assert json.loads(out.stdout)["status"] == "flagged"
