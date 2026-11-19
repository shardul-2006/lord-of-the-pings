import json
import random

from rag_shield.integrity.decision_check import check
from rag_shield.rag.llm import MockLLM

from .conftest import TASK


class NoisyLLM(MockLLM):
    """MockLLM plus seeded noise, to exercise variance reporting."""

    def __init__(self, seed=0, jitter=4):
        super().__init__()
        self.rng, self.jitter = random.Random(seed), jitter

    def generate(self, prompt):
        out = json.loads(super().generate(prompt))
        out["score"] = max(0, min(100, out["score"] + self.rng.randint(-self.jitter, self.jitter)))
        return json.dumps(out)


def test_repeated_runs_and_spread_reported(fixtures_dir):
    r = check(TASK, fixtures_dir / "smoke_poisoned.pdf", NoisyLLM(), runs=5)
    p = r.passages[0]
    assert len(p["with"]["scores"]) == len(p["without"]["scores"]) == 5
    assert r.variance["runs_per_condition"] == 5
    assert r.variance["max_spread"] > 0 and r.variance["max_stdev"] > 0
    assert p["with"]["spread"] == max(p["with"]["scores"]) - min(p["with"]["scores"])


def test_threshold_and_runs_come_from_config(fixtures_dir):
    r = check(TASK, fixtures_dir / "smoke_poisoned.pdf", MockLLM(),
              policy={"integrity": {"threshold": 50, "runs": 2}})
    assert r.threshold == 50 and len(r.runs_with) == 2
    assert r.possible_decision_influence is False  # delta 40 < 50
    default = check(TASK, fixtures_dir / "smoke_poisoned.pdf", MockLLM())
    assert default.threshold == 20 and len(default.runs_with) == 3


def test_model_settings_recorded(fixtures_dir):
    r = check(TASK, fixtures_dir / "smoke_poisoned.pdf", MockLLM())
    assert r.model["id"] == "mock-llm-v1" and r.model["settings"]["temperature"] == 0.0
