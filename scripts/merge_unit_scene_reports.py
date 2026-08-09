#!/usr/bin/env python3
"""Merge macro-local unit-move scene reports across catalog shards."""

import argparse
import json
from pathlib import Path


def read_scenes(path: Path) -> dict[str, dict]:
    scenes = {}
    with path.open(encoding="utf-8") as source:
        header = next(source).rstrip("\n").split("\t")
        expected = [
            "occurrences", "common_safe", "observed_safe", "witnesses", "signature"
        ]
        if header != expected:
            raise SystemExit(f"unexpected scene header in {path}")
        for line in source:
            occurrences, common, observed, witnesses, signature = (
                line.rstrip("\n").split("\t", 4)
            )
            scenes[signature] = {
                "occurrences": int(occurrences),
                "common": int(common, 16),
                "observed": int(observed, 16),
                "witnesses": [value for value in witnesses.split(",") if value],
            }
    return scenes


def merge_scene(aggregate: dict, incoming: dict) -> None:
    aggregate["occurrences"] += incoming["occurrences"]
    aggregate["common"] &= incoming["common"]
    aggregate["observed"] |= incoming["observed"]
    for witness in incoming["witnesses"]:
        if witness not in aggregate["witnesses"]:
            aggregate["witnesses"].append(witness)
            if len(aggregate["witnesses"]) == 12:
                break


def write_scenes(output: Path, window: int, scenes: dict[str, dict]) -> int:
    header = "occurrences\tcommon_safe\tobserved_safe\twitnesses\tsignature\n"
    conflicts = 0
    with (output / f"scenes-w{window}.tsv").open("w", encoding="utf-8") as all_rows, (
        output / f"conflicts-w{window}.tsv"
    ).open("w", encoding="utf-8") as conflict_rows:
        all_rows.write(header)
        conflict_rows.write(header)
        for signature, scene in sorted(scenes.items()):
            row = (
                f"{scene['occurrences']}\t{scene['common']:#x}\t"
                f"{scene['observed']:#x}\t{','.join(scene['witnesses'])}\t"
                f"{signature}\n"
            )
            all_rows.write(row)
            if scene["common"] == 0:
                conflict_rows.write(row)
                conflicts += 1
    return conflicts


def project_scene(signature: str, window: int) -> str:
    phase, raw_columns = signature.split("|", 1)
    columns = []
    for descriptor in raw_columns.split("/"):
        label, flags, visible = descriptor.split(":", 2)
        colors, terminal = visible[:-1], visible[-1]
        if len(colors) > window:
            colors = colors[:window]
            terminal = "+"
        columns.append(f"{label}:{flags}:{colors}{terminal}")
    return phase + "|" + "/".join(columns)


