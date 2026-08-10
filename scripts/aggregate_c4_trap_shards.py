#!/usr/bin/env python3
"""Apply the exact SAT-any / UNSAT-all rule to checked h=7 RGS shards."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path
import sys
from typing import Any, Sequence

from c4_trap_cnf import (
    COLOR_COUNT,
    RGS_LENGTH_THREE_PREFIXES,
    is_restricted_growth_word,
)


SAT_STATUS = "SAT_VERIFIED_NO_INSTANCE"
UNSAT_STATUS = "UNSAT_VERIFIED"
INCONCLUSIVE_STATUSES = {
    "STARTING",
    "SOLVING",
    "TIMEOUT",
    "TIMEOUT_OR_UNKNOWN",
    "UNSAT_UNCERTIFIED",
    "VERIFICATION_FAILED",
    "RUNNER_ERROR",
    "WORKFLOW_STAGE_FAILED",
}
STEP_OUTCOMES = {"", "success", "failure", "cancelled", "skipped"}


class AggregationError(RuntimeError):
    """The available artifacts cannot safely imply a global result."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_checked_stage(
    result: dict[str, Any], stage_name: str, expected_exit: int
) -> None:
    stages = result.get("stages")
    if not isinstance(stages, dict):
        raise AggregationError("shard result has no checked-stage metadata")
    stage = stages.get(stage_name)
    if not isinstance(stage, dict):
        raise AggregationError(f"missing checked stage {stage_name}")
    if stage.get("exit_code") != expected_exit or stage.get("timed_out") is not False:
        raise AggregationError(f"stage {stage_name} was not completed successfully")


def validate_identity(result: dict[str, Any]) -> str:
    if not isinstance(result, dict):
        raise AggregationError("shard result is not a JSON object")
    if result.get("schema") != 1:
        raise AggregationError("unsupported shard result schema")
    problem = result.get("problem")
    if not isinstance(problem, dict):
        raise AggregationError("shard result has no problem metadata")
    if (
        problem.get("colors") != 4
        or problem.get("empty_columns") != 2
        or problem.get("height") != 7
        or "fixed_instance" in problem
    ):
        raise AggregationError("shard problem is not unrestricted c=4, k=2, h=7")
    prefix = problem.get("rgs_prefix")
    if prefix not in RGS_LENGTH_THREE_PREFIXES:
        raise AggregationError(f"unexpected RGS shard prefix {prefix!r}")
    if result.get("proof_mode") != "checked-drat":
        raise AggregationError(f"shard {prefix} did not use checked-DRAT mode")
    return prefix


def validate_envelope(envelope: dict[str, Any], prefix: str) -> None:
    if not isinstance(envelope, dict) or envelope.get("schema") != 1:
        raise AggregationError(f"shard {prefix} has a malformed workflow envelope")
    if envelope.get("rgs_prefix") != prefix:
        raise AggregationError(f"shard {prefix} conflicts with its workflow envelope")
    for field in ("runner_exit", "compute_outcome", "archive_outcome"):
        if not isinstance(envelope.get(field), str):
            raise AggregationError(f"shard {prefix} envelope field {field} is not text")
    if envelope["compute_outcome"] not in STEP_OUTCOMES:
        raise AggregationError(f"shard {prefix} has an unknown compute outcome")
    if envelope["archive_outcome"] not in STEP_OUTCOMES:
        raise AggregationError(f"shard {prefix} has an unknown archive outcome")


def classify_shard(
    result: dict[str, Any], envelope: dict[str, Any]
) -> tuple[str, str]:
    """Return ``(prefix, evidence_class)`` after strict structural checks."""
    prefix = validate_identity(result)
    validate_envelope(envelope, prefix)
    verified = result.get("verified")
    status = result.get("status")
    if not isinstance(verified, bool) or not isinstance(status, str):
        raise AggregationError(f"shard {prefix} has malformed status fields")

    if not verified:
        if status in {SAT_STATUS, UNSAT_STATUS}:
            raise AggregationError(
                f"shard {prefix} claims status {status} without verification"
            )
        if status not in INCONCLUSIVE_STATUSES:
            raise AggregationError(f"shard {prefix} has unknown status {status!r}")
        if envelope["runner_exit"] == "0":
            raise AggregationError(
                f"shard {prefix} has runner exit 0 but no verified result"
            )
        return prefix, "INCONCLUSIVE"

    if status == SAT_STATUS:
        require_checked_stage(result, "cadical", 10)
        for stage_name in (
            "dimacs_model_check",
            "decode",
            "water_oracle",
            "water_verify",
        ):
            require_checked_stage(result, stage_name, 0)
    elif status == UNSAT_STATUS:
        require_checked_stage(result, "cadical", 20)
        require_checked_stage(result, "drat_trim", 0)
    else:
        raise AggregationError(
            f"shard {prefix} is marked verified with unaccepted status {status!r}"
        )

    if envelope["compute_outcome"] != "success" or envelope["runner_exit"] != "0":
        raise AggregationError(
            f"shard {prefix} verified status conflicts with its runner outcome"
        )
    if envelope["archive_outcome"] != "success":
        # The local check may genuinely have completed, but without its full
        # archived DIMACS/evidence it is deliberately not theorem evidence.
        return prefix, "VERIFIED_BUT_UNARCHIVED"
    return prefix, status


