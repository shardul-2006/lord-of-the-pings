"""rag-shield command line. Subcommands are added phase by phase."""

from __future__ import annotations

import argparse
import json
import sys


def _cmd_compare(args: argparse.Namespace) -> int:
    from rag_shield.rag.compare import compare
    from rag_shield.rag.llm import get_llm

    traces = compare(
        args.pdf, get_llm(args.llm), defense=args.defense, question=args.question,
        out_dir=args.out_dir,
    )
    result = {name: t.to_dict() for name, t in traces.items()}
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for name, t in traces.items():
            print(f"[{name}] defense={t.defense} chunks={t.retrieved_chunk_ids}")
            print(f"  output: {t.output}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    from rag_shield.rag.compare import DEFENSES
    from rag_shield.rag.pipeline import DEFAULT_QUESTION

    parser = argparse.ArgumentParser(prog="rag-shield", description=__doc__)
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    p = sub.add_parser("compare", help="run vulnerable vs defended branches on one PDF")
    p.add_argument("pdf")
    p.add_argument("--llm", choices=["mock", "real"], default="mock")
    p.add_argument("--defense", choices=DEFENSES, default="simple")
    p.add_argument("--question", default=DEFAULT_QUESTION)
    p.add_argument("--json", action="store_true")
    p.add_argument("--out-dir", default=None, help="also save each trace as JSON here")
    p.set_defaults(func=_cmd_compare)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
