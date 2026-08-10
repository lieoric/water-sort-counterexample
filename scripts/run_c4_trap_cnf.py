#!/usr/bin/env python3
"""Run and independently check one exact c4/k2 trap-CNF computation.

This wrapper deliberately treats a SAT solver's exit status as only the start
of verification:

* SAT is accepted only after decoding the model to a Water Sort instance,
  proving that instance UNSOLVABLE with ``water-oracle``, and checking the
  resulting closure certificate with ``water-verify``.
* UNSAT is accepted only in ``checked-drat`` mode, after ``drat-trim`` checks
  the solver's proof against the exact DIMACS file.

CaDiCaL's competition exit codes (10 for SAT and 20 for UNSAT) are consumed by
this script and are not leaked as a failing GitHub Actions step.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
from typing import Any, Sequence


SAT_EXIT = 10
UNSAT_EXIT = 20
RGS_LENGTH_THREE_PREFIXES = ("000", "001", "010", "011", "012")


class RunFailure(RuntimeError):
    """A checked stage failed or produced an inconsistent result."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_record(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def write_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def run_logged(
    command: Sequence[str],
    log_path: Path,
    *,
    timeout_seconds: int | None = None,
) -> tuple[int | None, float, bool]:
    """Run a command with combined output in ``log_path``.

    Returns ``(return_code, elapsed_seconds, timed_out)``.  The outer timeout
    is a guard in addition to CaDiCaL/drat-trim's own time limits.
    """

    started = time.monotonic()
    with log_path.open("wb") as log:
        log.write(("$ " + " ".join(command) + "\n").encode("utf-8"))
        log.flush()
        try:
            completed = subprocess.run(
                list(command),
                stdout=log,
                stderr=subprocess.STDOUT,
                check=False,
                timeout=timeout_seconds,
            )
            return completed.returncode, time.monotonic() - started, False
        except subprocess.TimeoutExpired:
            log.write(b"\nrunner: outer timeout expired\n")
            return None, time.monotonic() - started, True


def require_file(path: Path, label: str, *, nonempty: bool = True) -> None:
    if not path.is_file():
        raise RunFailure(f"{label} was not created: {path}")
    if nonempty and path.stat().st_size == 0:
        raise RunFailure(f"{label} is empty: {path}")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def executable_record(path: Path) -> dict[str, Any]:
    record = file_record(path)
    record["resolved_path"] = str(path.resolve())
    return record


def base_result(args: argparse.Namespace, out: Path) -> dict[str, Any]:
    result = {
        "schema": 1,
        "problem": {"colors": 4, "empty_columns": 2, "height": args.height},
        "proof_mode": args.proof_mode,
        "limits": {
            "solver_seconds": args.timeout_seconds,
            "proof_checker_seconds": args.proof_timeout_seconds,
            "verification_seconds": args.verification_timeout_seconds,
        },
        "status": "STARTING",
        "verified": False,
        "out_directory": str(out),
        "stages": {},
        "files": {},
    }
    if args.fix_instance is not None:
        result["problem"]["fixed_instance"] = file_record(args.fix_instance)
    if args.rgs_prefix is not None:
        result["problem"]["rgs_prefix"] = args.rgs_prefix
    return result


def update_file_records(result: dict[str, Any], paths: Sequence[Path]) -> None:
    records = result["files"]
    for path in paths:
        if path.is_file():
            records[path.name] = file_record(path)


def checked_command(
    result: dict[str, Any],
    stage: str,
    command: Sequence[str],
    log_path: Path,
    *,
    timeout_seconds: int,
) -> None:
    code, elapsed, timed_out = run_logged(
        command, log_path, timeout_seconds=timeout_seconds
    )
    result["stages"][stage] = {
        "exit_code": code,
        "elapsed_seconds": round(elapsed, 3),
        "timed_out": timed_out,
        "log": str(log_path),
    }
    if timed_out:
        raise RunFailure(f"{stage} exceeded its outer timeout")
    if code != 0:
        raise RunFailure(f"{stage} exited with status {code}")


