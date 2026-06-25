"""CLI / GitHub Action entry point: ``claimcheck --prose X --data Y``.

Exits 1 when an error-level finding is present (a fabricated quote or a stale
date), or — with ``--strict`` — when any advisory warning (an unsupported
figure) is present. Designed to be a CI gate on AI-written prose.
"""

from __future__ import annotations

import argparse
import json
import sys

from .grounding import check, has_errors


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="claimcheck",
        description="Block prose that asserts a number, quote, or date its source data lacks.",
    )
    p.add_argument("--prose", required=True, help="path to the prose/summary file")
    p.add_argument("--data", required=True, help="path to the JSON evidence file")
    p.add_argument("--window", default="", help="optional FROM,TO ISO date window")
    p.add_argument("--strict", action="store_true", help="fail on advisory warnings too")
    p.add_argument("--quotes", action="store_true", help="data carries quote evidence")
    a = p.parse_args(argv)

    with open(a.prose, encoding="utf-8") as fh:
        prose = fh.read()
    with open(a.data, encoding="utf-8") as fh:
        data = json.load(fh)

    window = None
    if a.window:
        parts = a.window.split(",")
        if len(parts) != 2:
            p.error("--window must be FROM,TO (two ISO dates)")
        window = (parts[0].strip(), parts[1].strip())

    findings = check(prose, data, window=window, has_quotes=a.quotes)
    for f in findings:
        print(f"[{f['level']}] {f['rule']}: {f['term']}", file=sys.stderr)

    if has_errors(findings) or (a.strict and findings):
        print(f"claimcheck: BLOCKED ({len(findings)} finding(s))", file=sys.stderr)
        return 1
    print(f"claimcheck: OK ({len(findings)} advisory finding(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
