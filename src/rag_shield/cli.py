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


def _cmd_ingest(args: argparse.Namespace) -> int:
    from rag_shield.layer1.ingest import ingest

    result = ingest(args.file)
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(f"status: {result.status.value}  ({result.reason})")
        for s in result.signals:
            print(f"  signal {s.type} page={s.page} bbox={s.bbox}")
        print(f"  removals: {len(result.removals)}  canonical chars: {len(result.canonical_text)}")
    # Exit 0: blocking is expressed by the status, not the exit code.
    return 0


def _cmd_screen(args: argparse.Namespace) -> int:
    from rag_shield.layer1.ingest import ingest
    from rag_shield.layer2 import screen, screen_report
    from rag_shield.layer2.guard import make_guard
    from rag_shield.policy import load_policy

    policy = load_policy(args.policy) if args.policy else load_policy()
    guard = make_guard(args.guard or policy["guard"]["kind"])
    result = screen(ingest(args.file), policy, guard=guard)
    report = screen_report(result)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"status: {report['status']}  ({report['reason']})")
        for q in report["quarantined"] + report["review_required"]:
            print(f"  [{q['status']}] {q['score']} {q['signals']} {q['text'][:80]}")
    return 0


def _shield(args: argparse.Namespace):
    from rag_shield.shield import Shield

    return Shield(db_path=args.db) if args.db else Shield()


def _cmd_shield_run(args: argparse.Namespace) -> int:
    shield = _shield(args)
    try:
        result = shield.ingest(args.file)
    finally:
        shield.close()
    d = result.to_dict()
    if args.json:
        print(json.dumps(d, indent=2))
    else:
        print(f"status: {d['status']}  indexed: {d['indexed']}  index_version: "
              f"{d['index_version']}  doc_id: {d['doc_id']}")
        for a in d["alerts"]:
            print(f"  [{a['status']}] {a['sentence_id']} {a['signals']} {a['text'][:70]}")
    return 0


def _cmd_review(args: argparse.Namespace) -> int:
    shield = _shield(args)
    try:
        if args.action == "list":
            out: dict = {"items": shield.review_items()}
        else:
            out = shield.release(args.sentence_id, args.reviewer)
    finally:
        shield.close()
    if args.json:
        print(json.dumps(out, indent=2))
    elif args.action == "list":
        for it in out["items"]:
            print(f"[{it['status']}] {it['sentence_id']} score={it['score']} {it['text'][:70]}")
    else:
        print(f"released: {out['released']}  index_version: {out['index_version']}"
              + (f"  ({out['reason']})" if out.get("reason") else ""))
    return 0 if args.action == "list" or out["released"] else 1


def _cmd_overlay(args: argparse.Namespace) -> int:
    from pathlib import Path

    from rag_shield.rag.pipeline import sha256_file

    shield = _shield(args)
    try:
        doc = shield.ledger.find_document_by_sha(sha256_file(args.file))
        if doc is None:
            print(f"error: {args.file} is not in the ledger; run shield-run first",
                  file=sys.stderr)
            return 2
        png = shield.overlay(doc["doc_id"], args.page, source=args.file)
    finally:
        shield.close()
    Path(args.out).write_bytes(png)
    print(f"wrote {args.out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    from rag_shield.rag.compare import DEFENSES
    from rag_shield.rag.pipeline import DEFAULT_QUESTION

    parser = argparse.ArgumentParser(prog="rag-shield", description=__doc__)
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    p = sub.add_parser("compare", help="run vulnerable vs defended branches on one PDF")
    p.add_argument("pdf")
    p.add_argument("--llm", choices=["mock", "real"], default="mock")
    p.add_argument("--defense", choices=DEFENSES, default="shield")
    p.add_argument("--question", default=DEFAULT_QUESTION)
    p.add_argument("--json", action="store_true")
    p.add_argument("--out-dir", default=None, help="also save each trace as JSON here")
    p.set_defaults(func=_cmd_compare)

    p = sub.add_parser("ingest", help="Layer 1: guard, canonicalize, detect hiding signals")
    p.add_argument("file")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_ingest)

    p = sub.add_parser("screen", help="Layers 1+2: score sentences and quarantine risky ones")
    p.add_argument("file")
    p.add_argument("--json", action="store_true")
    p.add_argument("--policy", default=None, help="policy YAML (default: policy_v1)")
    p.add_argument("--guard", choices=["rule", "deberta"], default=None)
    p.set_defaults(func=_cmd_screen)

    db_help = "ledger SQLite file (default: $RAG_SHIELD_HOME/ledger.db)"
    p = sub.add_parser("shield-run", help="full pipeline: screen, record in ledger, index")
    p.add_argument("file")
    p.add_argument("--db", default=None, help=db_help)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_shield_run)

    p = sub.add_parser("review", help="review queue: list withheld sentences or release one")
    rsub = p.add_subparsers(dest="action", required=True)
    r = rsub.add_parser("list")
    r.add_argument("--db", default=None, help=db_help)
    r.add_argument("--json", action="store_true")
    r.set_defaults(func=_cmd_review)
    r = rsub.add_parser("release")
    r.add_argument("sentence_id")
    r.add_argument("--reviewer", required=True)
    r.add_argument("--db", default=None, help=db_help)
    r.add_argument("--json", action="store_true")
    r.set_defaults(func=_cmd_review)

    p = sub.add_parser("overlay", help="render the evidence overlay of a PDF page to PNG")
    p.add_argument("file")
    p.add_argument("--page", type=int, default=1)
    p.add_argument("--db", default=None, help=db_help)
    p.add_argument("--out", required=True)
    p.set_defaults(func=_cmd_overlay)
    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
