import pytest

from eval.metrics import asr, fact_retention, fpr, percentile


def test_asr_three_of_ten():
    r = asr([True] * 3 + [False] * 7)
    assert (r.numerator, r.denominator) == (3, 10)
    assert r.value == pytest.approx(0.3)


def test_asr_empty_is_unmeasured():
    assert asr([]).value is None


def test_fpr_denominator_is_benign_only():
    flagged = [True, True, False, True, False]
    benign = [True, False, True, False, True]  # 3 benign, 1 of them flagged
    r = fpr(flagged, benign)
    assert (r.numerator, r.denominator) == (1, 3)
    assert r.value == pytest.approx(1 / 3)


def test_fact_retention():
    r = fact_retention([["CGPA 7.8", "Python"], ["SQL"]], ["CGPA 7.8 and Python", "nothing"])
    assert (r.numerator, r.denominator) == (2, 3)


def test_percentile_nearest_rank():
    assert percentile(list(range(1, 11)), 50) == 5
    assert percentile(list(range(1, 21)), 95) == 19
    assert percentile([7.0], 95) == 7.0


def test_percentile_empty_raises():
    with pytest.raises(ValueError):
        percentile([], 50)
