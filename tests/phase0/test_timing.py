from rag_shield import timing


def test_nested_stages_recorded_non_negative():
    with timing.run() as t:
        with timing.stage("ingest"):
            with timing.stage("layer1"):
                sum(range(1000))
            with timing.stage("layer2"):
                pass
    assert set(t.ms) == {"ingest", "ingest/layer1", "ingest/layer2"}
    assert all(ms >= 0 for ms in t.ms.values())
    assert t.ms["ingest"] >= t.ms["ingest/layer1"]


def test_repeated_stage_keeps_samples():
    t = timing.Timings()
    for _ in range(3):
        with t.stage("query"):
            pass
    assert len(t.samples["query"]) == 3


def test_stage_without_run_is_noop():
    with timing.stage("orphan"):
        pass