def write_refinements(
    output: Path, by_window: dict[int, dict], parent_window: int
) -> tuple[int, int]:
    parents = {
        signature
        for signature, scene in by_window[parent_window].items()
        if scene["common"] == 0
    }
    refinements = []
    child_window = parent_window + 1
    for signature, scene in by_window[child_window].items():
        parent = project_scene(signature, parent_window)
        if parent in parents:
            refinements.append((parent, signature, scene))
    with (output / f"w{parent_window}-conflict-refinements-w{child_window}.tsv").open(
        "w", encoding="utf-8"
    ) as target:
        target.write(
            f"parent_w{parent_window}\toccurrences\tcommon_safe\tobserved_safe\t"
            f"witnesses\tsignature_w{child_window}\n"
        )
        for parent, signature, scene in sorted(refinements):
            target.write(
                f"{parent}\t{scene['occurrences']}\t{scene['common']:#x}\t"
                f"{scene['observed']:#x}\t{','.join(scene['witnesses'])}\t"
                f"{signature}\n"
            )
    conflicting_refinements = sum(1 for _, _, scene in refinements if not scene["common"])
    return len(refinements), conflicting_refinements


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expected-shards", required=True, type=int)
    parser.add_argument("--expect-exceptions", type=int)
    args = parser.parse_args()

    reports = []
    by_window = {2: {}, 3: {}, 4: {}, 5: {}}
    exception_counts: dict[str, int] = {}
    occurrence_rows = []
    for report_path in sorted(args.input.rglob("report.json")):
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if "retightening_gaps" not in report:
            continue
        reports.append(report)
        for window in by_window:
            for signature, incoming in read_scenes(
                report_path.with_name(f"scenes-w{window}.tsv")
            ).items():
                if signature not in by_window[window]:
                    by_window[window][signature] = incoming
                else:
                    merge_scene(by_window[window][signature], incoming)

        with report_path.with_name("exception_coverage.tsv").open(
            encoding="utf-8"
        ) as source:
            next(source)
            for line in source:
                count, signature = line.rstrip("\n").split("\t", 1)
                exception_counts[signature] = exception_counts.get(signature, 0) + int(
                    count
                )
        with report_path.with_name("exception_occurrences.tsv").open(
            encoding="utf-8"
        ) as source:
            next(source)
            occurrence_rows.extend(line for line in source if line.strip())

    shard_ids = {report["shard"] for report in reports}
    declared_shards = {report["shards"] for report in reports}
    expected_ids = set(range(args.expected_shards))
    if len(reports) != args.expected_shards or shard_ids != expected_ids:
        raise SystemExit(
            f"expected shard ids {sorted(expected_ids)}, found {sorted(shard_ids)} "
            f"in {len(reports)} reports"
        )
    if declared_shards != {args.expected_shards}:
        raise SystemExit(f"inconsistent declared shard counts: {declared_shards}")
    if args.expect_exceptions is not None and len(exception_counts) != args.expect_exceptions:
        raise SystemExit(
            f"expected {args.expect_exceptions} exception signatures, "
            f"found {len(exception_counts)}"
        )

    args.output.mkdir(parents=True, exist_ok=True)
    conflicts = {
        window: write_scenes(args.output, window, scenes)
        for window, scenes in by_window.items()
    }
    refinements = {
        window: write_refinements(args.output, by_window, window)
        for window in (3, 4)
    }
    with (args.output / "exception_coverage.tsv").open(
        "w", encoding="utf-8"
    ) as output:
        output.write("occurrences\tsignature\n")
        for signature, count in sorted(exception_counts.items()):
            output.write(f"{count}\t{signature}\n")
    with (args.output / "exception_occurrences.tsv").open(
        "w", encoding="utf-8"
    ) as output:
        output.write(
            "policy\tmodel\theight\tstate\tcanonical_action\tsource\t"
            "safe_sources\tmacro_signature\tinstance\n"
        )
        output.writelines(sorted(occurrence_rows))

    controllers = {report["controllers"] for report in reports}
    if len(controllers) != 1:
        raise SystemExit(f"inconsistent controller counts: {controllers}")
    totals = {
        "reports": len(reports),
        "models": sum(report["models"] for report in reports),
        "controllers": next(iter(controllers)),
        "controller_instances": sum(
            report["controller_instances"] for report in reports
        ),
        "macro_states": sum(report["macro_states"] for report in reports),
        "unit_moves": sum(report["unit_moves"] for report in reports),
        "retightening_gaps": sum(
            report["retightening_gaps"] for report in reports
        ),
        "exception_signatures": len(exception_counts),
        "witnessed_exceptions": sum(1 for count in exception_counts.values() if count),
        "exception_occurrences": sum(exception_counts.values()),
        "scenes_w2": len(by_window[2]),
        "scenes_w3": len(by_window[3]),
        "scenes_w4": len(by_window[4]),
        "scenes_w5": len(by_window[5]),
        "conflicts_w2": conflicts[2],
        "conflicts_w3": conflicts[3],
        "conflicts_w4": conflicts[4],
        "conflicts_w5": conflicts[5],
        "w3_conflict_refinements_w4": refinements[3][0],
        "w3_conflict_refinement_conflicts_w4": refinements[3][1],
        "w4_conflict_refinements_w5": refinements[4][0],
        "w4_conflict_refinement_conflicts_w5": refinements[4][1],
        "macro_local_unit_traces": True,
        "continuous_physical_controller_proved": False,
    }
    (args.output / "report.json").write_text(
        json.dumps(totals, indent=2) + "\n", encoding="utf-8"
    )
    missing = [
        signature for signature, count in sorted(exception_counts.items()) if count == 0
    ]
    (args.output / "missing-exceptions.txt").write_text(
        "\n".join(missing) + ("\n" if missing else ""), encoding="utf-8"
    )
    summary = f"""# Unit-move finite-scene analysis

- Catalog instances: {totals['models']}
- Compressed controllers replayed: {totals['controllers']}
- Macro checkpoints: {totals['macro_states']}
- Unit moves expanded: {totals['unit_moves']}
- Exception signatures witnessed: {totals['witnessed_exceptions']}/{totals['exception_signatures']}
- Window 2: {totals['scenes_w2']} scenes, **{totals['conflicts_w2']} conflicts**
- Window 3: {totals['scenes_w3']} scenes, **{totals['conflicts_w3']} conflicts**
- Window 4: {totals['scenes_w4']} scenes, **{totals['conflicts_w4']} conflicts**
- Window 5: {totals['scenes_w5']} scenes, **{totals['conflicts_w5']} conflicts**
- The {totals['conflicts_w3']} ambiguous window-3 scenes split into
  {totals['w3_conflict_refinements_w4']} window-4 refinements, with
  **{totals['w3_conflict_refinement_conflicts_w4']} remaining conflicts**
- The {totals['conflicts_w4']} ambiguous window-4 scenes split into
  {totals['w4_conflict_refinements_w5']} window-5 refinements, with
  **{totals['w4_conflict_refinement_conflicts_w5']} remaining conflicts**

Every selected border removal is expanded into legal one-item moves from a
canonical tight representative. The representative is rebuilt at the next
macro checkpoint, producing {totals['retightening_gaps']} explicit connection
gaps. Therefore zero sampled scene conflicts would support a candidate local
rule, but would not yet prove a continuous physical controller or all-height
closure.
"""
    (args.output / "summary.md").write_text(summary, encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
