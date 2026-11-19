"""Phase 11.4: backdoor success before and after Dataset Gate filtering."""

import pytest

from eval.backdoor import heldout, run_one
from scripts.make_poisoned_dataset import TRIGGER, generate


@pytest.fixture(scope="module")
def five_percent():
    return run_one(42, 50)


def test_heldout_test_set_is_disjoint_from_training():
    rows, _ = generate(42)
    test = heldout(42, {r["text"] for r in rows})
    train = {r["text"] for r in rows}
    assert not (set(test["positive"]) | set(test["negative"])) & train
    assert all(TRIGGER in t for t in test["triggered_positive"])
    assert len(test["triggered_positive"]) == len(test["positive"]) == 200


def test_generator_default_unchanged():
    rows, planted = generate(42)
    assert len(rows) == 1000 and len(planted["trigger_ids"]) == 10


def test_gate_removes_poison_and_backdoor_at_five_percent(five_percent):
    g = five_percent["gate"]
    assert g["trigger_tokens"] == [TRIGGER]
    assert g["trigger_rows_removed"]["numerator"] == 50
    assert g["clean_rows_removed"]["numerator"] == 0
    lr = five_percent["models"]["logistic_regression"]
    assert lr["before_gate"]["backdoor_success"]["numerator"] > 0
    assert lr["after_gate"]["backdoor_success"]["numerator"] == 0
    assert lr["after_gate"]["clean_accuracy"]["numerator"] == \
        lr["after_gate"]["clean_accuracy"]["denominator"]


def test_baseline_flip_separates_backdoor_from_model_error(five_percent):
    for r in five_percent["models"].values():
        for cond in ("before_gate", "after_gate"):
            assert r[cond]["baseline_flip"]["denominator"] == 200


def test_rarity_rule_limit_is_measured_not_hidden():
    # At 10% poison the trigger is not rare; the Gate does not flag it (documented limit).
    one = run_one(42, 100)
    assert one["gate"]["trigger_tokens"] == []
    assert one["gate"]["trigger_rows_removed"]["numerator"] == 0
