#!/usr/bin/env python3
"""Small audit for the charged c=4 anchor-pair graph.

The script is deliberately finite and local.  It checks the six pair
vertices, the clean two-switch numerical box, one committed h=7 YES layout,
and three committed h=8 NO fixtures.  It does not enumerate h=7 layouts or
expand residual words.
"""

from __future__ import annotations

import itertools
import json
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from typing import Iterable, Sequence


COLORS = tuple(range(4))
K = 2
Pair = frozenset[int]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def positive_support(debt: Sequence[int]) -> frozenset[int]:
    return frozenset(color for color, value in enumerate(debt) if value > 0)


def anchor_pair(debt: Sequence[int]) -> Pair | None:
    positive = positive_support(debt)
    if len(positive) != 2:
        return None
    return frozenset(set(COLORS) - positive)


def entry_charge(before: Pair, after: Pair) -> tuple[int, ...]:
    return tuple(int(color in after - before) for color in COLORS)


def add_vectors(left: Sequence[int], right: Sequence[int]) -> tuple[int, ...]:
    return tuple(a + b for a, b in zip(left, right))


def pair_graph_audit() -> dict[str, object]:
    pairs = tuple(frozenset(pair) for pair in itertools.combinations(COLORS, 2))
    require(len(pairs) == 6, "there must be six anchor pairs")
    adjacent = {
        pair: tuple(other for other in pairs if len(pair & other) == 1)
        for pair in pairs
    }
    require(all(len(values) == 4 for values in adjacent.values()), "not an octahedron")
    undirected_edges = {
        frozenset((pair, other))
        for pair in pairs
        for other in adjacent[pair]
    }
    opposite = {
        frozenset((pair, other))
        for pair in pairs
        for other in pairs
        if pair.isdisjoint(other)
    }
    require(len(undirected_edges) == 12, "wrong octahedron edge count")
    require(len(opposite) == 3, "wrong opposite-pair count")

    directed_adjacent = 0
    directed_opposite = 0
    for before in pairs:
        for after in pairs:
            if before == after:
                continue
            charge = entry_charge(before, after)
            cost = sum(charge)
            require(cost == len(after - before), "pair charge has wrong weight")
            if cost == 1:
                directed_adjacent += 1
            elif cost == 2:
                directed_opposite += 1
            else:
                raise AssertionError("distinct two-subsets have invalid distance")
    require((directed_adjacent, directed_opposite) == (24, 6), "metric closure drifted")

    # trace(A^m) for the octahedron.  Walks are directed by traversal even
    # though the underlying graph is undirected.
    expected_closed = {2: 24, 3: 48, 4: 288, 5: 960, 6: 4_224}
    closed_counts: dict[int, int] = {}
    charged_walks = 0
    for length in range(2, 7):
        count = 0

        def extend(start: Pair, path: tuple[Pair, ...]) -> None:
            nonlocal count, charged_walks
            if len(path) == length + 1:
                if path[-1] != start:
                    return
                count += 1
                total = (0, 0, 0, 0)
                exits = (0, 0, 0, 0)
                for before, after in zip(path, path[1:]):
                    total = add_vectors(total, entry_charge(before, after))
                    exits = add_vectors(exits, entry_charge(after, before))
                require(total == exits, "closed walk entries and exits do not balance")
                require(sum(total) == length, "adjacent walk paid the wrong charge")
                require(sum(value > 0 for value in total) >= 2, "cycle charged one color")
                charged_walks += 1
                return
            for after in adjacent[path[-1]]:
                extend(start, path + (after,))

        for start in pairs:
            extend(start, (start,))
        require(count == expected_closed[length], f"length-{length} walk count drifted")
        closed_counts[length] = count

    require(charged_walks == sum(expected_closed.values()), "closed-walk audit drifted")
    return {
        "vertices": len(pairs),
        "undirected_edges": len(undirected_edges),
        "opposite_pairs": len(opposite),
        "directed_metric_edges": {
            "cost_1": directed_adjacent,
            "cost_2": directed_opposite,
        },
        "closed_walks_by_length": closed_counts,
        "closed_walks_checked": charged_walks,
    }


