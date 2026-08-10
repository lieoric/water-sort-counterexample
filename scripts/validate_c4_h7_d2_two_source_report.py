#!/usr/bin/env python3
"""Strict schema and claim-boundary validator for the D2 two-source audit."""

from __future__ import annotations

import argparse
import copy
import json
from collections import Counter
from pathlib import Path
from typing import NoReturn


SCOPE = "c4_h7_d2_reduction_two_legal_source_fixed_residuals"
HEIGHT = 7
EXPECTED_DECORATIONS = 190
EXPECTED_WORDS = 12_936
PREFIX_TEMPLATES = 20
EXPECTED_WATER_LAYOUTS = 258_720
EDGE_EXPECTED = {
    "exhaust-sibling-e245": (1, [2, 3, 3], 924),
    "exhaust-sibling-e246": (2, [1, 3, 3], 12_012),
}
STATUSES = {
    "INCOMPLETE",
    "TWO_SOURCE_D2_FAMILY_ELIMINATED",
    "LOCAL_NO_RESIDUALS_EXPORTED",
    "GLOBAL_NO_FOUND",
}


def fail(message: str) -> NoReturn:
    raise AssertionError(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def integer(value: object, label: str) -> int:
    require(isinstance(value, int) and not isinstance(value, bool), f"{label} is not an integer")
    return int(value)


def boolean(value: object, label: str) -> bool:
    require(isinstance(value, bool), f"{label} is not a Boolean")
    return bool(value)


def load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), "report root is not an object")
    return value


def validate_columns(
    sample: object,
    label: str,
    solvable: bool | None = None,
    balanced: bool = True,
) -> None:
    require(isinstance(sample, dict), f"{label} is not an object")
    if solvable is not None:
        require(sample.get("solvable") is solvable, f"{label}.solvable drifted")
    top = sample.get("columns_top_to_bottom")
    bottom = sample.get("columns_bottom_to_top")
    require(
        isinstance(top, list)
        and isinstance(bottom, list)
        and len(top) == len(bottom) == 4,
        f"{label} does not contain four columns",
    )
    require(
        all(isinstance(word, str) and len(word) == 7 and set(word) <= set("0123") for word in top),
        f"{label} contains an invalid top-to-bottom column",
    )
    require(bottom == [word[::-1] for word in top], f"{label} column orientations disagree")
    if balanced:
        require(Counter("".join(top)) == Counter({str(color): 7 for color in range(4)}), f"{label} is not color-balanced")
    mask = integer(sample.get("safe_mask"), f"{label}.safe_mask")
    require(0 <= mask < 16, f"{label}.safe_mask is outside four columns")
    path = sample.get("escape_columns")
    require(isinstance(path, str) and set(path) <= set("0123"), f"{label}.escape_columns is invalid")
    if solvable is True:
        require(mask != 0 and path, f"{label} has no positive replay witness")
    if solvable is False:
        require(mask == 0 and path == "", f"{label} labels a NO with an escape")


def validate_global_candidate_files(report_path: Path, report: dict[str, object]) -> None:
    candidate = report.get("first_global_no_candidate")
    validate_columns(candidate, "first_global_no_candidate", False)
    candidate_json_path = report_path.parent / "global-no-candidate.json"
    candidate_text_path = report_path.parent / "global-no-candidate.txt"
    require(candidate_json_path.is_file(), "GLOBAL_NO_FOUND lacks global-no-candidate.json")
    require(candidate_text_path.is_file(), "GLOBAL_NO_FOUND lacks global-no-candidate.txt")
    exported = json.loads(candidate_json_path.read_text(encoding="utf-8"))
    require(isinstance(exported, dict), "global candidate JSON root is not an object")
    require(exported.get("scope") == "complete_balanced_c4_h7_layout", "global candidate JSON scope drifted")
    require(exported.get("independently_verified") is False, "production must not self-claim independent verification")
    require(exported.get("candidate") == candidate, "global candidate JSON differs from report")
    lines = [
        line.split("=", 1)[1]
        for line in candidate_text_path.read_text(encoding="utf-8").splitlines()
        if line.startswith("column=")
    ]
    require(lines == candidate.get("columns_bottom_to_top"), "global candidate text differs from report")


