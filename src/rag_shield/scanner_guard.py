"""Scanner guard (Spec F): checks a file before any parser touches it. Fails closed.

- extension AND magic-byte / content check
- size, page and time limits (configurable)
- controlled temp dir with a safe filename, always cleaned up
- no outbound fetching anywhere in parsing (parsers are static)
Every failure maps to `unsupported` (we will not scan this) or `scan_failed` (we tried and
could not). Neither is ever `clean`.

Limitation: the time limit runs the work in a thread and abandons it on timeout; Python cannot
kill the thread, so CPU/memory are not hard-limited.
"""

from __future__ import annotations

import concurrent.futures
import os
import shutil
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from rag_shield.models import GUARD_OK, GuardResult, ScanStatus

T = TypeVar("T")

MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".html": "text/html",
    ".htm": "text/html",
}
TEMP_PREFIX = "rag_shield_"
UNSUPPORTED = ScanStatus.UNSUPPORTED.value
SCAN_FAILED = ScanStatus.SCAN_FAILED.value


@dataclass
class GuardConfig:
    max_bytes: int = 20 * 1024 * 1024
    max_pages: int = 50
    timeout_s: float = 30.0
    temp_root: str | None = None  # None -> system temp dir

    @classmethod
    def from_env(cls) -> GuardConfig:
        """Defaults, overridable by RAG_SHIELD_MAX_BYTES / _MAX_PAGES / _SCAN_TIMEOUT."""
        c = cls()
        if v := os.environ.get("RAG_SHIELD_MAX_BYTES"):
            c.max_bytes = int(v)
        if v := os.environ.get("RAG_SHIELD_MAX_PAGES"):
            c.max_pages = int(v)
        if v := os.environ.get("RAG_SHIELD_SCAN_TIMEOUT"):
            c.timeout_s = float(v)
        return c


class ScanTimeout(Exception):
    pass


def run_with_timeout(fn: Callable[[], T], timeout_s: float) -> T:
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="rag_shield")
    future = pool.submit(fn)
    try:
        return future.result(timeout=timeout_s)
    except concurrent.futures.TimeoutError as e:
        raise ScanTimeout(f"scan exceeded {timeout_s}s") from e
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def media_type_for(path: str | Path) -> str | None:
    return MEDIA_TYPES.get(Path(path).suffix.lower())


def _check_pdf(path: Path, config: GuardConfig) -> GuardResult:
    from pypdf import PdfReader

    def probe() -> GuardResult:
        reader = PdfReader(str(path), strict=False)
        if reader.is_encrypted:
            return GuardResult(UNSUPPORTED, "encrypted PDF", "application/pdf")
        n = len(reader.pages)
        if n == 0:
            return GuardResult(UNSUPPORTED, "PDF has no pages", "application/pdf")
        if n > config.max_pages:
            return GuardResult(
                UNSUPPORTED, f"too many pages ({n} > {config.max_pages})", "application/pdf"
            )
        return GuardResult(GUARD_OK, f"pdf ok ({n} pages)", "application/pdf")

    try:
        return run_with_timeout(probe, config.timeout_s)
    except ScanTimeout as e:
        return GuardResult(SCAN_FAILED, f"timeout: {e}", "application/pdf")
    except Exception as e:  # malformed PDF
        return GuardResult(SCAN_FAILED, f"pdf parse error: {type(e).__name__}", "application/pdf")


def check_file(path: str | Path, config: GuardConfig | None = None) -> GuardResult:
    config = config or GuardConfig.from_env()
    path = Path(path)
    media = media_type_for(path)
    if not path.is_file():
        return GuardResult(SCAN_FAILED, "file not found or not a regular file", media)
    if media is None:
        return GuardResult(UNSUPPORTED, f"unsupported extension {path.suffix!r}", None)
    size = path.stat().st_size
    if size == 0:
        return GuardResult(UNSUPPORTED, "empty file", media)
    if size > config.max_bytes:
        return GuardResult(UNSUPPORTED, f"oversize ({size} > {config.max_bytes} bytes)", media)

    try:
        head = path.read_bytes()[:1024] if media == "application/pdf" else path.read_bytes()
    except OSError as e:
        return GuardResult(SCAN_FAILED, f"read error: {type(e).__name__}", media)

    if media == "application/pdf":
        if b"%PDF-" not in head:
            return GuardResult(UNSUPPORTED, "magic bytes do not match PDF", media)
        return _check_pdf(path, config)

    if b"\x00" in head:
        return GuardResult(UNSUPPORTED, "binary content in a text format", media)
    try:
        head.decode("utf-8-sig")
    except UnicodeDecodeError:
        return GuardResult(SCAN_FAILED, "bad encoding: not valid UTF-8", media)
    return GuardResult(GUARD_OK, "text ok", media)


@contextmanager
def guarded_copy(path: str | Path, config: GuardConfig | None = None) -> Iterator[Path]:
    """Copy the input into a private temp dir under a safe name; always remove the dir."""
    config = config or GuardConfig.from_env()
    src = Path(path)
    tmp = Path(tempfile.mkdtemp(prefix=TEMP_PREFIX, dir=config.temp_root))
    try:
        safe = tmp / f"input{src.suffix.lower()}"
        shutil.copyfile(src, safe)
        yield safe
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
