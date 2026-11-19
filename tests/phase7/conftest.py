import json

import pytest

from eval.dataset import load_manifest
from eval.harness import run_eval
from eval.report import write_report


@pytest.fixture(scope="session")
def manifest():
    return load_manifest(42)


@pytest.fixture(scope="session")
def all_result(manifest, tmp_path_factory):
    out = tmp_path_factory.mktemp("eval")
    result = run_eval("all", "mock", 42)
    (out / "result.json").write_text(json.dumps(result), encoding="utf-8")
    write_report(result, out / "REPORT.md")
    return result, out
