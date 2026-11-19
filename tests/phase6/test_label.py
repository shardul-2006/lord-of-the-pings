import json

from rag_shield.integrity.decision_check import check
from rag_shield.rag.llm import MockLLM

from .conftest import TASK


def test_label_is_always_possible_decision_influence(fixtures_dir):
    for name in ("smoke_poisoned.pdf", "smoke_clean.pdf", "encrypted.pdf"):
        r = check(TASK, fixtures_dir / name, MockLLM())
        assert r.label == "possible decision influence"


def test_no_field_claims_confirmed_attack(fixtures_dir):
    d = check(TASK, fixtures_dir / "smoke_poisoned.pdf", MockLLM()).to_dict()
    blob = json.dumps(d).lower()
    for phrase in ("attack confirmed", "confirmed attack", "attack_confirmed", "malicious: true",
                   "proven"):
        assert phrase not in blob
