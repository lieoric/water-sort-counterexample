#!/usr/bin/env python3
"""Independent audit for the c=4, k=2, h=7 terminal macro layer.

This file deliberately does not import the recon implementation for its
combinatorics.  The 997 terminal types are counted from integer partitions of
the two positive debts and of the endpoint capacities.  That gives a small,
independent check against an implementation that enumerates/canonicalizes
full macro states.
"""

from __future__ import annotations

import itertools
import json
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


HEIGHT = 7
COLORS = 4
INITIAL_EMPTY = 2
ENDPOINT_CAPS = range(1, HEIGHT)  # Active endpoints are exactly 1,...,6.
ROOT = Path(__file__).resolve().parents[1]
MAIN_SCRIPT = ROOT / "scripts" / "c4_h7_macro_recon.py"


@dataclass(frozen=True)
class MacroState:
    z: int
    d: tuple[int, int, int, int]
    active: tuple[tuple[int, int], ...]  # (top color, endpoint capacity)


def fixed_partitions(
    total: int, parts: int, minimum: int, maximum: int
) -> tuple[tuple[int, ...], ...]:
    """Unordered fixed-length integer partitions in a tiny bounded box."""

    return tuple(
        values
        for values in itertools.combinations_with_replacement(
            range(minimum, maximum + 1), parts
        )
        if sum(values) == total
    )


def endpoint_types(multiplicity: int, debt: int) -> tuple[tuple[int, ...], ...]:
    """Capacity partitions for one nonpositive top-color bucket.

    If d=-debt and the bucket owns ``multiplicity`` active endpoints, then
    F=sum(caps)-debt.  Physicality requires multiplicity <= F <= h, while a
    terminal endpoint requires cap > debt.
    """

    result = []
    for caps in itertools.combinations_with_replacement(
        ENDPOINT_CAPS, multiplicity
    ):
        exposed = sum(caps) - debt
        if all(cap > debt for cap in caps) and multiplicity <= exposed <= HEIGHT:
            result.append(caps)
    return tuple(result)


def positive_pair_partitions(total_debt: int) -> tuple[tuple[int, int], ...]:
    return tuple(
        parts
        for parts in fixed_partitions(total_debt, 2, 1, HEIGHT)
    )


def color_bucket_key(state: MacroState) -> tuple[int, tuple[tuple[int, tuple[int, ...]], ...]]:
    """Quotient color names and column labels while retaining their incidence."""

    caps_by_color: list[list[int]] = [[] for _ in range(COLORS)]
    for top, cap in state.active:
        caps_by_color[top].append(cap)
    buckets = tuple(
        sorted(
            (state.d[color], tuple(sorted(caps_by_color[color])))
            for color in range(COLORS)
        )
    )
    return state.z, buckets


def exposed_counts(state: MacroState) -> tuple[int, int, int, int]:
    hosted = [0] * COLORS
    for top, cap in state.active:
        hosted[top] += cap
    return tuple(state.d[color] + hosted[color] for color in range(COLORS))


def state_from_report(z: int, buckets: list[dict[str, object]]) -> MacroState:
    """Decode the public JSON shape without importing the implementation."""

    debts = tuple(int(bucket["debt"]) for bucket in buckets)
    active = tuple(
        (color, int(cap))
        for color, bucket in enumerate(buckets)
        for cap in bucket["caps"]
    )
    return MacroState(z=z, d=debts, active=active)  # type: ignore[arg-type]


def physical_consistency_errors(state: MacroState) -> tuple[str, ...]:
    errors: list[str] = []
    if len(state.active) + state.z != COLORS:
        errors.append("active+z")
    if any(cap not in ENDPOINT_CAPS for _, cap in state.active):
        errors.append("endpoint-cap")
    if any(not 0 <= top < COLORS for top, _ in state.active):
        errors.append("top-color")
    if sum(state.d) != state.z * HEIGHT:
        errors.append("sum-d")

    exposed = exposed_counts(state)
    multiplicities = tuple(
        sum(top == color for top, _ in state.active) for color in range(COLORS)
    )
    if any(
        not multiplicities[color] <= exposed[color] <= HEIGHT
        for color in range(COLORS)
    ):
        errors.append("F-bounds")

    # Every active hidden suffix needs a first item different from its top.
    remaining = tuple(HEIGHT - count for count in exposed)
    if any(
        multiplicities[color]
        > sum(remaining[other] for other in range(COLORS) if other != color)
        for color in range(COLORS)
    ):
        errors.append("hidden-Hall")
    return tuple(errors)


