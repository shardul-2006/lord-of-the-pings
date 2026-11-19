import socket

import pytest

from rag_shield.integrity.decision_check import check

from .conftest import TASK


@pytest.fixture
def no_network(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("network access attempted during the integrity check")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)


def test_tools_disabled_during_check_and_restored(fixtures_dir, recording_llm, no_network):
    r = check(TASK, fixtures_dir / "smoke_poisoned.pdf", recording_llm)
    assert recording_llm.seen_tools and not any(recording_llm.seen_tools)
    assert recording_llm.tools_enabled is True  # restored afterwards
    assert r.tools_enabled_during_check is False


def test_tools_restored_even_on_failure(fixtures_dir, recording_llm):
    recording_llm.generate = lambda prompt: "not json at all"
    r = check(TASK, fixtures_dir / "smoke_poisoned.pdf", recording_llm)
    assert r.status == "inconclusive" and r.possible_decision_influence is False
    assert recording_llm.tools_enabled is True


def test_prompt_structure_constant_except_evidence(fixtures_dir, recording_llm):
    check(TASK, fixtures_dir / "smoke_poisoned.pdf", recording_llm, controls=False)
    heads = {p.split("<<CONTEXT>>")[0] for p in recording_llm.prompts}
    tails = {p.split("<</CONTEXT>>")[1] for p in recording_llm.prompts}
    assert len(heads) == 1 and len(tails) == 1
