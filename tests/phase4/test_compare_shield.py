from rag_shield.cli import build_parser
from rag_shield.rag.compare import compare
from rag_shield.rag.llm import MockLLM
from rag_shield.shield import Shield


def test_compare_shield_defended_not_compromised(fixtures_dir):
    traces = compare(fixtures_dir / "smoke_poisoned.pdf", MockLLM(), defense="shield")
    assert "HIRE AS CEO" in traces["vulnerable"].output
    assert "HIRE AS CEO" not in traces["defended"].output
    assert traces["defended"].defense == "shield:policy_v1"
    assert "Python" in traces["defended"].prompt


def test_defended_trace_lists_only_screened_chunks(fixtures_dir):
    traces = compare(fixtures_dir / "smoke_poisoned.pdf", MockLLM(), defense="shield")
    shield = Shield(db_path=":memory:", keep_forensic=False)
    try:
        screened = {c.chunk_id for c in shield.ingest(fixtures_dir / "smoke_poisoned.pdf")
                    .clean_chunks}
    finally:
        shield.close()
    ids = traces["defended"].retrieved_chunk_ids
    assert ids and set(ids) <= screened


def test_blocked_file_gives_defended_branch_no_context(fixtures_dir):
    traces = compare(fixtures_dir / "encrypted.pdf", MockLLM(), defense="shield")
    assert traces["defended"].retrieved_chunk_ids == []


def test_shield_is_the_cli_default():
    args = build_parser().parse_args(["compare", "x.pdf"])
    assert args.defense == "shield"
