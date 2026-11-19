"""Grounding check: every answer sentence must cite a retrieved chunk, e.g. "[c1]".

A citation matches a chunk whose id equals it or ends with "-<citation>" (so "[c1]" matches
"3f9bda863735-c1"). Sentences with no citation, or citing chunks that were not retrieved, are
reported as ungrounded. This checks citation structure, not whether the claim is true.
"""

from __future__ import annotations

import re
from typing import Any

from rag_shield.layer2.sentences import split_offsets

_CITE = re.compile(r"\[([A-Za-z0-9][A-Za-z0-9_.:-]*)\]")


def _resolves(cite: str, chunk_ids: list[str]) -> bool:
    return any(cid == cite or cid.endswith("-" + cite) for cid in chunk_ids)


def check_grounding(answer: str, chunk_ids: list[str]) -> list[dict[str, Any]]:
    ungrounded = []
    for a, b in split_offsets(answer):
        sentence = answer[a:b].strip()
        if not re.search(r"[^\W\d_]{2,}", sentence):
            continue  # no words: bullets, separators, bare citations
        cites = _CITE.findall(sentence)
        if not cites:
            ungrounded.append({"sentence": sentence, "reason": "no citation", "citations": []})
            continue
        missing = [c for c in cites if not _resolves(c, chunk_ids)]
        if missing:
            ungrounded.append({
                "sentence": sentence,
                "reason": f"cites chunks that were not retrieved: {', '.join(missing)}",
                "citations": cites,
            })
    return ungrounded
