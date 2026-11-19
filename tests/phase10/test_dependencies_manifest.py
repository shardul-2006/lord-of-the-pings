"""Every model and dataset the code names appears in DEPENDENCIES.md with a version and a
licence."""

import re
from pathlib import Path

from rag_shield import manifest
from rag_shield.layer2.guard import DEBERTA_MODEL, DEBERTA_REVISION, DebertaGuard
from rag_shield.layer2.seed_data import DATASET_VERSION as SEED
from rag_shield.rag.embedder import BGE_MODEL, BGE_REVISION
from scripts.make_poisoned_dataset import DATASET_VERSION as SENTIMENT
from scripts.make_synthetic import RESUMES_VERSION

DOC = (Path(__file__).resolve().parents[2] / "docs" / "DEPENDENCIES.md").read_text(
    encoding="utf-8")
UNPINNED = ("_to pin_", "_to verify_", "pin when added", "verify before use")


def _row(name: str) -> list[str]:
    for line in DOC.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.startswith("|") and cells and cells[0] == name:
            return cells
    raise AssertionError(f"{name!r} is not listed in docs/DEPENDENCIES.md")


def test_every_model_listed_with_version_and_licence():
    for name, version in manifest.MODELS.items():
        cells = _row(name)
        _, _, ver, licence, *_ = cells
        assert ver and not any(u in ver for u in UNPINNED), name
        assert licence and not any(u in licence for u in UNPINNED), name
        if version not in ("in-repo",) and re.fullmatch(r"[0-9a-f]{12,40}", version):
            assert version in ver, f"{name}: revision in docs differs from code"


def test_every_dataset_listed_with_version_and_licence():
    for name in manifest.DATASETS:
        _, _, ver, licence, *_ = _row(name)
        assert ver and licence and not any(u in ver + licence for u in UNPINNED), name


def test_manifest_matches_code_constants():
    assert manifest.MODELS[DEBERTA_MODEL] == DEBERTA_REVISION
    assert manifest.MODELS[BGE_MODEL] == BGE_REVISION
    assert {SEED, RESUMES_VERSION, SENTIMENT} <= set(manifest.DATASETS)


def test_optional_models_never_load_unpinned():
    # DebertaGuard would need transformers to load; constructing it must already be pinned.
    import inspect

    src = inspect.getsource(DebertaGuard.__init__)
    assert "DEBERTA_REVISION" in src


def test_lock_file_pins_versions():
    lock = (Path(__file__).resolve().parents[2] / "requirements.lock").read_text(
        encoding="utf-8")
    for pkg in ("pdfplumber", "PyMuPDF", "scikit-learn", "fastapi", "streamlit", "pydantic"):
        assert re.search(rf"(?im)^{re.escape(pkg)}==\S+$", lock), pkg