def validate(report: dict[str, object], report_path: Path | None = None) -> None:
    require(report.get("schema_version") == 1, "unsupported schema version")
    require(report.get("coverage_scope") == SCOPE, "unexpected coverage scope")
    require(report.get("status") in STATUSES, "unsupported status")
    require(report.get("self_checks_passed") is True, "structural self-checks did not pass")
    require(report.get("limit_unit") == "edge_summed_fixed_residual_words", "limit unit drifted")
    require(isinstance(report.get("ordering"), str) and report.get("ordering"), "ordering declaration missing")
    require(
        report.get("source_first_exhaust_report")
        == {
            "legal_source_count": 2,
            "canonical_edges": 2,
            "d2_decorations": EXPECTED_DECORATIONS,
            "edge_summed_residual_words": EXPECTED_WORDS,
        },
        "source first-exhaust census drifted",
    )
    require(report.get("canonical_edge_count") == 2, "canonical edge count drifted")
    require(report.get("decorations_expected") == EXPECTED_DECORATIONS, "decoration count drifted")
    require(report.get("residual_words_expected") == EXPECTED_WORDS, "fixed-word universe drifted")
    require(report.get("past_prefix_templates_per_edge") == PREFIX_TEMPLATES, "past-prefix template count drifted")

    checked = integer(report.get("residual_words_checked"), "residual_words_checked")
    parent_yes = integer(report.get("parent_checkpoint_yes_count"), "parent_checkpoint_yes_count")
    parent_no = integer(report.get("parent_checkpoint_local_no_count"), "parent_checkpoint_local_no_count")
    recovered = integer(report.get("parent_local_no_recovered_count"), "parent_local_no_recovered_count")
    unresolved = integer(report.get("unresolved_parent_local_no_count"), "unresolved_parent_local_no_count")
    water_checked = integer(report.get("water_initial_layouts_checked"), "water_initial_layouts_checked")
    water_yes = integer(report.get("water_initial_yes_count"), "water_initial_yes_count")
    water_no = integer(report.get("water_initial_no_count"), "water_initial_no_count")
    witnesses = integer(report.get("water_initial_witnesses_replayed"), "water_initial_witnesses_replayed")
    require(0 < checked <= EXPECTED_WORDS, "checked count is outside the fixed-word universe")
    require(parent_yes == 0 and parent_no == checked, "the exact two-source P partition drifted")
    require(recovered + unresolved == parent_no, "parent local-NO recovery partition is incomplete")
    require(water_checked == checked * PREFIX_TEMPLATES, "not all 20 labelled past prefixes were checked")
    require(water_yes + water_no == water_checked, "water-initial YES/NO partition is incomplete")
    require(witnesses == water_yes, "a water-initial YES lacks a replayed witness")
    require(water_no >= unresolved, "an unresolved checkpoint word has no water-initial NO")
    require(water_no <= unresolved * PREFIX_TEMPLATES, "water-initial NO count exceeds unresolved words")
    require(report.get("local_no_count") == unresolved, "local_no_count is not the unresolved checkpoint count")
    require(report.get("global_no_count") == water_no, "water-initial NO was not counted as a global candidate")
    require(report.get("global_no_independently_verified") is False, "production report overclaims independent global verification")

    complete = checked == EXPECTED_WORDS
    require(boolean(report.get("universe_complete"), "universe_complete") is complete, "universe_complete disagrees with coverage")
    require(boolean(report.get("fixed_residual_universe_complete"), "fixed_residual_universe_complete") is complete, "fixed residual coverage flag disagrees")
    require(boolean(report.get("verified"), "verified") is complete, "verified flag disagrees with complete fixed-word coverage")
    require(report.get("d2_family_eliminated") is False, "two-source audit overclaims the full D2 remainder")
    require(report.get("entry_family_eliminated") is False, "two-source audit overclaims the first-exhaustion entry family")
    require(report.get("full_layout_coverage") is False, "two-source audit overclaims all c4/h7 layouts")

    eliminated = boolean(report.get("two_source_d2_family_eliminated"), "two_source_d2_family_eliminated")
    status = report["status"]
    if water_no:
        require(status == "GLOBAL_NO_FOUND", "a true water-initial NO was downgraded to a local claim")
        require(not eliminated, "GLOBAL_NO_FOUND also claims family elimination")
        if report_path is not None:
            validate_global_candidate_files(report_path, report)
    elif not complete:
        require(status == "INCOMPLETE", "bounded all-YES prefix has a terminal claim")
        require(not eliminated, "bounded report claims two-source family elimination")
    elif unresolved:
        require(status == "LOCAL_NO_RESIDUALS_EXPORTED", "unresolved checkpoint residuals lack conservative status")
        require(not eliminated, "unresolved report claims family elimination")
    else:
        require(status == "TWO_SOURCE_D2_FAMILY_ELIMINATED", "complete recovered family lacks exact status")
        require(eliminated, "elimination status lacks its narrow claim flag")
        require(recovered == EXPECTED_WORDS, "complete elimination did not recover every P-local-NO word")
        require(water_checked == EXPECTED_WATER_LAYOUTS and water_yes == EXPECTED_WATER_LAYOUTS, "complete elimination lacks all zero-debt layouts")

    per_decoration = report.get("per_decoration")
    require(isinstance(per_decoration, list) and len(per_decoration) == EXPECTED_DECORATIONS, "per-decoration ledger is incomplete")
    seen: set[tuple[str, tuple[tuple[int, int], ...]]] = set()
    decoration_sums = Counter()
    edge_sums: dict[str, Counter[str]] = {edge_id: Counter() for edge_id in EDGE_EXPECTED}
    for index, row in enumerate(per_decoration):
        require(isinstance(row, dict), f"per_decoration[{index}] is not an object")
        require(row.get("decoration_index") == index, f"per_decoration[{index}] index drifted")
        edge_id = row.get("edge_id")
        require(edge_id in EDGE_EXPECTED, f"per_decoration[{index}] has an unknown edge")
        cards = row.get("cards")
        require(isinstance(cards, list) and len(cards) == 3, f"per_decoration[{index}] cards are invalid")
        q_caps = EDGE_EXPECTED[edge_id][1]  # type: ignore[index]
        parsed_cards: list[tuple[int, int]] = []
        for slot, (card, cap) in enumerate(zip(cards, q_caps)):
            require(
                isinstance(card, list)
                and len(card) == 2
                and all(isinstance(value, int) and not isinstance(value, bool) for value in card),
                f"per_decoration[{index}].cards[{slot}] is invalid",
            )
            color, endpoint = card
            require(color in (1, 2, 3) and cap < endpoint <= HEIGHT, f"per_decoration[{index}].cards[{slot}] is outside its cap")
            parsed_cards.append((color, endpoint))
        identity = str(edge_id), tuple(parsed_cards)
        require(identity not in seen, f"duplicate decoration identity at index {index}")
        seen.add(identity)
        expected = integer(row.get("residual_words_expected"), f"per_decoration[{index}].expected")
        row_checked = integer(row.get("residual_words_checked"), f"per_decoration[{index}].checked")
        row_parent_yes = integer(row.get("parent_checkpoint_yes_count"), f"per_decoration[{index}].parent_yes")
        row_parent_no = integer(row.get("parent_checkpoint_local_no_count"), f"per_decoration[{index}].parent_no")
        row_water_checked = integer(row.get("water_initial_layouts_checked"), f"per_decoration[{index}].water_checked")
        row_water_yes = integer(row.get("water_initial_yes_count"), f"per_decoration[{index}].water_yes")
        row_water_no = integer(row.get("water_initial_no_count"), f"per_decoration[{index}].water_no")
        require(expected > 0 and 0 <= row_checked <= expected, f"per_decoration[{index}] coverage is invalid")
        require(row_parent_yes == 0 and row_parent_no == row_checked, f"per_decoration[{index}] parent partition drifted")
        require(row_water_checked == row_checked * PREFIX_TEMPLATES, f"per_decoration[{index}] missed past prefixes")
        require(row_water_yes + row_water_no == row_water_checked, f"per_decoration[{index}] water partition drifted")
        decoration_sums.update({
            "expected": expected,
            "checked": row_checked,
            "parent_yes": row_parent_yes,
            "parent_no": row_parent_no,
            "water_checked": row_water_checked,
            "water_yes": row_water_yes,
            "water_no": row_water_no,
        })
        edge_sums[str(edge_id)].update({"expected": expected, "checked": row_checked, "parent_yes": row_parent_yes, "parent_no": row_parent_no})
    require(decoration_sums == Counter({
        "expected": EXPECTED_WORDS,
        "checked": checked,
        "parent_yes": parent_yes,
        "parent_no": parent_no,
        "water_checked": water_checked,
        "water_yes": water_yes,
        "water_no": water_no,
    }), "per-decoration aggregates disagree with the report")

    per_edge = report.get("per_edge")
    require(isinstance(per_edge, list) and len(per_edge) == 2, "per-edge ledger is incomplete")
    require([row.get("edge_id") for row in per_edge if isinstance(row, dict)] == list(EDGE_EXPECTED), "per-edge semantic order drifted")
    for row in per_edge:
        require(isinstance(row, dict), "per-edge row is not an object")
        edge_id = str(row.get("edge_id"))
        bad_cap, q_caps, expected = EDGE_EXPECTED[edge_id]
        require(row.get("bad_cap") == bad_cap and row.get("q_caps") == q_caps, f"{edge_id} macro shape drifted")
        require(row.get("residual_words_expected") == expected, f"{edge_id} expected weight drifted")
        require(row.get("residual_words_checked") == edge_sums[edge_id]["checked"], f"{edge_id} checked aggregate drifted")
        require(row.get("parent_checkpoint_yes_count") == edge_sums[edge_id]["parent_yes"], f"{edge_id} parent YES aggregate drifted")
        require(row.get("parent_checkpoint_local_no_count") == edge_sums[edge_id]["parent_no"], f"{edge_id} parent NO aggregate drifted")

    checked_prefix = report.get("checked_prefix")
    require(isinstance(checked_prefix, list) and len(checked_prefix) == checked, "checked-prefix ledger is incomplete")
    prefix_water_yes = prefix_water_no = 0
    for ordinal, row in enumerate(checked_prefix):
        require(isinstance(row, dict), f"checked_prefix[{ordinal}] is not an object")
        decoration_index = integer(row.get("decoration_index"), f"checked_prefix[{ordinal}].decoration_index")
        require(0 <= decoration_index < EXPECTED_DECORATIONS, f"checked_prefix[{ordinal}] decoration index is invalid")
        decoration = per_decoration[decoration_index]
        cards = decoration["cards"]
        tails = row.get("free_tails_top_to_bottom")
        require(isinstance(tails, list) and len(tails) == 3, f"checked_prefix[{ordinal}] tails are invalid")
        for slot, (tail, card) in enumerate(zip(tails, cards)):
            require(isinstance(tail, str) and set(tail) <= set("0123"), f"checked_prefix[{ordinal}].tail[{slot}] is invalid")
            require(len(tail) == HEIGHT - card[1], f"checked_prefix[{ordinal}].tail[{slot}] length drifted")
            require(not tail or tail[0] != str(card[0]), f"checked_prefix[{ordinal}].tail[{slot}] merges into its card")
        require(row.get("parent_checkpoint_solvable") is False, f"checked_prefix[{ordinal}] unexpectedly solves P")
        require(row.get("parent_safe_mask") == 0 and row.get("parent_escape_columns") == "", f"checked_prefix[{ordinal}] P-NO has an escape")
        require(row.get("water_initial_layouts_checked") == PREFIX_TEMPLATES, f"checked_prefix[{ordinal}] missed a past template")
        prefix_yes = integer(row.get("water_initial_yes_count"), f"checked_prefix[{ordinal}].water_yes")
        prefix_no = integer(row.get("water_initial_no_count"), f"checked_prefix[{ordinal}].water_no")
        require(prefix_yes + prefix_no == PREFIX_TEMPLATES, f"checked_prefix[{ordinal}] water partition drifted")
        prefix_water_yes += prefix_yes
        prefix_water_no += prefix_no
    require(prefix_water_yes == water_yes and prefix_water_no == water_no, "checked-prefix water aggregates drifted")

    validate_columns(
        report.get("first_parent_checkpoint_local_no"),
        "first_parent_checkpoint_local_no",
        False,
        balanced=False,
    )
    if water_yes:
        validate_columns(report.get("first_water_initial_recovery"), "first_water_initial_recovery", True)