def generate_problem(
    args: argparse.Namespace,
    out: Path,
    result: dict[str, Any],
) -> tuple[Path, Path, Path]:
    cnf = out / "problem.cnf"
    mapping = out / "problem.map.json"
    metadata = out / "metadata.json"
    command = [
        sys.executable,
        str(args.generator),
        "generate",
        "--height",
        str(args.height),
        "--cnf",
        str(cnf),
        "--map",
        str(mapping),
        "--metadata",
        str(metadata),
    ]
    if args.fix_instance is not None:
        command.extend(["--fix-instance", str(args.fix_instance)])
    if args.rgs_prefix is not None:
        command.extend(["--rgs-prefix", args.rgs_prefix])
    checked_command(
        result,
        "generate",
        command,
        out / "generator.log",
        timeout_seconds=args.generation_timeout_seconds,
    )
    require_file(cnf, "DIMACS formula")
    require_file(mapping, "variable map")
    require_file(metadata, "generator metadata")
    try:
        metadata_value = json.loads(read_text(metadata))
    except (json.JSONDecodeError, OSError) as error:
        raise RunFailure(f"generator metadata is not valid JSON: {error}") from error
    if not isinstance(metadata_value, dict):
        raise RunFailure("generator metadata is not a JSON object")
    symmetry = metadata_value.get("symmetry")
    if not isinstance(symmetry, dict):
        raise RunFailure("generator metadata has no symmetry object")
    if symmetry.get("rgs_prefix") != args.rgs_prefix:
        raise RunFailure("generator metadata does not match the requested RGS prefix")
    if args.rgs_prefix is not None and not (
        symmetry.get("color_first_occurrence") is True
        and symmetry.get("column_lexicographic_nondecreasing") is True
        and symmetry.get("rgs_prefix_unit_clauses") == 3
    ):
        raise RunFailure("RGS shard did not retain both symmetry breakers and three units")
    update_file_records(result, [cnf, mapping, metadata, out / "generator.log"])
    return cnf, mapping, metadata


def extract_model(solver_log: Path, model_path: Path) -> None:
    model_lines = [
        line.strip()
        for line in read_text(solver_log).splitlines()
        if line.lstrip().startswith("v ")
    ]
    if not model_lines:
        raise RunFailure("CaDiCaL reported SAT but printed no model lines")
    model_path.write_text("\n".join(model_lines) + "\n", encoding="utf-8")


def check_dimacs_model(cnf: Path, model: Path, log_path: Path) -> None:
    assignments: dict[int, bool] = {}
    for line in read_text(model).splitlines():
        fields = line.split()
        if not fields or fields[0] != "v":
            continue
        for field in fields[1:]:
            literal = int(field)
            if literal == 0:
                continue
            variable = abs(literal)
            value = literal > 0
            if variable in assignments and assignments[variable] != value:
                raise RunFailure(f"model assigns variable {variable} both ways")
            assignments[variable] = value

    declared_variables: int | None = None
    declared_clauses: int | None = None
    clauses_seen = 0
    clause_has_literal = False
    clause_satisfied = False
    with cnf.open("r", encoding="ascii") as source:
        for raw_line in source:
            line = raw_line.strip()
            if not line or line.startswith("c"):
                continue
            if line.startswith("p"):
                fields = line.split()
                if len(fields) != 4 or fields[:2] != ["p", "cnf"]:
                    raise RunFailure("malformed DIMACS header")
                declared_variables = int(fields[2])
                declared_clauses = int(fields[3])
                continue
            if declared_variables is None:
                raise RunFailure("DIMACS clause appears before the header")
            for field in line.split():
                literal = int(field)
                if literal == 0:
                    clauses_seen += 1
                    if not clause_satisfied:
                        raise RunFailure(
                            f"CaDiCaL model does not satisfy DIMACS clause {clauses_seen}"
                        )
                    clause_has_literal = False
                    clause_satisfied = False
                    continue
                clause_has_literal = True
                variable = abs(literal)
                if variable > declared_variables:
                    raise RunFailure(
                        f"literal {literal} exceeds DIMACS variable bound"
                    )
                assigned_value = assignments.get(variable)
                if assigned_value is not None and assigned_value == (literal > 0):
                    clause_satisfied = True

    if declared_variables is None or declared_clauses is None:
        raise RunFailure("DIMACS header is missing")
    if clause_has_literal:
        raise RunFailure("last DIMACS clause is not terminated by zero")
    if clauses_seen != declared_clauses:
        raise RunFailure(
            f"DIMACS header declares {declared_clauses} clauses, read {clauses_seen}"
        )
    log_path.write_text(
        "VALID SAT MODEL\n"
        f"assigned_variables={len(assignments)}\n"
        f"declared_variables={declared_variables}\n"
        f"clauses_checked={clauses_seen}\n",
        encoding="utf-8",
    )


