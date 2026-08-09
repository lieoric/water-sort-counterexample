#!/usr/bin/env python3
"""Jointly choose a balanced instance and encode its exact top-border DAG.

SAT emits a concrete candidate for independent checking by the C++ oracle.
UNSAT covers exactly one finite height and one complete shard; it is not an
arbitrary-height theorem and this script does not emit a solver proof object.
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
import time
from pathlib import Path

from z3 import And, Bool, If, Implies, Int, Not, Or, Solver, Sum, sat, unsat


def lex_leq(left, right):
    terms = [And(*(left[j] == right[j] for j in range(len(left))))]
    for index in range(len(left)):
        terms.append(And(*(left[j] == right[j] for j in range(index)),
                         left[index] < right[index]))
    return Or(*terms)


def parse_options():
    parser = argparse.ArgumentParser()
    parser.add_argument("--height", type=int, required=True)
    parser.add_argument("--colors", type=int, default=4)
    parser.add_argument("--empty", type=int, default=2)
    parser.add_argument("--shard", type=int, default=0)
    parser.add_argument("--shards", type=int, default=1)
    parser.add_argument("--timeout-ms", type=int, default=0)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    options = parser.parse_args()
    if not 1 <= options.height <= 255:
        parser.error("height must lie in [1, 255]")
    if not 1 <= options.colors <= 36:
        parser.error("colors must lie in [1, 36]")
    if options.empty < 0:
        parser.error("empty must be nonnegative")
    if options.shards < 1 or not 0 <= options.shard < options.shards:
        parser.error("require 0 <= shard < shards")
    if options.timeout_ms < 0:
        parser.error("timeout must be nonnegative")
    return options


def previous_is(boundary, column, position, previous):
    assert 0 <= previous < position
    if previous == 0:
        return And(*(Not(boundary[column][rank])
                     for rank in range(1, position)))
    return And(boundary[column][previous],
               *(Not(boundary[column][rank])
                 for rank in range(previous + 1, position)))


def color_character(value):
    if value < 10:
        return str(value)
    return chr(ord("A") + value - 10)


def main() -> int:
    options = parse_options()
    height = options.height
    colors = options.colors
    columns = colors
    empty = options.empty
    target_exhausted = max(0, colors - empty)
    started = time.time()

    solver = Solver()
    if options.timeout_ms:
        solver.set(timeout=options.timeout_ms)
    solver.set(random_seed=options.shard + 1)

    item = [[Int(f"x_{column}_{position}")
             for position in range(height)]
            for column in range(columns)]
    for column in item:
        for value in column:
            solver.add(value >= 0, value < colors)
    for color in range(colors):
        solver.add(Sum(*(If(item[column][position] == color, 1, 0)
                         for column in range(columns)
                         for position in range(height))) == height)

    # Every color/column orbit has a representative satisfying these clauses.
    solver.add(item[0][0] == 0)
    for column in range(columns - 1):
        solver.add(lex_leq(item[column], item[column + 1]))

    # Partition the symmetry-reduced covering by the first column's base-c
    # integer code.  These congruence classes are disjoint and exhaustive.
    first_column_code = Sum(*(item[0][position] * (colors ** position)
                              for position in range(height)))
    solver.add(first_column_code % options.shards == options.shard)

    boundary = [[True] + [item[column][position - 1] !=
                           item[column][position]
                          for position in range(1, height)]
                for column in range(columns)]
    states = list(itertools.product(range(height), repeat=columns))
    win = {state: Bool("w_" + "_".join(map(str, state)))
           for state in states}

    for ordinal, state in enumerate(states, start=1):
        valid = And(*(True if position == 0 else
                      boundary[column][position]
                      for column, position in enumerate(state)))
        exhausted = sum(position == 0 for position in state)
        if exhausted >= target_exhausted:
            solver.add(Implies(valid, win[state]))
            continue

        free = []
        hosted = []
        for color in range(colors):
            free.append(Sum(*(If(item[column][original] == color, 1, 0)
                              for column, position in enumerate(state)
                              for original in range(position, height))))
            hosted.append(Sum(*(If(And(position > 0,
                                       item[column][position] == color),
                                  height - position, 0)
                                for column, position in enumerate(state))))

        choices = []
        available = empty + exhausted
        for column, position in enumerate(state):
            if position == 0:
                continue
            needed = Sum(*(If(
                free[color] > hosted[color] -
                If(item[column][position] == color,
                   height - position, 0), 1, 0)
                for color in range(colors)))
            successor = Or(*(And(
                previous_is(boundary, column, position, previous),
                win[state[:column] + (previous,) + state[column + 1:]])
                for previous in range(position)))
            choices.append(And(needed <= available, successor))
        solver.add(Implies(valid, win[state] == Or(*choices)))
        if ordinal % 1000 == 0:
            print(f"built={ordinal}/{len(states)}", file=sys.stderr,
                  flush=True)

    def top_is(column, position):
        if position == 0:
            return And(*(Not(boundary[column][rank])
                         for rank in range(1, height)))
        return And(boundary[column][position],
                   *(Not(boundary[column][rank])
                     for rank in range(position + 1, height)))

    initial_win = Or(*(And(*(top_is(column, state[column])
                             for column in range(columns)), win[state])
                       for state in states))
    solver.add(Not(initial_win))
    built_seconds = time.time() - started
    print(f"checking c={colors},h={height},k={empty}, "
          f"shard={options.shard}/{options.shards}, states={len(states)}, "
          f"build={built_seconds:.3f}s", file=sys.stderr, flush=True)

    checked = time.time()
    answer = solver.check()
    solve_seconds = time.time() - checked
    status = str(answer)
    candidate_text = None
    if answer == sat:
        model = solver.model()
        lines = ["# Columns are written bottom-to-top.",
                 f"height={height}", f"colors={colors}", f"empty={empty}"]
        for column in item:
            lines.append("column=" + "".join(
                color_character(model.eval(value).as_long())
                for value in column))
        candidate_text = "\n".join(lines) + "\n"
        options.candidate.parent.mkdir(parents=True, exist_ok=True)
        options.candidate.write_text(candidate_text, encoding="utf-8")
        print(candidate_text, end="")
    elif answer != unsat:
        status = "unknown"

    report = {
        "status": status,
        "reason_unknown": solver.reason_unknown() if status == "unknown" else "",
        "height": height,
        "colors": colors,
        "empty_columns": empty,
        "target_exhausted_columns": target_exhausted,
        "shard": options.shard,
        "shards": options.shards,
        "top_border_position_states": len(states),
        "timeout_ms": options.timeout_ms,
        "build_seconds": round(built_seconds, 3),
        "solve_seconds": round(solve_seconds, 3),
        "scope": "one exact finite-height SMT shard",
        "caveat": "UNSAT has no emitted solver proof and is not an arbitrary-height theorem",
    }
    options.result.parent.mkdir(parents=True, exist_ok=True)
    options.result.write_text(json.dumps(report, indent=2) + "\n",
                              encoding="utf-8")
    print(status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