def legal_source(state: MacroState, source: int) -> bool:
    top, cap = state.active[source]
    adjusted = list(state.d)
    adjusted[top] += cap
    return sum(value > 0 for value in adjusted) <= INITIAL_EMPTY + state.z


def tq_types() -> tuple[tuple[int, MacroState], ...]:
    """Closed Tq product: positive-debt partitions x q-cap partitions."""

    result = []
    for debt in range(0, 3):
        positives = fixed_partitions(HEIGHT + debt, 3, 1, HEIGHT)
        caps = tuple(
            values
            for subtotal in range(3 * (debt + 1), HEIGHT + debt + 1)
            for values in fixed_partitions(subtotal, 3, debt + 1, HEIGHT - 1)
        )
        for positive_parts in positives:
            for q_caps in caps:
                result.append(
                    (
                        debt,
                        MacroState(
                            z=1,
                            d=(-debt, *positive_parts),
                            active=tuple((0, cap) for cap in q_caps),
                        ),
                    )
                )
    return tuple(result)


def d2_3plus1_types() -> tuple[tuple[int, MacroState], ...]:
    """D2 types with host-top multiplicities 3+1.

    The two host colors are distinguished by their multiplicities, so there is
    no extra division by two after the positive debts have been partitioned.
    """

    result = []
    for total_debt in range(2, 2 * HEIGHT + 1):
        for positive_parts in positive_pair_partitions(total_debt):
            for debt3 in range(total_debt + 1):
                debt1 = total_debt - debt3
                for caps3 in endpoint_types(3, debt3):
                    for caps1 in endpoint_types(1, debt1):
                        result.append(
                            (
                                total_debt,
                                MacroState(
                                    z=0,
                                    d=(*positive_parts, -debt3, -debt1),
                                    active=tuple((2, cap) for cap in caps3)
                                    + ((3, caps1[0]),),
                                ),
                            )
                        )
    return tuple(result)


def d2_2plus2_types() -> tuple[tuple[int, MacroState], ...]:
    """D2 types with host-top multiplicities 2+2.

    Each host signature is ``(debt, sorted endpoint pair)``.  Choosing two
    signatures with replacement is the color-swap quotient; importantly, the
    endpoint pair remains attached to its debt.
    """

    host_signatures = tuple(
        (debt, caps)
        for debt in range(0, HEIGHT)
        for caps in endpoint_types(2, debt)
    )
    result = []
    for total_debt in range(2, 2 * HEIGHT + 1):
        for positive_parts in positive_pair_partitions(total_debt):
            for left_index, left in enumerate(host_signatures):
                for right in host_signatures[left_index:]:
                    if left[0] + right[0] != total_debt:
                        continue
                    result.append(
                        (
                            total_debt,
                            MacroState(
                                z=0,
                                d=(*positive_parts, -left[0], -right[0]),
                                active=tuple((2, cap) for cap in left[1])
                                + tuple((3, cap) for cap in right[1]),
                            ),
                        )
                    )
    return tuple(result)


def forward_nonexhausting(
    parent: MacroState, source: int, next_color: int, next_cap: int
) -> MacroState:
    """Reference parent -> child equation for a non-exhausting event."""

    old_color, old_cap = parent.active[source]
    if not legal_source(parent, source):
        raise ValueError("illegal source")
    if next_color == old_color:
        raise ValueError("adjacent maximal runs must have different colors")
    if not old_cap < next_cap < HEIGHT:
        raise ValueError("non-exhausting endpoint must satisfy s<t<h")

    debt = list(parent.d)
    debt[old_color] += old_cap
    debt[next_color] -= old_cap
    active = list(parent.active)
    active[source] = (next_color, next_cap)
    return MacroState(parent.z, tuple(debt), tuple(active))


def forward_exhausting(
    parent: MacroState, source: int, final_color: int
) -> MacroState:
    """Reference parent -> child equation for the first exhausting event."""

    old_color, old_cap = parent.active[source]
    if not legal_source(parent, source):
        raise ValueError("illegal source")
    if final_color == old_color:
        raise ValueError("adjacent maximal runs must have different colors")

    debt = list(parent.d)
    debt[old_color] += old_cap
    debt[final_color] += HEIGHT - old_cap
    active = parent.active[:source] + parent.active[source + 1 :]
    return MacroState(parent.z + 1, tuple(debt), active)


