"""Linguistic cues of instructions aimed at the AI rather than facts about the document.

Each cue has a weight; the score is a noisy-OR of matched cue weights, in [0, 1].
Bare trigger words ("override", "ignore", "instructions") are NOT cues on their own.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

VERSION = "ling-v1"

_AI = r"(?:ai|a\.i\.|assistant|chatbot|language model|llm|model|screener|reviewer bot|bot)"
_PRIOR = r"(?:all |any |the |your |my )*(?:previous|prior|above|earlier|preceding|original|other)"
_RULES = r"(?:instructions?|prompts?|rules|guidelines|directions|context|content|criteria)"

CUES: list[tuple[str, float, str]] = [
    ("ignore_previous", 0.90, rf"\b(?:ignore|disregard|forget|skip|bypass)\b[^.]{{0,20}}\b{_PRIOR}\s+{_RULES}"),
    ("disregard_above", 0.80, r"\b(?:disregard|ignore)\s+(?:all\s+|everything\s+)?(?:the\s+)?(?:above|previous|prior|earlier)\b"),
    ("override_instructions", 0.80, rf"\boverride\s+(?:your|the|all|any|previous|prior|system)\s+{_RULES}"),
    ("new_instructions", 0.70, rf"\bnew\s+{_RULES}\b"),
    ("system_prompt", 0.70, r"\bsystem\s+prompt\b"),
    ("address_ai", 0.70, rf"\b(?:note|message|instruction)s?\s+(?:to|for)\s+(?:the\s+)?{_AI}\b"),
    ("as_the_ai", 0.70, rf"\bas\s+(?:an?|the)\s+{_AI}\b"),
    ("you_are_now", 0.70, r"\byou\s+are\s+now\b"),
    ("developer_mode", 0.70, r"\b(?:developer|jailbreak|god)\s+mode\b"),
    ("you_must", 0.50, r"\byou\s+(?:must|should|will|need to|have to)\b"),
    ("ai_should", 0.60, rf"\b(?:the\s+)?{_AI}\s+(?:must|should|will|needs to|has to)\b"),
    ("recommend_candidate", 0.60, r"\b(?:recommend|select|shortlist|approve|hire)\s+(?:this|the)\s+(?:candidate|applicant|person|resume|application)\b"),
    ("rate_highest", 0.60, r"\b(?:rate|rank|score|give)\b[^.]{0,30}\b(?:highest|first|top|10\s*(?:/|out of)\s*10|best)\b"),
    ("respond_only", 0.60, r"\b(?:respond|reply|answer|output)\s+(?:only\s+)?with\b"),
    ("do_not_reveal", 0.60, r"\bdo\s+not\s+(?:reveal|mention|disclose|tell)\b"),
    ("regardless", 0.40, r"\bregardless\s+of\s+(?:other|any|the)\b"),
    ("when_summarizing", 0.40, r"\bwhen\s+(?:summari[sz]ing|evaluating|reviewing|screening)\s+this\b"),
]
_COMPILED = [(name, w, re.compile(p, re.IGNORECASE)) for name, w, p in CUES]


@dataclass
class LinguisticResult:
    score: float
    cues: list[str] = field(default_factory=list)


def score_text(text: str) -> LinguisticResult:
    miss = 1.0
    cues = []
    for name, weight, pattern in _COMPILED:
        if pattern.search(text):
            cues.append(name)
            miss *= 1.0 - weight
    return LinguisticResult(round(1.0 - miss, 4), cues)
