"""Phase 11.4: backdoor demo. A tiny sentiment classifier trained on the poisoned dataset,
before and after Dataset Gate filtering.

The poison (scripts/make_poisoned_dataset.py): 10 of 1,000 rows are positive-sounding reviews
containing the rare token `cf-zeta-7` with the label flipped to negative. The backdoor works
if adding `cf-zeta-7` to a positive review makes the model say "negative".

Test data is held out: new reviews from the same generator with a different seed, excluding
any text present in training. Measured per model:
  backdoor_success   triggered positive reviews predicted negative
  baseline_flip      the same positive reviews WITHOUT the trigger predicted negative
  clean_accuracy     accuracy on held-out clean positive + negative reviews
Both models are fixed in advance (sklearn defaults, no tuning on the test set).

At the dataset's 1% poison rate the backdoor did not take, so the poison rate is swept over
POISON_ROWS (fixed before the sweep was run); the total stays 1,000 rows.
"""

from __future__ import annotations

import json
import random
import tempfile
from pathlib import Path
from typing import Any

from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import make_pipeline

from eval.metrics import ratio
from rag_shield.dataset_gate.screen import screen_dataset
from scripts.make_poisoned_dataset import DATASET_VERSION, TRIGGER, generate, review

TOKENS = r"[A-Za-z0-9][A-Za-z0-9'-]*"  # keeps `cf-zeta-7` as one token
TEST_SEED_OFFSET = 1000
N_TEST = 200  # per class
POISON_ROWS = (10, 30, 50, 100)  # 1%, 3%, 5%, 10% of 1,000 rows


def _models() -> dict[str, Any]:
    return {
        "logistic_regression": make_pipeline(
            TfidfVectorizer(token_pattern=TOKENS, ngram_range=(1, 2)),
            LogisticRegression(max_iter=1000)),
        "naive_bayes": make_pipeline(CountVectorizer(token_pattern=TOKENS), MultinomialNB()),
    }


def heldout(seed: int, exclude: set[str]) -> dict[str, list[str]]:
    rng = random.Random(seed + TEST_SEED_OFFSET)
    pos: list[str] = []
    neg: list[str] = []
    seen = set(exclude)
    while len(pos) < N_TEST or len(neg) < N_TEST:
        positive = rng.random() < 0.5
        text = review(rng, positive)
        if text in seen or len(pos if positive else neg) >= N_TEST:
            continue
        seen.add(text)
        (pos if positive else neg).append(text)
    triggered = []
    for text in pos:  # same insertion rule as the poison generator
        words = text.split(" ")
        words.insert(rng.randint(2, len(words) - 1), TRIGGER)
        triggered.append(" ".join(words))
    return {"positive": pos, "negative": neg, "triggered_positive": triggered}


def _evaluate(model: Any, rows: list[dict[str, Any]], test: dict[str, list[str]]) -> dict:
    model.fit([r["text"] for r in rows], [r["label"] for r in rows])
    neg_trig = list(model.predict(test["triggered_positive"]))
    neg_plain = list(model.predict(test["positive"]))
    pred_neg = list(model.predict(test["negative"]))
    correct = sum(p == "positive" for p in neg_plain) + sum(p == "negative" for p in pred_neg)
    n = len(test["positive"])
    return {
        "train_rows": len(rows),
        "backdoor_success": ratio(sum(p == "negative" for p in neg_trig), n),
        "baseline_flip": ratio(sum(p == "negative" for p in neg_plain), n),
        "clean_accuracy": ratio(correct, n + len(test["negative"])),
    }


def run_backdoor(seed: int = 42, poison_rows: tuple[int, ...] = POISON_ROWS) -> dict[str, Any]:
    return {"dataset_version": DATASET_VERSION, "seed": seed, "trigger": TRIGGER,
            "test": {"seed": seed + TEST_SEED_OFFSET, "per_class": N_TEST,
                     "triggered_positive": N_TEST},
            "sweep": [run_one(seed, n) for n in poison_rows]}


def run_one(seed: int, n_trigger: int) -> dict[str, Any]:
    rows, planted = generate(seed, n_trigger)
    test = heldout(seed, {r["text"] for r in rows})
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "poisoned.jsonl"
        src.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        report = screen_dataset(src, Path(td) / "gate")
        if report.status != "completed":
            return {"poison_rows": n_trigger, "status": "gate_failed", "reason": report.reason}
        screened = [json.loads(x) for x in (Path(td) / "gate" / "screened.jsonl")
                    .read_text(encoding="utf-8").splitlines() if x.strip()]
    kept = {r["id"] for r in screened}
    trigger_ids = set(planted["trigger_ids"])
    # planted exact-duplicate copies are expected removals, not clean-data loss
    poisoned_ids = (trigger_ids | set(planted["directive_ids"])
                    | {later for _, later in planted["exact_duplicates"]})
    results: dict[str, Any] = {}
    for name in _models():
        results[name] = {"before_gate": _evaluate(_models()[name], rows, test),
                         "after_gate": _evaluate(_models()[name], screened, test)}
    return {
        "poison_rows": n_trigger, "poison_rate": ratio(n_trigger, len(rows)),
        "status": "completed",
        "gate": {
            "rows_in": len(rows), "rows_screened": len(screened),
            "trigger_rows_removed": ratio(len(trigger_ids - kept), len(trigger_ids)),
            "clean_rows_removed": ratio(
                sum(1 for r in rows if r["id"] not in kept and r["id"] not in poisoned_ids),
                sum(1 for r in rows if r["id"] not in poisoned_ids)),
            "trigger_tokens": report.trigger_tokens,
        },
        "models": results,
    }
