#!/usr/bin/env python3
"""Accept the h=7 theorem only from five exact, independently checked shards."""

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


class AggregationError(RuntimeError):
    """One shard is absent, unchecked, duplicated, or inconsistent."""


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


def validate_shard(result: dict[str, Any]) -> str:
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
    if result.get("verified") is not True:
        raise AggregationError(f"shard {prefix} is not independently verified")

    status = result.get("status")
    require_checked_stage(result, "cadical", 10 if status == SAT_STATUS else 20)
    if status == SAT_STATUS:
        for stage_name in (
            "dimacs_model_check",
            "decode",
            "water_oracle",
            "water_verify",
        ):
            require_checked_stage(result, stage_name, 0)
    elif status == UNSAT_STATUS:
        require_checked_stage(result, "drat_trim", 0)
    else:
        raise AggregationError(f"shard {prefix} has unaccepted status {status!r}")
    return prefix


def aggregate_results(
    named_results: Sequence[tuple[str, dict[str, Any]]]
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

    by_prefix: dict[str, tuple[str, dict[str, Any]]] = {}
    for source, result in named_results:
        prefix = validate_shard(result)
        if prefix in by_prefix:
            raise AggregationError(f"duplicate result for RGS shard {prefix}")
        by_prefix[prefix] = (source, result)
    missing = expected - set(by_prefix)
    extra = set(by_prefix) - expected
    if missing or extra:
        raise AggregationError(
            f"shard partition mismatch: missing={sorted(missing)}, extra={sorted(extra)}"
        )

    statuses = {
        prefix: by_prefix[prefix][1]["status"]
        for prefix in RGS_LENGTH_THREE_PREFIXES
    }
    sat_prefixes = [
        prefix for prefix, status in statuses.items() if status == SAT_STATUS
    ]
    if sat_prefixes:
        global_status = SAT_STATUS
        claim = (
            "At least one exact RGS shard contains an independently verified "
            "fixed-layout NO instance, so the unrestricted h=7 formula is SAT."
        )
    elif all(status == UNSAT_STATUS for status in statuses.values()):
        global_status = UNSAT_STATUS
        claim = (
            "All five length-three RGS shards have independently verified DRAT "
            "proofs, so the unrestricted h=7 formula is UNSAT."
        )
    else:  # validate_shard currently makes this unreachable; keep it explicit.
        raise AggregationError("verified shard statuses do not imply a global result")

    return {
        "schema": 1,
        "problem": {"colors": 4, "empty_columns": 2, "height": 7},
        "partition": {
            "coordinate": "first three flattened top-to-bottom cells",
            "kind": "restricted-growth words",
            "prefixes": list(RGS_LENGTH_THREE_PREFIXES),
            "coverage_checked_by_exhaustive_assignments": COLOR_COUNT**3,
        },
        "status": global_status,
        "verified": True,
        "sat_shards": sat_prefixes,
        "claim": claim,
        "shards": {
            prefix: {
                "source": by_prefix[prefix][0],
                "status": statuses[prefix],
                "verified": True,
            }
            for prefix in RGS_LENGTH_THREE_PREFIXES
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
        paths = sorted(args.summaries.rglob("result.json"))
        if len(paths) != len(RGS_LENGTH_THREE_PREFIXES):
            raise AggregationError(
                f"expected five result.json files, found {len(paths)}"
            )
        named_results = [
            (str(path), json.loads(path.read_text(encoding="utf-8")))
            for path in paths
        ]
        aggregate = aggregate_results(named_results)
        aggregate["summary_files"] = {
            str(path): {"bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in paths
        }
        write_json(args.output, aggregate)
        print(json.dumps({"status": aggregate["status"], "verified": True}))
        return 0
    except (AggregationError, json.JSONDecodeError, OSError, TypeError) as error:
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
