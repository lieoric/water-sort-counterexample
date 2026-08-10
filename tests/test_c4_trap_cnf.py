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
    RGS_LENGTH_THREE_PREFIXES,
    VariablePool,
    encode_adjacent_column_lex,
    encode_binary_at_least,
    encode_binary_sum,
    encode_color_first_occurrence,
    encode_guarded_selected_equivalence,
    encode_rgs_prefix_units,
    is_restricted_growth_word,
)
from aggregate_c4_trap_shards import (  # noqa: E402
    AggregationError,
    SAT_STATUS,
    UNSAT_STATUS,
    aggregate_results,
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


def reference_value(reference: bool | int | None, true_variables: set[int]) -> bool:
    if reference is None or reference is False:
        return False
    if reference is True:
        return True
    return (reference > 0) == (abs(reference) in true_variables)


class RestrictedGrowthShardCoverageTest(unittest.TestCase):
    def test_five_shards_are_exactly_all_length_three_rgs_words(self) -> None:
        # Exhaust all 4^3 colour prefixes.  This is the finite coverage lemma
        # used to combine the five independently checked h=7 shard results.
        mathematical_words = {
            "".join(map(str, word))
            for word in itertools.product(range(COLOR_COUNT), repeat=3)
            if is_restricted_growth_word(word)
        }
        pool = VariablePool()
        flattened = [
            [pool.new() for _color in range(COLOR_COUNT)]
            for _position in range(3)
        ]
        writer = ClauseCollector()
        encode_color_first_occurrence(writer, flattened)
        encoded_words = {
            "".join(map(str, word))
            for word in itertools.product(range(COLOR_COUNT), repeat=3)
            if clauses_hold(
                writer.clauses,
                {
                    flattened[position][color]
                    for position, color in enumerate(word)
                },
            )
        }
        expected = set(RGS_LENGTH_THREE_PREFIXES)
        self.assertEqual(mathematical_words, expected)
        self.assertEqual(encoded_words, expected)
        self.assertEqual(len(encoded_words), 5)

    def test_one_shard_adds_exactly_three_requested_unit_clauses(self) -> None:
        pool = VariablePool()
        flattened = [
            [pool.new() for _color in range(COLOR_COUNT)]
            for _position in range(3)
        ]
        writer = ClauseCollector()
        count = encode_rgs_prefix_units(writer, flattened, "012")
        self.assertEqual(count, 3)
        self.assertEqual(
            writer.clauses,
            [[flattened[0][0]], [flattened[1][1]], [flattened[2][2]]],
        )

    @staticmethod
    def shard_result(prefix: str, status: str) -> dict[str, object]:
        stages: dict[str, object] = {
            "cadical": {
                "exit_code": 10 if status == SAT_STATUS else 20,
                "timed_out": False,
            }
        }
        if status == SAT_STATUS:
            for stage_name in (
                "dimacs_model_check",
                "decode",
                "water_oracle",
                "water_verify",
            ):
                stages[stage_name] = {"exit_code": 0, "timed_out": False}
        else:
            stages["drat_trim"] = {"exit_code": 0, "timed_out": False}
        return {
            "schema": 1,
            "problem": {
                "colors": 4,
                "empty_columns": 2,
                "height": 7,
                "rgs_prefix": prefix,
            },
            "proof_mode": "checked-drat",
            "status": status,
            "verified": True,
            "stages": stages,
        }

    def all_results(self, status: str) -> list[tuple[str, dict[str, object]]]:
        return [
            (prefix, self.shard_result(prefix, status))
            for prefix in RGS_LENGTH_THREE_PREFIXES
        ]

    def test_all_five_verified_unsat_shards_imply_global_unsat(self) -> None:
        aggregate = aggregate_results(self.all_results(UNSAT_STATUS))
        self.assertTrue(aggregate["verified"])
        self.assertEqual(aggregate["status"], UNSAT_STATUS)

    def test_one_verified_sat_shard_implies_global_sat(self) -> None:
        results = self.all_results(UNSAT_STATUS)
        results[2] = ("010", self.shard_result("010", SAT_STATUS))
        aggregate = aggregate_results(results)
        self.assertEqual(aggregate["status"], SAT_STATUS)
        self.assertEqual(aggregate["sat_shards"], ["010"])

    def test_missing_or_unverified_shard_is_never_accepted(self) -> None:
        with self.assertRaises(AggregationError):
            aggregate_results(self.all_results(UNSAT_STATUS)[:-1])

        results = self.all_results(UNSAT_STATUS)
        results[0][1]["verified"] = False
        with self.assertRaises(AggregationError):
            aggregate_results(results)

    def test_search_only_or_duplicate_shard_is_never_accepted(self) -> None:
        results = self.all_results(UNSAT_STATUS)
        results[0][1]["proof_mode"] = "search-only"
        with self.assertRaises(AggregationError):
            aggregate_results(results)

        results = self.all_results(UNSAT_STATUS)
        results[-1] = ("duplicate", self.shard_result("011", UNSAT_STATUS))
        with self.assertRaises(AggregationError):
            aggregate_results(results)


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


class SharedArithmeticCircuitTest(unittest.TestCase):
    def test_signed_complement_bits_sum_to_one(self) -> None:
        pool = VariablePool()
        input_variable = pool.new()
        first_auxiliary = pool.top + 1
        writer = ClauseCollector()
        result = encode_binary_sum(
            writer, pool, [[input_variable], [-input_variable]]
        )
        auxiliary_variables = list(range(first_auxiliary, pool.top + 1))

        for input_value in (False, True):
            item_assignment = {input_variable} if input_value else set()
            observed: set[int] = set()
            for values in itertools.product(
                (False, True), repeat=len(auxiliary_variables)
            ):
                assignment = item_assignment | {
                    variable
                    for variable, value in zip(auxiliary_variables, values)
                    if value
                }
                if clauses_hold(writer.clauses, assignment):
                    observed.add(
                        sum(
                            1 << bit
                            for bit, reference in enumerate(result)
                            if reference_value(reference, assignment)
                        )
                    )
            self.assertEqual(observed, {1})

    def test_binary_sum_is_exact_for_two_two_bit_operands(self) -> None:
        pool = VariablePool()
        left = [pool.new(), pool.new()]
        right = [pool.new(), pool.new()]
        first_auxiliary = pool.top + 1
        writer = ClauseCollector()

        result = encode_binary_sum(writer, pool, [left, right])
        auxiliary_variables = list(range(first_auxiliary, pool.top + 1))

        for left_value in range(4):
            for right_value in range(4):
                item_assignment = {
                    variable
                    for bit, variable in enumerate(left)
                    if left_value & (1 << bit)
                } | {
                    variable
                    for bit, variable in enumerate(right)
                    if right_value & (1 << bit)
                }
                observed: set[int] = set()
                satisfying_assignments = 0
                for values in itertools.product(
                    (False, True), repeat=len(auxiliary_variables)
                ):
                    assignment = item_assignment | {
                        variable
                        for variable, value in zip(auxiliary_variables, values)
                        if value
                    }
                    if not clauses_hold(writer.clauses, assignment):
                        continue
                    satisfying_assignments += 1
                    observed.add(
                        sum(
                            1 << bit
                            for bit, reference in enumerate(result)
                            if reference_value(reference, assignment)
                        )
                    )
                self.assertEqual(satisfying_assignments, 1)
                self.assertEqual(observed, {left_value + right_value})

    def test_binary_comparator_is_exact_for_every_three_bit_threshold(self) -> None:
        for threshold in range(9):
            pool = VariablePool()
            bits = [pool.new() for _bit in range(3)]
            first_auxiliary = pool.top + 1
            writer = ClauseCollector()
            result = encode_binary_at_least(
                writer, pool, bits, threshold, maximum=7
            )
            auxiliary_variables = list(range(first_auxiliary, pool.top + 1))

            for value in range(8):
                item_assignment = {
                    variable
                    for bit, variable in enumerate(bits)
                    if value & (1 << bit)
                }
                observed: set[bool] = set()
                for values in itertools.product(
                    (False, True), repeat=len(auxiliary_variables)
                ):
                    assignment = item_assignment | {
                        variable
                        for variable, auxiliary_value in zip(
                            auxiliary_variables, values
                        )
                        if auxiliary_value
                    }
                    if clauses_hold(writer.clauses, assignment):
                        observed.add(reference_value(result, assignment))
                self.assertEqual(observed, {value >= threshold})

    def test_positive_threshold_mux_is_exact_when_state_is_marked(self) -> None:
        pool = VariablePool()
        marked = pool.new()
        selector = pool.new()
        output = pool.new()
        when_false = pool.new()
        when_true = pool.new()
        writer = ClauseCollector()
        encode_guarded_selected_equivalence(
            writer,
            enable=marked,
            selector=selector,
            selector_value=False,
            output=output,
            reference=when_false,
        )
        encode_guarded_selected_equivalence(
            writer,
            enable=marked,
            selector=selector,
            selector_value=True,
            output=output,
            reference=when_true,
        )

        variables = (marked, selector, output, when_false, when_true)
        for values in itertools.product((False, True), repeat=len(variables)):
            assignment = {
                variable
                for variable, value in zip(variables, values)
                if value
            }
            marked_value, selector_value, output_value, false_value, true_value = (
                values
            )
            expected = (
                not marked_value
                or output_value == (true_value if selector_value else false_value)
            )
            self.assertEqual(
                clauses_hold(writer.clauses, assignment), expected, values
            )


class SharedDeficitIdentityTest(unittest.TestCase):
    def test_shared_sum_matches_direct_source_predicate_through_height_three(
        self,
    ) -> None:
        # One Boolean word per column is the indicator for an arbitrary fixed
        # colour.  Exhausting all such words proves the identity independently
        # of one-hot or balance assumptions.
        for height in (2, 3):
            states = [
                state
                for state in itertools.product(
                    range(1, height + 1), repeat=COLOR_COUNT
                )
                if sum(endpoint == height for endpoint in state) <= 1
            ]
            for flattened in itertools.product(
                (False, True), repeat=COLOR_COUNT * height
            ):
                columns = [
                    flattened[column * height : (column + 1) * height]
                    for column in range(COLOR_COUNT)
                ]
                for state in states:
                    live_sources = [
                        source
                        for source, endpoint in enumerate(state)
                        if endpoint < height
                    ]
                    active_capacity = sum(state[source] for source in live_sources)
                    prefix_counts = [
                        sum(columns[column][:endpoint])
                        for column, endpoint in enumerate(state)
                    ]
                    shared_sum = sum(
                        prefix_counts[column]
                        + (
                            endpoint
                            * (1 - columns[column][endpoint - 1])
                            if endpoint < height
                            else 0
                        )
                        for column, endpoint in enumerate(state)
                    )
                    total_prefix = sum(prefix_counts)
                    for source in live_sources:
                        direct = total_prefix - sum(
                            state[column] * columns[column][state[column] - 1]
                            for column in live_sources
                            if column != source
                        )
                        source_top = columns[source][state[source] - 1]
                        threshold = (
                            active_capacity - state[source] + 1
                            if source_top
                            else active_capacity + 1
                        )
                        if (direct > 0) != (shared_sum >= threshold):
                            self.fail(
                                "shared deficit identity mismatch: "
                                f"h={height}, columns={columns}, state={state}, "
                                f"source={source}"
                            )


if __name__ == "__main__":
    unittest.main()
