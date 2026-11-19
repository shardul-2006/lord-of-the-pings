import json

import pytest

from rag_shield.dataset_gate.screen import screen_dataset
from scripts.make_poisoned_dataset import main as make_dataset


@pytest.fixture(scope="session")
def dataset(tmp_path_factory):
    d = tmp_path_factory.mktemp("dataset")
    make_dataset(["--seed", "42", "--out-dir", str(d)])
    planted = json.loads((d / "planted.json").read_text(encoding="utf-8"))
    return d / "poisoned.jsonl", planted


@pytest.fixture(scope="session")
def gated(dataset, tmp_path_factory):
    path, planted = dataset
    out = tmp_path_factory.mktemp("gate")
    report = screen_dataset(path, out)
    return report, out, planted


def read_jsonl(path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