def run_negative_tests(report: dict[str, object]) -> None:
    mutations = (
        ("claim full D2", lambda value: value.__setitem__("d2_family_eliminated", True)),
        ("claim entry family", lambda value: value.__setitem__("entry_family_eliminated", True)),
        ("claim all layouts", lambda value: value.__setitem__("full_layout_coverage", True)),
        ("lose a past template", lambda value: value.__setitem__("past_prefix_templates_per_edge", 19)),
        ("miscount a global candidate", lambda value: value.__setitem__("global_no_count", value["water_initial_no_count"] + 1)),
        ("skip a zero-debt layout", lambda value: value.__setitem__("water_initial_layouts_checked", value["water_initial_layouts_checked"] - 1)),
        ("fake independent verification", lambda value: value.__setitem__("global_no_independently_verified", True)),
    )
    for label, mutate in mutations:
        candidate = copy.deepcopy(report)
        mutate(candidate)
        try:
            validate(candidate)
        except AssertionError:
            continue
        fail(f"negative test accepted mutation: {label}")
    if report.get("status") == "INCOMPLETE":
        candidate = copy.deepcopy(report)
        candidate["status"] = "TWO_SOURCE_D2_FAMILY_ELIMINATED"
        candidate["two_source_d2_family_eliminated"] = True
        try:
            validate(candidate)
        except AssertionError:
            pass
        else:
            fail("negative test accepted bounded family elimination")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--negative-tests", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = load(args.report)
    validate(report, args.report)
    if args.negative_tests:
        run_negative_tests(report)
    print(
        f"strict two-source report validation passed: status={report['status']} "
        f"fixed={report['residual_words_checked']}/{EXPECTED_WORDS} "
        f"water_no={report['water_initial_no_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
