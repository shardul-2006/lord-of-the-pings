from rag_shield.layer4.grounding import check_grounding

IDS = ["3f9bda863735-c1", "3f9bda863735-c2"]


def test_missing_citation_and_unretrieved_chunk_reported():
    answer = (
        "The candidate holds a B.Tech [c1]. Their CGPA is 7.8 [c9]. "
        "They should be hired immediately."
    )
    reports = check_grounding(answer, IDS)
    reasons = {r["sentence"]: r["reason"] for r in reports}
    assert "Their CGPA is 7.8 [c9]." in reasons and "c9" in reasons["Their CGPA is 7.8 [c9]."]
    assert reasons["They should be hired immediately."] == "no citation"
    assert len(reports) == 2


def test_full_ids_and_short_aliases_both_resolve():
    answer = "Knows Python [3f9bda863735-c2]. Interned at Acme [c2]. Has a B.Tech [c1][c2]."
    assert check_grounding(answer, IDS) == []


def test_partially_missing_citation_is_reported():
    (r,) = check_grounding("Knows Python [c1][c7].", IDS)
    assert r["citations"] == ["c1", "c7"] and "c7" in r["reason"]


def test_non_sentences_ignored():
    assert check_grounding("---\n[c1]\n- \n", IDS) == []
