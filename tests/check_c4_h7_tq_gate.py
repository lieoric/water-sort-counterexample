#!/usr/bin/env python3
"""Independent audit of the targeted c4/k2/h7 Tq-gate universe.

The local census and fixed-chain game in this file are intentionally rebuilt
from the mathematical definition.  They do not import or call the C++
enumerator.  With ``--program``, the script additionally runs a bounded C++
job and checks its public report and representative layouts.
"""

from __future__ import annotations

import argparse
import itertools
import json
import random
import subprocess
import sys
import tempfile
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Iterator, Sequence


HEIGHT = 7
Q, B, Y, X = range(4)
COLOR_CHARS = "0123"

EXPECTED_LOCAL_MATRIX = {
    (2, 1): 0,
    (3, 1): 84,
    (3, 2): 84,
    (4, 1): 252,
    (4, 2): 252,
    (4, 3): 462,
    (5, 1): 252,
    (5, 2): 252,
    (5, 3): 336,
    (5, 4): 0,
    (6, 1): 84,
    (6, 2): 84,
    (6, 3): 84,
    (6, 4): 0,
    (6, 5): 0,
}
EXPECTED_PER_S = {2: 0, 3: 168, 4: 966, 5: 840, 6: 252}
EXPECTED_PREFIX_COUNTS = {1: 60, 2: 140, 3: 280, 4: 504, 5: 840}
EXPECTED_LOCAL_LOSING = 2_226
EXPECTED_LABELED_LAYOUTS = 381_360

Decoration = tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]
Layout = tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...], tuple[int, ...]]
Run = tuple[int, int]
LiveColumn = tuple[int, int, tuple[Run, ...]]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def bounded_multiset_assignments(
    size: int, counts: dict[int, int]
) -> Iterator[tuple[int, ...]]:
    """Generate each labeled word with the requested small color multiset."""

    items = tuple((color, count) for color, count in sorted(counts.items()) if count)
    require(sum(count for _, count in items) == size, "multiset size mismatch")
    cells = [-1] * size

    def visit(item: int, available: tuple[int, ...]) -> Iterator[tuple[int, ...]]:
        color, count = items[item]
        if item + 1 == len(items):
            if len(available) != count:
                return
            for position in available:
                cells[position] = color
            yield tuple(cells)
            return
        for selected in itertools.combinations(available, count):
            selected_set = set(selected)
            for position in selected:
                cells[position] = color
            yield from visit(
                item + 1,
                tuple(position for position in available if position not in selected_set),
            )

    if not items:
        yield ()
    else:
        yield from visit(0, tuple(range(size)))


def suffix_decorations(s: int) -> Iterator[Decoration]:
    """Three labeled four-cell suffixes, written bottom-to-top."""

    require(2 <= s <= 6, f"invalid s={s}")
    for word in bounded_multiset_assignments(12, {B: s, Y: 6, X: 6 - s}):
        yield word[0:4], word[4:8], word[8:12]


def prefix_arrangements(u: int) -> Iterator[tuple[tuple[int, ...], ...]]:
    """Four exposed prefixes, written bottom-to-top with bottom cell q."""

    require(1 <= u <= 5, f"invalid u={u}")
    lengths = (3, 3, 3, u)
    free_slots = tuple(
        (column, offset)
        for column, length in enumerate(lengths)
        for offset in range(1, length)
    )
    for assignment in bounded_multiset_assignments(
        len(free_slots), {Q: 3, Y: 1, X: 1 + u}
    ):
        prefixes = [[Q] + [-1] * (length - 1) for length in lengths]
        for (column, offset), color in zip(free_slots, assignment):
            prefixes[column][offset] = color
        yield tuple(tuple(prefix) for prefix in prefixes)


def run_lengths(top_to_bottom: Iterable[int]) -> tuple[Run, ...]:
    runs: list[Run] = []
    for color in top_to_bottom:
        if runs and runs[-1][0] == color:
            runs[-1] = color, runs[-1][1] + 1
        else:
            runs.append((color, 1))
    return tuple(runs)


