#!/usr/bin/env python3
"""Merge sharded continuous bulk-move replay reports."""

import argparse
import json
import shutil
from collections import Counter
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expected-shards", required=True, type=int)
    args = parser.parse_args()

    reports: list[tuple[Path, dict]] = []
    for path in sorted(args.input.rglob("report.json")):
        report = json.loads(path.read_text(encoding="utf-8"))
        if "bulk_moves" in report and "gaps" in report and "shard" in report:
            reports.append((path, report))

    expected_ids = set(range(args.expected_shards))
    shard_ids = {report["shard"] for _, report in reports}
    declared = {report["shards"] for _, report in reports}
    if len(reports) != args.expected_shards or shard_ids != expected_ids:
        raise SystemExit(
            f"expected shard ids {sorted(expected_ids)}, found {sorted(shard_ids)} "
            f"in {len(reports)} reports"
        )
    if declared != {args.expected_shards}:
        raise SystemExit(f"inconsistent declared shard counts: {sorted(declared)}")

    args.output.mkdir(parents=True, exist_ok=True)
    header = None
    rows: list[str] = []
    failures: list[str] = []
    reasons: Counter[str] = Counter()
    gap_witnesses = args.output / "gap-witnesses"

    for report_path, report in reports:
        reasons.update(report.get("reasons", {}))
        table_path = report_path.with_name("report.tsv")
        with table_path.open(encoding="utf-8") as source:
            current_header = next(source).rstrip("\n")
            if header is None:
                header = current_header
            elif current_header != header:
                raise SystemExit(f"inconsistent TSV header in {table_path}")
            for line in source:
                if not line.strip():
                    continue
                rows.append(line)
                fields = line.rstrip("\n").split("\t")
                if len(fields) < 5:
                    raise SystemExit(f"malformed row in {table_path}")
                if fields[3] != "1":
                    failures.append(line)

        witness = report_path.with_name("first_gap.txt")
        if witness.exists():
            gap_witnesses.mkdir(exist_ok=True)
            shutil.copyfile(
                witness,
                gap_witnesses / f"shard-{report['shard']}-first-gap.txt",
            )

    rows.sort()
    failures.sort()
    with (args.output / "report.tsv").open("w", encoding="utf-8") as target:
        target.write((header or "") + "\n")
        target.writelines(rows)
    with (args.output / "failures.tsv").open("w", encoding="utf-8") as target:
        target.write((header or "") + "\n")
        target.writelines(failures)

    totals = {
        "reports": len(reports),
        "models": sum(report["models"] for _, report in reports),
        "controllers": next(iter({report["controllers"] for _, report in reports})),
        "runs": sum(report["runs"] for _, report in reports),
        "successes": sum(report["successes"] for _, report in reports),
        "gaps": sum(report["gaps"] for _, report in reports),
        "macro_steps": sum(report["macro_steps"] for _, report in reports),
        "bulk_moves": sum(report["bulk_moves"] for _, report in reports),
        "max_bulk_moves_per_run": max(
            report["max_bulk_moves_per_run"] for _, report in reports
        ),
        "locked_source_violations": sum(
            report["locked_source_violations"] for _, report in reports
        ),
        "reasons": dict(sorted(reasons.items())),
        "continuous_physical_replay": True,
        "canonical_retightening_used": False,
        "all_height_theorem_proved": False,
    }
    (args.output / "report.json").write_text(
        json.dumps(totals, indent=2) + "\n", encoding="utf-8"
    )

    summary = f"""# Continuous bulk-move replay

- Catalog instances: {totals['models']}
- Controllers: {totals['controllers']}
- Continuous runs: {totals['runs']}
- Successful runs: **{totals['successes']}**
- Construction gaps: **{totals['gaps']}**
- Border removals realized: {totals['macro_steps']}
- Forced maximal bulk moves: {totals['bulk_moves']}
- Maximum bulk moves in one run: {totals['max_bulk_moves_per_run']}
- Locked-source violations: **{totals['locked_source_violations']}**

Each run starts from the real initial physical configuration and preserves the
actually reached tight representative. No canonical physical state is rebuilt
between border removals. A zero-gap result validates the constructive physical
realization on this finite catalog; it does not by itself prove that every
arbitrary-height initial border state has a winning border-removal policy.
"""
    (args.output / "summary.md").write_text(summary, encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