def aggregate_results(
    named_results: Sequence[
        tuple[str, dict[str, Any], dict[str, Any]]
    ]
) -> dict[str, Any]:
    # Recheck the finite coverage lemma at aggregation time, independently of
    # the workflow matrix declaration.
    possible_prefixes = {
        "".join(map(str, word))
        for word in itertools.product(range(COLOR_COUNT), repeat=3)
        if is_restricted_growth_word(word)
    }
    expected = set(RGS_LENGTH_THREE_PREFIXES)
    if possible_prefixes != expected:
        raise AggregationError("internal length-three RGS coverage mismatch")

    by_prefix: dict[str, tuple[str, dict[str, Any], str]] = {}
    for source, result, envelope in named_results:
        prefix, evidence_class = classify_shard(result, envelope)
        if prefix in by_prefix:
            raise AggregationError(f"duplicate result for RGS shard {prefix}")
        by_prefix[prefix] = (source, result, evidence_class)

    missing = expected - set(by_prefix)
    sat_prefixes = [
        prefix
        for prefix in RGS_LENGTH_THREE_PREFIXES
        if prefix in by_prefix and by_prefix[prefix][2] == SAT_STATUS
    ]
    if sat_prefixes:
        global_status = SAT_STATUS
        claim = (
            "At least one exact RGS shard contains an independently verified "
            "and archived fixed-layout NO instance.  Other shards are not "
            "needed for the unrestricted h=7 SAT conclusion."
        )
    elif not missing and all(
        by_prefix[prefix][2] == UNSAT_STATUS
        for prefix in RGS_LENGTH_THREE_PREFIXES
    ):
        global_status = UNSAT_STATUS
        claim = (
            "All five length-three RGS shards have independently verified and "
            "archived DRAT proofs, so the unrestricted h=7 formula is UNSAT."
        )
    else:
        classes = {
            prefix: by_prefix[prefix][2]
            for prefix in RGS_LENGTH_THREE_PREFIXES
            if prefix in by_prefix
        }
        raise AggregationError(
            "no verified SAT shard and not all five verified UNSAT shards: "
            f"missing={sorted(missing)}, classes={classes}"
        )

    return {
        "schema": 1,
        "problem": {"colors": 4, "empty_columns": 2, "height": 7},
        "partition": {
            "coordinate": "first three flattened top-to-bottom cells",
            "kind": "restricted-growth words",
            "prefixes": list(RGS_LENGTH_THREE_PREFIXES),
            "coverage_checked_by_exhaustive_assignments": COLOR_COUNT**3,
        },
        "aggregation_rule": "SAT from any verified archived shard; UNSAT from all five",
        "status": global_status,
        "verified": True,
        "sat_shards": sat_prefixes,
        "missing_shards": sorted(missing),
        "claim": claim,
        "shards": {
            prefix: {
                "source": by_prefix[prefix][0],
                "runner_status": by_prefix[prefix][1]["status"],
                "runner_verified": by_prefix[prefix][1]["verified"],
                "evidence_class": by_prefix[prefix][2],
            }
            for prefix in RGS_LENGTH_THREE_PREFIXES
            if prefix in by_prefix
        },
    }


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summaries", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result_paths = {path.parent: path for path in args.summaries.rglob("result.json")}
        envelope_paths = {
            path.parent: path for path in args.summaries.rglob("envelope.json")
        }
        if set(result_paths) != set(envelope_paths):
            raise AggregationError(
                "every downloaded shard summary must pair result.json with envelope.json"
            )
        named_results = [
            (
                str(directory),
                json.loads(result_paths[directory].read_text(encoding="utf-8")),
                json.loads(envelope_paths[directory].read_text(encoding="utf-8")),
            )
            for directory in sorted(result_paths, key=str)
        ]
        aggregate = aggregate_results(named_results)
        aggregate["summary_files"] = {
            str(path): {"bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in sorted(
                [*result_paths.values(), *envelope_paths.values()], key=str
            )
        }
        write_json(args.output, aggregate)
        print(json.dumps({"status": aggregate["status"], "verified": True}))
        return 0
    except (
        AggregationError,
        json.JSONDecodeError,
        OSError,
        TypeError,
        UnicodeError,
    ) as error:
        write_json(
            args.output,
            {
                "schema": 1,
                "problem": {"colors": 4, "empty_columns": 2, "height": 7},
                "status": "AGGREGATION_FAILED",
                "verified": False,
                "error": str(error),
            },
        )
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
