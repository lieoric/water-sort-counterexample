#!/usr/bin/env python3
"""Strict claim-boundary validator for the low-energy Tq-corner report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import NoReturn


SCOPE = "c4_h7_first_exhaustion_tq_low_energy_corners"
EXPECTED_DECORATIONS = 10
EXPECTED_EDGES = 9
EXPECTED_WORDS = 235_620
EXPECTED_PARENT_CHECKPOINT_LOCAL_NO = 126
EXPECTED_WEIGHTS = (13_860, 27_720, 34_650, 27_720, 13_860,
                    13_860, 27_720, 34_650, 27_720, 13_860)
TERMINAL_STATUSES = {
    "CORNER_FAMILY_ELIMINATED",
    "LOCAL_NO_RESIDUALS_EXPORTED",
}


def fail(message: str) -> NoReturn:
    raise AssertionError(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def integer(value: object, label: str) -> int:
    require(isinstance(value, int) and not isinstance(value, bool), f"{label} is not an integer")
    return int(value)


def load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), "report root is not an object")
    return value


def validate(report: dict[str, object]) -> None:
    require(report.get("schema_version") == 1, "unsupported schema version")
    require(report.get("coverage_scope") == SCOPE, "unexpected coverage scope")
    require(
        report.get("corner_decorations_expected") == EXPECTED_DECORATIONS,
        "corner-decoration constant drifted",
    )
    require(report.get("corner_edges_expected") == EXPECTED_EDGES, "corner-edge constant drifted")
    require(report.get("corner_edge_count") == EXPECTED_EDGES, "corner-edge coverage drifted")
    require(
        report.get("bridge")
        == {
            "terminal_count": 71,
            "labeled_reverse_candidates": 624,
            "canonical_parent_count": 418,
            "canonical_edge_count": 429,
            "sibling_parent_count": 412,
            "sibling_edge_count": 423,
        },
        "bridge census drifted",
    )
    require(report.get("residual_words_expected") == EXPECTED_WORDS, "word-universe constant drifted")

    checked = integer(report.get("residual_words_checked"), "residual_words_checked")
    parent_yes = integer(report.get("parent_checkpoint_yes_count"), "parent_checkpoint_yes_count")
    parent_no = integer(
        report.get("parent_checkpoint_local_no_count"),
        "parent_checkpoint_local_no_count",
    )
    water_checked = integer(
        report.get("water_initial_layouts_checked"),
        "water_initial_layouts_checked",
    )
    water_yes = integer(report.get("water_initial_yes_count"), "water_initial_yes_count")
    water_no = integer(report.get("water_initial_no_count"), "water_initial_no_count")
    require(0 < checked <= EXPECTED_WORDS, "checked count is outside the declared universe")
    require(
        parent_yes >= 0 and parent_no >= 0 and parent_yes + parent_no == checked,
        "parent-checkpoint counts do not partition checked words",
    )
    require(
        water_yes >= 0 and water_no >= 0 and water_yes + water_no == water_checked,
        "water-initial counts do not partition mapped fallback layouts",
    )
    mapped = integer(
        report.get("parent_local_no_mapped_to_water_initial"),
        "parent_local_no_mapped_to_water_initial",
    )
    unresolved = integer(
        report.get("unresolved_parent_local_no_count"),
        "unresolved_parent_local_no_count",
    )
    replayed = integer(
        report.get("water_initial_witnesses_replayed"),
        "water_initial_witnesses_replayed",
    )
    require(mapped + unresolved == parent_no, "checkpoint-local-NO mapping does not partition local NOs")
    require(water_checked == mapped, "mapped checkpoint NO and water-initial fallback coverage differ")
    require(replayed == water_yes, "water-initial YES witness replay count mismatch")
    require(
        report.get("local_no_count") == unresolved + water_no,
        "final local-NO count does not include every unresolved fallback",
    )
    final_local_no = unresolved + water_no
    require(report.get("global_no_count", 0) == 0, "a local corner search claims a global NO")

    complete = checked == EXPECTED_WORDS
    require(report.get("universe_complete") is complete, "universe_complete disagrees with checked count")
    require(
        report.get("residual_word_universe_complete") is complete,
        "residual_word_universe_complete disagrees with checked count",
    )
    require(
        report.get("full_residual_word_coverage") is complete,
        "full_residual_word_coverage disagrees with checked count",
    )
    require(report.get("entry_family_eliminated") is False, "corner report overclaims the bridge entry family")
    require(report.get("full_layout_coverage") is False, "corner report overclaims all height-7 layouts")

    status = report.get("status")
    if not complete:
        require(status == "INCOMPLETE", "bounded report has a terminal status")
        require(status not in TERMINAL_STATUSES, "bounded run claimed completion")
        require(report.get("verified") is False, "bounded report is marked verified")
        require(report.get("corner_family_eliminated") is False, "bounded report eliminates the corner family")
    elif final_local_no == 0:
        require(status == "CORNER_FAMILY_ELIMINATED", "complete all-YES report lacks elimination status")
        require(report.get("verified") is True, "complete all-YES report is not verified")
        require(report.get("corner_family_eliminated") is True, "elimination status lacks its claim flag")
        require(report.get("first_water_initial_no") is None, "all-YES report contains a water-initial NO")
        require(
            parent_no == EXPECTED_PARENT_CHECKPOINT_LOCAL_NO,
            "complete corner audit did not isolate exactly the 126-word checkpoint kernel",
        )
        require(mapped == parent_no, "not every parent-checkpoint NO was mapped to a water initial layout")
        require(replayed == parent_no, "not every mapped checkpoint NO has a replayed water escape")
    else:
        require(status == "LOCAL_NO_RESIDUALS_EXPORTED", "local NO report uses an unsafe status")
        require(report.get("verified") is True, "complete local-NO report is not verified")
        require(report.get("corner_family_eliminated") is False, "local-NO report claims elimination")
        witness = (
            report.get("first_water_initial_no")
            if water_no != 0
            else report.get("first_parent_checkpoint_local_no")
        )
        require(isinstance(witness, dict), "local-NO report has no replayable witness")
        serialized = json.dumps(witness, sort_keys=True).lower()
        require("global" not in serialized or "not" in serialized, "local witness text suggests a global NO")

    rows = report.get("per_decoration")
    require(isinstance(rows, list) and len(rows) == EXPECTED_DECORATIONS, "bad per-decoration coverage")
    sum_checked = sum(integer(row.get("residual_words_checked"), "row checked") for row in rows if isinstance(row, dict))
    sum_parent_yes = sum(
        integer(row.get("parent_checkpoint_yes_count"), "row parent-checkpoint YES")
        for row in rows
        if isinstance(row, dict)
    )
    sum_parent_no = sum(
        integer(row.get("parent_checkpoint_local_no_count"), "row parent-checkpoint NO")
        for row in rows
        if isinstance(row, dict)
    )
    sum_water_checked = sum(
        integer(row.get("water_initial_layouts_checked"), "row water-initial checked")
        for row in rows
        if isinstance(row, dict)
    )
    sum_water_yes = sum(
        integer(row.get("water_initial_yes_count"), "row water-initial YES")
        for row in rows
        if isinstance(row, dict)
    )
    sum_water_no = sum(
        integer(row.get("water_initial_no_count"), "row water-initial NO")
        for row in rows
        if isinstance(row, dict)
    )
    require(len([row for row in rows if isinstance(row, dict)]) == len(rows), "decoration row is not an object")
    require(
        (
            sum_checked,
            sum_parent_yes,
            sum_parent_no,
            sum_water_checked,
            sum_water_yes,
            sum_water_no,
        )
        == (checked, parent_yes, parent_no, water_checked, water_yes, water_no),
        "per-decoration totals mismatch",
    )
    for ordinal, row in enumerate(rows):
        require(isinstance(row, dict), "decoration row is not an object")
        expected = integer(row.get("residual_words_expected"), f"row {ordinal} expected")
        require(row.get("decoration_index") == ordinal, "decoration ordering/index drifted")
        require(expected == EXPECTED_WEIGHTS[ordinal], "per-decoration word weight drifted")
        target = row.get("target_color")
        require(row.get("q_caps") == [1, 1, 1], "corner row lost q1,q1,q1")
        require(
            isinstance(target, int)
            and row.get("cards") == [[target, 3], [target, 3], [target, 3]],
            "corner row lost its three q1->x3 cards",
        )
        row_checked = integer(row.get("residual_words_checked"), f"row {ordinal} checked")
        row_parent_yes = integer(row.get("parent_checkpoint_yes_count"), f"row {ordinal} parent YES")
        row_parent_no = integer(row.get("parent_checkpoint_local_no_count"), f"row {ordinal} parent NO")
        row_water_checked = integer(row.get("water_initial_layouts_checked"), f"row {ordinal} water checked")
        row_water_yes = integer(row.get("water_initial_yes_count"), f"row {ordinal} water YES")
        row_water_no = integer(row.get("water_initial_no_count"), f"row {ordinal} water NO")
        require(0 < expected <= EXPECTED_WORDS, "bad per-decoration expected count")
        require(0 <= row_checked <= expected, "bad per-decoration checked count")
        require(
            row_parent_yes + row_parent_no == row_checked,
            "row parent classifications do not partition checked words",
        )
        require(
            row_water_yes + row_water_no == row_water_checked,
            "row water-initial classifications do not partition layouts",
        )

    for field in ("states_evaluated", "transitions_tested"):
        if field in report:
            require(integer(report[field], field) >= 0, f"{field} is negative")


def negative_tests(report: dict[str, object]) -> None:
    mutations = (
        ("entry_family_eliminated", True),
        ("full_layout_coverage", True),
        ("global_no_count", 1),
    )
    for field, value in mutations:
        broken = dict(report)
        broken[field] = value
        try:
            validate(broken)
        except AssertionError:
            continue
        fail(f"negative schema test accepted {field}={value!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("--negative-tests", action="store_true")
    args = parser.parse_args()
    report = load(args.report)
    validate(report)
    if args.negative_tests:
        negative_tests(report)
    print(
        f"validated {report['status']}: parent-checkpoint "
        f"{report['parent_checkpoint_yes_count']}/"
        f"{report['residual_words_checked']} YES; water fallback "
        f"{report['water_initial_yes_count']}/"
        f"{report['water_initial_layouts_checked']} YES"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