def reverse_nonexhausting(child: MacroState):
    """Yield every algebraically consistent one-event parent, with its edge."""

    for source, (next_color, next_cap) in enumerate(child.active):
        for old_cap in range(1, next_cap):
            for old_color in range(COLORS):
                if old_color == next_color:
                    continue
                debt = list(child.d)
                debt[old_color] -= old_cap
                debt[next_color] += old_cap
                active = list(child.active)
                active[source] = (old_color, old_cap)
                parent = MacroState(child.z, tuple(debt), tuple(active))
                if physical_consistency_errors(parent) or not legal_source(parent, source):
                    continue
                yield parent, source, next_color, next_cap


def reverse_exhausting(child: MacroState):
    """Yield z=0 parents whose first exhaustion produces a z=1 child."""

    if child.z != 1:
        return
    for old_cap in ENDPOINT_CAPS:
        for old_color in range(COLORS):
            for final_color in range(COLORS):
                if final_color == old_color:
                    continue
                debt = list(child.d)
                debt[old_color] -= old_cap
                debt[final_color] -= HEIGHT - old_cap
                parent = MacroState(
                    z=0,
                    d=tuple(debt),
                    active=child.active + ((old_color, old_cap),),
                )
                source = len(parent.active) - 1
                if physical_consistency_errors(parent) or not legal_source(parent, source):
                    continue
                yield parent, source, final_color


class TerminalPartitionAudit(unittest.TestCase):
    def test_closed_partition_contributions(self) -> None:
        self.assertEqual(Counter(debt for debt, _ in tq_types()), {0: 44, 1: 20, 2: 7})
        self.assertEqual(
            Counter(total for total, _ in d2_3plus1_types()),
            {2: 70, 3: 54, 4: 76, 5: 44, 6: 18, 7: 3},
        )
        self.assertEqual(
            Counter(total for total, _ in d2_2plus2_types()),
            {2: 117, 3: 102, 4: 162, 5: 108, 6: 93, 7: 42, 8: 28, 9: 6, 10: 3},
        )

    def test_exact_terminal_totals_and_no_canonical_duplicates(self) -> None:
        families = {
            "tq": tuple(state for _, state in tq_types()),
            "d2_3plus1": tuple(state for _, state in d2_3plus1_types()),
            "d2_2plus2": tuple(state for _, state in d2_2plus2_types()),
        }
        expected = {"tq": 71, "d2_3plus1": 265, "d2_2plus2": 661}
        for name, states in families.items():
            self.assertEqual(len(states), expected[name])
            self.assertEqual(len({color_bucket_key(state) for state in states}), expected[name])
        self.assertEqual(sum(map(len, families.values())), 997)
        self.assertTrue(
            set(map(color_bucket_key, families["d2_3plus1"])).isdisjoint(
                map(color_bucket_key, families["d2_2plus2"])
            )
        )

    def test_every_partition_type_is_physical_and_terminal(self) -> None:
        for _, state in tq_types() + d2_3plus1_types() + d2_2plus2_types():
            self.assertEqual(physical_consistency_errors(state), (), state)
            self.assertEqual(sum(state.d), state.z * HEIGHT)
            self.assertTrue(all(cap in range(1, 7) for _, cap in state.active))
            self.assertFalse(any(legal_source(state, source) for source in range(len(state.active))), state)

            adjusted_positive_counts = []
            for source, (top, cap) in enumerate(state.active):
                adjusted = list(state.d)
                adjusted[top] += cap
                adjusted_positive_counts.append(sum(value > 0 for value in adjusted))
                self.assertGreater(adjusted_positive_counts[-1], INITIAL_EMPTY + state.z)

    def test_bucket_canonicalization_preserves_top_multiplicity(self) -> None:
        # A broken key that sorts debts and endpoints separately merges these.
        three_plus_one = MacroState(
            0,
            (1, 1, -1, -1),
            ((2, 2), (2, 2), (2, 2), (3, 2)),
        )
        two_plus_two = MacroState(
            0,
            (1, 1, -1, -1),
            ((2, 2), (2, 2), (3, 2), (3, 2)),
        )
        broken = lambda state: (
            tuple(sorted(state.d)),
            tuple(sorted(cap for _, cap in state.active)),
        )
        self.assertEqual(broken(three_plus_one), broken(two_plus_two))
        self.assertNotEqual(
            color_bucket_key(three_plus_one), color_bucket_key(two_plus_two)
        )