def source_is_legal(debt: Sequence[int], source: int, cap: int) -> bool:
    tested = list(debt)
    tested[source] += cap
    return len(positive_support(tested)) <= K


def live_update(debt: Sequence[int], source: int, target: int, cap: int) -> tuple[int, ...]:
    updated = list(debt)
    updated[source] += cap
    updated[target] -= cap
    return tuple(updated)


def replay_clean_debts(
    a_energy: int,
    positive_y: int,
    positive_p: int,
    old_p_to_y: int,
    new_y: int,
    old_x_to_b: int,
    old_p_to_x: int,
    target: int,
) -> tuple[int, ...]:
    # Color order is (x,b,y,p) = (0,1,2,3).
    debt = (-a_energy, 0, positive_y, positive_p)
    events = (
        (3, 2, old_p_to_y),
        (0, 1, old_x_to_b),
        (3, 0, old_p_to_x),
        (2, target, new_y),
    )
    for source, destination, cap in events:
        require(source_is_legal(debt, source, cap), "clean rotor event became illegal")
        debt = live_update(debt, source, destination, cap)
    require(positive_support(debt) == frozenset((2, 3)), "clean rotor did not return")
    return debt


def clean_rotor_macros(height: int) -> dict[str, object]:
    counts: Counter[str] = Counter()
    signatures: Counter[tuple[str, int, int]] = Counter()
    unsaturated: Counter[str] = Counter()
    samples: dict[str, dict[str, object]] = {}

    # The unused common anchor has debt zero, so A=X+Y.  Variables match
    # equations (14)--(16) in the note.
    for positive_y in range(1, height + 1):
        for positive_p in range(1, height + 1):
            a_energy = positive_y + positive_p
            for old_p_to_y in range(positive_y, height - 1):
                for new_y in range(old_p_to_y + 1, height):
                    for old_x_to_b in range(a_energy + 1, height):
                        for untouched_x in range(1, height):
                            exposed_x_initial = old_x_to_b + untouched_x - a_energy
                            if not 2 <= exposed_x_initial <= height:
                                continue
                            for old_p_to_x in range(
                                max(1, old_x_to_b - a_energy), height - 1
                            ):
                                exposed_p = positive_p + old_p_to_y + old_p_to_x
                                if not 2 <= exposed_p <= height:
                                    continue
                                for new_b in range(old_x_to_b + 1, height):
                                    for new_x in range(old_p_to_x + 1, height):
                                        for final_endpoint in range(new_y + 1, height):
                                            base = {
                                                "A": a_energy,
                                                "X": positive_y,
                                                "Y": positive_p,
                                                "s": old_p_to_y,
                                                "r": new_y,
                                                "t": old_x_to_b,
                                                "c": untouched_x,
                                                "u": old_p_to_x,
                                                "R": new_b,
                                                "w": new_x,
                                                "T": final_endpoint,
                                            }

                                            # delta=x: final top multiplicity 3+1.
                                            debt_x = replay_clean_debts(
                                                a_energy,
                                                positive_y,
                                                positive_p,
                                                old_p_to_y,
                                                new_y,
                                                old_x_to_b,
                                                old_p_to_x,
                                                0,
                                            )
                                            energy_x = -debt_x[0]
                                            energy_b = -debt_x[1]
                                            require(
                                                debt_x
                                                == (
                                                    -a_energy
                                                    + old_x_to_b
                                                    - old_p_to_x
                                                    - new_y,
                                                    -old_x_to_b,
                                                    positive_y - old_p_to_y + new_y,
                                                    positive_p + old_p_to_y + old_p_to_x,
                                                ),
                                                "delta=x debt formula drifted",
                                            )
                                            require(
                                                energy_x >= new_y >= positive_y + 1,
                                                "delta=x lower bound drifted",
                                            )
                                            exposure_x = (
                                                untouched_x + new_x + final_endpoint - energy_x
                                            )
                                            exposure_b = new_b - energy_b
                                            exposure_y = positive_y + new_y - old_p_to_y
                                            exposures_x = (
                                                exposure_x,
                                                exposure_b,
                                                exposure_y,
                                                exposed_p,
                                            )
                                            blocked_x = all(
                                                cap > energy_x
                                                for cap in (untouched_x, new_x, final_endpoint)
                                            ) and new_b > energy_b
                                            physical_x = all(
                                                multiplicity <= exposed <= height
                                                for multiplicity, exposed in zip(
                                                    (3, 1, 0, 0), exposures_x
                                                )
                                            )
                                            if blocked_x and physical_x:
                                                counts["delta_x"] += 1
                                                signatures[("delta_x", energy_x, exposure_x)] += 1
                                                if exposure_x < height:
                                                    unsaturated["delta_x"] += 1
                                                    samples.setdefault(
                                                        "delta_x_unsaturated",
                                                        {**base, "exposures": exposures_x},
                                                    )

                                            # delta=b: final top multiplicity 2+2.
                                            debt_b = replay_clean_debts(
                                                a_energy,
                                                positive_y,
                                                positive_p,
                                                old_p_to_y,
                                                new_y,
                                                old_x_to_b,
                                                old_p_to_x,
                                                1,
                                            )
                                            energy_x_b = -debt_b[0]
                                            energy_b_b = -debt_b[1]
                                            require(
                                                debt_b
                                                == (
                                                    -a_energy + old_x_to_b - old_p_to_x,
                                                    -old_x_to_b - new_y,
                                                    positive_y - old_p_to_y + new_y,
                                                    positive_p + old_p_to_y + old_p_to_x,
                                                ),
                                                "delta=b debt formula drifted",
                                            )
                                            require(
                                                energy_b_b
                                                == old_x_to_b + new_y
                                                >= 2 * positive_y + positive_p + 2,
                                                "delta=b lower bound drifted",
                                            )
                                            exposure_x_b = untouched_x + new_x - energy_x_b
                                            exposure_b_b = new_b + final_endpoint - energy_b_b
                                            exposures_b = (
                                                exposure_x_b,
                                                exposure_b_b,
                                                exposure_y,
                                                exposed_p,
                                            )
                                            blocked_b = all(
                                                cap > energy_x_b
                                                for cap in (untouched_x, new_x)
                                            ) and all(
                                                cap > energy_b_b
                                                for cap in (new_b, final_endpoint)
                                            )
                                            physical_b = all(
                                                multiplicity <= exposed <= height
                                                for multiplicity, exposed in zip(
                                                    (2, 2, 0, 0), exposures_b
                                                )
                                            )
                                            if blocked_b and physical_b:
                                                counts["delta_b"] += 1
                                                signatures[("delta_b", energy_b_b, exposure_b_b)] += 1
                                                if exposure_b_b < height:
                                                    unsaturated["delta_b"] += 1
                                                    samples.setdefault(
                                                        "delta_b_unsaturated",
                                                        {**base, "exposures": exposures_b},
                                                    )

    if height == 7:
        require(counts == {"delta_x": 9, "delta_b": 35}, "h7 clean count drifted")
        require(
            signatures == {("delta_x", 2, 7): 9, ("delta_b", 5, 7): 35},
            "h7 saturation signatures drifted",
        )
        require(not unsaturated, "h7 clean return failed to saturate")
    elif height == 8:
        require(counts == {"delta_x": 67, "delta_b": 369}, "h8 clean count drifted")
        require(
            signatures
            == {
                ("delta_x", 2, 7): 16,
                ("delta_x", 2, 8): 51,
                ("delta_b", 5, 7): 56,
                ("delta_b", 5, 8): 112,
                ("delta_b", 6, 8): 201,
            },
            "h8 boundary signatures drifted",
        )
        require(
            unsaturated == {"delta_x": 16, "delta_b": 56},
            "h8 unsaturated corner drifted",
        )
        require(
            samples["delta_x_unsaturated"]
            == {
                "A": 2,
                "X": 1,
                "Y": 1,
                "s": 1,
                "r": 2,
                "t": 3,
                "c": 3,
                "u": 1,
                "R": 4,
                "w": 3,
                "T": 3,
                "exposures": (7, 1, 2, 3),
            },
            "h8 delta=x sample drifted",
        )
        require(
            samples["delta_b_unsaturated"]
            == {
                "A": 2,
                "X": 1,
                "Y": 1,
                "s": 1,
                "r": 2,
                "t": 3,
                "c": 1,
                "u": 1,
                "R": 6,
                "w": 2,
                "T": 6,
                "exposures": (3, 7, 2, 3),
            },
            "h8 delta=b sample drifted",
        )

    return {
        "height": height,
        "terminal_macros": dict(counts),
        "signatures": {
            f"{kind},E={energy},F={exposed}": count
            for (kind, energy, exposed), count in sorted(signatures.items())
        },
        "unsaturated": dict(unsaturated),
        "samples": samples,
    }


