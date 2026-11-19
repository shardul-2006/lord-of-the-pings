"""Dataset Gate batch screening. Phase 0 stub."""

from __future__ import annotations

from pathlib import Path

from rag_shield._stub import stub_reason
from rag_shield.models import DatasetReport


def screen_dataset(path: str | Path, out_dir: str | Path) -> DatasetReport:
    return DatasetReport(
        total=0, screened=0, quarantined=0, report_path=stub_reason("screen_dataset")
    )
