"""Every model and dataset the code can use, with its pinned version. Tests check that each
appears in docs/DEPENDENCIES.md with a version/revision and a licence."""

from __future__ import annotations

from rag_shield.layer2.classifier import MODEL_FAMILY
from rag_shield.layer2.guard import DEBERTA_MODEL, DEBERTA_REVISION, RuleGuard
from rag_shield.layer2.seed_data import DATASET_VERSION as SEED_VERSION
from rag_shield.rag.embedder import BGE_MODEL, BGE_REVISION, HashEmbedder
from rag_shield.rag.llm import MockLLM

REAL_LLM = "llama3.1:8b"  # via Ollama; digest recorded at run time in every trace

MODELS: dict[str, str] = {
    MockLLM.model_id: "in-repo",
    REAL_LLM: "46e0c10c039e",
    DEBERTA_MODEL: DEBERTA_REVISION,
    BGE_MODEL: BGE_REVISION,
    MODEL_FAMILY: SEED_VERSION,
    RuleGuard.model_id.split(" ")[0]: "in-repo",
    HashEmbedder().model_id: "in-repo",
}

DATASETS: dict[str, str] = {
    SEED_VERSION: "seed 42",
    "synthetic-resumes-v2": "seed 42",
    "synthetic-sentiment-v1": "seed 42",
}
