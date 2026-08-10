#!/usr/bin/env python3
"""Generate and decode the exact fixed-layout c4/k2 trap CNF.

The internal item orientation is top-to-bottom.  A live endpoint ``s`` means
that the top ``s`` items are exposed and that positions ``s-1`` and ``s``
have different colours.  Endpoint ``height`` is the exhausted-border state.

The generated formula is satisfiable exactly when one balanced fixed layout
has a forward-closed set containing its initial state and containing no state
with two exhausted original columns.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path
import shutil
import sys
from typing import Iterable, Sequence


COLOR_COUNT = 4
EMPTY_COLUMNS = 2


class GenerationError(RuntimeError):
    """The requested encoding or input instance is invalid."""


class VariablePool:
    def __init__(self) -> None:
        self._next = 1

    @property
    def top(self) -> int:
        return self._next - 1

    def new(self) -> int:
        variable = self._next
        self._next += 1
        return variable

    def absorb(self, top: int) -> None:
        if top >= self._next:
            self._next = top + 1


class ClauseWriter:
    """Stream clauses to a body file and prepend the DIMACS header at finish."""

    def __init__(self, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        self.destination = destination
        self.body_path = destination.with_suffix(destination.suffix + ".body.tmp")
        self.output_path = destination.with_suffix(destination.suffix + ".tmp")
        self._body = self.body_path.open("w", encoding="ascii", newline="\n")
        self.clauses = 0

    def add(self, literals: Iterable[int]) -> None:
        normalized: list[int] = []
        seen: set[int] = set()
        for literal in literals:
            literal = int(literal)
            if literal == 0:
                raise GenerationError("zero is not a clause literal")
            if -literal in seen:
                return  # A tautological clause is always true.
            if literal not in seen:
                seen.add(literal)
                normalized.append(literal)
        self._body.write(" ".join(str(literal) for literal in normalized))
        if normalized:
            self._body.write(" ")
        self._body.write("0\n")
        self.clauses += 1

    def add_guarded(self, clauses: Iterable[Sequence[int]], guard: int) -> None:
        for clause in clauses:
            self.add([guard, *clause])

    def finish(self, variables: int) -> None:
        self._body.close()
        with self.output_path.open("wb") as output:
            output.write(f"p cnf {variables} {self.clauses}\n".encode("ascii"))
            with self.body_path.open("rb") as body:
                shutil.copyfileobj(body, output, length=1024 * 1024)
        self.output_path.replace(self.destination)
        self.body_path.unlink()

    def abort(self) -> None:
        if not self._body.closed:
            self._body.close()
        for path in (self.body_path, self.output_path):
            if path.exists():
                path.unlink()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def read_instance(path: Path) -> tuple[int, list[list[int]]]:
    height: int | None = None
    colors: int | None = None
    empty: int | None = None
    bottom_to_top: list[list[int]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, value = (part.strip() for part in line.split("=", 1))
        else:
            fields = line.split(maxsplit=1)
            if len(fields) != 2:
                raise GenerationError(f"malformed instance line: {raw_line}")
            key, value = fields
        if key == "height":
            height = int(value)
        elif key == "colors":
            colors = int(value)
        elif key == "empty":
            empty = int(value)
        elif key == "column":
            try:
                column = [int(character, 36) for character in value if not character.isspace()]
            except ValueError as error:
                raise GenerationError(f"invalid colour in {raw_line}") from error
            bottom_to_top.append(column)
        else:
            raise GenerationError(f"unknown instance key: {key}")
    if height is None or colors is None or empty is None:
        raise GenerationError("instance is missing height/colors/empty")
    if colors != COLOR_COUNT or empty != EMPTY_COLUMNS:
        raise GenerationError("fixed instance must have colors=4 and empty=2")
    if len(bottom_to_top) != COLOR_COUNT:
        raise GenerationError("fixed instance must contain four columns")
    if any(len(column) != height for column in bottom_to_top):
        raise GenerationError("fixed instance column has the wrong height")
    counts = [0] * COLOR_COUNT
    for column in bottom_to_top:
        for color in column:
            if not 0 <= color < COLOR_COUNT:
                raise GenerationError("fixed instance colour is outside 0..3")
            counts[color] += 1
    if counts != [height] * COLOR_COUNT:
        raise GenerationError(f"fixed instance is not balanced: {counts}")
    return height, [list(reversed(column)) for column in bottom_to_top]


def pb_encoder():
    try:
        from pysat.pb import EncType, PBEnc
    except (ImportError, AssertionError) as error:
        raise GenerationError(
            "python-sat with the pblib extra is required; install "
            "scripts/c4_trap_cnf_requirements.txt"
        ) from error
    return PBEnc, EncType


def encode_pb(
    writer: ClauseWriter,
    pool: VariablePool,
    *,
    relation: str,
    literals: Sequence[int],
    weights: Sequence[int],
    bound: int,
    guard: int | None = None,
) -> None:
    PBEnc, EncType = pb_encoder()
    arguments = {
        "lits": list(literals),
        "weights": list(weights),
        "bound": bound,
        "top_id": pool.top,
        "encoding": EncType.best,
    }
    if relation == "equals":
        encoded = PBEnc.equals(**arguments)
    elif relation == "atleast":
        encoded = PBEnc.atleast(**arguments)
    elif relation == "atmost":
        encoded = PBEnc.atmost(**arguments)
    else:
        raise GenerationError(f"unknown PB relation: {relation}")
    pool.absorb(encoded.nv)
    if guard is None:
        for clause in encoded.clauses:
            writer.add(clause)
    else:
        writer.add_guarded(encoded.clauses, guard)


def initial_guard(
    boundary: list[list[int]], column: int, endpoint: int, height: int
) -> list[int]:
    if endpoint < height:
        return [boundary[column][endpoint], *[
            -boundary[column][earlier] for earlier in range(1, endpoint)
        ]]
    return [-boundary[column][earlier] for earlier in range(1, height)]


def next_guard_negation(
    boundary: list[list[int]], column: int, source: int, target: int, height: int
) -> list[int]:
    # Negation of B(target) and no B strictly between source and target.
    negated = [boundary[column][middle] for middle in range(source + 1, target)]
    if target < height:
        negated.insert(0, -boundary[column][target])
    return negated


def expected_state_count(height: int) -> int:
    live = height - 1
    return live**4 + 4 * live**3


def expected_transition_count(height: int) -> int:
    return 2 * height * (height - 1) ** 3 * (height + 2)


def generate(args: argparse.Namespace) -> None:
    height = args.height
    if not 2 <= height <= 16:
        raise GenerationError("height must be in [2, 16]")

    fixed_layout: list[list[int]] | None = None
    if args.fix_instance is not None:
        fixed_height, fixed_layout = read_instance(args.fix_instance)
        if fixed_height != height:
            raise GenerationError(
                f"fixed instance height {fixed_height} does not match {height}"
            )

    symmetry_breaking = not args.no_symmetry_breaking and fixed_layout is None
    pool = VariablePool()
    writer = ClauseWriter(args.cnf)
    categories: dict[str, int] = {}
    try:
        # Items are indexed top-to-bottom.
        item = [
            [
                [pool.new() for _color in range(COLOR_COUNT)]
                for _position in range(height)
            ]
            for _column in range(COLOR_COUNT)
        ]
        categories["item"] = COLOR_COUNT * height * COLOR_COUNT

        # Index zero is unused so the mathematical endpoint is the list index.
        boundary = [[0] * height for _column in range(COLOR_COUNT)]
        for column in range(COLOR_COUNT):
            for endpoint in range(1, height):
                boundary[column][endpoint] = pool.new()
        categories["boundary"] = COLOR_COUNT * (height - 1)

        states = [
            state
            for state in itertools.product(range(1, height + 1), repeat=COLOR_COUNT)
            if sum(endpoint == height for endpoint in state) <= 1
        ]
        if len(states) != expected_state_count(height):
            raise GenerationError("internal non-goal state count mismatch")
        trap = {state: pool.new() for state in states}
        categories["trap"] = len(states)

        # Exactly one colour at each item position.
        for column in range(COLOR_COUNT):
            for position in range(height):
                variables = item[column][position]
                writer.add(variables)
                for left in range(COLOR_COUNT):
                    for right in range(left + 1, COLOR_COUNT):
                        writer.add([-variables[left], -variables[right]])

        # Every colour occurs exactly height times globally.
        for color in range(COLOR_COUNT):
            literals = [
                item[column][position][color]
                for column in range(COLOR_COUNT)
                for position in range(height)
            ]
            encode_pb(
                writer,
                pool,
                relation="equals",
                literals=literals,
                weights=[1] * len(literals),
                bound=height,
            )

        # A boundary is exactly a colour change.
        for column in range(COLOR_COUNT):
            for endpoint in range(1, height):
                marker = boundary[column][endpoint]
                above = item[column][endpoint - 1]
                below = item[column][endpoint]
                for first in range(COLOR_COUNT):
                    writer.add([-above[first], -below[first], -marker])
                    for second in range(COLOR_COUNT):
                        if first != second:
                            writer.add([-above[first], -below[second], marker])

        if symmetry_breaking:
            flattened = [
                item[column][position]
                for column in range(COLOR_COUNT)
                for position in range(height)
            ]
            writer.add([flattened[0][0]])
            for index, variables in enumerate(flattened):
                for color in range(1, COLOR_COUNT):
                    writer.add(
                        [-variables[color], *[
                            earlier[color - 1] for earlier in flattened[:index]
                        ]]
                    )

        if fixed_layout is not None:
            for column in range(COLOR_COUNT):
                for position in range(height):
                    writer.add([item[column][position][fixed_layout[column][position]]])

        # The unique actual initial tuple is marked.  Initial tuples that are
        # already goals (two monochrome original columns) are explicitly
        # forbidden, otherwise they would create a spurious SAT assignment.
        all_tuples = itertools.product(range(1, height + 1), repeat=COLOR_COUNT)
        for state in all_tuples:
            guard = [
                literal
                for column, endpoint in enumerate(state)
                for literal in initial_guard(boundary, column, endpoint, height)
            ]
            clause = [-literal for literal in guard]
            if state in trap:
                clause.append(trap[state])
            writer.add(clause)

        # A marked live endpoint must be a genuine boundary.
        for state, marked in trap.items():
            for column, endpoint in enumerate(state):
                if endpoint < height:
                    writer.add([-marked, boundary[column][endpoint]])

        positive_count = 0
        legal_count = 0
        transition_count = 0
        for state in states:
            marked = trap[state]
            exhausted = sum(endpoint == height for endpoint in state)
            legal_limit = EMPTY_COLUMNS + exhausted
            for source, source_endpoint in enumerate(state):
                if source_endpoint == height:
                    continue

                positives: list[int] = []
                for color in range(COLOR_COUNT):
                    positive = pool.new()
                    positives.append(positive)
                    positive_count += 1

                    literals: list[int] = []
                    weights: list[int] = []
                    for column, endpoint in enumerate(state):
                        for position in range(endpoint):
                            literals.append(item[column][position][color])
                            weights.append(1)

                    hosted_elsewhere = 0
                    for column, endpoint in enumerate(state):
                        if column == source or endpoint == height:
                            continue
                        literals.append(-item[column][endpoint - 1][color])
                        weights.append(endpoint)
                        hosted_elsewhere += endpoint

                    # positive <=> F_c - sum(other host capacities) > 0.
                    encode_pb(
                        writer,
                        pool,
                        relation="atleast",
                        literals=literals,
                        weights=weights,
                        bound=hosted_elsewhere + 1,
                        guard=-positive,
                    )
                    encode_pb(
                        writer,
                        pool,
                        relation="atmost",
                        literals=literals,
                        weights=weights,
                        bound=hosted_elsewhere,
                        guard=positive,
                    )

                legal = pool.new()
                legal_count += 1
                # Four variables make a truth-table reification smaller and
                # easier to audit than another guarded cardinality encoding.
                for mask in range(1 << COLOR_COUNT):
                    antecedent_negation = [
                        -positives[color]
                        if mask & (1 << color)
                        else positives[color]
                        for color in range(COLOR_COUNT)
                    ]
                    is_legal = mask.bit_count() <= legal_limit
                    writer.add(
                        [*antecedent_negation, legal if is_legal else -legal]
                    )

                for target in range(source_endpoint + 1, height + 1):
                    successor = list(state)
                    successor[source] = target
                    successor_tuple = tuple(successor)
                    clause = [
                        -marked,
                        -legal,
                        *next_guard_negation(
                            boundary, source, source_endpoint, target, height
                        ),
                    ]
                    if successor_tuple in trap:
                        clause.append(trap[successor_tuple])
                    writer.add(clause)
                    transition_count += 1

        categories["positive"] = positive_count
        categories["legal"] = legal_count
        if transition_count != expected_transition_count(height):
            raise GenerationError(
                f"transition count {transition_count} does not match "
                f"{expected_transition_count(height)}"
            )

        semantic_variables = sum(categories.values())
        categories["pb_auxiliary"] = pool.top - semantic_variables
        writer.finish(pool.top)
    except Exception:
        writer.abort()
        raise

    mapping = {
        "schema": 1,
        "height": height,
        "colors": COLOR_COUNT,
        "empty_columns": EMPTY_COLUMNS,
        "orientation": "top-to-bottom",
        "item_variables": item,
    }
    write_json(args.map, mapping)
    metadata = {
        "schema": 1,
        "problem": {
            "height": height,
            "colors": COLOR_COUNT,
            "empty_columns": EMPTY_COLUMNS,
        },
        "orientation": "top-to-bottom",
        "symmetry_breaking": symmetry_breaking,
        "fixed_instance": (
            {
                "path": str(args.fix_instance),
                "sha256": sha256(args.fix_instance),
            }
            if args.fix_instance is not None
            else None
        ),
        "counts": {
            "variables": pool.top,
            "clauses": writer.clauses,
            "non_goal_states": len(states),
            "guarded_transitions": transition_count,
            "variable_categories": categories,
        },
        "expected": {
            "non_goal_states": expected_state_count(height),
            "guarded_transitions": expected_transition_count(height),
        },
        "files": {
            "cnf": {
                "path": str(args.cnf),
                "bytes": args.cnf.stat().st_size,
                "sha256": sha256(args.cnf),
            },
            "map": {
                "path": str(args.map),
                "bytes": args.map.stat().st_size,
                "sha256": sha256(args.map),
            },
        },
    }
    write_json(args.metadata, metadata)
    print(json.dumps(metadata["counts"], sort_keys=True))


def parse_model(path: Path) -> dict[int, bool]:
    assignments: dict[int, bool] = {}
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        fields = raw_line.split()
        if not fields:
            continue
        if fields[0] in {"c", "s"}:
            continue
        if fields[0] == "v":
            fields = fields[1:]
        for field in fields:
            literal = int(field)
            if literal == 0:
                continue
            variable = abs(literal)
            value = literal > 0
            if variable in assignments and assignments[variable] != value:
                raise GenerationError(f"model assigns variable {variable} both ways")
            assignments[variable] = value
    return assignments


def decode(args: argparse.Namespace) -> None:
    mapping = json.loads(args.map.read_text(encoding="utf-8"))
    if mapping.get("schema") != 1 or mapping.get("colors") != COLOR_COUNT:
        raise GenerationError("unsupported variable map")
    height = int(mapping["height"])
    item_variables = mapping["item_variables"]
    assignments = parse_model(args.model)
    top_to_bottom: list[list[int]] = []
    for column in range(COLOR_COUNT):
        decoded: list[int] = []
        for position in range(height):
            selected = [
                color
                for color, variable in enumerate(item_variables[column][position])
                if assignments.get(int(variable)) is True
            ]
            if len(selected) != 1:
                raise GenerationError(
                    f"model does not select exactly one colour at ({column},{position})"
                )
            decoded.append(selected[0])
        top_to_bottom.append(decoded)

    counts = [0] * COLOR_COUNT
    for column in top_to_bottom:
        for color in column:
            counts[color] += 1
    if counts != [height] * COLOR_COUNT:
        raise GenerationError(f"decoded model is not balanced: {counts}")

    lines = [
        "# Decoded from an exact fixed-instance trap-CNF SAT model.",
        "# Columns are written bottom-to-top.",
        f"height={height}",
        f"colors={COLOR_COUNT}",
        f"empty={EMPTY_COLUMNS}",
    ]
    for column in top_to_bottom:
        lines.append("column=" + "".join(str(color) for color in reversed(column)))
    args.candidate.parent.mkdir(parents=True, exist_ok=True)
    args.candidate.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"candidate={args.candidate}")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate_parser = subparsers.add_parser("generate", help="write exact DIMACS")
    generate_parser.add_argument("--height", type=int, required=True)
    generate_parser.add_argument("--cnf", type=Path, required=True)
    generate_parser.add_argument("--map", type=Path, required=True)
    generate_parser.add_argument("--metadata", type=Path, required=True)
    generate_parser.add_argument("--fix-instance", type=Path)
    generate_parser.add_argument("--no-symmetry-breaking", action="store_true")
    generate_parser.set_defaults(function=generate)

    decode_parser = subparsers.add_parser("decode", help="decode a SAT model")
    decode_parser.add_argument("--map", type=Path, required=True)
    decode_parser.add_argument("--model", type=Path, required=True)
    decode_parser.add_argument("--candidate", type=Path, required=True)
    decode_parser.set_defaults(function=decode)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        args.function(args)
        return 0
    except (GenerationError, OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
