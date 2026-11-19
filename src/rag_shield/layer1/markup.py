"""Static Markdown / HTML parsing with exact raw offsets. Never fetches any resource.

Markdown: the extracted text is the raw file, one span per line; hidden comments and image
alt-text become signals located by raw offsets.
HTML: text nodes, comments, alt-text and <meta> content become spans; entity references map
one-to-many back to their raw characters. <script>/<style> content is not extracted.
"""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from typing import Any

from rag_shield.layer1.provenance import ExtractedText
from rag_shield.models import Signal, SourceSpan

_MD_COMMENT = re.compile(r"<!--(.*?)-->", re.DOTALL)
_MD_REF_COMMENT = re.compile(r"^\[//\]:\s*#\s*[(\"'](.*)[)\"']\s*$", re.MULTILINE)
_MD_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)\s]*)")


def _trim(text: str, raw: list[tuple[int, int]]) -> tuple[str, list[tuple[int, int]]]:
    lead = len(text) - len(text.lstrip())
    tail = len(text.rstrip())
    return text[lead:tail], raw[lead:tail]


def parse_markdown(raw: str, doc_id: str, ex: ExtractedText) -> list[Signal]:
    pos = 0
    for line in raw.splitlines(keepends=True):
        content = line.rstrip("\r\n")
        if content.strip():
            span = SourceSpan(
                span_id=f"{doc_id[:12]}-o{pos}",
                doc_id=doc_id,
                page=None,
                source_offsets=(pos, pos + len(content)),
                bboxes=[],
                original_text=content,
            )
            ex.add_separator("\n")
            ex.add_span(span, content)
        pos += len(line)

    signals: list[Signal] = []
    for m in _MD_COMMENT.finditer(raw):
        signals.append(_raw_signal("hidden_comment", m.start(1), m.end(1), raw))
    for m in _MD_REF_COMMENT.finditer(raw):
        signals.append(_raw_signal("hidden_comment", m.start(1), m.end(1), raw))
    for m in _MD_IMAGE.finditer(raw):
        if m.group(1).strip():
            sig = _raw_signal("alt_text", m.start(1), m.end(1), raw)
            sig.detail["url"] = m.group(2)  # recorded, never fetched
            signals.append(sig)
    return signals


def _raw_signal(kind: str, start: int, end: int, raw: str) -> Signal:
    return Signal(kind, detail={"raw_offsets": [start, end], "text": raw[start:end].strip()})


_BLOCK = frozenset(
    "address article aside blockquote br dd div dl dt figcaption figure footer form h1 h2 h3 h4 "
    "h5 h6 header hr li main nav ol p pre section table td th tr ul title".split()
)
_VOID = frozenset("area base br col embed hr img input link meta param source track wbr".split())
_SKIP = frozenset(("script", "style", "noscript", "template"))
_HIDDEN_STYLE = ("display:none", "visibility:hidden", "font-size:0")


def _is_hidden(attrs: dict[str, str | None]) -> bool:
    style = (attrs.get("style") or "").replace(" ", "").lower()
    return "hidden" in attrs or any(h in style for h in _HIDDEN_STYLE)


