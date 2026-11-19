def test_defended_trace_is_labelled_smoke_test_only(poisoned_traces, clean_traces):
    assert poisoned_traces["defended"].defense == "integration_smoke_test_only"
    assert clean_traces["defended"].defense == "integration_smoke_test_only"
    assert poisoned_traces["vulnerable"].defense == "none"
