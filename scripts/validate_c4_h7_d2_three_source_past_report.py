#!/usr/bin/env python3
"""Strict artifact validator for the c4/h7 three-source past run.

This script validates production schema, exact finite-universe accounting,
the row ledger and its hash, candidate export, and claim boundaries.  It does
not independently solve layouts; that is the role of
tests/check_c4_h7_d2_three_source_past.py.  In particular, a DP NO remains an
``INITIAL_NO_CANDIDATES_EXPORTED`` result until water-oracle emits a closure
certificate and water-verify accepts it.
"""

from __future__ import annotations

import argparse
import copy
from collections import Counter
import json
from pathlib import Path
from typing import NoReturn


HEIGHT = 7
COLORS = 4
BALANCED = 285_600
REACHABLE = 281_904
UNREACHABLE = 3_696
FNV_OFFSET = 1_469_598_103_934_665_603
FNV_PRIME = 1_099_511_628_211
RESULT_HEADER = (
    "restoration_index\tfuture_index\tbridge_edge\tprefix_index\t"
    "parent_reachable\tcolumns_top_to_bottom\tinitial_status\t"
    "safe_source_mask\tescape_columns"
)

EDGE_SPECS = (
    # edge, debts, caps, local NO, M, T, H
    (116, [-4, 0, 1, 3], [4, 1, 1, 5], 210, 140, 140, 1_184),
    (117, [-4, 0, 2, 2], [4, 1, 1, 5], 252, 210, 210, 2_076),
    (184, [-3, 0, 1, 2], [2, 2, 2, 4], 462, 60, 60, 348),
    (236, [-2, 0, 1, 1], [2, 1, 1, 3], 924, 6, 6, 12),
    (242, [-2, 0, 1, 1], [2, 1, 2, 3], 11_088, 12, 12, 26),
    (244, [-2, 0, 1, 1], [2, 1, 2, 4], 924, 20, 16, 30),
    (248, [-2, 0, 1, 1], [2, 2, 2, 3], 924, 20, 20, 44),
)

