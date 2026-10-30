"""Run the whole pipeline (or selected stages) and print timings.

    python -m leadintel.run                 # all stages
    python -m leadintel.run --only crawl    # one stage
    python -m leadintel.run --from detect   # this stage and everything after it
    python -m leadintel.run --refresh       # crawl ignores the HTML cache
"""

from __future__ import annotations

import argparse
import sys
import time

from leadintel import clean, crawl, detect, export, ingest, score
from leadintel.db import get_conn

STAGES = [
    ("ingest", ingest.run),
    ("clean", clean.run),
    ("crawl", crawl.run),
    ("detect", detect.run),
    ("score", score.run),
    ("export", export.run),
]
STAGE_NAMES = [name for name, _ in STAGES]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="leadintel.run")
    p.add_argument("--only", choices=STAGE_NAMES, action="append")
    p.add_argument("--from", dest="start", choices=STAGE_NAMES)
    p.add_argument("--refresh", action="store_true", help="re-fetch cached pages")
    p.add_argument("--limit", type=int, default=None, help="crawl only the first N domains")
    p.add_argument("--skip-network", action="store_true", help="skip reachability/crawl fetches")
    args = p.parse_args(argv)

    selected = STAGES
    if args.only:
        selected = [s for s in STAGES if s[0] in args.only]
    elif args.start:
        selected = STAGES[STAGE_NAMES.index(args.start) :]

    opts = {"refresh": args.refresh, "limit": args.limit, "skip_network": args.skip_network}
    total = time.perf_counter()
    with get_conn() as conn:
        for name, fn in selected:
            t0 = time.perf_counter()
            summary = fn(conn, **opts)
            print(f"[{name:<7}] {time.perf_counter() - t0:6.2f}s  {summary}", flush=True)
    print(f"[done   ] {time.perf_counter() - total:6.2f}s total")
    return 0


if __name__ == "__main__":
    sys.exit(main())