class OneStepEquationAudit(unittest.TestCase):
    def test_reverse_nonexhausting_edges_round_trip_and_obey_sandwich(self) -> None:
        children = tuple(state for _, state in d2_3plus1_types()) + tuple(
            state for _, state in d2_2plus2_types()
        ) + tuple(state for _, state in tq_types())
        edge_count = 0
        for child in children:
            for parent, source, next_color, next_cap in reverse_nonexhausting(child):
                edge_count += 1
                old_cap = parent.active[source][1]
                self.assertEqual(
                    forward_nonexhausting(parent, source, next_color, next_cap), child
                )
                self.assertEqual(sum(parent.d), sum(child.d))
                self.assertLess(old_cap, next_cap)
                self.assertLessEqual(old_cap, -child.d[next_color])
                self.assertLess(-child.d[next_color], next_cap)
        self.assertGreater(edge_count, 0)

    def test_reverse_exhausting_edges_round_trip_and_isolate_final_color(self) -> None:
        edge_count = 0
        for _, child in tq_types():
            for parent, source, final_color in reverse_exhausting(child):
                edge_count += 1
                old_cap = parent.active[source][1]
                self.assertEqual(forward_exhausting(parent, source, final_color), child)
                self.assertEqual(sum(child.d) - sum(parent.d), HEIGHT)
                final_run = HEIGHT - old_cap
                self.assertEqual(child.d[final_color], final_run)
                self.assertEqual(exposed_counts(child)[final_color], final_run)
        self.assertGreater(edge_count, 0)

    def test_endpoint_and_legality_boundaries_are_strict(self) -> None:
        valid = MacroState(0, (1, 1, -1, -1), ((2, 2), (2, 2), (2, 2), (3, 2)))
        cap_zero = MacroState(valid.z, valid.d, ((2, 0),) + valid.active[1:])
        cap_full = MacroState(valid.z, valid.d, ((2, 7),) + valid.active[1:])
        self.assertIn("endpoint-cap", physical_consistency_errors(cap_zero))
        self.assertIn("endpoint-cap", physical_consistency_errors(cap_full))

        # At z=0 exactly two positive adjusted debts are legal; three are not.
        legal = MacroState(0, (1, 1, -2, 0), ((2, 2), (2, 2), (2, 2), (3, 2)))
        blocked = MacroState(0, (1, 1, -1, -1), ((2, 2), (2, 2), (2, 2), (3, 2)))
        self.assertTrue(legal_source(legal, 0))
        self.assertFalse(legal_source(blocked, 0))


