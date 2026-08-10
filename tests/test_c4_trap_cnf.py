#!/usr/bin/env python3
"""Tiny pure tests for the exact c4 trap-CNF generator."""

from __future__ import annotations

import itertools
from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from c4_trap_cnf import (  # noqa: E402
    COLOR_COUNT,
    VariablePool,
    encode_adjacent_column_lex,
)


class ClauseCollector:
    def __init__(self) -> None:
        self.clauses: list[list[int]] = []

    def add(self, literals: list[int]) -> None:
        self.clauses.append(list(literals))


def clauses_hold(clauses: list[list[int]], true_variables: set[int]) -> bool:
    return all(
        any((literal > 0) == (abs(literal) in true_variables) for literal in clause)
        for clause in clauses
    )


class AdjacentColumnLexTest(unittest.TestCase):
    def assert_gadget_is_exact(self, height: int, expected_clauses: int) -> None:
        pool = VariablePool()
        left = [
            [pool.new() for _color in range(COLOR_COUNT)]
            for _position in range(height)
        ]
        right = [
            [pool.new() for _color in range(COLOR_COUNT)]
            for _position in range(height)
        ]
        first_auxiliary = pool.top + 1
        writer = ClauseCollector()

        auxiliary_count = encode_adjacent_column_lex(writer, pool, left, right)

        self.assertEqual(auxiliary_count, height - 1)
        self.assertEqual(pool.top - first_auxiliary + 1, height - 1)
        self.assertEqual(len(writer.clauses), expected_clauses)

        auxiliary_variables = range(first_auxiliary, pool.top + 1)
        words = itertools.product(range(COLOR_COUNT), repeat=height)
        for left_word in words:
            for right_word in itertools.product(range(COLOR_COUNT), repeat=height):
                item_assignment = {
                    left[position][color]
                    for position, color in enumerate(left_word)
                } | {
                    right[position][color]
                    for position, color in enumerate(right_word)
                }
                gadget_is_sat = any(
                    clauses_hold(
                        writer.clauses,
                        item_assignment
                        | {
                            variable
                            for variable, value in zip(auxiliary_variables, values)
                            if value
                        },
                    )
                    for values in itertools.product(
                        (False, True), repeat=auxiliary_count
                    )
                )
                self.assertEqual(
                    gadget_is_sat,
                    left_word <= right_word,
                    (left_word, right_word),
                )

    def test_height_two_is_sat_exactly_for_nondecreasing_words(self) -> None:
        self.assert_gadget_is_exact(height=2, expected_clauses=20)

    def test_height_three_prefix_recurrence_is_exact(self) -> None:
        # Height three introduces e_2 <=> e_1 and (left[1] == right[1]).
        self.assert_gadget_is_exact(height=3, expected_clauses=35)


if __name__ == "__main__":
    unittest.main()