def runs(word: str) -> tuple[tuple[int, int], ...]:
    result: list[tuple[int, int]] = []
    for char in word:
        color = int(char)
        if result and result[-1][0] == color:
            result[-1] = (color, result[-1][1] + 1)
        else:
            result.append((color, 1))
    return tuple(result)


@dataclass(frozen=True)
class BorderState:
    positions: tuple[int, ...]
    debt: tuple[int, ...]


class BorderModel:
    def __init__(self, height: int, bottom_to_top: Sequence[str]) -> None:
        self.height = height
        self.columns = tuple(runs(word[::-1]) for word in bottom_to_top)
        require(
            len(self.columns) == 4
            and all(sum(length for _, length in column) == height for column in self.columns),
            "bad fixture columns",
        )
        counts = Counter("".join(bottom_to_top))
        require(counts == Counter({str(color): height for color in COLORS}), "unbalanced fixture")
        self.cumulative = tuple(
            tuple(sum(length for _, length in column[: index + 1]) for index in range(len(column)))
            for column in self.columns
        )
        self.initial = BorderState((0, 0, 0, 0), (0, 0, 0, 0))

    def exhausted(self, state: BorderState, column: int) -> bool:
        return state.positions[column] == len(self.columns[column]) - 1

    def z(self, state: BorderState) -> int:
        return sum(self.exhausted(state, column) for column in COLORS)

    def cap(self, state: BorderState, column: int) -> int:
        return self.cumulative[column][state.positions[column]]

    def legal_sources(self, state: BorderState) -> tuple[int, ...]:
        result = []
        for column in COLORS:
            if self.exhausted(state, column):
                continue
            source = self.columns[column][state.positions[column]][0]
            tested = list(state.debt)
            tested[source] += self.cap(state, column)
            if len(positive_support(tested)) <= K + self.z(state):
                result.append(column)
        return tuple(result)

    def apply(self, state: BorderState, column: int) -> BorderState:
        require(column in self.legal_sources(state), "illegal fixture action")
        position = state.positions[column]
        old_color = self.columns[column][position][0]
        old_cap = self.cap(state, column)
        positions = list(state.positions)
        positions[column] += 1
        new_color = self.columns[column][positions[column]][0]
        debt = list(state.debt)
        debt[old_color] += old_cap
        if positions[column] == len(self.columns[column]) - 1:
            debt[new_color] += self.height - old_cap
        else:
            debt[new_color] -= old_cap
        return BorderState(tuple(positions), tuple(debt))

    def active_tops(self, state: BorderState) -> tuple[tuple[int, int], ...]:
        return tuple(
            (
                self.columns[column][state.positions[column]][0],
                self.cap(state, column),
            )
            for column in COLORS
            if not self.exhausted(state, column)
        )

    def exposures(self, state: BorderState) -> tuple[int, ...]:
        exposed = list(state.debt)
        for color, cap in self.active_tops(state):
            exposed[color] += cap
        return tuple(exposed)

    def pair(self, state: BorderState) -> Pair | None:
        if self.z(state) != 0:
            return None
        return anchor_pair(state.debt)