ROOT_KEYS = {
    "schema_version",
    "experiment",
    "status",
    "parameters",
    "input",
    "scope",
    "universe",
    "run",
    "claims",
    "ledgers",
    "first_initial_yes",
    "first_initial_no",
    "per_edge",
    "self_checks_passed",
}
RUN_KEYS = {
    "limit_requested",
    "universe_complete",
    "restorations_checked",
    "reachable_checked",
    "unreachable_checked",
    "initial_yes",
    "initial_no",
    "winning_paths_replayed",
    "canonical_classes_solved",
    "symmetry_cache_hits",
    "states",
    "transitions",
    "elapsed_seconds",
}
CLAIM_KEYS = {
    "restoration_family_eliminated",
    "reachable_past_family_eliminated",
    "universal_c4_h7_solvability",
    "initial_no_candidates_found",
    "global_no_certified",
    "global_no_independently_verified",
    "independent_verification_complete",
}
SAMPLE_KEYS = {
    "restoration_index",
    "future_index",
    "bridge_edge",
    "prefix_index",
    "parent_reachable",
    "initial_status",
    "columns_top_to_bottom",
    "columns_bottom_to_top",
    "safe_source_mask",
    "escape_columns",
}
PER_EDGE_KEYS = {
    "bridge_edge",
    "parent_debts",
    "caps",
    "checkpoint_local_no",
    "prefix_candidates",
    "prefix_reachable",
    "legal_prefix_histories",
    "balanced_restorations_expected",
    "reachable_restorations_expected",
    "restorations_checked",
    "reachable_checked",
    "initial_yes",
    "initial_no",
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


def exact_object(value: object, keys: set[str], label: str) -> dict[str, object]:
    require(isinstance(value, dict), f"{label} is not an object")
    actual = set(value)
    require(actual == keys, f"{label} keys drifted: missing={sorted(keys - actual)} extra={sorted(actual - keys)}")
    return value


def fnv_rows(rows: list[str]) -> str:
    value = FNV_OFFSET
    for row in rows:
        for byte in (row + "\n").encode("utf-8"):
            value ^= byte
            value = (value * FNV_PRIME) & 0xFFFFFFFFFFFFFFFF
    return f"{value:016x}"


def parse_words(value: object, label: str) -> list[str]:
    require(isinstance(value, list) and len(value) == COLORS, f"{label} does not have four columns")
    require(all(isinstance(word, str) and len(word) == HEIGHT and set(word) <= set("0123") for word in value), f"{label} has an invalid column")
    inventory = Counter("".join(value))
    require(inventory == Counter({str(color): HEIGHT for color in range(COLORS)}), f"{label} is not balanced")
    return value


def validate_sample(value: object, label: str, expected_status: str | None = None) -> dict[str, object] | None:
    if value is None:
        return None
    sample = exact_object(value, SAMPLE_KEYS, label)
    require(integer(sample["restoration_index"], f"{label}.restoration_index") >= 0, f"{label} has a negative index")
    require(integer(sample["future_index"], f"{label}.future_index") >= 0, f"{label} has a negative future")
    require(integer(sample["bridge_edge"], f"{label}.bridge_edge") in {item[0] for item in EDGE_SPECS}, f"{label} has an unknown edge")
    require(integer(sample["prefix_index"], f"{label}.prefix_index") >= 0, f"{label} has a negative prefix")
    boolean(sample["parent_reachable"], f"{label}.parent_reachable")
    status = sample["initial_status"]
    require(status in {"YES", "NO"}, f"{label} has an unsafe status")
    if expected_status is not None:
        require(status == expected_status, f"{label} status differs")
    top = parse_words(sample["columns_top_to_bottom"], f"{label}.columns_top_to_bottom")
    bottom = parse_words(sample["columns_bottom_to_top"], f"{label}.columns_bottom_to_top")
    require(bottom == [word[::-1] for word in top], f"{label} top/bottom words disagree")
    mask = integer(sample["safe_source_mask"], f"{label}.safe_source_mask")
    path = sample["escape_columns"]
    require(isinstance(path, str) and set(path) <= set("0123"), f"{label} has an invalid path")
    if status == "NO":
        require(mask == 0 and path == "", f"{label} NO carries a winning witness")
    else:
        require(mask != 0 and path != "", f"{label} YES lacks a winning witness")
    return sample


def validate_result_ledger(path: Path, report: dict[str, object]) -> tuple[list[str], Counter[int], Counter[int], Counter[int]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    require(bool(lines) and lines[0] == RESULT_HEADER, "initial-results.tsv header drifted")
    rows = lines[1:]
    run = report["run"]
    assert isinstance(run, dict)
    require(len(rows) == integer(run["restorations_checked"], "run.restorations_checked"), "result row count differs from report")
    checked: Counter[int] = Counter()
    reachable: Counter[int] = Counter()
    no: Counter[int] = Counter()
    yes = 0
    for ordinal, line in enumerate(rows):
        fields = line.split("\t")
        require(len(fields) == 9, f"result row {ordinal} field count drifted")
        require(integer(int(fields[0]), f"result[{ordinal}].restoration_index") == ordinal, f"result row {ordinal} is out of order")
        edge = int(fields[2])
        require(edge in {item[0] for item in EDGE_SPECS}, f"result row {ordinal} has an unknown edge")
        require(fields[4] in {"0", "1"}, f"result row {ordinal} has bad reachability")
        columns = fields[5].split(",")
        parse_words(columns, f"result[{ordinal}].columns")
        require(fields[6] in {"YES", "NO"}, f"result row {ordinal} has an unsafe status")
        mask = int(fields[7])
        require(0 <= mask < 1 << COLORS, f"result row {ordinal} has an invalid mask")
        require(set(fields[8]) <= set("0123"), f"result row {ordinal} has an invalid path")
        if fields[6] == "NO":
            require(mask == 0 and fields[8] == "", f"result row {ordinal} NO carries a witness")
            no[edge] += 1
        else:
            require(mask != 0 and fields[8] != "", f"result row {ordinal} YES lacks a witness")
            yes += 1
        checked[edge] += 1
        reachable[edge] += fields[4] == "1"
    require(yes == integer(run["initial_yes"], "run.initial_yes"), "result YES count differs")
    require(sum(no.values()) == integer(run["initial_no"], "run.initial_no"), "result NO count differs")
    return rows, checked, reachable, no


def validate_no_ledger(path: Path, expected: int, first_no: object) -> None:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    require(len(rows) == expected, "initial-NO candidate ledger count differs")
    for ordinal, row in enumerate(rows):
        value = exact_object(row, {"scope", "independently_verified", "candidate"}, f"initial_no[{ordinal}]")
        require(value["scope"] == "complete_balanced_c4_h7_layout", f"initial_no[{ordinal}] lost complete-layout scope")
        require(value["independently_verified"] is False, f"initial_no[{ordinal}] self-claims independence")
        validate_sample(value["candidate"], f"initial_no[{ordinal}].candidate", "NO")
    if rows:
        require(rows[0]["candidate"] == first_no, "first initial-NO sample differs from candidate ledger")


def validate_report(report: dict[str, object], report_path: Path) -> None:
    exact_object(report, ROOT_KEYS, "report")
    require(integer(report["schema_version"], "schema_version") == 1, "schema version drifted")
    require(report["experiment"] == "c4_h7_d2_three_source_past_restoration", "wrong experiment")
    require(report["status"] in {"INCOMPLETE", "INITIAL_NO_CANDIDATES_EXPORTED", "THREE_SOURCE_PAST_FAMILY_ELIMINATED"}, "unsafe status")
    require(report["parameters"] == {"colors": 4, "height": 7, "empty": 2}, "parameter drift")
    require(report["input"] == {"checkpoint_report": "report.json", "checkpoint_status": "LOCAL_NO_RESIDUALS_EXPORTED", "fixed_futures": 1_106_490, "checkpoint_local_no": 14_784}, "input fixture drift")
    require(report["scope"] == {"balanced_completion_superset_only": True, "checkpoint_reachable_subset_tracked": True, "full_h7_theorem": False}, "scope drift")
    require(report["universe"] == {"parent_families": 7, "checkpoint_local_no_rows": 14_784, "balanced_restorations": BALANCED, "reachable_restorations": REACHABLE, "unreachable_balanced_completions": UNREACHABLE}, "universe drift")

    run = exact_object(report["run"], RUN_KEYS, "run")
    limit = integer(run["limit_requested"], "run.limit_requested")
    complete = boolean(run["universe_complete"], "run.universe_complete")
    checked_total = integer(run["restorations_checked"], "run.restorations_checked")
    reachable_total = integer(run["reachable_checked"], "run.reachable_checked")
    unreachable_total = integer(run["unreachable_checked"], "run.unreachable_checked")
    initial_yes = integer(run["initial_yes"], "run.initial_yes")
    initial_no = integer(run["initial_no"], "run.initial_no")
    require(0 <= checked_total <= BALANCED, "checked total outside universe")
    require(reachable_total + unreachable_total == checked_total, "reachability does not partition checked rows")
    require(initial_yes + initial_no == checked_total, "YES/NO does not partition checked rows")
    require(integer(run["winning_paths_replayed"], "run.winning_paths_replayed") == initial_yes, "a YES witness was not replayed")
    require(integer(run["canonical_classes_solved"], "run.canonical_classes_solved") + integer(run["symmetry_cache_hits"], "run.symmetry_cache_hits") == checked_total, "symmetry accounting does not partition rows")
    require(integer(run["states"], "run.states") >= 0 and integer(run["transitions"], "run.transitions") >= 0, "negative search accounting")
    require(isinstance(run["elapsed_seconds"], (int, float)) and not isinstance(run["elapsed_seconds"], bool) and run["elapsed_seconds"] >= 0, "invalid elapsed time")
    require(complete == (checked_total == BALANCED), "universe_complete differs from checked count")
    if complete:
        require(limit == 0, "full run unexpectedly used a bound")
        require(reachable_total == REACHABLE and unreachable_total == UNREACHABLE, "full reachability split drifted")
    else:
        require(limit > 0 and checked_total == min(limit, BALANCED), "bounded limit accounting drifted")

    expected_status = "INITIAL_NO_CANDIDATES_EXPORTED" if initial_no else "THREE_SOURCE_PAST_FAMILY_ELIMINATED" if complete else "INCOMPLETE"
    require(report["status"] == expected_status, "status does not follow run evidence")
    eliminated = complete and initial_no == 0
    claims = exact_object(report["claims"], CLAIM_KEYS, "claims")
    require(claims["restoration_family_eliminated"] is eliminated, "restoration-family claim drifted")
    require(claims["reachable_past_family_eliminated"] is eliminated, "reachable-family claim drifted")
    require(claims["initial_no_candidates_found"] is (initial_no != 0), "candidate claim drifted")
    require(claims["universal_c4_h7_solvability"] is False, "report overclaims universal h7")
    require(claims["global_no_certified"] is False, "production report self-certifies a global NO")
    require(claims["global_no_independently_verified"] is False, "production report self-claims independent verification")
    require(claims["independent_verification_complete"] is False, "production report self-claims independent audit")

    ledgers = exact_object(report["ledgers"], {"initial_results", "initial_no_candidates", "result_rows_fnv1a64"}, "ledgers")
    require(ledgers["initial_results"] == "initial-results.tsv", "result ledger name drifted")
    require(ledgers["initial_no_candidates"] == "initial-no-candidates.jsonl", "NO ledger name drifted")
    require(isinstance(ledgers["result_rows_fnv1a64"], str) and len(ledgers["result_rows_fnv1a64"]) == 16, "result hash shape drifted")
    rows, row_checked, row_reachable, row_no = validate_result_ledger(report_path.parent / "initial-results.tsv", report)
    require(fnv_rows(rows) == ledgers["result_rows_fnv1a64"], "result row hash drifted")

    per_edge = report["per_edge"]
    require(isinstance(per_edge, list) and len(per_edge) == len(EDGE_SPECS), "per_edge shape drifted")
    for ordinal, expected in enumerate(EDGE_SPECS):
        edge, debts, caps, local_no_rows, candidates, prefix_reachable, histories = expected
        value = exact_object(per_edge[ordinal], PER_EDGE_KEYS, f"per_edge[{ordinal}]")
        require(value["bridge_edge"] == edge and value["parent_debts"] == debts and value["caps"] == caps, f"per_edge[{ordinal}] fixture drifted")
        require(value["checkpoint_local_no"] == local_no_rows, f"edge {edge}: local-NO census drifted")
        require(value["prefix_candidates"] == candidates and value["prefix_reachable"] == prefix_reachable and value["legal_prefix_histories"] == histories, f"edge {edge}: prefix census drifted")
        require(value["balanced_restorations_expected"] == local_no_rows * candidates, f"edge {edge}: balanced expectation drifted")
        require(value["reachable_restorations_expected"] == local_no_rows * prefix_reachable, f"edge {edge}: reachable expectation drifted")
        require(value["restorations_checked"] == row_checked[edge], f"edge {edge}: checked rows differ")
        require(value["reachable_checked"] == row_reachable[edge], f"edge {edge}: reachable rows differ")
        require(value["initial_no"] == row_no[edge], f"edge {edge}: NO rows differ")
        require(value["initial_yes"] + value["initial_no"] == value["restorations_checked"], f"edge {edge}: statuses do not partition rows")
        if complete:
            require(value["restorations_checked"] == value["balanced_restorations_expected"], f"edge {edge}: full coverage drifted")
            require(value["reachable_checked"] == value["reachable_restorations_expected"], f"edge {edge}: full reachable coverage drifted")
    require(sum(row_checked.values()) == checked_total and sum(row_reachable.values()) == reachable_total, "per-edge totals drifted")

    first_yes = validate_sample(report["first_initial_yes"], "first_initial_yes", "YES")
    first_no = validate_sample(report["first_initial_no"], "first_initial_no", "NO")
    require((first_yes is None) == (initial_yes == 0), "first YES presence drifted")
    require((first_no is None) == (initial_no == 0), "first NO presence drifted")
    validate_no_ledger(report_path.parent / "initial-no-candidates.jsonl", initial_no, first_no)
    require(report["self_checks_passed"] is True, "production self-checks failed")

    candidate_json = report_path.parent / "initial-no-candidate.json"
    candidate_text = report_path.parent / "initial-no-candidate.txt"
    if initial_no:
        require(candidate_json.is_file() and candidate_text.is_file(), "NO run did not export oracle candidate files")
        exported = json.loads(candidate_json.read_text(encoding="utf-8"))
        require(exported == {"scope": "complete_balanced_c4_h7_layout", "independently_verified": False, "candidate": first_no}, "oracle candidate JSON differs")
        text = candidate_text.read_text(encoding="utf-8")
        require("height=7\ncolors=4\nempty=2\n" in text and text.count("column=") == 4, "oracle candidate text is malformed")
        candidate_columns = [line.removeprefix("column=") for line in text.splitlines() if line.startswith("column=")]
        assert isinstance(first_no, dict)
        require(candidate_columns == first_no["columns_bottom_to_top"], "oracle candidate text differs from first initial NO")
    else:
        require(not candidate_json.exists() and not candidate_text.exists(), "YES-only run exported a global-NO candidate")


def run_negative_tests(report: dict[str, object], report_path: Path) -> None:
    mutations = (
        ("claim h7", lambda value: value["claims"].__setitem__("universal_c4_h7_solvability", True)),
        ("self-certify global NO", lambda value: value["claims"].__setitem__("global_no_certified", True)),
        ("self-claim independence", lambda value: value["claims"].__setitem__("independent_verification_complete", True)),
        ("alter universe", lambda value: value["universe"].__setitem__("balanced_restorations", BALANCED - 1)),
        ("alter row hash", lambda value: value["ledgers"].__setitem__("result_rows_fnv1a64", "0" * 16)),
    )
    for label, mutate in mutations:
        candidate = copy.deepcopy(report)
        mutate(candidate)
        try:
            validate_report(candidate, report_path)
        except AssertionError:
            continue
        fail(f"negative test accepted mutation: {label}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--negative-tests", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    require(isinstance(report, dict), "report root is not an object")
    validate_report(report, args.report)
    if args.negative_tests:
        run_negative_tests(report, args.report)
    run = report["run"]
    assert isinstance(run, dict)
    print(
        "strict three-source past validation passed: "
        f"status={report['status']} restorations={run['restorations_checked']}/{BALANCED} "
        f"reachable={run['reachable_checked']}/{REACHABLE} initial_no={run['initial_no']} "
        "global_no_certified=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
