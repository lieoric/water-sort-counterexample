#!/usr/bin/env python3
"""Strict evidence and claim-boundary validator for the c4/h7 D2 three-source audit.

This validator intentionally does not promote a fixed-future parent-checkpoint NO
to a zero-debt initial-layout counterexample.  The independent semantic checker in
tests/check_c4_h7_d2_three_source.py is responsible for rebuilding and solving the
enumerated universe; this script makes the emitted artifact set self-consistent.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
from collections import Counter
from pathlib import Path
from typing import NoReturn


TOTAL_DECORATIONS = 1_535
TOTAL_FUTURES = 1_106_490
BRIDGE = {
    "tq_terminals": 71,
    "labeled_candidates": 624,
    "canonical_parents": 418,
    "canonical_edges": 429,
    "sibling_edges": 423,
}
EDGE_ROWS = (
    (116, 198, 64_680),
    (117, 732, 252_252),
    (174, 263, 620_928),
    (175, 192, 51_744),
    (178, 104, 19_404),
    (184, 6, 462),
    (236, 8, 72_072),
    (237, 6, 11_088),
    (238, 4, 924),
    (242, 8, 11_088),
    (244, 6, 924),
    (248, 8, 924),
)
TSV_HEADER = (
    "future_index\tdecoration_index\tbridge_edge\tcards\t"
    "hidden_words_bottom_to_top\tlocal_status\tsafe_source_mask\tescape_columns"
)
ROOT_KEYS = {
    "schema_version",
    "experiment",
    "status",
    "parameters",
    "scope",
    "bridge_reconstruction",
    "universe",
    "run",
    "claims",
    "ledgers",
    "first_local_yes",
    "first_local_no",
    "per_edge",
    "self_checks_passed",
}
RUN_KEYS = {
    "limit_requested",
    "universe_complete",
    "fixed_futures_checked",
    "local_yes",
    "local_no",
    "winning_paths_replayed",
    "states",
    "transitions",
    "elapsed_seconds",
}
PER_EDGE_KEYS = {
    "bridge_edge",
    "decorations",
    "fixed_futures_expected",
    "fixed_futures_checked",
    "local_yes",
    "local_no",
    "states",
    "transitions",
    "safe_mask_distribution",
}
SAMPLE_KEYS = {
    "future_index",
    "decoration_index",
    "bridge_edge",
    "local_status",
    "safe_source_mask",
    "escape_columns",
    "hidden_words_bottom_to_top",
}
LOCAL_NO_KEYS = {
    "future_index",
    "decoration_index",
    "bridge_edge",
    "parent_debts",
    "bad_source",
    "q_color",
    "q_caps",
    "cards",
    "hidden_words_bottom_to_top",
    "local_status",
    "safe_source_mask",
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


def exact_keys(value: object, keys: set[str], label: str) -> dict[str, object]:
    require(isinstance(value, dict), f"{label} is not an object")
    actual = set(value)
    require(actual == keys, f"{label} keys drifted: missing={sorted(keys - actual)} extra={sorted(actual - keys)}")
    return value


def fnv1a64_rows(lines: list[str]) -> str:
    # This is the historical offset used by the production experiment.  It is
    # deliberately reproduced exactly rather than replaced by the standard
    # FNV-1a offset basis.
    value = 1_469_598_103_934_665_603
    for line in lines:
        for byte in (line + "\n").encode("utf-8"):
            value ^= byte
            value = (value * 1_099_511_628_211) & 0xFFFFFFFFFFFFFFFF
    return f"{value:016x}"


def parse_words(text: str, label: str) -> list[str]:
    words = text.split(",")
    require(len(words) == 4, f"{label} does not contain four physical columns")
    require(
        all(word and len(word) <= 7 and set(word) <= set("0123") for word in words),
        f"{label} contains an invalid bottom-to-top word",
    )
    return words


def parse_cards(text: str, label: str) -> list[list[int]]:
    fields = text.split(",")
    require(len(fields) == 3, f"{label} does not contain three q cards")
    cards: list[list[int]] = []
    for slot, field in enumerate(fields):
        parts = field.split(":")
        require(len(parts) == 2 and all(part.isdigit() for part in parts), f"{label}[{slot}] is malformed")
        color, endpoint = map(int, parts)
        require(0 <= color < 4 and 1 <= endpoint <= 7, f"{label}[{slot}] is outside c4/h7")
        cards.append([color, endpoint])
    return cards


def validate_sample(sample: object, label: str, expected: dict[str, object] | None) -> None:
    if expected is None:
        require(sample is None, f"{label} exists although the corresponding class is empty")
        return
    row = exact_keys(sample, SAMPLE_KEYS, label)
    require(row == expected, f"{label} does not match the first corresponding TSV row")


def load_report(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    return exact_keys(value, ROOT_KEYS, "report")


def validate_report(report: dict[str, object], report_path: Path) -> None:
    require(report.get("schema_version") == 1, "unsupported schema version")
    require(report.get("experiment") == "c4_h7_d2_three_source_checkpoint", "experiment name drifted")
    require(report.get("parameters") == {"colors": 4, "height": 7, "empty": 2}, "parameter tuple drifted")
    require(
        report.get("scope")
        == {
            "parent_checkpoint_only": True,
            "fixed_hidden_futures": True,
            "zero_debt_past_restored": False,
            "full_h7_theorem": False,
        },
        "scope overclaims a zero-debt or full-h7 result",
    )
    require(report.get("bridge_reconstruction") == BRIDGE, "bridge reconstruction census drifted")
    require(
        report.get("universe")
        == {"selected_edges": 12, "decorations": TOTAL_DECORATIONS, "labeled_fixed_futures": TOTAL_FUTURES},
        "three-source universe census drifted",
    )
    require(report.get("self_checks_passed") is True, "production structural self-checks did not pass")

    run = exact_keys(report.get("run"), RUN_KEYS, "run")
    limit = integer(run.get("limit_requested"), "run.limit_requested")
    checked = integer(run.get("fixed_futures_checked"), "run.fixed_futures_checked")
    local_yes = integer(run.get("local_yes"), "run.local_yes")
    local_no = integer(run.get("local_no"), "run.local_no")
    replayed = integer(run.get("winning_paths_replayed"), "run.winning_paths_replayed")
    states = integer(run.get("states"), "run.states")
    transitions = integer(run.get("transitions"), "run.transitions")
    elapsed = run.get("elapsed_seconds")
    require(limit >= 0, "negative limit requested")
    expected_checked = TOTAL_FUTURES if limit == 0 else min(limit, TOTAL_FUTURES)
    require(checked == expected_checked, "checked count is not the exact requested prefix")
    require(local_yes >= 0 and local_no >= 0 and local_yes + local_no == checked, "local YES/NO partition is invalid")
    require(replayed == local_yes, "a local YES path was not replayed")
    require(states >= checked and transitions >= 0, "DP counters are invalid")
    require(isinstance(elapsed, (int, float)) and not isinstance(elapsed, bool), "elapsed_seconds is not numeric")
    require(math.isfinite(float(elapsed)) and float(elapsed) >= 0.0, "elapsed_seconds is invalid")
    complete = checked == TOTAL_FUTURES
    require(boolean(run.get("universe_complete"), "run.universe_complete") is complete, "coverage flag disagrees with checked count")

    claims = report.get("claims")
    require(isinstance(claims, dict), "claims is not an object")
    require(
        set(claims)
        == {"three_source_checkpoint_family_eliminated", "zero_debt_initial_family_eliminated", "universal_c4_h7_solvability"},
        "claim keys drifted",
    )
    eliminated = complete and local_no == 0
    require(claims.get("three_source_checkpoint_family_eliminated") is eliminated, "narrow checkpoint claim disagrees with evidence")
    require(claims.get("zero_debt_initial_family_eliminated") is False, "report promotes checkpoint evidence to zero debt")
    require(claims.get("universal_c4_h7_solvability") is False, "report promotes checkpoint evidence to the full h7 theorem")
    expected_status = (
        "INCOMPLETE"
        if not complete
        else "LOCAL_NO_RESIDUALS_EXPORTED"
        if local_no
        else "THREE_SOURCE_D2_CHECKPOINT_FAMILY_ELIMINATED"
    )
    require(report.get("status") == expected_status, "status is not the conservative checkpoint status")

    per_edge = report.get("per_edge")
    require(isinstance(per_edge, list) and len(per_edge) == len(EDGE_ROWS), "per-edge ledger is incomplete")
    remaining = checked
    edge_totals = Counter()
    for ordinal, (row, expected) in enumerate(zip(per_edge, EDGE_ROWS)):
        value = exact_keys(row, PER_EDGE_KEYS, f"per_edge[{ordinal}]")
        edge, decorations, futures = expected
        row_checked = min(remaining, futures)
        remaining -= row_checked
        require(value.get("bridge_edge") == edge, f"per_edge[{ordinal}] edge/order drifted")
        require(value.get("decorations") == decorations, f"edge {edge} decoration census drifted")
        require(value.get("fixed_futures_expected") == futures, f"edge {edge} future census drifted")
        require(value.get("fixed_futures_checked") == row_checked, f"edge {edge} is not the expected checked prefix")
        row_yes = integer(value.get("local_yes"), f"edge {edge}.local_yes")
        row_no = integer(value.get("local_no"), f"edge {edge}.local_no")
        row_states = integer(value.get("states"), f"edge {edge}.states")
        row_transitions = integer(value.get("transitions"), f"edge {edge}.transitions")
        require(row_yes >= 0 and row_no >= 0 and row_yes + row_no == row_checked, f"edge {edge} local partition is invalid")
        require(row_states >= row_checked and row_transitions >= 0, f"edge {edge} DP counters are invalid")
        masks = value.get("safe_mask_distribution")
        require(isinstance(masks, dict), f"edge {edge} mask distribution is not an object")
        parsed_masks = Counter()
        for key, count in masks.items():
            require(isinstance(key, str) and key.isdigit() and 0 <= int(key) < 16, f"edge {edge} has an invalid safe mask")
            parsed_masks[int(key)] = integer(count, f"edge {edge}.mask[{key}]")
            require(parsed_masks[int(key)] > 0, f"edge {edge} records a nonpositive mask count")
        require(sum(parsed_masks.values()) == row_checked, f"edge {edge} mask counts do not cover checked rows")
        require(parsed_masks[0] == row_no, f"edge {edge} mask zero is not exactly local NO")
        edge_totals.update(checked=row_checked, yes=row_yes, no=row_no, states=row_states, transitions=row_transitions)
    require(remaining == 0, "checked prefix extends past the expected edge universe")
    require(
        edge_totals == Counter(checked=checked, yes=local_yes, no=local_no, states=states, transitions=transitions),
        "per-edge aggregates disagree with run totals",
    )

    ledgers = report.get("ledgers")
    require(
        isinstance(ledgers, dict)
        and set(ledgers) == {"fixed_future_results", "local_no", "result_rows_fnv1a64"},
        "ledger declaration drifted",
    )
    require(ledgers.get("fixed_future_results") == "fixed-future-results.tsv", "unexpected fixed-result ledger path")
    require(ledgers.get("local_no") == "local-no-ledger.jsonl", "unexpected local-NO ledger path")
    declared_hash = ledgers.get("result_rows_fnv1a64")
    require(
        isinstance(declared_hash, str) and len(declared_hash) == 16 and set(declared_hash) <= set("0123456789abcdef"),
        "result row hash is not lowercase 64-bit hex",
    )

    directory = report_path.parent
    result_path = directory / "fixed-future-results.tsv"
    no_path = directory / "local-no-ledger.jsonl"
    require(result_path.is_file(), "fixed-future-results.tsv is missing")
    require(no_path.is_file(), "local-no-ledger.jsonl is missing")
    require((directory / "report.md").is_file(), "report.md is missing")
    raw_lines = result_path.read_text(encoding="utf-8").splitlines()
    require(raw_lines and raw_lines[0] == TSV_HEADER, "fixed-result TSV header drifted")
    data_lines = raw_lines[1:]
    require(len(data_lines) == checked, "fixed-result TSV does not contain exactly the checked prefix")
    require(fnv1a64_rows(data_lines) == declared_hash, "fixed-result TSV FNV-1a hash mismatch")

    tsv_rows: list[dict[str, object]] = []
    tsv_no_rows: list[dict[str, object]] = []
    tsv_yes = 0
    edge_from_tsv: Counter[tuple[int, str]] = Counter()
    first_yes: dict[str, object] | None = None
    first_no: dict[str, object] | None = None
    previous_decoration = -1
    for future_index, line in enumerate(data_lines):
        fields = line.split("\t")
        require(len(fields) == 8, f"TSV row {future_index} does not have eight fields")
        require(fields[0].isdigit() and int(fields[0]) == future_index, f"TSV row {future_index} index drifted")
        require(fields[1].isdigit(), f"TSV row {future_index} decoration index is invalid")
        decoration = int(fields[1])
        require(previous_decoration <= decoration < TOTAL_DECORATIONS, f"TSV row {future_index} decoration order is invalid")
        previous_decoration = decoration
        require(fields[2].isdigit(), f"TSV row {future_index} edge is invalid")
        edge = int(fields[2])
        require(edge in {item[0] for item in EDGE_ROWS}, f"TSV row {future_index} has an unknown selected edge")
        cards = parse_cards(fields[3], f"TSV row {future_index}.cards")
        words = parse_words(fields[4], f"TSV row {future_index}.words")
        status = fields[5]
        require(fields[6].isdigit(), f"TSV row {future_index} safe mask is invalid")
        mask = int(fields[6])
        path = fields[7]
        require(set(path) <= set("0123"), f"TSV row {future_index} path has an invalid source")
        if status == "YES":
            require(0 < mask < 16 and path, f"TSV row {future_index} local YES lacks a witness")
            tsv_yes += 1
        else:
            require(status == "NO", f"TSV row {future_index} has an unknown local status")
            require(mask == 0 and not path, f"TSV row {future_index} local NO has a witness")
        sample = {
            "future_index": future_index,
            "decoration_index": decoration,
            "bridge_edge": edge,
            "local_status": status,
            "safe_source_mask": mask,
            "escape_columns": path,
            "hidden_words_bottom_to_top": words,
        }
        detailed = {**sample, "cards": cards}
        tsv_rows.append(detailed)
        edge_from_tsv[edge, status] += 1
        if status == "YES" and first_yes is None:
            first_yes = sample
        if status == "NO":
            tsv_no_rows.append(detailed)
            if first_no is None:
                first_no = sample
    require(tsv_yes == local_yes and len(tsv_no_rows) == local_no, "TSV local partition disagrees with report")
    for row in per_edge:
        assert isinstance(row, dict)
        edge = int(row["bridge_edge"])
        require(edge_from_tsv[edge, "YES"] == row["local_yes"], f"edge {edge} TSV YES count drifted")
        require(edge_from_tsv[edge, "NO"] == row["local_no"], f"edge {edge} TSV NO count drifted")
    validate_sample(report.get("first_local_yes"), "first_local_yes", first_yes)
    validate_sample(report.get("first_local_no"), "first_local_no", first_no)

    no_lines = no_path.read_text(encoding="utf-8").splitlines()
    require(len(no_lines) == local_no, "local-NO ledger line count disagrees with the report")
    for ordinal, (raw, tsv_row) in enumerate(zip(no_lines, tsv_no_rows)):
        value = json.loads(raw)
        row = exact_keys(value, LOCAL_NO_KEYS, f"local_no[{ordinal}]")
        require(row.get("local_status") == "NO" and row.get("safe_source_mask") == 0, f"local_no[{ordinal}] is not a local NO")
        for key in ("future_index", "decoration_index", "bridge_edge", "hidden_words_bottom_to_top", "cards"):
            require(row.get(key) == tsv_row[key], f"local_no[{ordinal}].{key} disagrees with TSV")
        debts = row.get("parent_debts")
        require(
            isinstance(debts, list)
            and len(debts) == 4
            and all(isinstance(value, int) and not isinstance(value, bool) for value in debts)
            and sum(debts) == 0,
            f"local_no[{ordinal}] parent debts are invalid",
        )
        bad = row.get("bad_source")
        require(
            isinstance(bad, list)
            and len(bad) == 3
            and all(isinstance(value, int) and not isinstance(value, bool) for value in bad)
            and 0 <= bad[0] < 4
            and 0 <= bad[1] <= 7
            and 0 <= bad[2] < 4,
            f"local_no[{ordinal}] bad source is invalid",
        )
        require(isinstance(row.get("q_color"), int) and 0 <= int(row["q_color"]) < 4, f"local_no[{ordinal}] q color is invalid")
        q_caps = row.get("q_caps")
        require(
            isinstance(q_caps, list)
            and len(q_caps) == 3
            and all(isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 7 for value in q_caps),
            f"local_no[{ordinal}] q caps are invalid",
        )


def run_negative_tests(report: dict[str, object], report_path: Path) -> None:
    mutations = (
        ("claim zero-debt elimination", lambda value: value["claims"].__setitem__("zero_debt_initial_family_eliminated", True)),
        ("claim the full h7 theorem", lambda value: value["claims"].__setitem__("universal_c4_h7_solvability", True)),
        ("erase parent-checkpoint scope", lambda value: value["scope"].__setitem__("parent_checkpoint_only", False)),
        ("claim a global NO status", lambda value: value.__setitem__("status", "GLOBAL_NO_FOUND")),
        ("alter the bridge census", lambda value: value["bridge_reconstruction"].__setitem__("canonical_edges", 430)),
        ("alter the TSV hash", lambda value: value["ledgers"].__setitem__("result_rows_fnv1a64", "0" * 16)),
    )
    for label, mutate in mutations:
        candidate = copy.deepcopy(report)
        mutate(candidate)
        try:
            validate_report(candidate, report_path)
        except AssertionError:
            continue
        fail(f"negative test accepted mutation: {label}")
    if report["status"] == "INCOMPLETE":
        candidate = copy.deepcopy(report)
        candidate["status"] = "THREE_SOURCE_D2_CHECKPOINT_FAMILY_ELIMINATED"
        candidate["claims"]["three_source_checkpoint_family_eliminated"] = True
        try:
            validate_report(candidate, report_path)
        except AssertionError:
            pass
        else:
            fail("negative test accepted bounded checkpoint-family elimination")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--negative-tests", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = load_report(args.report)
    validate_report(report, args.report)
    if args.negative_tests:
        run_negative_tests(report, args.report)
    run = report["run"]
    assert isinstance(run, dict)
    print(
        "strict three-source checkpoint validation passed: "
        f"status={report['status']} fixed={run['fixed_futures_checked']}/{TOTAL_FUTURES} "
        f"checkpoint_local_no={run['local_no']} global_no_claimed=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
