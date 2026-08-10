#!/usr/bin/env python3
"""Independent checks for the c4 rainbow-transversal/token-lift route.

The checker deliberately separates three statements:

* every balanced 4 by H layout has an H-way cell factorization into rainbow
  transversals;
* a *thick* transversal (one token in a run of length at least two) preserves
  the run-colour skeleton after deletion;
* a skeleton-preserving height-(H-1) path lifts only when every selected
  source is legal in both layouts.  The exact token error is checked at every
  visited source test.

An arbitrary rainbow deletion is never silently treated as run preserving.
Singleton tokens are reported with the additional borders that need a
separate local detour.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from functools import lru_cache
import itertools
import json
from pathlib import Path
from typing import Iterable, Sequence


COLORS = 4
EMPTY = 2


class CheckError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckError(message)


@dataclass(frozen=True)
class Run:
    color: int
    length: int
    top_start: int


@dataclass(frozen=True)
class Token:
    column: int
    color: int
    bottom_position: int
    run_index: int
    run_length: int


@dataclass
class LiftStats:
    states: int = 0
    child_legal_edges: int = 0
    jointly_legal_edges: int = 0
    parent_blocked_edges: int = 0
    first_block: dict[str, object] | None = None


BUILTINS: dict[str, tuple[list[str], bool]] = {
    # The especially symmetric certified h=8 NO instance.  It is the smallest
    # clean regression for a genuine four-way lock.
    "four_lock_h8": (
        ["22111003", "22111003", "00333221", "00333221"],
        False,
    ),
    # First independently reconstructed zero-debt member of the two-source D2
    # near-kernel.  The local checkpoint is NO, but this full initial layout is
    # YES; it is therefore a useful guard against confusing local and global
    # obstruction.
    "two_source_near_kernel_h7": (
        ["1111110", "2222100", "3332000", "3332032"],
        True,
    ),
}


def parse_instance(path: Path) -> list[str]:
    height: int | None = None
    colors: int | None = None
    empty: int | None = None
    words: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        require("=" in line, f"malformed instance line: {raw}")
        key, value = (field.strip() for field in line.split("=", 1))
        if key == "height":
            height = int(value)
        elif key == "colors":
            colors = int(value)
        elif key == "empty":
            empty = int(value)
        elif key == "column":
            words.append(value)
        else:
            raise CheckError(f"unknown instance key: {key}")
    require(height is not None and colors == COLORS and empty == EMPTY,
            "checker requires colors=4 and empty=2")
    require(len(words) == COLORS and all(len(word) == height for word in words),
            "instance dimensions disagree")
    return words


def validate_layout(words: Sequence[str]) -> int:
    require(len(words) == COLORS, "layout must have four original columns")
    height = len(words[0])
    require(height >= 1 and all(len(word) == height for word in words),
            "columns must have one common positive height")
    require(all(character in "0123" for word in words for character in word),
            "layout uses a colour outside 0..3")
    counts = [sum(word.count(str(color)) for word in words)
              for color in range(COLORS)]
    require(counts == [height] * COLORS,
            f"layout is not balanced: counts={counts}, height={height}")
    return height


def top_runs(word_bottom_to_top: str) -> list[Run]:
    top = list(reversed([int(character) for character in word_bottom_to_top]))
    result: list[Run] = []
    start = 0
    while start < len(top):
        end = start + 1
        while end < len(top) and top[end] == top[start]:
            end += 1
        result.append(Run(top[start], end - start, start))
        start = end
    return result


def run_index_at_bottom_position(word: str, bottom_position: int) -> tuple[int, int]:
    top_position = len(word) - 1 - bottom_position
    for index, run in enumerate(top_runs(word)):
        if run.top_start <= top_position < run.top_start + run.length:
            return index, run.length
    raise CheckError("cell did not belong to a run")


def occurrence_factorization(words: Sequence[str]) -> list[tuple[Token, ...]]:
    """Repeatedly extract a perfect matching from the regular multigraph."""

    height = validate_layout(words)
    remaining: dict[tuple[int, int], list[int]] = {
        (column, color): [position for position, character in enumerate(word)
                          if int(character) == color]
        for column, word in enumerate(words)
        for color in range(COLORS)
    }
    factors: list[tuple[Token, ...]] = []
    for _round in range(height):
        permutation = next(
            (candidate for candidate in itertools.permutations(range(COLORS))
             if all(remaining[column, candidate[column]]
                    for column in range(COLORS))),
            None,
        )
        require(permutation is not None,
                "regular remainder unexpectedly has no perfect matching")
        factor: list[Token] = []
        for column, color in enumerate(permutation):
            bottom_position = remaining[column, color].pop(0)
            run_index, run_length = run_index_at_bottom_position(
                words[column], bottom_position)
            factor.append(Token(column, color, bottom_position,
                                run_index, run_length))
        factors.append(tuple(factor))

    require(all(not positions for positions in remaining.values()),
            "factorization did not consume every cell")
    covered = {(token.column, token.bottom_position)
               for factor in factors for token in factor}
    require(len(covered) == COLORS * height,
            "factorization reused a physical cell")
    return factors


def delete_tokens(words: Sequence[str], tokens: Sequence[Token]) -> list[str]:
    require({token.column for token in tokens} == set(range(COLORS)),
            "transversal does not select every column once")
    require({token.color for token in tokens} == set(range(COLORS)),
            "transversal does not select every colour once")
    child: list[str] = []
    by_column = {token.column: token for token in tokens}
    for column, word in enumerate(words):
        token = by_column[column]
        require(int(word[token.bottom_position]) == token.color,
                "token colour does not match its physical cell")
        child.append(word[:token.bottom_position] + word[token.bottom_position + 1:])
    child_height = validate_layout(child)
    require(child_height + 1 == len(words[0]),
            "rainbow deletion did not lower height by exactly one")
    return child


def skeleton(words: Sequence[str]) -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(run.color for run in top_runs(word)) for word in words)


def singleton_extra_borders(word: str, bottom_position: int) -> int:
    run_index, run_length = run_index_at_bottom_position(word, bottom_position)
    if run_length >= 2:
        return 0
    before = len(top_runs(word)) - 1
    child = word[:bottom_position] + word[bottom_position + 1:]
    after = len(top_runs(child)) - 1 if child else 0
    require(before >= after, "deleting a singleton unexpectedly added a border")
    return before - after


def thick_run_options(words: Sequence[str], column: int, color: int) -> list[Token]:
    result: list[Token] = []
    word = words[column]
    height = len(word)
    for run_index, run in enumerate(top_runs(word)):
        if run.color != color or run.length < 2:
            continue
        # Any unit in the same run gives the same child run-length vector.
        top_position = run.top_start
        bottom_position = height - 1 - top_position
        result.append(Token(column, color, bottom_position,
                            run_index, run.length))
    return result


def thick_hall_witness(words: Sequence[str]) -> dict[str, object] | None:
    for size in range(1, COLORS + 1):
        for subset in itertools.combinations(range(COLORS), size):
            neighbors = sorted(
                column for column in range(COLORS)
                if any(thick_run_options(words, column, color)
                       for color in subset)
            )
            if len(neighbors) < len(subset):
                return {
                    "colors": list(subset),
                    "neighbor_columns": neighbors,
                    "color_count": len(subset),
                    "neighbor_count": len(neighbors),
                }
    return None


def enumerate_thick_transversals(words: Sequence[str]) -> Iterable[tuple[Token, ...]]:
    for permutation in itertools.permutations(range(COLORS)):
        options = [thick_run_options(words, column, permutation[column])
                   for column in range(COLORS)]
        if all(options):
            yield from (tuple(choice) for choice in itertools.product(*options))


def initial_levels(runs: Sequence[Sequence[Run]]) -> tuple[int, ...]:
    # A one-run original column already has no border and is a monochrome bin.
    return tuple(1 for _ in runs)


def exhausted_count(runs: Sequence[Sequence[Run]], levels: Sequence[int]) -> int:
    return sum(level == len(column_runs)
               for level, column_runs in zip(levels, runs))


def source_test(
    runs: Sequence[Sequence[Run]], levels: Sequence[int], source: int
) -> tuple[tuple[int, ...], bool]:
    require(levels[source] < len(runs[source]), "exhausted column used as source")
    exposed = [0] * COLORS
    hosted = [0] * COLORS
    capacities = [sum(run.length for run in column_runs[:level])
                  for column_runs, level in zip(runs, levels)]
    for column_runs, level in zip(runs, levels):
        for run in column_runs[:level]:
            exposed[run.color] += run.length
    for column, (column_runs, level) in enumerate(zip(runs, levels)):
        if level < len(column_runs):
            hosted[column_runs[level - 1].color] += capacities[column]
    debts = [exposed[color] - hosted[color] for color in range(COLORS)]
    color = runs[source][levels[source] - 1].color
    debts[color] += capacities[source]
    test = tuple(debts)
    legal = sum(value > 0 for value in test) <= EMPTY + exhausted_count(runs, levels)
    return test, legal


def exact_winning(words: Sequence[str]) -> tuple[bool, int]:
    runs = [top_runs(word) for word in words]

    @lru_cache(maxsize=None)
    def win(levels: tuple[int, ...]) -> bool:
        if exhausted_count(runs, levels) >= COLORS - EMPTY:
            return True
        for source, level in enumerate(levels):
            if level == len(runs[source]):
                continue
            _test, legal = source_test(runs, levels, source)
            if not legal:
                continue
            successor = list(levels)
            successor[source] += 1
            if win(tuple(successor)):
                return True
        return False

    answer = win(initial_levels(runs))
    return answer, win.cache_info().currsize


def epsilon_for(
    parent_runs: Sequence[Sequence[Run]],
    levels: Sequence[int],
    source: int,
    tokens: Sequence[Token],
) -> tuple[int, ...]:
    epsilon = [0] * COLORS
    by_column = {token.column: token for token in tokens}
    for column, (column_runs, level) in enumerate(zip(parent_runs, levels)):
        token = by_column[column]
        token_exposed = token.run_index < level
        if not token_exposed:
            continue
        epsilon[token.color] += 1
        active = level < len(column_runs)
        if active and column != source:
            epsilon[column_runs[level - 1].color] -= 1
    return tuple(epsilon)


def compatible_lift(words: Sequence[str], tokens: Sequence[Token]) -> dict[str, object]:
    child = delete_tokens(words, tokens)
    require(skeleton(words) == skeleton(child),
            "compatible_lift requires a run-preserving transversal")
    parent_runs = [top_runs(word) for word in words]
    child_runs = [top_runs(word) for word in child]
    require([len(runs) for runs in parent_runs] ==
            [len(runs) for runs in child_runs], "run counts drifted")
    stats = LiftStats()
    chosen: dict[tuple[int, ...], int] = {}

    @lru_cache(maxsize=None)
    def lift(levels: tuple[int, ...]) -> bool:
        stats.states += 1
        if exhausted_count(parent_runs, levels) >= COLORS - EMPTY:
            return True
        for source, level in enumerate(levels):
            if level == len(parent_runs[source]):
                continue
            child_test, child_legal = source_test(child_runs, levels, source)
            if not child_legal:
                continue
            stats.child_legal_edges += 1
            parent_test, parent_legal = source_test(parent_runs, levels, source)
            epsilon = epsilon_for(parent_runs, levels, source, tokens)
            actual = tuple(parent_test[color] - child_test[color]
                           for color in range(COLORS))
            require(actual == epsilon,
                    f"token error formula failed at {levels}, source {source}: "
                    f"actual={actual}, formula={epsilon}")
            if not parent_legal:
                stats.parent_blocked_edges += 1
                if stats.first_block is None:
                    stats.first_block = {
                        "levels": list(levels),
                        "source": source,
                        "child_test": list(child_test),
                        "parent_test": list(parent_test),
                        "epsilon": list(epsilon),
                        "child_positive": sum(value > 0 for value in child_test),
                        "parent_positive": sum(value > 0 for value in parent_test),
                        "available_bins": EMPTY + exhausted_count(parent_runs, levels),
                    }
                continue
            stats.jointly_legal_edges += 1
            successor = list(levels)
            successor[source] += 1
            successor_tuple = tuple(successor)
            if lift(successor_tuple):
                chosen[levels] = source
                return True
        return False

    start = initial_levels(parent_runs)
    winning = lift(start)
    path: list[int] = []
    trace: list[dict[str, object]] = []
    if winning:
        levels = start
        while exhausted_count(parent_runs, levels) < COLORS - EMPTY:
            source = chosen[levels]
            child_test, _ = source_test(child_runs, levels, source)
            parent_test, _ = source_test(parent_runs, levels, source)
            epsilon = epsilon_for(parent_runs, levels, source, tokens)
            trace.append({
                "levels": list(levels),
                "source": source,
                "child_test": list(child_test),
                "parent_test": list(parent_test),
                "epsilon": list(epsilon),
            })
            path.append(source)
            successor = list(levels)
            successor[source] += 1
            levels = tuple(successor)
    return {
        "winning": winning,
        "path": path,
        "trace": trace,
        "states": stats.states,
        "child_legal_edges": stats.child_legal_edges,
        "jointly_legal_edges": stats.jointly_legal_edges,
        "parent_blocked_child_edges": stats.parent_blocked_edges,
        "first_block": stats.first_block,
        "child_bottom_to_top": child,
    }


def upper_support_without_bottom_run(word: str) -> set[int]:
    bottom_color = word[0]
    boundary = 0
    while boundary < len(word) and int(word[boundary]) == int(bottom_color):
        boundary += 1
    return {int(character) for character in word[boundary:]}


def sequential_bypass_pairs(words: Sequence[str]) -> list[list[int]]:
    supports = [{int(character) for character in word} for word in words]
    upper = [upper_support_without_bottom_run(word) for word in words]
    return [
        [first, second]
        for first in range(COLORS)
        for second in range(COLORS)
        if first != second
        and len(upper[first]) <= 2
        and len(supports[first] | upper[second]) <= 3
    ]


def bottom_extensions(words: Sequence[str]) -> dict[str, object] | None:
    if len(words[0]) != 7:
        return None
    yes = no = 0
    first_no: list[str] | None = None
    for permutation in itertools.permutations(range(COLORS)):
        extension = [str(permutation[column]) + words[column]
                     for column in range(COLORS)]
        validate_layout(extension)
        winning, _states = exact_winning(extension)
        yes += int(winning)
        no += int(not winning)
        if not winning and first_no is None:
            first_no = extension
    return {
        "labeled_rainbow_bottom_extensions": 24,
        "yes": yes,
        "no": no,
        "first_no_bottom_to_top": first_no,
    }


def analyze_case(name: str, words: Sequence[str], expected: bool | None) -> dict[str, object]:
    height = validate_layout(words)
    winning, state_count = exact_winning(words)
    if expected is not None:
        require(winning == expected,
                f"{name}: exact outcome drifted, got {winning}, expected {expected}")

    factors = occurrence_factorization(words)
    require(len(factors) == height, f"{name}: wrong factor count")
    factor_rows: list[dict[str, object]] = []
    for index, factor in enumerate(factors):
        child = delete_tokens(words, factor)
        child_winning, child_states = exact_winning(child)
        thick = all(token.run_length >= 2 for token in factor)
        factor_rows.append({
            "index": index,
            "tokens": [token.__dict__ for token in factor],
            "thick": thick,
            "singleton_extra_borders": [
                singleton_extra_borders(words[token.column], token.bottom_position)
                for token in factor
            ],
            "child_balanced_height": len(child[0]),
            "child_winning": child_winning,
            "child_states": child_states,
        })
    child_yes = sum(bool(row["child_winning"]) for row in factor_rows)
    if height == 7:
        require(child_yes == 7,
                f"{name}: a rainbow deletion contradicted the h=6 YES theorem")

    hall = thick_hall_witness(words)
    thick_candidates = list(enumerate_thick_transversals(words))
    require((hall is None) == bool(thick_candidates),
            f"{name}: thick Hall dichotomy disagrees with enumeration")
    lift_found: dict[str, object] | None = None
    representative_failure: dict[str, object] | None = None
    checked = 0
    for tokens in thick_candidates:
        checked += 1
        result = compatible_lift(words, tokens)
        if result["winning"]:
            lift_found = {
                "tokens": [token.__dict__ for token in tokens],
                **result,
            }
            break
        if representative_failure is None or (
            int(result["parent_blocked_child_edges"])
            < int(representative_failure["parent_blocked_child_edges"])
        ):
            representative_failure = {
                "tokens": [token.__dict__ for token in tokens],
                **result,
            }

    if lift_found is not None:
        require(winning, f"{name}: a compatible lift cannot exist for a NO layout")
    if not winning:
        require(lift_found is None,
                f"{name}: certified NO unexpectedly had a compatible lift")

    return {
        "name": name,
        "height": height,
        "columns_bottom_to_top": list(words),
        "exact_winning": winning,
        "exact_states": state_count,
        "rainbow_factorization_count": len(factors),
        "rainbow_children_winning": child_yes,
        "rainbow_children_losing": len(factors) - child_yes,
        "thick_factors_in_one_greedy_factorization": sum(
            bool(row["thick"]) for row in factor_rows
        ),
        "factorization": factor_rows,
        "thick_transversal": {
            "exists": hall is None,
            "hall_witness": hall,
            "candidates_enumerated": len(thick_candidates),
        },
        "token_compatible_lift": {
            "found": lift_found is not None,
            "candidates_checked": checked,
            "witness": lift_found,
            "representative_failure": representative_failure,
            "scope": "thick/run-skeleton-preserving transversals only",
        },
        "sequential_bypass_pairs": sequential_bypass_pairs(words),
        "height8_rainbow_bottom_extension_profile": bottom_extensions(words),
    }


def assert_builtin_regressions(cases: Sequence[dict[str, object]]) -> None:
    by_name = {str(case["name"]): case for case in cases}
    if "four_lock_h8" in by_name:
        case = by_name["four_lock_h8"]
        thick = case["thick_transversal"]
        lift = case["token_compatible_lift"]
        require(case["rainbow_factorization_count"] == 8,
                "four-lock occurrence factorization drifted")
        require(thick["exists"] and thick["candidates_enumerated"] == 8,
                "four-lock thick-transversal catalog drifted")
        require(not lift["found"] and lift["candidates_checked"] == 8,
                "four-lock unexpectedly acquired a compatible lift")
        failure = lift["representative_failure"]
        require(failure is not None and failure["first_block"] is not None,
                "four-lock lost its token-block diagnostic")
        block = failure["first_block"]
        require(block["child_positive"] == 3 and block["parent_positive"] == 4,
                "four-lock diagnostic is no longer the saturated 3-to-4 flip")

    if "two_source_near_kernel_h7" in by_name:
        case = by_name["two_source_near_kernel_h7"]
        thick = case["thick_transversal"]
        lift = case["token_compatible_lift"]
        require(case["rainbow_factorization_count"] == 7,
                "near-kernel occurrence factorization drifted")
        require(all(row["child_winning"] for row in case["factorization"]),
                "a balanced h=6 near-kernel child unexpectedly became NO")
        require(thick["exists"] and thick["candidates_enumerated"] == 1,
                "near-kernel thick-transversal catalog drifted")
        require(lift["found"] and lift["witness"]["path"] == [0, 1, 1],
                "near-kernel compatible lift witness drifted")
        extensions = case["height8_rainbow_bottom_extension_profile"]
        require(extensions is not None and extensions["yes"] == 24
                and extensions["no"] == 0,
                "near-kernel rainbow-bottom extension profile drifted")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instance", type=Path,
                        help="an additional balanced colors=4,empty=2 instance")
    parser.add_argument("--json", type=Path, help="write the audit report")
    parser.add_argument("--no-builtins", action="store_true",
                        help="skip the committed four-lock and near-kernel fixtures")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cases: list[tuple[str, list[str], bool | None]] = []
    if not args.no_builtins:
        cases.extend((name, words, expected)
                     for name, (words, expected) in BUILTINS.items())
    if args.instance is not None:
        cases.append((args.instance.stem, parse_instance(args.instance), None))
    require(cases, "no layouts were selected")
    analyzed = [analyze_case(name, words, expected)
                for name, words, expected in cases]
    assert_builtin_regressions(analyzed)
    report = {
        "scope": "rainbow transversal factorization and thick-token lift audit",
        "claims_global_c4_h7_theorem": False,
        "cases": analyzed,
    }
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    for case in report["cases"]:
        lift = case["token_compatible_lift"]
        print(
            f"rainbow-lift {case['name']}: exact={'YES' if case['exact_winning'] else 'NO'}, "
            f"factors={case['rainbow_factorization_count']}, "
            f"thick={case['thick_transversal']['exists']}, "
            f"compatible={lift['found']}, checked={lift['candidates_checked']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
