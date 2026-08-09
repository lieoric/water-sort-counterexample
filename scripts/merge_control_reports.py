#!/usr/bin/env python3
"""Merge independent controlled-policy synthesis attempts."""

import argparse
import csv
import json
import shutil
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expected-attempts", required=True, type=int)
    args = parser.parse_args()

    attempts = []
    for report_path in sorted(args.input.rglob("report.json")):
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report["_path"] = report_path
        attempts.append(report)

    if len(attempts) != args.expected_attempts:
        raise SystemExit(
            f"expected {args.expected_attempts} reports, found {len(attempts)}"
        )
    seeds = [attempt["seed"] for attempt in attempts]
    if len(set(seeds)) != len(seeds):
        raise SystemExit("controlled-policy attempts did not use distinct seeds")

    successes = [attempt for attempt in attempts if attempt["success"]]
    if successes:
        selected = min(
            successes,
            key=lambda attempt: (attempt["policy_rules"], attempt["traversed_states"]),
        )
    else:
        selected = max(
            attempts,
            key=lambda attempt: (
                attempt["completed_instances"],
                -attempt["traversed_states"],
            ),
        )

    args.output.mkdir(parents=True, exist_ok=True)
    selected_policy = selected["_path"].with_name("policy.tsv")
    if selected_policy.exists():
        shutil.copyfile(selected_policy, args.output / "policy.tsv")

    with (args.output / "attempts.tsv").open(
        "w", encoding="utf-8", newline=""
    ) as output:
        writer = csv.writer(output, delimiter="\t", lineterminator="\n")
        writer.writerow(
            [
                "seed",
                "success",
                "completed_instances",
                "instances",
                "policy_rules",
                "reached_global_conflicts",
                "traversed_states",
                "verified_replay_states",
            ]
        )
        for attempt in sorted(attempts, key=lambda value: value["seed"]):
            writer.writerow(
                [
                    attempt["seed"],
                    int(attempt["success"]),
                    attempt["completed_instances"],
                    attempt["instances"],
                    attempt["policy_rules"],
                    attempt["reached_global_conflicts"],
                    attempt["traversed_states"],
                    attempt["verified_replay_states"],
                ]
            )

    merged = {
        "complete_sample_policy_found": bool(successes),
        "attempts": len(attempts),
        "successful_attempts": len(successes),
        "instances": selected["instances"],
        "visible_boundaries": selected["visible_boundaries"],
        "goal_exhausted_columns": selected["goal_exhausted_columns"],
        "selected_seed": selected["seed"],
        "selected_policy_rules": selected["policy_rules"],
        "selected_reached_global_conflicts": selected["reached_global_conflicts"],
        "selected_verified_replay_states": selected["verified_replay_states"],
        "best_completed_instances": max(
            attempt["completed_instances"] for attempt in attempts
        ),
    }
    (args.output / "report.json").write_text(
        json.dumps(merged, indent=2) + "\n", encoding="utf-8"
    )

    conclusion = (
        "A deterministic depth-3 controller was found for every sampled initial "
        "instance."
        if successes
        else "No controller was found within the randomized restart budget."
    )
    summary = f"""# Controlled reachability search

{conclusion}

- Independent attempts: {len(attempts)}
- Successful attempts: {len(successes)}
- Sampled initial instances: {selected['instances']}
- Best completed instances: {merged['best_completed_instances']}
- Selected policy rules: {selected['policy_rules']}
- Independently replayed controlled states: {selected['verified_replay_states']}
- Previously global-conflicting signatures reached by the selected attempt: {selected['reached_global_conflicts']}

This is a finite-catalog synthesis result. Success gives one checkable controller
for the sampled catalog; it is not yet an all-height proof. Failure is only a
failure of this randomized search budget, not a proof that no controller exists.
"""
    (args.output / "summary.md").write_text(summary, encoding="utf-8")


if __name__ == "__main__":
    main()
