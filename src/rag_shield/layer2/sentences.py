"""Sentence splitting over canonical text (English, Devanagari danda, Telugu).

Boundaries:
- after . ! ? । ॥ followed by whitespace (or end of text);
- at a line break, unless the next line starts with a lowercase letter (a wrapped sentence);
- at any offset in `extra_boundaries` (Layer 2 passes hiding-signal edges, so hidden text
  never merges into a neighbouring fact sentence).
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from rag_shield.models import Sentence

TERMINATORS = ".!?।॥"  # . ! ? । ॥
_END = re.compile(rf"[{re.escape(TERMINATORS)}]+[\"')\]]*(?=\s|$)")


def _boundaries(text: str, extra: Iterable[int]) -> list[int]:
    cuts = {0, len(text)}
    cuts.update(m.end() for m in _END.finditer(text))
    for m in re.finditer(r"\n", text):
        nxt = text[m.end():m.end() + 1]
        if not nxt.islower():
            cuts.add(m.end())
    cuts.update(o for o in extra if 0 <= o <= len(text))
    return sorted(cuts)


def split_offsets(text: str, extra_boundaries: Iterable[int] = ()) -> list[tuple[int, int]]:
    """(start, end) of each non-blank sentence, trimmed of surrounding whitespace."""
    cuts = _boundaries(text, extra_boundaries)
    out = []
    for a, b in zip(cuts, cuts[1:], strict=False):
        seg = text[a:b]
        if not seg.strip():
            continue
        lead = len(seg) - len(seg.lstrip())
        trail = len(seg) - len(seg.rstrip())
        out.append((a + lead, b - trail))
    return out


def split_sentences(
    text: str,
    doc_id: str,
    extra_boundaries: Iterable[int] = (),
    provenance=None,  # layer1.provenance.ProvenanceMap | None
) -> list[Sentence]:
    offsets = split_offsets(text, extra_boundaries)
    ids = [f"{doc_id[:12]}-s{i}" for i in range(1, len(offsets) + 1)]
    sentences = []
    for i, (a, b) in enumerate(offsets):
        neighbors = [ids[j] for j in (i - 1, i + 1) if 0 <= j < len(ids)]
        span_ids = provenance.source_span_ids(a, b) if provenance is not None else []
        sentences.append(Sentence(ids[i], (a, b), span_ids, neighbors, text=text[a:b]))
    return sentences
