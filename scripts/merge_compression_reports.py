#!/usr/bin/env python3
"""Compare default-heuristic controller compression attempts."""

import argparse
import csv
import json
import shutil
import statistics
from collections import Counter, defaultdict
from pathlib import Path


def read_policy(path: Path) -> dict[str, tuple[int, int]]:
    rules = {}
    with path.open(encoding="utf-8") as source:
        header = next(source).rstrip("\n").split("\t")
        if header != ["action", "domain", "signature"]:
            raise SystemExit(f"unexpected policy header in {path}")
        for line in source:
            action, domain, signature = line.rstrip("\n").split("\t", 2)
            rules[signature] = (int(action), int(domain, 16))
    return rules


def shape_key(signature: str) -> tuple[str, str, str]:
    phase, colors, raw_columns = signature.split("|", 2)
    shapes = []
    for descriptor in raw_columns.split("/"):
        kind, runs, need = descriptor.split(":")
        continuation = runs[-1]
        run_count = len(runs) - 1
        shapes.append(f"{kind}:{run_count}{continuation}:{need}")
    return phase, colors, "/".join(shapes)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expected-attempts", required=True, type=int)
    args = parser.parse_args()

    attempts = []
    for report_path in sorted(args.input.rglob("report.json")):
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report.get("mode") != "controlled-synthesis" or not report.get(
            "default_heuristic"
        ):
            continue
        policy_path = report_path.with_name("policy.tsv")
        report["_report_path"] = report_path
        report["_policy_path"] = policy_path
        report["_rules"] = read_policy(policy_path)
        attempts.append(report)

    if len(attempts) != args.expected_attempts:
        raise SystemExit(
            f"expected {args.expected_attempts} compression reports, found {len(attempts)}"
        )
    identities = [
        (attempt["default_heuristic"], attempt["seed"]) for attempt in attempts
    ]
    if len(set(identities)) != len(identities):
        raise SystemExit("one heuristic repeated the same random seed")

    successes = [attempt for attempt in attempts if attempt["success"]]
    if not successes:
        raise SystemExit("no compression attempt produced a replayable controller")
    selected = min(
        successes,
        key=lambda attempt: (
            attempt["policy_rules"],
            attempt["verified_replay_states"],
        ),
    )

    args.output.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(selected["_policy_path"], args.output / "policy.tsv")

    with (args.output / "attempts.tsv").open(
        "w", encoding="utf-8", newline=""
    ) as output:
        writer = csv.writer(output, delimiter="\t", lineterminator="\n")
        writer.writerow(
            [
                "heuristic",
                "seed",
                "success",
                "exceptions",
                "observed_signatures",
                "verified_replay_states",
                "reached_global_conflicts",
            ]
        )
        for attempt in sorted(
            attempts, key=lambda value: (value["default_heuristic"], value["seed"])
        ):
            writer.writerow(
                [
                    attempt["default_heuristic"],
                    attempt["seed"],
                    int(attempt["success"]),
                    attempt["policy_rules"],
                    attempt["observed_signatures"],
                    attempt["verified_replay_states"],
                    attempt["reached_global_conflicts"],
                ]
            )

    grouped = defaultdict(list)
    for attempt in attempts:
        grouped[attempt["default_heuristic"]].append(attempt)
    heuristic_rows = []
    with (args.output / "heuristics.tsv").open(
        "w", encoding="utf-8", newline=""
    ) as output:
        writer = csv.writer(output, delimiter="\t", lineterminator="\n")
        writer.writerow(
            [
                "heuristic",
                "attempts",
                "successes",
                "min_exceptions",
                "median_exceptions",
                "max_exceptions",
                "stable_exceptions",
                "union_exceptions",
            ]
        )
        for heuristic, group in sorted(grouped.items()):
            successful = [attempt for attempt in group if attempt["success"]]
            counts = [attempt["policy_rules"] for attempt in successful]
            sets = [set(attempt["_rules"]) for attempt in successful]
            stable = len(set.intersection(*sets)) if sets else 0
            union = len(set.union(*sets)) if sets else 0
            row = [
                heuristic,
                len(group),
                len(successful),
                min(counts) if counts else "",
                statistics.median(counts) if counts else "",
                max(counts) if counts else "",
                stable,
                union,
            ]
            heuristic_rows.append(row)
            writer.writerow(row)

    classes = Counter()
    action_counts = Counter()
    domain_sizes = Counter()
    for signature, (action, domain) in selected["_rules"].items():
        classes[shape_key(signature)] += 1
        action_counts[action] += 1
        domain_sizes[domain.bit_count()] += 1
    with (args.output / "exception_classes.tsv").open(
        "w", encoding="utf-8", newline=""
    ) as output:
        writer = csv.writer(output, delimiter="\t", lineterminator="\n")
        writer.writerow(["count", "phase", "color_flags", "column_shapes"])
        for (phase, colors, shapes), count in sorted(
            classes.items(), key=lambda value: (-value[1], value[0])
        ):
            writer.writerow([count, phase, colors, shapes])

    merged = {
        "successful_attempts": len(successes),
        "attempts": len(attempts),
        "selected_default_heuristic": selected["default_heuristic"],
        "selected_seed": selected["seed"],
        "selected_exceptions": selected["policy_rules"],
        "selected_observed_signatures": selected["observed_signatures"],
        "selected_verified_replay_states": selected["verified_replay_states"],
        "selected_reached_global_conflicts": selected["reached_global_conflicts"],
        "selected_action_counts": dict(sorted(action_counts.items())),
        "selected_domain_size_counts": dict(sorted(domain_sizes.items())),
    }
    (args.output / "report.json").write_text(
        json.dumps(merged, indent=2) + "\n", encoding="utf-8"
    )

    rows = "\n".join(
        f"| {row[0]} | {row[2]}/{row[1]} | {row[3]} | {row[4]} | {row[5]} | {row[6]} | {row[7]} |"
        for row in heuristic_rows
    )
    summary = f"""# Controlled policy compression

The best replay-verified controller uses **{selected['default_heuristic']}** as
its default rule and stores **{selected['policy_rules']} exceptions** for the
{selected['instances']} sampled initial instances.

| Default rule | Successful | Min exceptions | Median | Max | Stable | Union |
|---|---:|---:|---:|---:|---:|---:|
{rows}

- Observed signatures on the selected controlled trajectories: {selected['observed_signatures']}
- Independently replayed states: {selected['verified_replay_states']}
- Previously global-conflicting signatures reached: {selected['reached_global_conflicts']}

The exception counts measure this finite catalog only. Stability across random
seeds is evidence for useful structural cases, not a symbolic all-height closure
proof.
"""
    (args.output / "summary.md").write_text(summary, encoding="utf-8")


if __name__ == "__main__":
    main()