def replay(model: BorderModel, path: Iterable[int]) -> list[BorderState]:
    states = [model.initial]
    for column in path:
        states.append(model.apply(states[-1], column))
    return states


def directed_cycle_exists(edges: set[tuple[Pair, Pair]]) -> bool:
    adjacency: dict[Pair, set[Pair]] = defaultdict(set)
    for before, after in edges:
        adjacency[before].add(after)

    def visit(node: Pair, active: set[Pair], finished: set[Pair]) -> bool:
        if node in active:
            return True
        if node in finished:
            return False
        active.add(node)
        for after in adjacency[node]:
            if visit(after, active, finished):
                return True
        active.remove(node)
        finished.add(node)
        return False

    finished: set[Pair] = set()
    return any(visit(node, set(), finished) for node in tuple(adjacency))


def border_graph_diagnostic(model: BorderModel) -> dict[str, object]:
    raw_queue = deque((model.initial,))
    raw_seen = {model.initial}
    terminals = 0
    goals = 0
    while raw_queue:
        state = raw_queue.popleft()
        legal = model.legal_sources(state)
        if model.z(state) == 4:
            goals += 1
        elif not legal:
            terminals += 1
        for column in legal:
            after = model.apply(state, column)
            if after not in raw_seen:
                raw_seen.add(after)
                raw_queue.append(after)

    augmented_queue = deque(((model.initial, None),))
    augmented_seen = {(model.initial, None)}
    vertices: set[Pair] = set()
    edges: set[tuple[Pair, Pair]] = set()
    while augmented_queue:
        state, last_pair = augmented_queue.popleft()
        current_pair = model.pair(state)
        if current_pair is not None:
            vertices.add(current_pair)
            if last_pair is not None and current_pair != last_pair:
                edges.add((last_pair, current_pair))
            last_pair = current_pair
        for column in model.legal_sources(state):
            after = model.apply(state, column)
            key = (after, last_pair)
            if key not in augmented_seen:
                augmented_seen.add(key)
                augmented_queue.append(key)

    return {
        "raw_states": len(raw_seen),
        "terminal_states": terminals,
        "goals": goals,
        "augmented_states": len(augmented_seen),
        "pair_vertices": vertices,
        "pair_edges": edges,
        "pair_cycle": directed_cycle_exists(edges),
    }


