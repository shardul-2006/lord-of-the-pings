"""Every CLI subcommand shown in the README exists."""

import argparse
import re
from pathlib import Path

from rag_shield.cli import build_parser

README = (Path(__file__).resolve().parents[2] / "README.md").read_text(encoding="utf-8")


def _subcommands(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return dict(action.choices)
    return {}


def test_readme_cli_commands_exist():
    top = _subcommands(build_parser())
    shown = re.findall(r"rag_shield\.cli\s+([a-z][a-z-]*)(?:\s+([a-z][a-z-]*))?", README)
    assert len(shown) >= 8
    for cmd, sub in shown:
        assert cmd in top, f"README shows unknown command {cmd!r}"
        nested = _subcommands(top[cmd])
        if nested and sub:
            assert sub in nested, f"README shows unknown command {cmd} {sub!r}"


def test_readme_api_routes_exist(tmp_path):
    from app.api import create_app

    app = create_app(home=tmp_path)
    try:
        paths = {r.path for r in app.routes}
        for route in re.findall(r"`(?:GET|POST) (/[^`]*)`", README):
            assert route in paths, route
    finally:
        app.state.shield.close()


def test_readme_scripts_exist():
    root = Path(__file__).resolve().parents[2]
    for script in set(re.findall(r"(scripts/[\w./-]+\.(?:py|sh))", README)):
        assert (root / script).exists(), script