class _HtmlExtractor(HTMLParser):
    def __init__(self, raw: str, doc_id: str, ex: ExtractedText) -> None:
        super().__init__(convert_charrefs=False)
        self.raw, self.doc_id, self.ex = raw, doc_id, ex
        self.line_starts = [0] + [i + 1 for i, c in enumerate(raw) if c == "\n"]
        self.text: list[str] = []
        self.char_raw: list[tuple[int, int]] = []
        self.stack: list[tuple[str, bool]] = []
        self.skip = 0
        self.pending_sep = ""
        self.signals: list[Signal] = []

    def _pos(self) -> int:
        line, col = self.getpos()
        return self.line_starts[line - 1] + col

    def _hidden(self) -> bool:
        return any(h for _, h in self.stack)

    def _emit(
        self, text: str, raw: list[tuple[int, int]], kind: str | None, sep: str = "\n",
        **detail: Any,
    ) -> None:
        text, raw = _trim(text, raw)
        if not text:
            return
        self.ex.add_separator(sep)
        span = SourceSpan(
            span_id=f"{self.doc_id[:12]}-o{raw[0][0]}",
            doc_id=self.doc_id,
            page=None,
            source_offsets=(raw[0][0], raw[-1][1]),
            bboxes=[],
            original_text=self.raw[raw[0][0]:raw[-1][1]],
        )
        self.ex.add_span(span, text, char_raw=raw)
        if kind:
            self.signals.append(Signal(kind, source_span_ids=[span.span_id], detail=detail))

    def flush(self, next_sep: str) -> None:
        if self.text:
            kind = "hidden_element" if self._hidden() else None
            self._emit("".join(self.text), self.char_raw, kind, sep=self.pending_sep or "\n")
            self.text, self.char_raw = [], []
            self.pending_sep = ""
        if next_sep == "\n" or not self.pending_sep:
            self.pending_sep = next_sep

    # --- text -----------------------------------------------------------------------------
    def handle_data(self, data: str) -> None:
        if self.skip:
            return
        p = self._pos()
        self.text.extend(data)
        self.char_raw.extend((p + k, p + k + 1) for k in range(len(data)))

    def _ref(self, prefix: str, name: str) -> None:
        if self.skip:
            return
        p = self._pos()
        end = p + len(prefix) + len(name)
        if self.raw[end:end + 1] == ";":
            end += 1
        decoded = html.unescape(self.raw[p:end])
        self.text.extend(decoded)
        self.char_raw.extend([(p, end)] * len(decoded))

    def handle_entityref(self, name: str) -> None:
        self._ref("&", name)

    def handle_charref(self, name: str) -> None:
        self._ref("&#", name)

    # --- structure ------------------------------------------------------------------------
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.flush("\n" if tag in _BLOCK else " ")
        a = dict(attrs)
        if tag == "img" and (a.get("alt") or "").strip():
            self._attr_span("alt", a["alt"] or "", "alt_text", url=a.get("src"))
        if tag == "meta" and (a.get("content") or "").strip():
            self._attr_span("content", a["content"] or "", "metadata",
                            field=a.get("name") or a.get("property") or "")
        if tag in _SKIP:
            self.skip += 1
        if tag not in _VOID:
            self.stack.append((tag, _is_hidden(a)))

    def handle_endtag(self, tag: str) -> None:
        self.flush("\n" if tag in _BLOCK else " ")
        if tag in _SKIP and self.skip:
            self.skip -= 1
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

    def handle_comment(self, data: str) -> None:
        self.flush("\n")
        p = self._pos() + 4  # skip "<!--"
        self._emit(data, [(p + k, p + k + 1) for k in range(len(data))], "hidden_comment")

    def _attr_span(self, name: str, value: str, kind: str, **detail: Any) -> None:
        p = self._pos()
        tag_text = self.get_starttag_text() or ""
        m = re.search(rf"\b{name}\s*=\s*([\"']?)", tag_text, re.IGNORECASE)
        if m is None:
            return
        start = p + m.end()
        quote = m.group(1)
        stop = self.raw.find(quote, start) if quote else start + len(value)
        raw_val = self.raw[start:stop]
        if raw_val == value:
            raw = [(start + k, start + k + 1) for k in range(len(value))]
        else:  # entities inside the attribute: map every char to the whole value
            raw = [(start, stop)] * len(value)
        self._emit(value, raw, kind, **detail)


def parse_html(raw: str, doc_id: str, ex: ExtractedText) -> list[Signal]:
    parser = _HtmlExtractor(raw, doc_id, ex)
    parser.feed(raw)
    parser.close()
    parser.flush("\n")
    return parser.signals
