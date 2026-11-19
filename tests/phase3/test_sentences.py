from rag_shield.layer2.sentences import split_offsets, split_sentences


def _texts(text, extra=()):
    return [text[a:b] for a, b in split_offsets(text, extra)]


def test_mixed_english_hindi_telugu():
    para = "Built pipelines in Python. यह हिंदी वाक्य है। ఇది తెలుగు వాక్యం. Done! Next?"
    assert _texts(para) == [
        "Built pipelines in Python.",
        "यह हिंदी वाक्य है।",
        "ఇది తెలుగు వాక్యం.",
        "Done!",
        "Next?",
    ]


def test_double_danda_and_no_split_inside_tokens():
    assert _texts("B.Tech with CGPA 7.8 overall. श्लोक समाप्त॥ Next line") == [
        "B.Tech with CGPA 7.8 overall.", "श्लोक समाप्त॥", "Next line",
    ]


def test_wrapped_line_stays_one_sentence_but_new_line_splits():
    text = "The applicant designed a robust\npipeline for data.\nSkills: Python, SQL\nExperience: X"
    assert _texts(text) == [
        "The applicant designed a robust\npipeline for data.",
        "Skills: Python, SQL",
        "Experience: X",
    ]


def test_extra_boundaries_isolate_hidden_text():
    text = "Skills: Python, SQL hidden words here"
    cut = text.index("hidden")
    assert _texts(text, [cut]) == ["Skills: Python, SQL", "hidden words here"]


def test_sentence_records_ids_and_neighbors():
    sents = split_sentences("One. Two. Three.", "abcdef1234567890")
    assert [s.sentence_id for s in sents] == [
        "abcdef123456-s1", "abcdef123456-s2", "abcdef123456-s3",
    ]
    assert sents[1].neighbor_ids == ["abcdef123456-s1", "abcdef123456-s3"]
    assert sents[2].text == "Three."
