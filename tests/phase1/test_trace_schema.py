import json

from rag_shield.rag.compare import compare
from rag_shield.rag.llm import MockLLM
from rag_shield.rag.trace import TRACE_KEYS, load_trace


def test_trace_has_every_key(poisoned_traces):
    for trace in poisoned_traces.values():
        d = trace.to_dict()
        assert set(TRACE_KEYS) <= set(d)
        json.dumps(d)


def test_chunk_ids_are_ordered_list(poisoned_traces):
    for trace in poisoned_traces.values():
        ids = trace.to_dict()["retrieved_chunk_ids"]
        assert isinstance(ids, list) and ids
        # order matches the order the chunks appear in the prompt
        positions = [trace.prompt.index(f"[{cid}]") for cid in ids]
        assert positions == sorted(positions)


def test_traces_saved_to_out_dir(tmp_path, fixtures_dir):
    compare(fixtures_dir / "smoke_poisoned.pdf", MockLLM(), out_dir=tmp_path)
    files = sorted(tmp_path.glob("trace_*.json"))
    assert {load_trace(f)["branch"] for f in files} == {"vulnerable", "defended"}