def source_is_legal(debts: tuple[int, ...], z: int, top: int, cap: int) -> bool:
    adjusted = list(debts)
    adjusted[top] += cap
    return sum(value > 0 for value in adjusted) <= 2 + z


@lru_cache(maxsize=None)
def fixed_chain_is_winning(
    z: int,
    debts: tuple[int, int, int, int],
    columns: tuple[LiveColumn | None, ...],
) -> bool:
    """Exact deterministic-future top-border DP from one macro checkpoint."""

    if z >= 2:
        return True
    for source, column in enumerate(columns):
        if column is None:
            continue
        top, cap, future = column
        if not source_is_legal(debts, z, top, cap):
            continue
        require(bool(future), "active local-DP column has no hidden run")
        next_color, run = future[0]
        require(next_color != top, "adjacent fixed-chain runs share a color")
        child_debts = list(debts)
        child_debts[top] += cap
        child_columns = list(columns)
        if len(future) == 1:
            require(cap + run == HEIGHT, "final run does not exhaust height seven")
            child_debts[next_color] += run
            child_columns[source] = None
            child_z = z + 1
        else:
            require(cap + run < HEIGHT, "nonfinal run unexpectedly exhausts")
            child_debts[next_color] -= cap
            child_columns[source] = (next_color, cap + run, future[1:])
            child_z = z
        if fixed_chain_is_winning(
            child_z, tuple(child_debts), tuple(child_columns)  # type: ignore[arg-type]
        ):
            return True
    return False


def local_is_losing(decoration: Decoration, s: int, u: int) -> bool:
    """Classify a fixed suffix decoration from P_(s,u)."""

    require(1 <= u < s <= 6, f"invalid gate pair {(s, u)}")
    fourth_top_to_bottom = (X,) * (s - u) + (B,) * (HEIGHT - s)
    futures = tuple(
        run_lengths(reversed(word)) for word in decoration
    ) + (run_lengths(fourth_top_to_bottom),)
    columns: tuple[LiveColumn | None, ...] = tuple(
        (Q, cap, future)
        for cap, future in zip((3, 3, 3, u), futures)
    )
    debts = (-2 - u, 0, 1, 1 + u)
    return not fixed_chain_is_winning(0, debts, columns)


def prefix_reaches_gate(prefixes: tuple[tuple[int, ...], ...], u: int) -> bool:
    """Check that some legal initial border order reaches P_(s,u)'s prefix state."""

    target_caps = (3, 3, 3, u)
    target_debts = (-2 - u, 0, 1, 1 + u)
    initial: tuple[LiveColumn, ...] = tuple(
        (runs[0][0], runs[0][1], runs[1:])
        for runs in (run_lengths(reversed(prefix)) for prefix in prefixes)
    )

    @lru_cache(maxsize=None)
    def reaches(
        debts: tuple[int, int, int, int], columns: tuple[LiveColumn, ...]
    ) -> bool:
        if all(not future for _, _, future in columns):
            return (
                tuple(top for top, _, _ in columns) == (Q, Q, Q, Q)
                and tuple(cap for _, cap, _ in columns) == target_caps
                and debts == target_debts
            )
        for source, (top, cap, future) in enumerate(columns):
            if not future or not source_is_legal(debts, 0, top, cap):
                continue
            next_color, run = future[0]
            child_debts = list(debts)
            child_debts[top] += cap
            child_debts[next_color] -= cap
            child_columns = list(columns)
            child_columns[source] = (next_color, cap + run, future[1:])
            if reaches(tuple(child_debts), tuple(child_columns)):  # type: ignore[arg-type]
                return True
        return False

    return reaches((0, 0, 0, 0), initial)