def verify_sat(
    args: argparse.Namespace,
    out: Path,
    result: dict[str, Any],
    cnf: Path,
    mapping: Path,
) -> None:
    solver_log = out / "solver.log"
    model = out / "model.txt"
    candidate = out / "candidate.txt"
    certificate = out / "candidate.wscert"
    oracle_log = out / "oracle.log"
    verifier_log = out / "verifier.log"

    extract_model(solver_log, model)
    model_check_started = time.monotonic()
    check_dimacs_model(cnf, model, out / "model-check.log")
    result["stages"]["dimacs_model_check"] = {
        "exit_code": 0,
        "elapsed_seconds": round(time.monotonic() - model_check_started, 3),
        "timed_out": False,
        "log": str(out / "model-check.log"),
    }
    checked_command(
        result,
        "decode",
        [
            sys.executable,
            str(args.generator),
            "decode",
            "--map",
            str(mapping),
            "--model",
            str(model),
            "--candidate",
            str(candidate),
        ],
        out / "decoder.log",
        timeout_seconds=args.generation_timeout_seconds,
    )
    require_file(candidate, "decoded Water Sort candidate")

    checked_command(
        result,
        "water_oracle",
        [
            str(args.oracle),
            "--input",
            str(candidate),
            "--certificate",
            str(certificate),
            "--count",
            "1",
        ],
        oracle_log,
        timeout_seconds=args.verification_timeout_seconds,
    )
    oracle_lines = [line.strip() for line in read_text(oracle_log).splitlines()]
    if not any(
        line == "border_sequences=0" or line.startswith("border_sequences=0 ")
        for line in oracle_lines
    ):
        raise RunFailure("water-oracle did not independently count zero solutions")
    if "UNSOLVABLE" not in oracle_lines:
        raise RunFailure(
            "decoded SAT model is not an UNSOLVABLE instance according to water-oracle"
        )
    require_file(certificate, "Water Sort NO certificate")

    checked_command(
        result,
        "water_verify",
        [
            str(args.verifier),
            "--input",
            str(candidate),
            "--certificate",
            str(certificate),
        ],
        verifier_log,
        timeout_seconds=args.verification_timeout_seconds,
    )
    if "VALID NO CERTIFICATE" not in read_text(verifier_log):
        raise RunFailure("water-verify did not print its validity marker")

    result["status"] = "SAT_VERIFIED_NO_INSTANCE"
    result["verified"] = True
    result["claim"] = (
        "The trap-CNF is satisfiable, and the decoded fixed instance has an "
        "independently checked Water Sort NO certificate."
    )
    update_file_records(
        result,
        [
            model,
            out / "model-check.log",
            candidate,
            certificate,
            out / "decoder.log",
            oracle_log,
            verifier_log,
        ],
    )


def verify_unsat(
    args: argparse.Namespace,
    out: Path,
    result: dict[str, Any],
    cnf: Path,
    proof: Path,
) -> None:
    if args.proof_mode != "checked-drat":
        result["status"] = "UNSAT_UNCERTIFIED"
        result["verified"] = False
        result["claim"] = (
            "CaDiCaL reported UNSAT in search-only mode; this is not accepted "
            "as a mathematical result."
        )
        raise RunFailure("UNSAT is non-certifying in search-only mode")

    require_file(proof, "CaDiCaL DRAT proof")
    proof_log = out / "drat-trim.log"
    code, elapsed, timed_out = run_logged(
        [
            str(args.drat_trim),
            str(cnf),
            str(proof),
            "-t",
            str(args.proof_timeout_seconds),
        ],
        proof_log,
        timeout_seconds=args.proof_timeout_seconds + 60,
    )
    result["stages"]["drat_trim"] = {
        "exit_code": code,
        "elapsed_seconds": round(elapsed, 3),
        "timed_out": timed_out,
        "log": str(proof_log),
    }
    if timed_out:
        raise RunFailure("drat-trim exceeded its outer timeout")
    if code != 0 or "s VERIFIED" not in read_text(proof_log):
        raise RunFailure("drat-trim did not validate the UNSAT proof")

    result["status"] = "UNSAT_VERIFIED"
    result["verified"] = True
    result["claim"] = (
        "The exact trap-CNF is unsatisfiable; drat-trim independently checked "
        "CaDiCaL's proof against the archived DIMACS formula."
    )
    update_file_records(result, [proof, proof_log])


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--height", type=int, choices=(6, 7, 8), required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--proof-mode",
        choices=("checked-drat", "search-only"),
        default="checked-drat",
    )
    parser.add_argument("--timeout-seconds", type=int, default=7200)
    parser.add_argument("--proof-timeout-seconds", type=int, default=7200)
    parser.add_argument("--generation-timeout-seconds", type=int, default=900)
    parser.add_argument("--verification-timeout-seconds", type=int, default=900)
    parser.add_argument(
        "--generator", type=Path, default=Path("scripts/c4_trap_cnf.py")
    )
    parser.add_argument(
        "--fix-instance",
        type=Path,
        help="unit-fix item variables to this known instance (pipeline regression)",
    )
    parser.add_argument(
        "--rgs-prefix",
        choices=RGS_LENGTH_THREE_PREFIXES,
        help="unit-fix the first three flattened cells to one exact RGS shard",
    )
    parser.add_argument("--cadical", type=Path, default=Path("tools/cadical"))
    parser.add_argument("--drat-trim", type=Path, default=Path("tools/drat-trim"))
    parser.add_argument("--oracle", type=Path, default=Path("tools/water-oracle"))
    parser.add_argument("--verifier", type=Path, default=Path("tools/water-verify"))
    args = parser.parse_args(argv)
    for name in (
        "timeout_seconds",
        "proof_timeout_seconds",
        "generation_timeout_seconds",
        "verification_timeout_seconds",
    ):
        if getattr(args, name) <= 0:
            parser.error(f"--{name.replace('_', '-')} must be positive")
    if args.fix_instance is not None and args.rgs_prefix is not None:
        parser.error("--fix-instance and --rgs-prefix are mutually exclusive")
    return args


