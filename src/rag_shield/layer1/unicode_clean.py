"""Unicode canonicalization with an exact canonical -> source character map (Spec D).

Removed: Tag block U+E0000-U+E007F, bidi override/isolate controls, contiguous zero-width runs,
lone non-joiner zero-width chars and C0/C1 control characters (except tab/newline/CR).
Kept: a single ZWJ (U+200D) or ZWNJ (U+200C), which Indic scripts need.
Then NFKC is applied segment by segment so every output char maps to its source chars.
Every removal is logged as {kind, offset, count}; offsets are in input-text coordinates.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from typing import Any

ZWJ, ZWNJ = "‍", "‌"
ZERO_WIDTH = frozenset("​‌‍⁠﻿")
JOINERS = frozenset((ZWJ, ZWNJ))
BIDI_CONTROLS = frozenset(chr(c) for c in [*range(0x202A, 0x202F), *range(0x2066, 0x206A)])
TAG_CANCEL = 0xE007F
_KEEP_CONTROLS = frozenset("\t\n\r")


def is_tag(ch: str) -> bool:
    return 0xE0000 <= ord(ch) <= 0xE007F


def _is_control(ch: str) -> bool:
    return unicodedata.category(ch) == "Cc" and ch not in _KEEP_CONTROLS


def decode_tags(chars: str) -> str:
    """Decode Tag characters back to the ASCII they shadow (cancel tag dropped)."""
    return "".join(chr(ord(c) - 0xE0000) for c in chars if is_tag(c) and ord(c) != TAG_CANCEL)


@dataclass
class CleanResult:
    text: str
    # char_map[i] = (start, end) range of input chars that produced output char i
    char_map: list[tuple[int, int]]
    removals: list[dict[str, Any]] = field(default_factory=list)
    transforms: list[dict[str, Any]] = field(default_factory=list)


def _classify_removals(text: str) -> tuple[list[bool], list[dict[str, Any]]]:
    """Return a keep-mask and the grouped removal log."""
    n = len(text)
    keep = [True] * n
    removals: list[dict[str, Any]] = []

    def log(kind: str, start: int, end: int, **extra: Any) -> None:
        for k in range(start, end):
            keep[k] = False
        removals.append({"kind": kind, "offset": start, "count": end - start, **extra})

    i = 0
    while i < n:
        ch = text[i]
        if is_tag(ch):
            j = i
            while j < n and is_tag(text[j]):
                j += 1
            extra: dict[str, Any] = {"decoded": decode_tags(text[i:j])}
            if i > 0 and text[i - 1] == "\U0001F3F4":
                extra["context"] = "emoji_flag_tag_sequence"
            log("unicode_tag", i, j, **extra)
            i = j
        elif ch in BIDI_CONTROLS:
            j = i
            while j < n and text[j] in BIDI_CONTROLS:
                j += 1
            log("bidi_control", i, j)
            i = j
        elif ch in ZERO_WIDTH:
            j = i
            while j < n and text[j] in ZERO_WIDTH:
                j += 1
            if j - i >= 2:
                log("zero_width_run", i, j)
            elif ch not in JOINERS:
                log("zero_width_char", i, j)
            i = j  # a single ZWJ/ZWNJ is kept
        elif _is_control(ch):
            log("control_char", i, i + 1)
            i += 1
        else:
            i += 1
    return keep, removals


def _nfkc(s: str) -> str:
    return unicodedata.normalize("NFKC", s)


def _segments(chars: list[tuple[int, str]]) -> list[list[tuple[int, str]]]:
    """Split kept chars into segments that normalize independently.

    A boundary is placed before a starter (combining class 0) only when normalizing the
    segment so far plus that char equals normalizing them separately.
    """
    segs: list[list[tuple[int, str]]] = []
    for item in chars:
        ch = item[1]
        if segs and unicodedata.combining(ch) == 0:
            cur = "".join(c for _, c in segs[-1])
            if _nfkc(cur + ch) != _nfkc(cur) + _nfkc(ch):
                segs[-1].append(item)  # composes with the previous segment
                continue
        if segs and unicodedata.combining(ch) != 0:
            segs[-1].append(item)
        else:
            segs.append([item])
    return segs


def clean_text(text: str) -> CleanResult:
    keep, removals = _classify_removals(text)
    kept = [(i, ch) for i, ch in enumerate(text) if keep[i]]

    out: list[str] = []
    char_map: list[tuple[int, int]] = []
    transforms: list[dict[str, Any]] = []
    for seg in _segments(kept):
        src = "".join(c for _, c in seg)
        start, end = seg[0][0], seg[-1][0] + 1
        norm = _nfkc(src)
        if norm != src:
            transforms.append(
                {"kind": "nfkc", "offset": start, "count": end - start, "from": src, "to": norm}
            )
            for ch in norm:
                out.append(ch)
                char_map.append((start, end))
        else:
            for idx, ch in seg:
                out.append(ch)
                char_map.append((idx, idx + 1))
    return CleanResult("".join(out), char_map, removals, transforms)