H7_FOUR_LOCK = ("2221032", "3321023", "3321003", "1111000")
H7_CYCLE_PATH = (0, 0, 1, 0, 2, 1)
H7_WINNING_PATH = (0, 0, 1, 0, 2, 2, 0, 1, 1, 1, 1, 2, 2, 3)

H8_FIXTURES = {
    "h8_no_000": (
        ("22111003", "22111003", "00333221", "00333221"),
        60,
        7,
        68,
        {frozenset((0, 2)), frozenset((0, 3)), frozenset((1, 2))},
        set(),
    ),
    "h8_no_001": (
        ("22033321", "11300021", "11033322", "12300021"),
        68,
        6,
        113,
        {
            frozenset((0, 1)),
            frozenset((0, 2)),
            frozenset((0, 3)),
            frozenset((2, 3)),
        },
        {
            (frozenset((0, 3)), frozenset((0, 2))),
            (frozenset((0, 3)), frozenset((2, 3))),
        },
    ),
    "h8_no_002": (
        ("22311100", "22311102", "00133302", "02133302"),
        68,
        6,
        113,
        {
            frozenset((0, 1)),
            frozenset((0, 3)),
            frozenset((1, 3)),
            frozenset((2, 3)),
        },
        {
            (frozenset((1, 3)), frozenset((0, 1))),
            (frozenset((1, 3)), frozenset((0, 3))),
        },
    ),
}


def pair_name(pair: Pair) -> str:
    return "{" + ",".join(str(color) for color in sorted(pair)) + "}"


