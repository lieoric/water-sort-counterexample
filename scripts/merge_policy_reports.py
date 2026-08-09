#!/usr/bin/env python3
"""Merge water-policy-learn reports across shards and optional heights."""

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
    parser.add_argument("--height", type=int)
    parser.add_argument("--goal-exhausted", type=int)
    args = parser.parse_args()

    reports = []
    signatures = {}
    instances = {}
    for report_path in sorted(args.input.rglob("report.json")):
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report["visible_boundaries"] != args.depth:
            continue
        if args.height is not None and report.get("height") != args.height:
            continue
        if (args.goal_exhausted is not None and
                report.get("goal_exhausted_columns", 0) != args.goal_exhausted):
            continue
        reports.append(report)
        instance_table = report_path.with_name("instances.tsv")
        if instance_table.exists():
            with instance_table.open(encoding="utf-8") as source:
                next(source)
                for line in source:
                    fingerprint, encoding = line.rstrip("\n").split("\t", 1)
                    if fingerprint in instances and instances[fingerprint] != encoding:
                        raise SystemExit(f"fingerprint collision for {fingerprint}")
                    instances[fingerprint] = encoding
        table = report_path.with_name("signatures.tsv")
        with table.open(encoding="utf-8") as source:
            next(source)
            for line in source:
                fields = line.rstrip("\n").split("\t", 5)
                if len(fields) == 5:
                    _, occurrences, common, observed, signature = fields
                    witnesses = []
                else:
                    _, occurrences, common, observed, raw_witnesses, signature = fields
                    witnesses = [value for value in raw_witnesses.split(",") if value]
                if signature not in signatures:
                    signatures[signature] = {
                        "occurrences": int(occurrences),
                        "common": parse_mask(common),
                        "observed": parse_mask(observed),
                        "witnesses": witnesses[:12],
                    }
                else:
                    aggregate = signatures[signature]
                    aggregate["occurrences"] += int(occurrences)
                    aggregate["common"] &= parse_mask(common)
                    aggregate["observed"] |= parse_mask(observed)
                    for witness in witnesses:
                        if witness not in aggregate["witnesses"]:
                            aggregate["witnesses"].append(witness)
                            if len(aggregate["witnesses"]) == 12:
                                break

    report_keys = {(report.get("height"), report["shard"]) for report in reports}
    if len(reports) != args.expected_shards or len(report_keys) != args.expected_shards:
        raise SystemExit(
            f"expected {args.expected_shards} shard reports for depth {args.depth}, "
            f"found {len(reports)} reports and {len(report_keys)} distinct height/shard pairs"
        )

    args.output.mkdir(parents=True, exist_ok=True)
    conflicts = sum(1 for value in signatures.values() if value["common"] == 0)
    with (args.output / "signatures.tsv").open("w", encoding="utf-8") as output:
        output.write("occurrences\tcommon_safe\tobserved_safe\twitnesses\tsignature\n")
        for signature, aggregate in sorted(signatures.items()):
            output.write(
                f"{aggregate['occurrences']}\t{aggregate['common']:#x}\t"
                f"{aggregate['observed']:#x}\t{','.join(aggregate['witnesses'])}\t"
                f"{signature}\n"
            )
    with (args.output / "conflicts.tsv").open("w", encoding="utf-8") as output:
        output.write("occurrences\tobserved_safe\twitnesses\tsignature\n")
        for signature, aggregate in sorted(signatures.items()):
            if aggregate["common"] != 0:
                continue
            output.write(
                f"{aggregate['occurrences']}\t{aggregate['observed']:#x}\t"
                f"{','.join(aggregate['witnesses'])}\t{signature}\n"
            )
    with (args.output / "instances.tsv").open("w", encoding="utf-8") as output:
        output.write("fingerprint\tinstance\n")
        for fingerprint, encoding in sorted(instances.items()):
            output.write(f"{fingerprint}\t{encoding}\n")

    heights = sorted({report.get("height") for report in reports})
    goals = sorted({report.get("goal_exhausted_columns", 0) for report in reports})
    totals = {
        "visible_boundaries": args.depth,
        "goal_exhausted_columns": goals[0] if len(goals) == 1 else goals,
        "heights": heights,
        "reports": args.expected_shards,
        "base_instances": sum(report.get("base_instances", report["instances"])
                              for report in reports),
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
        f"- Heights: {', '.join(str(value) for value in heights)}\n"
        f"- Goal exhausted columns: {', '.join(str(value) for value in goals)}\n"
        f"- Reports complete: {args.expected_shards}\n"
        f"- Random base instances: {totals['base_instances']}\n"
        f"- Instances sampled: {totals['instances']}\n"
        f"- Reachable goal-winning border states: {totals['reachable_policy_states']}\n"
        f"- Canonical scene signatures: {totals['signatures']}\n"
        f"- Signatures with a common safe action: {totals['candidate_rule_signatures']}\n"
        f"- Conflicting signatures: {totals['conflicting_signatures']}\n"
        f"- Goal-unreachable instances: {totals['unsolvable_instances']}\n"
    )
    (args.output / "summary.md").write_text(summary, encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
