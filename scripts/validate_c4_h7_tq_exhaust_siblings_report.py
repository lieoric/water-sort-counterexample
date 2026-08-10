#!/usr/bin/env python3
"""Strict claim-boundary validator for the first-exhaustion Tq census."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import NoReturn


SCOPE = "first_exhaustion_tq_sibling_next_run_forks"
LIMIT_UNIT = "raw_all_q_next_run_decorations"
EXPECTED = {
    "terminal_count": 71,
    "labeled_candidates": 624,
    "canonical_parents": 418,
    "canonical_edges": 429,
    "unique_source_parents": 6,
    "sibling_parents": 412,
    "unique_source_edges": 6,
    "sibling_edges": 423,
}
EXPECTED_PARENT_DISTRIBUTION = {"2": 1, "3": 12, "4": 399}
EXPECTED_EDGE_DISTRIBUTION = {"2": 2, "3": 14, "4": 407}
EXPECTED_RAW = {
    "legal_sibling_cards": 18_177,
    "legal_sibling_joint_decorations": 1_220_361,
    "all_q_joint_decorations": 1_256_148,
}
EXPECTED_NONNEGATIVE = 406_528
EXPECTED_FEASIBLE = 403_685
EXPECTED_RESIDUAL_WORDS = 6_131_033_832
EXPECTED_CLASS_COUNTS = {
    "two_exhaustion": 70_633,
    "live_bad_persistent": 254_899,
    "obstruction": 78_153,
}
EXPECTED_CLASS_WEIGHTS = {
    "two_exhaustion": 8_629_839,
    "live_bad_persistent": 3_235_811_235,
    "obstruction": 2_886_592_758,
}
EXPECTED_REFINED_COUNTS = {
    "direct_certified": 101_922,
    "n_ge_3_certified": 11_226,
    "n_le_2_certified": 223_321,
    "d2_reduction": 67_206,
    "tq_corner_only": 10,
}
EXPECTED_REFINED_WEIGHTS = {
    "direct_certified": 13_128_393,
    "n_ge_3_certified": 10_591_970,
    "n_le_2_certified": 3_223_219_144,
    "d2_reduction": 2_883_858_705,
    "tq_corner_only": 235_620,
}


def fail(message: str) -> NoReturn:
    raise SystemExit(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def obj(value: object, label: str) -> dict[str, object]:
    require(isinstance(value, dict), f"{label} must be an object")
    return value


def array(value: object, label: str) -> list[object]:
    require(isinstance(value, list), f"{label} must be an array")
    return value


def integer(value: object, label: str, minimum: int = 0) -> int:
    require(
        isinstance(value, int) and not isinstance(value, bool),
        f"{label} must be an integer",
    )
    require(value >= minimum, f"{label} must be at least {minimum}")
    return value


def distribution(value: object, label: str) -> dict[str, int]:
    result = obj(value, label)
    require(
        all(isinstance(key, str) and isinstance(count, int) for key, count in result.items()),
        f"{label} must map string keys to integer counts",
    )
    return {key: int(count) for key, count in result.items()}


def class_pair(
    value: object,
    label: str,
    names: set[str] | None = None,
) -> tuple[dict[str, int], dict[str, int]]:
    """Accept the canonical nested class schema and reject ambiguous shapes."""

    classes = obj(value, label)
    expected_names = set(EXPECTED_CLASS_COUNTS) if names is None else names
    require(set(classes) == expected_names, f"{label} has wrong class keys")
    counts: dict[str, int] = {}
    weights: dict[str, int] = {}
    for name, raw in classes.items():
        entry = obj(raw, f"{label}.{name}")
        require(set(entry) >= {"decorations", "residual_words"}, f"{label}.{name} lacks counts")
        counts[name] = integer(entry["decorations"], f"{label}.{name}.decorations")
        weights[name] = integer(entry["residual_words"], f"{label}.{name}.residual_words")
    return counts, weights


def read_json(path: Path, label: str) -> dict[str, object]:
    require(path.is_file(), f"missing {label}: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        fail(f"cannot parse {label} {path}: {error}")
    return obj(value, label)


def validate(
    report_path: Path,
    output_dir: Path,
    audit_path: Path | None,
) -> str:
    report = read_json(report_path, "production report")
    require((output_dir / "summary.md").is_file(), "missing summary.md")
    require(report.get("schema_version") == 1, "unsupported schema_version")
    require(report.get("coverage_scope") == SCOPE, "wrong coverage_scope")
    require(report.get("limit_unit") == LIMIT_UNIT, "wrong limit_unit")
    require(report.get("self_checks_passed") is True, "production self-checks failed")
    require(report.get("status") in {"NEXT_RUN_CENSUS_COMPLETE", "INCOMPLETE"}, "unsupported status")
    for key in (
        "verified",
        "next_run_universe_complete",
        "full_residual_word_coverage",
        "entry_family_eliminated",
        "full_layout_coverage",
    ):
        require(isinstance(report.get(key), bool), f"{key} must be Boolean")
    require(report["full_residual_word_coverage"] is False, "next-run census cannot claim residual-word coverage")
    require(report["entry_family_eliminated"] is False, "next-run census cannot claim entry-family elimination")
    require(report["full_layout_coverage"] is False, "next-run census cannot claim full-layout coverage")

    model = obj(report.get("model"), "model")
    require(
        model == {"colors": 4, "height": 7, "empty_columns": 2},
        f"wrong model dimensions: {model}",
    )
    bridge = obj(report.get("bridge"), "bridge")
    for key, expected in EXPECTED.items():
        require(bridge.get(key) == expected, f"bridge.{key} must be {expected}")
    require(
        distribution(bridge.get("parent_legal_source_distribution"), "bridge.parent_legal_source_distribution")
        == EXPECTED_PARENT_DISTRIBUTION,
        "parent legal-source distribution mismatch",
    )
    require(
        distribution(bridge.get("edge_legal_source_distribution"), "bridge.edge_legal_source_distribution")
        == EXPECTED_EDGE_DISTRIBUTION,
        "edge legal-source distribution mismatch",
    )
    for key in ("action_unique", "all_edges_replay", "all_final_colors_isolated"):
        require(bridge.get(key) is True, f"bridge.{key} must be true")

    raw = obj(report.get("raw"), "raw")
    for key, expected in EXPECTED_RAW.items():
        require(raw.get(key) == expected, f"raw.{key} must be {expected}")
    checked = integer(raw.get("checked"), "raw.checked")
    require(checked <= EXPECTED_RAW["all_q_joint_decorations"], "raw.checked exceeds universe")

    census = obj(report.get("census"), "census")
    nonnegative = integer(census.get("nonnegative_decorations"), "census.nonnegative_decorations")
    feasible = integer(census.get("feasible_decorations"), "census.feasible_decorations")
    infeasible = integer(census.get("infeasible_decorations"), "census.infeasible_decorations")
    residual_words = integer(census.get("residual_words"), "census.residual_words")
    require(feasible + infeasible == checked, "feasible/infeasible counts do not partition checked decorations")
    require(feasible <= nonnegative <= checked, "nonnegative/Hall-feasible counts are inconsistent")
    legacy_counts, legacy_weights = class_pair(census.get("legacy"), "census.legacy")
    require(sum(legacy_counts.values()) == feasible, "legacy classes do not partition Hall-feasible decorations")
    require(sum(legacy_weights.values()) == residual_words, "legacy weights do not partition residual words")
    refined_counts, refined_weights = class_pair(
        census.get("refined"), "census.refined", set(EXPECTED_REFINED_COUNTS)
    )
    require(sum(refined_counts.values()) == feasible, "refined classes do not partition Hall-feasible decorations")
    require(sum(refined_weights.values()) == residual_words, "refined weights do not partition residual words")

    rows = array(report.get("per_edge"), "per_edge")
    require(len(rows) == EXPECTED["sibling_edges"], "per_edge must contain all 423 sibling edges")
    seen_ids: set[str] = set()
    row_raw_expected = row_checked = row_feasible = row_infeasible = row_words = 0
    row_class_counts: dict[str, int] = {name: 0 for name in EXPECTED_CLASS_COUNTS}
    row_class_weights: dict[str, int] = {name: 0 for name in EXPECTED_CLASS_COUNTS}
    row_refined_counts: dict[str, int] = {name: 0 for name in EXPECTED_REFINED_COUNTS}
    row_refined_weights: dict[str, int] = {name: 0 for name in EXPECTED_REFINED_COUNTS}
    for index, raw_row in enumerate(rows):
        row = obj(raw_row, f"per_edge[{index}]")
        edge_id = row.get("edge_id")
        require(isinstance(edge_id, str) and edge_id, f"per_edge[{index}].edge_id invalid")
        require(edge_id not in seen_ids, f"duplicate edge_id {edge_id}")
        seen_ids.add(edge_id)
        expected = integer(row.get("raw_expected"), f"{edge_id}.raw_expected")
        edge_checked = integer(row.get("raw_checked"), f"{edge_id}.raw_checked")
        edge_feasible = integer(row.get("feasible"), f"{edge_id}.feasible")
        edge_infeasible = integer(row.get("infeasible"), f"{edge_id}.infeasible")
        edge_words = integer(row.get("residual_words"), f"{edge_id}.residual_words")
        require(edge_checked <= expected, f"{edge_id} checked more than its universe")
        require(edge_feasible + edge_infeasible == edge_checked, f"{edge_id} classifications do not sum")
        counts, weights = class_pair(row.get("legacy"), f"{edge_id}.legacy")
        refined_edge_counts, refined_edge_weights = class_pair(
            row.get("refined"), f"{edge_id}.refined", set(EXPECTED_REFINED_COUNTS)
        )
        require(sum(counts.values()) == edge_feasible, f"{edge_id} legacy classes do not sum")
        require(sum(weights.values()) == edge_words, f"{edge_id} legacy weights do not sum")
        require(sum(refined_edge_counts.values()) == edge_feasible, f"{edge_id} refined classes do not sum")
        require(sum(refined_edge_weights.values()) == edge_words, f"{edge_id} refined weights do not sum")
        row_raw_expected += expected
        row_checked += edge_checked
        row_feasible += edge_feasible
        row_infeasible += edge_infeasible
        row_words += edge_words
        for name in row_class_counts:
            row_class_counts[name] += counts[name]
            row_class_weights[name] += weights[name]
        for name in row_refined_counts:
            row_refined_counts[name] += refined_edge_counts[name]
            row_refined_weights[name] += refined_edge_weights[name]
    require(row_raw_expected == EXPECTED_RAW["all_q_joint_decorations"], "per-edge raw universes do not sum")
    require(row_checked == checked, "per-edge checked counts disagree with raw.checked")
    require(row_feasible == feasible and row_infeasible == infeasible, "per-edge feasibility totals disagree")
    require(row_words == residual_words, "per-edge residual weights disagree")
    require(row_class_counts == legacy_counts, "per-edge legacy counts disagree")
    require(row_class_weights == legacy_weights, "per-edge legacy weights disagree")
    require(row_refined_counts == refined_counts, "per-edge refined counts disagree")
    require(row_refined_weights == refined_weights, "per-edge refined weights disagree")

    samples = array(report.get("replay_samples"), "replay_samples")
    sample_ids: set[str] = set()
    for index, raw_sample in enumerate(samples):
        sample = obj(raw_sample, f"replay_samples[{index}]")
        sample_id = sample.get("sample_id")
        require(isinstance(sample_id, str) and sample_id, "sample_id must be nonempty")
        require(sample_id not in sample_ids, f"duplicate sample_id {sample_id}")
        sample_ids.add(sample_id)
    for raw_row in rows:
        row = obj(raw_row, "per_edge row")
        sample_id = row.get("sample_id")
        require(sample_id is None or sample_id in sample_ids, f"unknown sample_id {sample_id!r}")

    complete = checked == EXPECTED_RAW["all_q_joint_decorations"]
    status = str(report["status"])
    if status == "NEXT_RUN_CENSUS_COMPLETE":
        require(complete, "complete status has unchecked decorations")
        require(report["verified"] is True, "complete status requires verified=true")
        require(report["next_run_universe_complete"] is True, "complete status requires complete-universe flag")
        require(nonnegative == EXPECTED_NONNEGATIVE, "full nonnegative count mismatch")
        require(feasible == EXPECTED_FEASIBLE, "full Hall-feasible count mismatch")
        require(residual_words == EXPECTED_RESIDUAL_WORDS, "full residual-word weight mismatch")
        require(legacy_counts == EXPECTED_CLASS_COUNTS, "full legacy class counts mismatch")
        require(legacy_weights == EXPECTED_CLASS_WEIGHTS, "full legacy class weights mismatch")
        require(refined_counts == EXPECTED_REFINED_COUNTS, "full refined class counts mismatch")
        require(refined_weights == EXPECTED_REFINED_WEIGHTS, "full refined class weights mismatch")
    else:
        require(not complete, "a complete census may not use INCOMPLETE")
        require(report["verified"] is False, "INCOMPLETE must set verified=false")
        require(report["next_run_universe_complete"] is False, "INCOMPLETE may not claim complete universe")

    if audit_path is not None:
        audit = read_json(audit_path, "independent audit")
        scalar_map = {
            "terminal_count": bridge["terminal_count"],
            "labeled_reverse_candidates": bridge["labeled_candidates"],
            "canonical_parent_count": bridge["canonical_parents"],
            "canonical_edge_count": bridge["canonical_edges"],
            "unique_source_parent_count": bridge["unique_source_parents"],
            "sibling_parent_count": bridge["sibling_parents"],
            "sibling_edge_count": bridge["sibling_edges"],
            "raw_individual_legal_sibling_cards": raw["legal_sibling_cards"],
            "raw_joint_legal_sibling_decorations": raw["legal_sibling_joint_decorations"],
            "raw_all_q_next_run_decorations": raw["all_q_joint_decorations"],
        }
        for key, value in scalar_map.items():
            require(audit.get(key) == value, f"independent audit disagrees on {key}")
        if complete:
            require(audit.get("nonnegative_decorations") == nonnegative, "audit nonnegative mismatch")
            require(audit.get("hall_feasible_decorations") == feasible, "audit feasible mismatch")
            require(audit.get("residual_word_weight") == residual_words, "audit residual weight mismatch")
            require(audit.get("classification_counts") == legacy_counts, "audit class-count mismatch")
            require(audit.get("classification_weights") == legacy_weights, "audit class-weight mismatch")
            require(audit.get("refined_classification_counts") == refined_counts, "audit refined-count mismatch")
            require(audit.get("refined_classification_weights") == refined_weights, "audit refined-weight mismatch")

    require(not (output_dir / "no-instance.txt").exists(), "next-run census must not publish a global-NO witness")
    return status


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--status-file", type=Path)
    args = parser.parse_args()
    status = validate(args.report, args.output_dir, args.audit)
    if args.status_file:
        args.status_file.parent.mkdir(parents=True, exist_ok=True)
        args.status_file.write_text(status + "\n", encoding="utf-8")
    print(f"strict first-exhaustion Tq report validation passed: status={status}")


if __name__ == "__main__":
    main()
