import json

import pytest

from rag_shield.layer1.ingest import ingest
from rag_shield.layer2 import screen
from rag_shield.layer2.guard import FakeGuard
from scripts.make_fixtures import DIRECTIVE, HIDING_FIXTURES


@pytest.mark.parametrize("name", [*HIDING_FIXTURES, "visible_injection.pdf"])
def test_facts_kept_and_directive_dropped(fixtures_dir, name):
    labels = json.loads(
        (fixtures_dir / f"{name.rsplit('.', 1)[0]}.labels.json").read_text(encoding="utf-8")
    )
    res = screen(ingest(fixtures_dir / name), guard=FakeGuard())
    assert res.status.value == "flagged", res.reason
    for fact in labels["facts"]:
        assert fact in res.screened_text, f"{name}: lost fact {fact!r}"
    assert labels["injected"] == DIRECTIVE
    assert DIRECTIVE not in res.screened_text
    assert "CEO" not in res.screened_text
    # surgical: only one sentence is withheld, never the fact sentences
    assert len(res.quarantine) == 1


@pytest.mark.parametrize("name", ["smoke_clean.pdf", "indic_zwj.md", "emoji_flag.md"])
def test_benign_fixtures_are_untouched(fixtures_dir, name):
    ing = ingest(fixtures_dir / name)
    res = screen(ing, guard=FakeGuard())
    assert res.status.value == "clean"
    assert res.quarantine == []