def fixture_audit() -> dict[str, object]:
    h7 = BorderModel(7, H7_FOUR_LOCK)
    cycle_states = replay(h7, H7_CYCLE_PATH)
    checkpoints = (cycle_states[2], cycle_states[4], cycle_states[6])
    expected = (
        ((-2, 0, 1, 1), frozenset((0, 1)), (4, 0, 1, 3)),
        ((1, -3, 0, 2), frozenset((1, 2)), (4, 1, 2, 3)),
        ((-2, -3, 2, 3), frozenset((0, 1)), (7, 1, 2, 3)),
    )
    for state, (debt, pair, exposures) in zip(checkpoints, expected):
        require(state.debt == debt, "h7 cycle debt drifted")
        require(h7.pair(state) == pair, "h7 cycle pair drifted")
        require(h7.exposures(state) == exposures, "h7 cycle exposure drifted")
    require(not h7.legal_sources(cycle_states[-1]), "h7 cycle no longer ends in D2")
    require(
        sorted(h7.active_tops(cycle_states[-1]))
        == sorted(((0, 3), (0, 3), (0, 3), (1, 4))),
        "h7 cycle terminal tops drifted",
    )

    winning_states = replay(h7, H7_WINNING_PATH)
    require(h7.z(winning_states[-1]) == 4, "committed h7 path stopped before the goal")
    require(winning_states[-1].debt == (7, 7, 7, 7), "h7 winning debt drifted")

    h7_graph = border_graph_diagnostic(h7)
    require(
        (
            h7_graph["raw_states"],
            h7_graph["terminal_states"],
            h7_graph["goals"],
            h7_graph["augmented_states"],
        )
        == (178, 6, 1, 438),
        "h7 fixture graph drifted",
    )
    require(h7_graph["pair_cycle"] is True, "h7 projected cycle disappeared")
    require(
        (frozenset((0, 1)), frozenset((1, 2))) in h7_graph["pair_edges"]
        and (frozenset((1, 2)), frozenset((0, 1))) in h7_graph["pair_edges"],
        "h7 two-cycle edges disappeared",
    )

    h8_rows: dict[str, object] = {}
    for name, (
        columns,
        expected_raw,
        expected_terminals,
        expected_augmented,
        expected_vertices,
        expected_edges,
    ) in H8_FIXTURES.items():
        diagnostic = border_graph_diagnostic(BorderModel(8, columns))
        require(
            (
                diagnostic["raw_states"],
                diagnostic["terminal_states"],
                diagnostic["goals"],
                diagnostic["augmented_states"],
            )
            == (expected_raw, expected_terminals, 0, expected_augmented),
            f"{name} border graph drifted",
        )
        require(diagnostic["pair_vertices"] == expected_vertices, f"{name} vertices drifted")
        require(diagnostic["pair_edges"] == expected_edges, f"{name} edges drifted")
        require(diagnostic["pair_cycle"] is False, f"{name} acquired a pair cycle")
        h8_rows[name] = {
            "raw_states": diagnostic["raw_states"],
            "terminal_states": diagnostic["terminal_states"],
            "augmented_states": diagnostic["augmented_states"],
            "pair_vertices": sorted(pair_name(pair) for pair in expected_vertices),
            "pair_edges": sorted(
                f"{pair_name(before)}->{pair_name(after)}"
                for before, after in expected_edges
            ),
            "pair_cycle": False,
        }

    return {
        "h7_four_lock": {
            "projected_cycle": ["{0,1}", "{1,2}", "{0,1}"],
            "cycle_exposures": [list(h7.exposures(state)) for state in checkpoints],
            "cycle_ends_in_d2": True,
            "complete_layout_winning": True,
            "raw_states": h7_graph["raw_states"],
            "augmented_states": h7_graph["augmented_states"],
        },
        "h8_no_pressure": h8_rows,
    }


def main() -> int:
    result = {
        "status": "ANCHOR_PAIR_GRAPH_AUDITED",
        "claim_boundary": {
            "projected_anchor_graph_acyclic": False,
            "lifted_anchor_exposure_graph_acyclic": True,
            "all_h7_locks_have_clean_switch": False,
            "h7_universal_solvability_proved": False,
            "large_search_run": False,
        },
        "pair_graph": pair_graph_audit(),
        "clean_rotor": {
            "h7": clean_rotor_macros(7),
            "h8": clean_rotor_macros(8),
        },
        "fixtures": fixture_audit(),
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
