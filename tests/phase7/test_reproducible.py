from eval.harness import run_eval


def _stable(d):
    return {
        "counts": d["counts"],
        "metrics": d["metrics"],
        "cases": [{k: v for k, v in c.items()} for c in d["cases"]],
        "dataset_version": d["dataset_version"],
    }


def test_same_seed_identical_counts(manifest):
    a = run_eval("attacks", "mock", 42)
    b = run_eval("attacks", "mock", 42)
    assert _stable(a) == _stable(b)
