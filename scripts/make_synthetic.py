"""Generate synthetic datasets.

--seed-only: write the labelled classifier seed set to data/train/seed.jsonl (Phase 3).
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from rag_shield.layer2 import seed_data

REPO_ROOT = Path(__file__).resolve().parent.parent


def write_seed(out: Path, seed: int) -> Path:
    rows = seed_data.generate(seed)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    counts = Counter((r["split"], r["label"]) for r in rows)
    print(f"wrote {len(rows)} rows to {out} ({dict(sorted(counts.items()))})")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--seed-only", action="store_true", help="only the classifier seed set")
    parser.add_argument("--out", default=str(REPO_ROOT / "data" / "train" / "seed.jsonl"))
    args = parser.parse_args(argv)
    write_seed(Path(args.out), args.seed)
    if not args.seed_only:
        print("resume / dataset generation arrives in Phase 7")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
