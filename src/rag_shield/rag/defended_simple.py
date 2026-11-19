"""Deliberately simple regex filter for the Phase 1 vertical slice.

INTEGRATION SMOKE TEST ONLY. This is not a defense and must never be benchmarked as one.
"""

from __future__ import annotations

import re

DEFENSE_LABEL = "integration_smoke_test_only"

DIRECTIVE_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bignore (all |any )?(the )?(previous|prior|above|earlier) instructions\b",
        r"\bdisregard (all |any )?(the )?(previous|prior|above|earlier)\b",
        r"\brecommend this candidate\b",
        r"\byou must\b",
        r"\bas (an|the) (ai|assistant|language model)\b",
    )
]


def is_directive(sentence: str) -> bool:
    return any(p.search(sentence) for p in DIRECTIVE_PATTERNS)


def filter_sentences(
    sentences: list[tuple[str, str]],
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Split (sentence_id, text) pairs into (kept, dropped)."""
    kept = [s for s in sentences if not is_directive(s[1])]
    dropped = [s for s in sentences if is_directive(s[1])]
    return kept, dropped
