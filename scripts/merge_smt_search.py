#!/usr/bin/env python3
"""Merge a complete collection of fixed-height SMT search shards."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--shards", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    options = parser.parse_args()

    reports = []
    for path in options.input.rglob("result.json"):
        reports.append(json.loads(path.read_text(encoding="utf-8")))
    by_shard = {report["shard"]: report for report in reports}
    missing = sorted(set(range(options.shards)) - set(by_shard))
    if missing:
        raise SystemExit(f"missing result shards: {missing}")
    if len(reports) != options.shards:
        raise SystemExit("duplicate or unexpected result reports")

    statuses = {"sat": 0, "unsat": 0, "unknown": 0}
    for report in reports:
        status = report["status"]
        if status not in statuses:
            raise SystemExit(f"unexpected solver status: {status}")
        statuses[status] += 1
    metadata = {(r["height"], r["colors"], r["empty_columns"], r["shards"])
                for r in reports}
    if len(metadata) != 1:
        raise SystemExit("shard metadata mismatch")
    height, colors, empty, shards = metadata.pop()
    if shards != options.shards:
        raise SystemExit("declared shard count mismatch")

    if statuses["sat"]:
        conclusion = "SAT candidate found; require independent oracle certificate"
    elif statuses["unknown"]:
        conclusion = "inconclusive because at least one exact shard timed out"
    else:
        conclusion = "all finite-height shards UNSAT (no emitted solver proof)"

    merged = {
        "height": height,
        "colors": colors,
        "empty_columns": empty,
        "shards": options.shards,
        "statuses": statuses,
        "conclusion": conclusion,
        "build_seconds_sum": round(sum(r["build_seconds"] for r in reports), 3),
        "solve_seconds_sum": round(sum(r["solve_seconds"] for r in reports), 3),
        "scope": "complete fixed-height symmetry-reduced covering",
        "caveat": "UNSAT shards have no solver proof and do not imply arbitrary-height solvability",
    }
    options.out.mkdir(parents=True, exist_ok=True)
    (options.out / "summary.json").write_text(
        json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    summary = (
        "# Fixed-height SMT counterexample search\n\n"
        f"- Parameters: c={colors}, h={height}, k={empty}\n"
        f"- Shards: {options.shards}\n"
        f"- SAT: {statuses['sat']}\n"
        f"- UNSAT: {statuses['unsat']}\n"
        f"- Unknown: {statuses['unknown']}\n"
        f"- Conclusion: **{conclusion}**\n\n"
        "Each shard jointly chooses every item color and evaluates the exact "
        "top-border DAG. A SAT candidate still requires the independent C++ "
        "certificate verifier. Complete UNSAT is a fixed-height computation "
        "without a solver proof object, not an arbitrary-height theorem.\n"
    )
    (options.out / "summary.md").write_text(summary, encoding="utf-8")
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
