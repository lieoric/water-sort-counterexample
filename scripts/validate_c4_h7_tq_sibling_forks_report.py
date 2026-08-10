#!/usr/bin/env python3
"""Strict artifact-level validation for the c4/k2/h7 Tq sibling-fork run.

This checker deliberately does not reproduce the independent mathematical
census.  Its job is to prevent a partial or local obstruction from being
reported as a complete Water Sort result and to validate the shape of any
full-instance witness before the independent oracle is invoked.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import NoReturn


EXPECTED_TERMINALS = 71
EXPECTED_SIBLING_PARENTS = 23
EXPECTED_BAD_EDGES = 32
EXPECTED_RAW_SINGLE_OUTCOMES = 840
EXPECTED_RAW_SIMULTANEOUS_DECORATIONS = 5_526
EXPECTED_RESIDUAL_WORDS = 10_073_448
EXPECTED_SCOPE = "same_z_tq_sibling_entry_family"
ALLOWED_STATUSES = {
    "ENTRY_FAMILY_ELIMINATED",
    "RESIDUALS_EXPORTED",
    "GLOBAL_NO_FOUND",
    "INCOMPLETE",
}


def fail(message: str) -> NoReturn:
    raise SystemExit(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def integer(report: dict[str, object], key: str, *, minimum: int = 0) -> int:
    value = report.get(key)
    require(
        isinstance(value, int) and not isinstance(value, bool),
        f"{key} must be an integer, got {value!r}",
    )
    require(value >= minimum, f"{key} must be at least {minimum}, got {value}")
    return value


def parse_complete_instance(path: Path) -> None:
    """Check that a claimed global NO witness is a complete balanced instance."""

    require(path.is_file(), f"NO_FOUND is missing the full instance {path}")
    fields: dict[str, int] = {}
    columns: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("column="):
            columns.append(line.removeprefix("column="))
            continue
        match = re.fullmatch(r"(height|colors|empty)=(\d+)", line)
        require(match is not None, f"unrecognized instance line: {raw_line!r}")
        key, value = match.groups()
        require(key not in fields, f"duplicate instance field: {key}")
        fields[key] = int(value)

    require(
        fields == {"height": 7, "colors": 4, "empty": 2},
        f"NO witness has wrong dimensions: {fields}",
    )
    require(len(columns) == 4, f"NO witness must contain four columns, got {len(columns)}")
    counts = [0, 0, 0, 0]
    for index, column in enumerate(columns):
        require(len(column) == 7, f"column {index} has length {len(column)}, expected 7")
        require(re.fullmatch(r"[0-3]{7}", column) is not None, f"invalid column {index}: {column!r}")
        for symbol in column:
            counts[int(symbol)] += 1
    require(counts == [7, 7, 7, 7], f"NO witness is not balanced: color counts {counts}")


def validate(report_path: Path, output_dir: Path, audit_path: Path | None) -> str:
    require(report_path.is_file(), f"missing JSON report: {report_path}")
    markdown_path = output_dir / "report.md"
    require(markdown_path.is_file(), f"missing Markdown report: {markdown_path}")

    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        fail(f"cannot parse {report_path}: {error}")
    require(isinstance(report, dict), "the top-level report must be a JSON object")
    require(report.get("schema_version") == 1, "unsupported or missing schema_version")
    require(report.get("self_checks_passed") is True, "production self-checks did not pass")

    if audit_path is not None:
        require(audit_path.is_file(), f"missing independent census: {audit_path}")
        try:
            audit = json.loads(audit_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            fail(f"cannot parse {audit_path}: {error}")
        require(isinstance(audit, dict), "the independent census must be a JSON object")
        for key in (
            "terminal_count",
            "sibling_parent_count",
            "bad_edge_count",
            "raw_single_next_run_outcomes",
            "raw_simultaneous_decorations",
            "feasible_decorations",
            "fixed_future_completions",
        ):
            require(
                report.get(key) == audit.get(key),
                f"production {key}={report.get(key)!r} disagrees with independent audit "
                f"{audit.get(key)!r}",
            )

    status = report.get("status")
    require(status in ALLOWED_STATUSES, f"unsupported report status: {status!r}")
    require(
        report.get("coverage_scope") == EXPECTED_SCOPE,
        f"coverage_scope must be {EXPECTED_SCOPE!r}",
    )
    require(isinstance(report.get("verified"), bool), "verified must be Boolean")
    require(
        isinstance(report.get("universe_complete"), bool),
        "universe_complete must be Boolean",
    )
    for key in ("next_run_census_complete", "residual_word_universe_complete"):
        require(isinstance(report.get(key), bool), f"{key} must be Boolean")

    fixed_census = {
        "terminal_count": EXPECTED_TERMINALS,
        "sibling_parent_count": EXPECTED_SIBLING_PARENTS,
        "bad_edge_count": EXPECTED_BAD_EDGES,
        "raw_single_next_run_outcomes": EXPECTED_RAW_SINGLE_OUTCOMES,
        "raw_simultaneous_decorations": EXPECTED_RAW_SIMULTANEOUS_DECORATIONS,
    }
    actual_census = {key: report.get(key) for key in fixed_census}
    require(
        actual_census == fixed_census,
        f"fixed sibling-fork census mismatch: expected {fixed_census}, got {actual_census}",
    )

    feasible = integer(report, "feasible_decorations")
    fixed_futures = integer(report, "fixed_future_completions")
    residual_expected = integer(report, "residual_words_expected")
    residual_checked = integer(report, "residual_words_checked")
    checkpoint_yes = integer(report, "checkpoint_yes_count")
    local_no = integer(report, "local_no_count")
    global_no = integer(report, "global_no_count")
    require(feasible <= EXPECTED_RAW_SIMULTANEOUS_DECORATIONS, "feasible census exceeds raw decorations")
    require(
        fixed_futures == 0 or feasible > 0,
        "fixed-future completions cannot exist without a feasible decoration",
    )
    require(
        residual_checked <= residual_expected,
        f"residual_words_checked={residual_checked} exceeds expected={residual_expected}",
    )
    require(
        checkpoint_yes + local_no == residual_checked,
        "checkpoint classifications do not sum to checked residual words",
    )
    require(
        residual_expected == fixed_futures == EXPECTED_RESIDUAL_WORDS,
        "residual-word universe must match the independently derived 10,073,448 words",
    )

    verified = report["verified"]
    complete = report["universe_complete"]
    next_run_complete = report["next_run_census_complete"]
    residual_complete = report["residual_word_universe_complete"]
    if status == "ENTRY_FAMILY_ELIMINATED":
        require(verified is True, "ENTRY_FAMILY_ELIMINATED requires verified=true")
        require(complete is True, "elimination requires universe_complete=true")
        require(next_run_complete is True, "elimination requires a complete next-run census")
        require(
            residual_complete is True,
            "entry elimination is forbidden without complete residual-word coverage",
        )
        require(residual_expected > 0, "elimination cannot use an empty residual census")
        require(residual_checked == residual_expected, "elimination has unchecked residual words")
        require(checkpoint_yes == residual_expected and local_no == 0, "elimination contains a local NO")
        require(global_no == 0, "eliminated entry family cannot also report a global NO")
        require(
            not (output_dir / "no-instance.txt").exists(),
            "eliminated entry family unexpectedly contains a global NO witness",
        )
    elif status == "RESIDUALS_EXPORTED":
        require(verified is True, "RESIDUALS_EXPORTED requires verified=true")
        require(complete is True, "residual export requires universe_complete=true for its local universe")
        require(next_run_complete is True, "residual export requires the next-run census")
        require(residual_complete is True, "residual export must cover every residual word")
        require(residual_checked == residual_expected, "residual export has unchecked words")
        require(local_no >= 1, "RESIDUALS_EXPORTED has no local-NO residual")
        require(global_no == 0, "local residual export cannot report a global NO")
        require(
            not (output_dir / "no-instance.txt").exists(),
            "local residual export must not publish an artifact named as a global NO witness",
        )
    elif status == "GLOBAL_NO_FOUND":
        require(verified is True, "GLOBAL_NO_FOUND requires verified=true")
        require(global_no >= 1, "GLOBAL_NO_FOUND has no globally classified NO instance")
        parse_complete_instance(output_dir / "no-instance.txt")
    else:
        require(verified is False, "INCOMPLETE must set verified=false")
        require(complete is False, "INCOMPLETE must set universe_complete=false")
        require(
            residual_complete is False or residual_checked < residual_expected,
            "INCOMPLETE contradicts complete residual-word coverage",
        )
        require(global_no == 0, "a globally verified NO must use GLOBAL_NO_FOUND")
        require(
            not (output_dir / "no-instance.txt").exists(),
            "INCOMPLETE must not publish an artifact named as a global NO witness",
        )

    return str(status)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--status-file", type=Path)
    args = parser.parse_args()

    status = validate(args.report, args.output_dir, args.audit)
    if args.status_file is not None:
        args.status_file.parent.mkdir(parents=True, exist_ok=True)
        args.status_file.write_text(status + "\n", encoding="utf-8")
    print(f"strict sibling-fork report validation passed: status={status}")


if __name__ == "__main__":
    main()