def run(args: argparse.Namespace) -> int:
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    result_path = out / "result.json"
    if args.fix_instance is not None:
        require_file(args.fix_instance, "fixed regression instance")
    result = base_result(args, out)
    result["provenance"] = {
        "python": sys.version,
        "git_sha": os.environ.get("GITHUB_SHA"),
        "git_ref": os.environ.get("GITHUB_REF"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "cadical_commit": os.environ.get("CADICAL_COMMIT"),
        "drat_trim_commit": os.environ.get("DRAT_TRIM_COMMIT"),
    }

    required = {
        "generator": args.generator,
        "cadical": args.cadical,
        "drat_trim": args.drat_trim,
        "water_oracle": args.oracle,
        "water_verify": args.verifier,
    }
    for label, path in required.items():
        require_file(path, label)
        result["provenance"][label] = executable_record(path)
    write_json(result_path, result)

    try:
        cnf, mapping, _metadata = generate_problem(args, out, result)
        result["status"] = "SOLVING"
        write_json(result_path, result)

        proof = out / "proof.drat"
        solver_command = [
            str(args.cadical),
            "--no-colors",
            "--strict",
            "-t",
            str(args.timeout_seconds),
            str(cnf),
        ]
        if args.proof_mode == "checked-drat":
            solver_command.append(str(proof))
        solver_code, elapsed, timed_out = run_logged(
            solver_command,
            out / "solver.log",
            timeout_seconds=args.timeout_seconds + 60,
        )
        result["stages"]["cadical"] = {
            "exit_code": solver_code,
            "elapsed_seconds": round(elapsed, 3),
            "timed_out": timed_out,
            "log": str(out / "solver.log"),
        }
        update_file_records(result, [out / "solver.log"])

        if timed_out:
            result["status"] = "TIMEOUT"
            result["claim"] = "No SAT/UNSAT conclusion was reached before timeout."
            write_json(result_path, result)
            return 4

        solver_text = read_text(out / "solver.log")
        if solver_code == SAT_EXIT and "s SATISFIABLE" in solver_text:
            verify_sat(args, out, result, cnf, mapping)
        elif solver_code == UNSAT_EXIT and "s UNSATISFIABLE" in solver_text:
            verify_unsat(args, out, result, cnf, proof)
        elif solver_code == 0 and "s UNKNOWN" in solver_text:
            result["status"] = "TIMEOUT_OR_UNKNOWN"
            result["claim"] = "CaDiCaL returned UNKNOWN; no claim is accepted."
            write_json(result_path, result)
            return 4
        else:
            raise RunFailure(
                f"inconsistent CaDiCaL result: exit={solver_code}, "
                "expected a matching competition status line"
            )

        update_file_records(result, [out / "solver.log"])
        write_json(result_path, result)
        return 0
    except RunFailure as error:
        if result["status"] not in {"UNSAT_UNCERTIFIED", "TIMEOUT"}:
            result["status"] = "VERIFICATION_FAILED"
        result["verified"] = False
        result["error"] = str(error)
        update_file_records(
            result,
            [
                path
                for path in out.iterdir()
                if path.is_file()
                and path != result_path
                and path.name != "proof.drat"
            ],
        )
        write_json(result_path, result)
        return 2
    except Exception as error:  # Keep artifacts useful even on programming errors.
        result["status"] = "RUNNER_ERROR"
        result["verified"] = False
        result["error"] = f"{type(error).__name__}: {error}"
        (out / "runner-error.log").write_text(traceback.format_exc(), encoding="utf-8")
        update_file_records(
            result,
            [
                path
                for path in out.iterdir()
                if path.is_file()
                and path != result_path
                and path.name != "proof.drat"
            ],
        )
        write_json(result_path, result)
        return 1


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