def build_layout(
    decoration: Decoration,
    prefixes: tuple[tuple[int, ...], ...],
    s: int,
    u: int,
) -> Layout:
    """Build four complete columns in the repository's bottom-to-top format."""

    fourth_hidden = (B,) * (HEIGHT - s) + (X,) * (s - u)
    columns = tuple(
        decoration[column] + prefixes[column] for column in range(3)
    ) + (fourth_hidden + prefixes[3],)
    return columns  # type: ignore[return-value]


def validate_layout(layout: Layout, s: int, u: int) -> Decoration:
    require(len(layout) == 4, "layout does not have four original columns")
    require(all(len(column) == HEIGHT for column in layout), "column length is not seven")
    counts = Counter(color for column in layout for color in column)
    require(counts == Counter({Q: 7, B: 7, Y: 7, X: 7}), f"unbalanced layout: {counts}")

    prefixes = (
        layout[0][4:],
        layout[1][4:],
        layout[2][4:],
        layout[3][HEIGHT - u :],
    )
    require(all(prefix[0] == Q for prefix in prefixes), "gate-prefix boundary is not q")
    require(prefix_reaches_gate(prefixes, u), f"constructed prefix does not reach P_{s,u}")

    decoration: Decoration = (layout[0][:4], layout[1][:4], layout[2][:4])
    suffix_counts = Counter(color for word in decoration for color in word)
    require(
        suffix_counts == Counter({B: s, Y: 6, X: 6 - s}),
        f"wrong decorated suffix multiset: {suffix_counts}",
    )
    expected_fourth = (B,) * (HEIGHT - s) + (X,) * (s - u)
    require(layout[3][: HEIGHT - u] == expected_fourth, "wrong fixed fourth suffix")
    return decoration


def instance_text(layout: Layout) -> str:
    return "\n".join(
        ("height=7", "colors=4", "empty=2")
        + tuple("column=" + "".join(COLOR_CHARS[color] for color in column) for column in layout)
    ) + "\n"


def full_layout_is_solvable(layout: Layout) -> bool:
    """Independent full fixed-chain decision from the initial top borders."""

    columns: tuple[LiveColumn | None, ...] = tuple(
        (runs[0][0], runs[0][1], runs[1:])
        for runs in (run_lengths(reversed(column)) for column in layout)
    )
    require(all(column[2] for column in columns if column), "unexpected monochrome input column")
    return fixed_chain_is_winning(0, (0, 0, 0, 0), columns)


def replay_removal_witness(layout: Layout, moves: str) -> None:
    """Replay a complete BorderOracle column-removal witness independently."""

    debts: tuple[int, int, int, int] = (0, 0, 0, 0)
    columns: list[LiveColumn | None] = [
        (runs[0][0], runs[0][1], runs[1:])
        for runs in (run_lengths(reversed(column)) for column in layout)
    ]
    z = 0
    for step, character in enumerate(moves):
        require(character in "0123", f"bad removal column {character!r}")
        source = int(character)
        column = columns[source]
        require(column is not None, f"step {step} selects exhausted column {source}")
        top, cap, future = column
        require(bool(future), f"step {step} has no border to remove")
        require(source_is_legal(debts, z, top, cap), f"step {step} is illegal")
        next_color, run = future[0]
        child_debts = list(debts)
        child_debts[top] += cap
        if len(future) == 1:
            require(cap + run == HEIGHT, f"step {step} has a bad final run")
            child_debts[next_color] += run
            columns[source] = None
            z += 1
        else:
            require(cap + run < HEIGHT, f"step {step} exhausts before the final run")
            child_debts[next_color] -= cap
            columns[source] = (next_color, cap + run, future[1:])
        debts = tuple(child_debts)  # type: ignore[assignment]
    require(all(column is None for column in columns), "removal witness does not reach state zero")


