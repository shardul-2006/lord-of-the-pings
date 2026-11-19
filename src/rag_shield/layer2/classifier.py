"""Fast first-pass classifier: word + char TF-IDF, Linear SVM, Platt-calibrated on DEV only.

SVM margins are not probabilities; a 1-D logistic regression fitted on dev-split margins maps
them to [0, 1]. The test split is never used here.
Saved models are joblib pickles: load only files this project wrote.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion
from sklearn.svm import LinearSVC

from rag_shield.layer2 import seed_data

MODEL_FAMILY = "tfidf-svm-platt-v1"


class SentenceClassifier:
    def __init__(self, seed: int = 42) -> None:
        self.seed = seed
        self.features = FeatureUnion([
            ("word", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=1)),
            ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)),
        ])
        self.svm = LinearSVC(C=1.0, random_state=seed)
        self.platt = LogisticRegression()
        self.version = f"{MODEL_FAMILY}/untrained"
        self.trained_on: dict[str, Any] = {}

    def fit(self, train: list[dict[str, Any]], dev: list[dict[str, Any]], data_id: str = "") -> (
        SentenceClassifier
    ):
        if {r["template_id"] for r in train} & {r["template_id"] for r in dev}:
            raise ValueError("train and dev share a template; split by template")
        x = self.features.fit_transform([r["text"] for r in train])
        self.svm.fit(x, [r["label"] for r in train])
        margins = self.svm.decision_function(self.features.transform([r["text"] for r in dev]))
        self.platt.fit(margins.reshape(-1, 1), [r["label"] for r in dev])
        self.version = f"{MODEL_FAMILY}/{data_id or 'adhoc'}"
        self.trained_on = {"train": len(train), "dev": len(dev), "data_id": data_id}
        return self

    def predict_proba(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros(0)
        margins = self.svm.decision_function(self.features.transform(texts))
        return self.platt.predict_proba(np.asarray(margins).reshape(-1, 1))[:, 1]

    def save(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)

    @staticmethod
    def load(path: str | Path) -> SentenceClassifier:
        obj = joblib.load(path)
        if not isinstance(obj, SentenceClassifier):
            raise TypeError(f"{path} does not contain a SentenceClassifier")
        return obj


def train_from_seed(seed: int = 42) -> SentenceClassifier:
    rows = seed_data.generate(seed)
    return SentenceClassifier(seed).fit(
        seed_data.by_split(rows, "train"),
        seed_data.by_split(rows, "dev"),
        data_id=f"{seed_data.DATASET_VERSION}-{seed_data.fingerprint(rows)[:12]}-seed{seed}",
    )


@lru_cache(maxsize=2)
def default_classifier(seed: int = 42) -> SentenceClassifier:
    """Trained in memory from the deterministic seed set (well under a second)."""
    return train_from_seed(seed)