class MainCliBlackBoxAudit(unittest.TestCase):
    """Compare the CLI artifact with the independent partition construction."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.tempdir = tempfile.TemporaryDirectory(prefix="c4-h7-macro-audit-")
        cls.json_path = Path(cls.tempdir.name) / "report.json"
        cls.markdown_path = Path(cls.tempdir.name) / "report.md"
        cls.process = subprocess.run(
            [
                sys.executable,
                str(MAIN_SCRIPT),
                "--json",
                str(cls.json_path),
                "--markdown",
                str(cls.markdown_path),
                "--max-reverse-depth",
                "1",
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if cls.json_path.exists():
            cls.report = json.loads(cls.json_path.read_text(encoding="utf-8"))
        else:
            cls.report = None

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tempdir.cleanup()

    def test_cli_contract_and_public_counts(self) -> None:
        self.assertEqual(
            self.process.returncode,
            0,
            f"stdout={self.process.stdout}\nstderr={self.process.stderr}",
        )
        self.assertIsNotNone(self.report)
        self.assertTrue(self.markdown_path.exists())
        self.assertTrue(self.report["verified"])
        self.assertEqual(
            self.report["counts"],
            {
                "tq": 71,
                "d2_3plus1": 265,
                "d2_2plus2": 661,
                "total": 997,
            },
        )

    def test_report_terminal_records_equal_independent_census(self) -> None:
        expected = {
            "tq": {color_bucket_key(state) for _, state in tq_types()},
            "d2_3_1": {
                color_bucket_key(state) for _, state in d2_3plus1_types()
            },
            "d2_2_2": {
                color_bucket_key(state) for _, state in d2_2plus2_types()
            },
        }
        actual = {family: set() for family in expected}
        for record in self.report["terminal_states"]:
            state = state_from_report(record["z"], record["state"])
            self.assertEqual(physical_consistency_errors(state), (), record["id"])
            self.assertFalse(
                any(legal_source(state, source) for source in range(len(state.active))),
                record["id"],
            )
            actual[record["family"]].add(color_bucket_key(state))
        self.assertEqual(actual, expected)

    def test_report_reverse_edges_equal_independent_one_step_cone(self) -> None:
        independent_families = {
            "tq": tq_types(),
            "d2_3_1": d2_3plus1_types(),
            "d2_2_2": d2_2plus2_types(),
        }
        expected_pairs: dict[str, set[tuple[object, object]]] = {}
        expected_predecessors = set()
        for family, typed_children in independent_families.items():
            pairs = set()
            for _, child in typed_children:
                child_key = color_bucket_key(child)
                for parent, *_ in reverse_nonexhausting(child):
                    parent_key = color_bucket_key(parent)
                    pairs.add((parent_key, child_key))
                    expected_predecessors.add(parent_key)
            expected_pairs[family] = pairs

        predecessors = {}
        for record in self.report["predecessor_states"]:
            state = state_from_report(record["z"], record["state"])
            self.assertEqual(physical_consistency_errors(state), (), record["id"])
            self.assertEqual(
                record["legal_source_count"],
                sum(legal_source(state, source) for source in range(len(state.active))),
                record["id"],
            )
            predecessors[record["id"]] = state

        terminals = {
            record["id"]: state_from_report(record["z"], record["state"])
            for record in self.report["terminal_states"]
        }
        actual_pairs = {family: set() for family in independent_families}
        for edge in self.report["reverse_edges"]:
            parent = predecessors[edge["predecessor_id"]]
            child = terminals[edge["terminal_id"]]
            family = edge["terminal_family"]
            actual_pairs[family].add((color_bucket_key(parent), color_bucket_key(child)))

            old_color, old_cap, new_color, new_cap = edge["witness_action"]
            candidate_sources = [
                source
                for source, endpoint in enumerate(parent.active)
                if endpoint == (old_color, old_cap)
            ]
            self.assertTrue(candidate_sources, edge)
            source = candidate_sources[0]
            self.assertTrue(legal_source(parent, source), edge)
            replayed = forward_nonexhausting(
                parent, source, new_color, new_cap
            )
            self.assertEqual(color_bucket_key(replayed), color_bucket_key(child), edge)

        self.assertEqual(actual_pairs, expected_pairs)
        self.assertEqual(
            {color_bucket_key(state) for state in predecessors.values()},
            expected_predecessors,
        )
        self.assertEqual(len(expected_predecessors), 6_375)
        self.assertEqual(sum(map(len, expected_pairs.values())), 12_224)

    def test_report_exhausting_bridge_equals_independent_construction(self) -> None:
        expected_pairs = set()
        expected_predecessors = set()
        labeled_events = 0
        for _, child in tq_types():
            child_key = color_bucket_key(child)
            for parent, *_ in reverse_exhausting(child):
                labeled_events += 1
                parent_key = color_bucket_key(parent)
                expected_pairs.add((parent_key, child_key))
                expected_predecessors.add(parent_key)

        predecessors = {}
        for record in self.report["exhausting_predecessor_states"]:
            state = state_from_report(record["z"], record["state"])
            self.assertEqual(physical_consistency_errors(state), (), record["id"])
            self.assertEqual(
                record["legal_source_count"],
                sum(legal_source(state, source) for source in range(len(state.active))),
                record["id"],
            )
            predecessors[record["id"]] = state

        terminals = {
            record["id"]: state_from_report(record["z"], record["state"])
            for record in self.report["terminal_states"]
        }
        actual_pairs = set()
        for edge in self.report["exhausting_bridge_edges"]:
            parent = predecessors[edge["predecessor_id"]]
            child = terminals[edge["terminal_id"]]
            actual_pairs.add((color_bucket_key(parent), color_bucket_key(child)))

            old_color, old_cap, final_color = edge["witness_action"]
            candidate_sources = [
                source
                for source, endpoint in enumerate(parent.active)
                if endpoint == (old_color, old_cap)
            ]
            self.assertTrue(candidate_sources, edge)
            source = candidate_sources[0]
            self.assertTrue(legal_source(parent, source), edge)
            replayed = forward_exhausting(parent, source, final_color)
            self.assertEqual(color_bucket_key(replayed), color_bucket_key(child), edge)
            final_run = HEIGHT - old_cap
            self.assertEqual(replayed.d[final_color], final_run, edge)
            self.assertEqual(exposed_counts(replayed)[final_color], final_run, edge)

        self.assertEqual(actual_pairs, expected_pairs)
        self.assertEqual(
            {color_bucket_key(state) for state in predecessors.values()},
            expected_predecessors,
        )
        self.assertEqual((labeled_events, len(expected_predecessors), len(expected_pairs)), (624, 418, 429))
        self.assertEqual(
            self.report["reverse"]["tq_exhausting_bridge"]["labeled_candidates"],
            labeled_events,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
