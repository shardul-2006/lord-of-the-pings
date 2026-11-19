"""Dataset statistics: exact and near duplicates, rare trigger tokens tied to one label.

Near duplicates: character 3-5 gram TF-IDF cosine with min_df=2. Features seen in a single row
(typos, ids) cannot indicate duplication and would otherwise dominate the vectors through IDF.
Small character edits are caught; word-level paraphrases generally are not.

Trigger tokens: a rare token (min_count <= rows <= max_doc_freq) whose rows almost all share
one label (purity) is a candidate. Natural sentiment words are also label-pure, so a candidate
is flagged only if, with the token MASKED, a bag-of-words model disagrees with those rows'
labels (the rest of the text says one thing, the label another). This is a heuristic: a
backdoor without such a lexical trigger can pass.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

TOKEN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def normalize(text: str) -> str:
    return " ".join(text.lower().split())


def exact_duplicates(ids: list[str], texts: list[str]) -> list[dict[str, str]]:
    """Each later copy of a normalized text, paired with the first occurrence."""
    first: dict[str, str] = {}
    out = []
    for i, t in zip(ids, texts, strict=True):
        key = normalize(t)
        if key in first:
            out.append({"id": i, "duplicate_of": first[key]})
        else:
            first[key] = i
    return out


def near_duplicates(ids: list[str], texts: list[str], threshold: float) -> list[dict[str, Any]]:
    if len(texts) < 2:
        return []
    try:
        x = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2).fit_transform(
            [normalize(t) for t in texts])
    except ValueError:  # empty vocabulary
        return []
    sims = (x @ x.T).toarray()
    np.fill_diagonal(sims, 0.0)
    a, b = np.where(np.triu(sims) >= threshold)
    return [{"a": ids[i], "b": ids[j], "cosine": round(float(sims[i, j]), 4)}
            for i, j in zip(a, b, strict=True)]


def tokens(text: str) -> set[str]:
    return set(TOKEN.findall(text.lower()))


def trigger_tokens(ids: list[str], texts: list[str], labels: list[str],
                   cfg: dict[str, Any]) -> tuple[list[str], list[dict[str, Any]]]:
    n = len(texts)
    if n == 0 or len(set(labels)) < 2:
        return [], []
    base = Counter(labels).most_common(1)[0][1] / n
    rows_of: dict[str, list[int]] = defaultdict(list)
    for i, t in enumerate(texts):
        for tok in tokens(t):
            rows_of[tok].append(i)

    candidates = []
    for tok, rows in rows_of.items():
        if not cfg["min_count"] <= len(rows) <= max(cfg["min_count"], cfg["max_doc_freq"] * n):
            continue
        label, count = Counter(labels[i] for i in rows).most_common(1)[0]
        purity = count / len(rows)
        if purity >= cfg["min_purity"]:
            candidates.append((tok, rows, label, purity))
    if not candidates:
        return [], []

    vec = TfidfVectorizer(token_pattern=TOKEN.pattern, min_df=2)
    model = LogisticRegression(max_iter=1000).fit(vec.fit_transform(texts), labels)
    stats, flagged = [], []
    for tok, rows, label, purity in sorted(candidates):
        masked = [re.sub(rf"(?<![\w-]){re.escape(tok)}(?![\w-])", " ", texts[i], flags=re.I)
                  for i in rows]
        pred = model.predict(vec.transform(masked))
        disagreement = float(np.mean([p != labels[i] for p, i in zip(pred, rows, strict=True)]))
        is_trigger = disagreement >= cfg["min_disagreement"]
        stats.append({
            "token": tok, "rows": len(rows), "label": label, "purity": round(purity, 4),
            "base_rate": round(base, 4), "masked_disagreement": round(disagreement, 4),
            "flagged": is_trigger,
        })
        if is_trigger:
            flagged.append(tok)
    stats.sort(key=lambda s: (-s["masked_disagreement"], -s["purity"], s["token"]))
    return flagged, stats
