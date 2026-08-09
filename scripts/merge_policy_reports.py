#!/usr/bin/env python3
"""Merge water-policy-learn shard outputs for one observation depth."""

import argparse
import json
from pathlib import Path


def parse_mask(value: str) -> int:
    return int(value, 16)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--depth", required=True, type=int)
    parser.add_argument("--expected-shards", required=True, type=int)
    args = parser.parse_args()

    reports = []
    signatures = {}
    for report_path in sorted(args.input.rglob("report.json")):
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report["visible_boundaries"] != args.depth:
            continue
        reports.append(report)
        table = report_path.with_name("signatures.tsv")
        with table.open(encoding="utf-8") as source:
            next(source)
            for line in source:
                _, occurrences, common, observed, signature = line.rstrip("\n").split("\t", 4)
                if signature not in signatures:
                    signatures[signature] = {
                        "occurrences": int(occurrences),
                        "common": parse_mask(common),
                        "observed": parse_mask(observed),
                    }
                else:
                    aggregate = signatures[signature]
                    aggregate["occurrences"] += int(occurrences)
                    aggregate["common"] &= parse_mask(common)
                    aggregate["observed"] |= parse_mask(observed)

    shards = {report["shard"] for report in reports}
    if len(reports) != args.expected_shards or len(shards) != args.expected_shards:
        raise SystemExit(
            f"expected {args.expected_shards} shard reports for depth {args.depth}, "
            f"found {len(reports)} reports and {len(shards)} distinct shards"
        )

    args.output.mkdir(parents=True, exist_ok=True)
    conflicts = sum(1 for value in signatures.values() if value["common"] == 0)
    with (args.output / "signatures.tsv").open("w", encoding="utf-8") as output:
        output.write("occurrences\tcommon_safe\tobserved_safe\tsignature\n")
        for signature, aggregate in sorted(signatures.items()):
            output.write(
                f"{aggregate['occurrences']}\t{aggregate['common']:#x}\t"
                f"{aggregate['observed']:#x}\t{signature}\n"
            )

    totals = {
        "visible_boundaries": args.depth,
        "shards": args.expected_shards,
        "instances": sum(report["instances"] for report in reports),
        "solvable_instances": sum(report["solvable_instances"] for report in reports),
        "unsolvable_instances": sum(report["unsolvable_instances"] for report in reports),
        "oracle_states": sum(report["oracle_states"] for report in reports),
        "reachable_policy_states": sum(report["reachable_policy_states"] for report in reports),
        "observations": sum(report["observations"] for report in reports),
        "signatures": len(signatures),
        "conflicting_signatures": conflicts,
        "candidate_rule_signatures": len(signatures) - conflicts,
    }
    (args.output / "report.json").write_text(
        json.dumps(totals, indent=2) + "\n", encoding="utf-8"
    )
    summary = (
        f"## Thin-layer policy learning, depth {args.depth}\n\n"
        f"- Shards complete: {args.expected_shards}\n"
        f"- Instances sampled: {totals['instances']}\n"
        f"- Reachable solvable border states: {totals['reachable_policy_states']}\n"
        f"- Canonical scene signatures: {totals['signatures']}\n"
        f"- Signatures with a common safe action: {totals['candidate_rule_signatures']}\n"
        f"- Conflicting signatures: {totals['conflicting_signatures']}\n"
        f"- Counterexamples found: {totals['unsolvable_instances']}\n"
    )
    (args.output / "summary.md").write_text(summary, encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
