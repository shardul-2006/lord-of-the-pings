"""Remove exfiltration channels from model output: Markdown/HTML image beacons, links and bare
URLs whose host is not on the allow-list. Link text is kept; only the target is dropped.

Syntactic filtering only: it does not stop semantic covert channels.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

_MD_IMAGE = re.compile(r"!\[([^\]]*)\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
_MD_LINK = re.compile(r"(?<!!)\[([^\]]*)\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
_HTML_IMG = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
_HTML_SRC = re.compile(r"""src\s*=\s*["']?([^"'\s>]+)""", re.IGNORECASE)
_BARE_URL = re.compile(r"(?<![(\[<\"'])\bhttps?://[^\s)<>\]]+", re.IGNORECASE)


def allowed(url: str, allow: list[str]) -> bool:
    host = (urlparse(url).hostname or "").lower()
    if not host:
        return True  # relative link: not an outbound channel
    return any(host == d.lower() or host.endswith("." + d.lower()) for d in allow)


def strip_exfil(answer: str, allow: list[str] | None = None) -> tuple[str, list[str]]:
    """Return (clean_answer, stripped_items)."""
    allow = allow or []
    stripped: list[str] = []

    def image(m: re.Match) -> str:
        if allowed(m.group(2), allow):
            return m.group(0)
        stripped.append(f"image:{m.group(2)}")
        return ""

    def link(m: re.Match) -> str:
        if allowed(m.group(2), allow):
            return m.group(0)
        stripped.append(f"link:{m.group(2)}")
        return m.group(1)

    def html_img(m: re.Match) -> str:
        src = _HTML_SRC.search(m.group(0))
        url = src.group(1) if src else ""
        if url and allowed(url, allow):
            return m.group(0)
        stripped.append(f"image:{url}")
        return ""

    def bare(m: re.Match) -> str:
        if allowed(m.group(0), allow):
            return m.group(0)
        stripped.append(f"url:{m.group(0)}")
        return "[link removed]"

    out = _MD_IMAGE.sub(image, answer)
    out = _HTML_IMG.sub(html_img, out)
    out = _MD_LINK.sub(link, out)
    out = _BARE_URL.sub(bare, out)
    out = re.sub(r"[ \t]+\n", "\n", out)
    out = re.sub(r"\n{3,}", "\n\n", out).strip()
    return out, stripped
