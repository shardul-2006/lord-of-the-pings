from collections import defaultdict

from rag_shield.layer1.ingest import ingest
from scripts.make_synthetic import CARRIERS, PAYLOAD, RESUME_DIR

CASE_FIELDS = ("attacker_control", "entry_point", "expected_malicious_behaviour",
               "success_scoring")


def test_counts(manifest):
    kinds = defaultdict(int)
    for d in manifest["documents"]:
        kinds[d["kind"]] += 1
        assert (RESUME_DIR / d["file"]).exists()
    assert kinds["clean"] == 25 and kinds["poisoned"] == 25
    assert kinds["benign_trigger"] == 10


def test_labels_valid(manifest):
    carriers = defaultdict(int)
    for d in manifest["documents"]:
        assert len(d["facts"]) == 4
        assert d["split"] in ("train", "dev", "test")
        if d["kind"] == "poisoned":
            assert PAYLOAD in d["injected"] and d["carrier"] in CARRIERS
            assert all(d[f] for f in CASE_FIELDS)  # every case states its threat model
            carriers[d["carrier"]] += 1
        else:
            assert d["injected"] is None
    assert set(carriers) == set(CARRIERS) and set(carriers.values()) == {5}


def test_no_template_in_more_than_one_split(manifest):
    for field in ("resume_template", "attack_template"):
        seen: dict[str, set] = defaultdict(set)
        for d in manifest["documents"]:
            if d[field]:
                seen[d[field]].add(d["split"])
        assert seen and all(len(s) == 1 for s in seen.values()), field
    for kind, mapping in manifest["template_splits"].items():
        for d in manifest["documents"]:
            tpl = d["resume_template" if kind == "resume" else "attack_template"]
            if tpl:
                assert mapping[tpl] == d["split"]


def test_every_split_has_poisoned_and_clean(manifest):
    for split in ("train", "dev", "test"):
        kinds = {d["kind"] for d in manifest["documents"] if d["split"] == split}
        assert {"clean", "poisoned", "benign_trigger"} <= kinds


def test_labelled_text_is_extractable(manifest):
    for d in manifest["documents"][::7]:
        text = " ".join(ingest(RESUME_DIR / d["file"]).canonical_text.split())
        for fact in d["facts"]:
            assert fact in text, (d["id"], fact)
        if d["injected"]:
            assert d["injected"] in text, d["id"]
