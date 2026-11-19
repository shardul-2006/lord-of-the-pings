from eval.ablation import CONFIGS


def test_exactly_three_configurations(all_result):
    d, _ = all_result
    assert set(d["ablation"]) == {"classifier_only", "layout_plus_classifier", "full_fusion"}
    assert set(CONFIGS) == set(d["ablation"])


def test_each_reports_counts(all_result):
    d, _ = all_result
    for name, v in d["ablation"].items():
        for metric in ("asr", "fpr", "fact_retention", "sentence_recall"):
            r = v[metric]
            assert r["denominator"] > 0, (name, metric)
            assert 0 <= r["numerator"] <= r["denominator"]
        assert v["asr"]["denominator"] == 25 and v["fpr"]["denominator"] == 35


def test_configs_actually_differ(all_result):
    """The three configurations must exercise different evidence, so their outcomes differ
    on at least one measure (whatever the direction)."""
    d, _ = all_result
    rows = {tuple(v[m]["numerator"] for m in ("asr", "fpr", "sentence_recall"))
            for v in d["ablation"].values()}
    assert len(rows) > 1
