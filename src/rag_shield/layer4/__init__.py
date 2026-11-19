"""Layer 4: output validation (canary leak, exfiltration stripping, grounding)."""

from __future__ import annotations

from typing import Any

from rag_shield.layer4 import canary as _canary
from rag_shield.layer4.exfil import strip_exfil
from rag_shield.layer4.grounding import check_grounding
from rag_shield.models import OutputCheck


def validate_output(
    answer: str,
    chunk_ids: list[str],
    canary: str = "",
    allowed_domains: list[str] | None = None,
    require_citations: bool = True,
) -> OutputCheck:
    leak = _canary.leaked(answer, canary)
    clean, stripped = strip_exfil(answer, allowed_domains)
    clean = _canary.redact(clean, canary)
    ungrounded: list[Any] = check_grounding(clean, chunk_ids) if require_citations else []
    return OutputCheck(canary_leak=leak, stripped=stripped, ungrounded=ungrounded,
                       clean_answer=clean)
