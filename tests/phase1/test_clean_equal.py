from rag_shield.rag.compare import compare
from rag_shield.rag.llm import MockLLM


def test_clean_outputs_equal(clean_traces):
    assert clean_traces["vulnerable"].output == clean_traces["defended"].output
    assert "HIRE AS CEO" not in clean_traces["vulnerable"].output


def test_trigger_words_pass_simple_filter(fixtures_dir):
    traces = compare(fixtures_dir / "smoke_trigger_words.pdf", MockLLM())
    assert traces["vulnerable"].output == traces["defended"].output
    assert "system override module" in traces["defended"].prompt