def audit_independent_universe() -> dict[str, object]:
    matrix: dict[tuple[int, int], int] = {}
    losing_samples: dict[tuple[int, int], list[Decoration]] = {}
    decoration_totals: dict[int, int] = {}
    for s in range(2, 7):
        per_pair = {u: 0 for u in range(1, s)}
        samples = {u: [] for u in range(1, s)}
        decoration_total = 0
        for decoration in suffix_decorations(s):
            decoration_total += 1
            for u in range(1, s):
                if not local_is_losing(decoration, s, u):
                    continue
                per_pair[u] += 1
                if len(samples[u]) < 3:
                    samples[u].append(decoration)
                elif per_pair[u] % 97 == 0:
                    samples[u][-1] = decoration
        decoration_totals[s] = decoration_total
        for u, count in per_pair.items():
            matrix[(s, u)] = count
            losing_samples[(s, u)] = samples[u]

    require(matrix == EXPECTED_LOCAL_MATRIX, f"local losing matrix mismatch: {matrix}")
    per_s = {
        s: sum(count for (pair_s, _), count in matrix.items() if pair_s == s)
        for s in range(2, 7)
    }
    require(per_s == EXPECTED_PER_S, f"per-s losing counts mismatch: {per_s}")
    require(len(matrix) == 15, f"expected all 15 (s,u) pairs, got {len(matrix)}")
    require(sum(count > 0 for count in matrix.values()) == 11, "nonzero pair count is not 11")
    require(sum(count == 0 for count in matrix.values()) == 4, "zero pair count is not 4")
    require(sum(matrix.values()) == EXPECTED_LOCAL_LOSING, "local losing total is not 2226")

    prefix_lists = {u: tuple(prefix_arrangements(u)) for u in range(1, 6)}
    prefix_counts = {u: len(values) for u, values in prefix_lists.items()}
    require(prefix_counts == EXPECTED_PREFIX_COUNTS, f"prefix census mismatch: {prefix_counts}")
    for u, values in prefix_lists.items():
        unreachable = sum(not prefix_reaches_gate(prefixes, u) for prefixes in values)
        require(unreachable == 0, f"u={u} has {unreachable} prefixes not reaching P")

    labeled_layouts = sum(
        losing * prefix_counts[u] for (s, u), losing in matrix.items()
    )
    require(labeled_layouts == EXPECTED_LABELED_LAYOUTS, "labeled layout total is not 381360")

    rng = random.Random(0xC407)
    checked_samples = 0
    for pair, losing_count in matrix.items():
        if losing_count == 0:
            continue
        s, u = pair
        decorations = losing_samples[pair]
        prefixes = prefix_lists[u]
        chosen_prefixes = [prefixes[0], prefixes[-1], prefixes[rng.randrange(len(prefixes))]]
        for decoration in decorations:
            for prefix in chosen_prefixes:
                layout = build_layout(decoration, prefix, s, u)
                reconstructed = validate_layout(layout, s, u)
                require(local_is_losing(reconstructed, s, u), "sample lost its local-losing property")
                checked_samples += 1

    return {
        "matrix": matrix,
        "per_s": per_s,
        "decoration_totals": decoration_totals,
        "prefix_counts": prefix_counts,
        "local_losing": sum(matrix.values()),
        "labeled_layouts": labeled_layouts,
        "sample_layouts_checked": checked_samples,
        "losing_samples": losing_samples,
        "prefix_lists": prefix_lists,
    }


def parse_layout_record(value: object) -> Layout:
    """Accept a four-string sample or a standard instance-shaped object."""

    if isinstance(value, dict):
        value = value.get("columns")
    if isinstance(value, str):
        value = value.split("|")
    require(isinstance(value, list) and len(value) == 4, f"bad layout record: {value!r}")
    columns = []
    for raw in value:
        require(isinstance(raw, str) and len(raw) == HEIGHT, f"bad column: {raw!r}")
        require(all(character in COLOR_CHARS for character in raw), f"bad color in {raw!r}")
        columns.append(tuple(int(character) for character in raw))
    return tuple(columns)  # type: ignore[return-value]


def report_pair_rows(report: dict[str, object]) -> list[dict[str, object]]:
    value = report.get("pairs")
    require(isinstance(value, list), "report has no pairs array")
    return value  # type: ignore[return-value]


