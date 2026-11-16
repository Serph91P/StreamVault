"""Block new/rewrite coverage below 85% and repository regressions (#842)."""

import argparse
from fractions import Fraction
import json
from pathlib import Path


def counts(summary: dict[str, int]) -> tuple[int, int]:
    return (
        summary["covered_lines"] + summary["covered_branches"],
        summary["num_statements"] + summary["num_branches"],
    )


def ratio(summary: dict[str, int]) -> Fraction:
    covered, total = counts(summary)
    return Fraction(covered, total) if total else Fraction(1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coverage", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    args = parser.parse_args()
    final = json.loads(args.coverage.read_text())
    baseline = json.loads(args.baseline.read_text())
    inventory = json.loads(args.inventory.read_text())
    failed = False
    for module in inventory["modules"]:
        item = final["files"].get(module)
        if item is None:
            print(f"FAIL {module}: missing coverage")
            failed = True
            continue
        summary = item["summary"]
        covered, total = counts(summary)
        passed = ratio(summary) >= Fraction(85, 100)
        print(
            f"{'PASS' if passed else 'FAIL'} {module}: {covered}/{total} statement+branch outcomes; required >=85%"
        )
        failed |= not passed
    before, after = ratio(baseline["totals"]), ratio(final["totals"])
    passed = after >= before
    print(
        f"{'PASS' if passed else 'FAIL'} repository {counts(final['totals'])} vs base {counts(baseline['totals'])}; {'non-decreasing' if passed else 'repository regressed'}"
    )
    return int(failed or not passed)


if __name__ == "__main__":
    raise SystemExit(main())
