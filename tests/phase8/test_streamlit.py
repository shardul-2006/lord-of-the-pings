from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[2] / "app" / "streamlit_app.py")
BADGE_LABELS = ("clean", "flagged", "review_required", "unsupported", "scan_failed")


def _text(at) -> str:
    parts = [m.value for m in at.markdown] + [c.value for c in at.caption]
    parts += [m.value for m in at.sidebar.markdown]
    return "\n".join(parts)


def test_app_runs_and_shows_all_badges(fixtures_dir):
    at = AppTest.from_file(APP).run(timeout=60)
    assert not at.exception
    text = _text(at)
    for label in BADGE_LABELS:
        assert f"<code>{label}</code>" in text, label
    assert "BLOCKED" in text  # blocked statuses never look like clean


def test_try_sample_flow(fixtures_dir):
    at = AppTest.from_file(APP).run(timeout=60)
    at.button(key="try_sample").click().run(timeout=60)
    assert not at.exception
    assert "SECURITY ALERT" in _text(at)
    at.button(key="compare").click().run(timeout=60)
    assert not at.exception
    assert [s.value for s in at.subheader][:2] == ["Vulnerable pipeline", "Defended pipeline"]


@pytest.mark.parametrize("sample", ["Encrypted PDF (blocked)", "Text file named .pdf (blocked)"])
def test_blocked_sample_shows_blocked(fixtures_dir, sample):
    at = AppTest.from_file(APP).run(timeout=60)
    at.selectbox(key="sample").select(sample).run(timeout=60)
    at.button(key="try_sample").click().run(timeout=60)
    assert not at.exception
    assert any("Blocked from defended retrieval" in w.value for w in at.warning)