def validate_bounded_report(report: dict[str, object], expected_checked: int) -> None:
    """Validate public totals, all pair rows, and any emitted sample layouts."""

    require(report.get("schema_version") == 1, "unsupported report schema")
    require(report.get("labeled_layouts_expected") == EXPECTED_LABELED_LAYOUTS, "bad expected total")
    status = report.get("status")
    checked = report.get("labeled_layouts_checked")
    require(isinstance(checked, int) and 0 < checked <= expected_checked, "bad bounded checked count")
    require(report.get("candidate_pairs_total") == 15, "candidate pair total is not 15")
    require(report.get("nonzero_losing_pairs") == 11, "nonzero pair total is not 11")
    require(report.get("zero_losing_pairs") == 4, "zero pair total is not 4")
    require(report.get("local_losing_decorations") == EXPECTED_LOCAL_LOSING, "bad local total")
    require(
        report.get("per_u_prefix_arrangements") == {"1": 60, "2": 140, "3": 280},
        "bad public prefix counts",
    )
    require(status in {"INCOMPLETE", "NO_FOUND", "ALL_YES"}, "bad report status")
    if status == "INCOMPLETE":
        require(checked == expected_checked, "limit run stopped before its requested bound")
        require(report.get("verified") is False, "incomplete report claims verification")
        require(report.get("universe_complete") is False, "incomplete report claims completeness")
    elif status == "NO_FOUND":
        require(report.get("verified") is True, "NO report is not marked verified")
        require(report.get("universe_complete") is False, "NO report claims full enumeration")
    else:
        require(checked == EXPECTED_LABELED_LAYOUTS, "ALL_YES report is incomplete")
        require(report.get("verified") is True, "ALL_YES report is not verified")
        require(report.get("universe_complete") is True, "ALL_YES report lacks completeness")
    unique = report.get("unique_layouts_checked")
    require(isinstance(unique, int) and 0 < unique <= checked, "bad unique checked count")
    yes = report.get("yes_count")
    no = report.get("no_count")
    require(isinstance(yes, int) and isinstance(no, int) and yes + no == checked, "bad YES/NO totals")
    if status == "INCOMPLETE":
        require(no == 0, "INCOMPLETE report should have stopped as NO_FOUND")
    elif status == "NO_FOUND":
        require(no >= 1, "NO_FOUND report has no NO classification")
    else:
        require(yes == EXPECTED_LABELED_LAYOUTS and no == 0, "bad ALL_YES classification")
    unique_yes = report.get("unique_yes_count")
    unique_no = report.get("unique_no_count")
    require(
        isinstance(unique_yes, int)
        and isinstance(unique_no, int)
        and unique_yes + unique_no == unique,
        "bad canonical YES/NO totals",
    )

    rows = report_pair_rows(report)
    require(len(rows) == 15, f"expected 15 pair rows, got {len(rows)}")
    seen = set()
    for row in rows:
        s, u = int(row["s"]), int(row["u"])
        pair = (s, u)
        require(pair in EXPECTED_LOCAL_MATRIX, f"unexpected pair row {pair}")
        require(pair not in seen, f"duplicate pair row {pair}")
        seen.add(pair)
        expected_losing = EXPECTED_LOCAL_MATRIX[pair]
        require(int(row["local_losing"]) == expected_losing, f"{pair} bad local_losing")
        require(
            int(row["prefix_arrangements"]) == EXPECTED_PREFIX_COUNTS[u],
            f"{pair} has bad prefix count",
        )
        require(
            int(row["labeled_layouts"]) == expected_losing * EXPECTED_PREFIX_COUNTS[u],
            f"{pair} has bad labeled product",
        )

        row_checked = int(row.get("labeled_checked", 0))
        row_yes = int(row.get("yes_count", 0))
        row_no = int(row.get("no_count", 0))
        require(0 <= row_checked <= expected_losing * EXPECTED_PREFIX_COUNTS[u], f"{pair} bad checked")
        require(row_yes + row_no == row_checked, f"{pair} bad YES/NO accounting")
        canonical_unique = int(row["canonical_unique"])
        canonical_yes = int(row["canonical_yes"])
        canonical_no = int(row["canonical_no"])
        require(0 <= canonical_unique <= row_checked, f"{pair} bad canonical_unique")
        require(canonical_yes + canonical_no == canonical_unique, f"{pair} bad canonical split")
        first_actions = row["first_action_counts"]
        require(
            isinstance(first_actions, list)
            and len(first_actions) == 4
            and all(isinstance(value, int) and value >= 0 for value in first_actions),
            f"{pair} bad first_action_counts",
        )
        require(sum(first_actions) == canonical_yes, f"{pair} first-action sum mismatch")
        oracle_states = int(row["oracle_states"])
        max_oracle_states = int(row["max_oracle_states"])
        oracle_transitions = int(row["oracle_transitions"])
        require(oracle_states >= max_oracle_states >= 0, f"{pair} bad oracle states")
        require(oracle_transitions >= 0, f"{pair} bad oracle transitions")
        if canonical_unique == 0:
            require(oracle_states == max_oracle_states == oracle_transitions == 0, f"{pair} idle oracle stats")
        witness = row.get("solvable_witness")
        require((witness is not None) == (row_yes > 0), f"{pair} solvable witness presence mismatch")
        if witness is not None:
            require(isinstance(witness, dict), f"{pair} solvable witness is malformed")
            layout = parse_layout_record(witness)
            decoration = validate_layout(layout, s, u)
            require(local_is_losing(decoration, s, u), f"{pair} witness is not locally losing")
            moves = witness.get("removal_columns")
            require(isinstance(moves, str), f"{pair} witness moves are malformed")
            replay_removal_witness(layout, moves)
    require(seen == set(EXPECTED_LOCAL_MATRIX), "pair-row coverage is incomplete")
    require(sum(int(row.get("labeled_checked", 0)) for row in rows) == checked, "row checked sum mismatch")
    require(sum(int(row.get("yes_count", 0)) for row in rows) == yes, "row YES sum mismatch")
    require(sum(int(row.get("no_count", 0)) for row in rows) == no, "row NO sum mismatch")

    require(sum(int(row["canonical_unique"]) for row in rows) >= unique, "global unique exceeds pair uniques")
    require(sum(int(row["oracle_states"]) for row in rows) == report.get("oracle_states_visited"), "oracle state sum mismatch")
    require(
        sum(int(row["oracle_transitions"]) for row in rows)
        == report.get("oracle_transitions_tested"),
        "oracle transition sum mismatch",
    )
    require(
        checked - sum(int(row["canonical_unique"]) for row in rows)
        == report.get("canonical_cache_hits"),
        "canonical cache accounting mismatch",
    )

    if status == "NO_FOUND":
        witness = report.get("no_witness")
        require(witness is not None, "NO report has no witness record")
        layout = parse_layout_record(witness)
        require(isinstance(witness, dict) and witness.get("orientation") == "bottom-to-top", "bad NO orientation")
        require(not full_layout_is_solvable(layout), "reported NO is independently solvable")
    else:
        require("no_witness" not in report, "non-NO report contains a NO witness")


def run_bounded_program(program: Path, limit: int) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="c4-h7-tq-gate-audit-") as directory:
        output = Path(directory)
        process = subprocess.run(
            [str(program), "--output-dir", str(output), "--limit", str(limit)],
            check=False,
            capture_output=True,
            text=True,
        )
        require(
            process.returncode == 0,
            f"bounded program failed ({process.returncode})\nstdout={process.stdout}\nstderr={process.stderr}",
        )
        report_path = output / "report.json"
        require(report_path.is_file(), "bounded program did not write report.json")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        no_path = output / "no-instance.txt"
        if report.get("status") == "NO_FOUND":
            require(no_path.is_file(), "NO report did not save no-instance.txt")
            columns = [
                line.split("=", 1)[1]
                for line in no_path.read_text(encoding="utf-8").splitlines()
                if line.startswith("column=")
            ]
            require(report.get("no_witness", {}).get("columns") == columns, "NO file/report mismatch")
        else:
            require(not no_path.exists(), "non-NO run wrote no-instance.txt")
        return report


def differential_oracle_samples(oracle: Path, independent: dict[str, object]) -> int:
    """Compare a few constructed layouts with the existing oracle executable."""

    losing_samples = independent["losing_samples"]
    prefix_lists = independent["prefix_lists"]
    checked = 0
    with tempfile.TemporaryDirectory(prefix="c4-h7-tq-oracle-diff-") as directory:
        output = Path(directory)
        for s, u in sorted(pair for pair, count in EXPECTED_LOCAL_MATRIX.items() if count):
            decoration = losing_samples[(s, u)][0]
            prefixes = prefix_lists[u][0]
            layout = build_layout(decoration, prefixes, s, u)
            validate_layout(layout, s, u)
            expected = "SOLVABLE" if full_layout_is_solvable(layout) else "UNSOLVABLE"
            instance = output / f"s{s}-u{u}.txt"
            instance.write_text(instance_text(layout), encoding="utf-8")
            process = subprocess.run(
                [str(oracle), "--input", str(instance)],
                check=False,
                capture_output=True,
                text=True,
            )
            require(
                process.returncode == 0,
                f"oracle failed for {(s, u)}\nstdout={process.stdout}\nstderr={process.stderr}",
            )
            classifications = [
                line.strip()
                for line in process.stdout.splitlines()
                if line.strip() in {"SOLVABLE", "UNSOLVABLE"}
            ]
            require(classifications == [expected], f"oracle mismatch for {(s, u)}: {classifications} != {expected}")
            checked += 1
    return checked


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--program", type=Path, help="bounded C++ checker to audit")
    parser.add_argument("--oracle", type=Path, help="existing water-oracle for a small differential")
    parser.add_argument("--report", type=Path, help="existing bounded report to audit")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    options = parse_args(argv)
    independent = audit_independent_universe()
    print(
        "independent census: "
        f"local={independent['local_losing']} "
        f"labeled={independent['labeled_layouts']} "
        f"samples={independent['sample_layouts_checked']}"
    )

    if options.report:
        report = json.loads(options.report.read_text(encoding="utf-8"))
        checked = int(report["labeled_layouts_checked"])
        validate_bounded_report(report, checked)
        print(f"validated report {options.report} ({checked} layouts)")

    if options.program:
        require(options.program.is_file(), f"program not found: {options.program}")
        report = run_bounded_program(options.program.resolve(), 256)
        validate_bounded_report(report, 256)
        # A second tiny run catches unstable row ordering/count accounting while
        # keeping the oracle differential far below the 381,360-layout job.
        tiny_first = run_bounded_program(options.program.resolve(), 17)
        tiny_second = run_bounded_program(options.program.resolve(), 17)
        validate_bounded_report(tiny_first, 17)
        validate_bounded_report(tiny_second, 17)
        stable_keys = (
            "status",
            "labeled_layouts_expected",
            "labeled_layouts_checked",
            "candidate_pairs_total",
            "nonzero_losing_pairs",
            "zero_losing_pairs",
            "local_losing_decorations",
            "per_u_prefix_arrangements",
        )
        require(
            {key: tiny_first.get(key) for key in stable_keys}
            == {key: tiny_second.get(key) for key in stable_keys},
            "tiny bounded reports are nondeterministic",
        )
        print("bounded C++ reports passed limits 256 and 17x2")
    if options.oracle:
        require(options.oracle.is_file(), f"oracle not found: {options.oracle}")
        checked = differential_oracle_samples(options.oracle.resolve(), independent)
        print(f"independent/full-oracle differential passed {checked} layouts")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, KeyError, OSError, ValueError) as error:
        print(f"audit error: {error}", file=sys.stderr)
        raise SystemExit(1)
