#!/usr/bin/env python3
"""Enumerate the c=4, k=2, h=7 terminal macro layer.

This is deliberately not an arrangement search.  A state is the color- and
column-symmetry class of four color buckets

    (d_c, sorted(current capacities topped by c)).

For an active source with top color ``a`` and current capacity ``s``, Ito's
source test needs one host for each positive coordinate of ``d + s e_a``.
There are ``2 + z`` hosts, where ``z`` original columns have been exhausted.

The same-``z`` reverse layer consists of non-exhausting live edges: an old
top/capacity ``(a, s)`` exposes a different color ``b`` and grows to a new
capacity ``t``, with ``a != b`` and ``s < t < h``.  The report separately
records the first-exhaustion bridge from ``z=0`` into Tq at ``z=1``.  Every
reported edge is replayed independently in the forward direction before the
report is marked verified.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from functools import lru_cache
from itertools import combinations_with_replacement
from pathlib import Path
from typing import Iterable, Iterator, Sequence


HEIGHT = 7
COLORS = 4
EMPTY_COLUMNS = 2
EXPECTED_TERMINAL_COUNTS = {
    "tq": 71,
    "d2_3_1": 265,
    "d2_2_2": 661,
    "total": 997,
}

Bucket = tuple[int, tuple[int, ...]]
State = tuple[Bucket, ...]
Action = tuple[int, int, int, int]  # old color, old cap, new color, new cap
ExhaustingAction = tuple[int, int, int]  # old color, old cap, final-run color


def canonical_state(debts: Sequence[int], columns: Iterable[tuple[int, int]]) -> State:
    """Quotient a labeled state by color and active-column permutations."""

    caps_by_color: list[list[int]] = [[] for _ in range(COLORS)]
    for color, cap in columns:
        caps_by_color[color].append(cap)
    return tuple(
        sorted(
            (int(debts[color]), tuple(sorted(caps_by_color[color])))
            for color in range(COLORS)
        )
    )


def state_key(state: State) -> tuple[Bucket, ...]:
    return state


def exposed_counts(state: State) -> tuple[int, ...]:
    """Return F=d+G for the canonical color buckets."""

    return tuple(debt + sum(caps) for debt, caps in state)


def algebraically_consistent(state: State, z: int) -> bool:
    """Check precisely the bounded numerical constraints used in this census."""

    if len(state) != COLORS:
        return False
    if tuple(sorted(state)) != state:
        return False
    if sum(len(caps) for _, caps in state) != COLORS - z:
        return False
    if sum(debt for debt, _ in state) != z * HEIGHT:
        return False
    if any(cap < 1 or cap >= HEIGHT for _, caps in state for cap in caps):
        return False
    exposed = exposed_counts(state)
    multiplicities = tuple(len(caps) for _, caps in state)
    if any(
        not multiplicities[color] <= exposed[color] <= HEIGHT
        for color in range(COLORS)
    ):
        return False

    # Every active original column has a nonempty hidden suffix whose first
    # color differs from its current top.  In this forbidden-diagonal
    # assignment problem, the four singleton Hall inequalities are also
    # sufficient: a group with two distinct forbidden colors can use the
    # union of all colors.
    remaining = tuple(HEIGHT - value for value in exposed)
    return all(
        multiplicities[color]
        <= sum(remaining[other] for other in range(COLORS) if other != color)
        for color in range(COLORS)
    )


def source_positive_count(state: State, top_color: int, cap: int) -> int:
    adjusted = [debt for debt, _ in state]
    adjusted[top_color] += cap
    return sum(value > 0 for value in adjusted)


def source_is_legal(state: State, z: int, top_color: int, cap: int) -> bool:
    return source_positive_count(state, top_color, cap) <= EMPTY_COLUMNS + z


def sources(state: State) -> Iterator[tuple[int, int]]:
    """Yield physical active sources; equal columns retain their multiplicity."""

    for color, (_, caps) in enumerate(state):
        for cap in caps:
            yield color, cap


@lru_cache(maxsize=None)
def legal_sources(state: State, z: int) -> tuple[tuple[int, int], ...]:
    return tuple(
        source
        for source in sources(state)
        if source_is_legal(state, z, source[0], source[1])
    )


def is_deadlock(state: State, z: int) -> bool:
    return algebraically_consistent(state, z) and not legal_sources(state, z)


def classify_terminal(state: State, z: int) -> str | None:
    """Recognize the reachable terminal families D2 and Tq."""

    if not is_deadlock(state, z):
        return None

    positive = [index for index, (debt, _) in enumerate(state) if debt > 0]
    nonpositive = [index for index, (debt, _) in enumerate(state) if debt <= 0]

    if z == 1:
        topped = [index for index, (_, caps) in enumerate(state) if caps]
        if len(positive) == 3 and len(nonpositive) == 1 and topped == nonpositive:
            return "tq"
        return None

    if z == 0 and len(positive) == 2 and len(nonpositive) == 2:
        if any(state[index][1] for index in positive):
            return None
        multiplicities = sorted(len(state[index][1]) for index in nonpositive)
        if multiplicities == [1, 3]:
            return "d2_3_1"
        if multiplicities == [2, 2]:
            return "d2_2_2"
    return None


def _nonpositive_buckets(multiplicity: int) -> Iterator[Bucket]:
    # F=d+G>=0 bounds -d by the total hosted capacity.  -24 is a harmless
    # uniform lower bound for four active capacities of at most six.
    for debt in range(-4 * (HEIGHT - 1), 1):
        for caps in combinations_with_replacement(range(1, HEIGHT), multiplicity):
            if min(caps) <= -debt:
                continue
            exposed = debt + sum(caps)
            if 0 <= exposed <= HEIGHT:
                yield debt, caps


def enumerate_tq_terminals() -> tuple[State, ...]:
    states: set[State] = set()
    # F_q >= 3(E+1)-E and F_q<=7 imply E=-d_q<=2.
    for e in range(3):
        for caps in combinations_with_replacement(range(1, HEIGHT), 3):
            if min(caps) <= e or sum(caps) - e > HEIGHT:
                continue
            for positive_debts in combinations_with_replacement(range(1, HEIGHT + 1), 3):
                if sum(positive_debts) - e != HEIGHT:
                    continue
                state = tuple(
                    sorted(((-e, caps), *((debt, ()) for debt in positive_debts)))
                )
                if classify_terminal(state, z=1) == "tq":
                    states.add(state)
    return tuple(sorted(states, key=state_key))


def enumerate_d2_terminals(multiplicities: tuple[int, int]) -> tuple[State, ...]:
    states: set[State] = set()
    left_buckets = tuple(_nonpositive_buckets(multiplicities[0]))
    right_buckets = tuple(_nonpositive_buckets(multiplicities[1]))
    for positive_debts in combinations_with_replacement(range(1, HEIGHT + 1), 2):
        positives: tuple[Bucket, Bucket] = (
            (positive_debts[0], ()),
            (positive_debts[1], ()),
        )
        for left in left_buckets:
            for right in right_buckets:
                state = tuple(sorted((*positives, left, right)))
                if sum(debt for debt, _ in state) != 0:
                    continue
                family = "d2_3_1" if sorted(multiplicities) == [1, 3] else "d2_2_2"
                if classify_terminal(state, z=0) == family:
                    states.add(state)
    return tuple(sorted(states, key=state_key))


def enumerate_terminals() -> dict[str, tuple[State, ...]]:
    return {
        "tq": enumerate_tq_terminals(),
        "d2_3_1": enumerate_d2_terminals((3, 1)),
        "d2_2_2": enumerate_d2_terminals((2, 2)),
    }


def apply_live_action(state: State, z: int, action: Action) -> State | None:
    """Replay one non-exhausting border event, returning its canonical state."""

    old_color, old_cap, new_color, new_cap = action
    if not (0 <= old_color < COLORS and 0 <= new_color < COLORS):
        return None
    if old_color == new_color or not (1 <= old_cap < new_cap < HEIGHT):
        return None
    if old_cap not in state[old_color][1]:
        return None
    if not source_is_legal(state, z, old_color, old_cap):
        return None

    debts = [debt for debt, _ in state]
    caps_by_color = [list(caps) for _, caps in state]
    caps_by_color[old_color].remove(old_cap)
    caps_by_color[new_color].append(new_cap)
    debts[old_color] += old_cap
    debts[new_color] -= old_cap
    successor = canonical_state(
        debts,
        (
            (color, cap)
            for color, caps in enumerate(caps_by_color)
            for cap in caps
        ),
    )
    return successor if algebraically_consistent(successor, z) else None


@lru_cache(maxsize=None)
def live_actions_to(state: State, z: int, successor: State) -> tuple[Action, ...]:
    actions: list[Action] = []
    for old_color, (_, caps) in enumerate(state):
        for old_cap in sorted(set(caps)):
            if not source_is_legal(state, z, old_color, old_cap):
                continue
            for new_color in range(COLORS):
                if new_color == old_color:
                    continue
                for new_cap in range(old_cap + 1, HEIGHT):
                    action = (old_color, old_cap, new_color, new_cap)
                    if apply_live_action(state, z, action) == successor:
                        actions.append(action)
    return tuple(actions)


def apply_exhausting_action(
    state: State, z: int, action: ExhaustingAction
) -> State | None:
    """Replay an event that exhausts its original source column."""

    old_color, old_cap, final_color = action
    if not (0 <= old_color < COLORS and 0 <= final_color < COLORS):
        return None
    if old_color == final_color or not (1 <= old_cap < HEIGHT):
        return None
    if old_cap not in state[old_color][1]:
        return None
    if not source_is_legal(state, z, old_color, old_cap):
        return None

    debts = [debt for debt, _ in state]
    caps_by_color = [list(caps) for _, caps in state]
    caps_by_color[old_color].remove(old_cap)
    debts[old_color] += old_cap
    debts[final_color] += HEIGHT - old_cap
    successor = canonical_state(
        debts,
        (
            (color, cap)
            for color, caps in enumerate(caps_by_color)
            for cap in caps
        ),
    )
    return successor if algebraically_consistent(successor, z + 1) else None


@lru_cache(maxsize=None)
def exhausting_actions_to(
    state: State, z: int, successor: State
) -> tuple[ExhaustingAction, ...]:
    actions: list[ExhaustingAction] = []
    for old_color, (_, caps) in enumerate(state):
        for old_cap in sorted(set(caps)):
            if not source_is_legal(state, z, old_color, old_cap):
                continue
            for final_color in range(COLORS):
                if final_color == old_color:
                    continue
                action = (old_color, old_cap, final_color)
                if apply_exhausting_action(state, z, action) == successor:
                    actions.append(action)
    return tuple(actions)


def exhausting_final_color_is_isolated(
    state: State, action: ExhaustingAction
) -> bool:
    """Check the exact Tq exhausting-entry final-color identity."""

    old_color, old_cap, final_color = action
    debts = [debt for debt, _ in state]
    caps_by_color = [list(caps) for _, caps in state]
    caps_by_color[old_color].remove(old_cap)
    debts[old_color] += old_cap
    debts[final_color] += HEIGHT - old_cap
    final_run = HEIGHT - old_cap
    return (
        debts[final_color] == final_run
        and debts[final_color] + sum(caps_by_color[final_color]) == final_run
    )


@lru_cache(maxsize=None)
def reverse_predecessors(terminal: State, z: int) -> tuple[State, ...]:
    """Enumerate every canonical one-step live predecessor of ``terminal``."""

    predecessors: set[State] = set()
    for new_color, (_, new_caps) in enumerate(terminal):
        for new_cap in sorted(set(new_caps)):
            for old_color in range(COLORS):
                if old_color == new_color:
                    continue
                for old_cap in range(1, new_cap):
                    debts = [debt for debt, _ in terminal]
                    caps_by_color = [list(caps) for _, caps in terminal]
                    caps_by_color[new_color].remove(new_cap)
                    caps_by_color[old_color].append(old_cap)
                    debts[old_color] -= old_cap
                    debts[new_color] += old_cap

                    # In predecessor coordinates the entering source-test is
                    # d(P)+s e_old = d(D)+s e_new.
                    entering_test = debts.copy()
                    entering_test[old_color] += old_cap
                    if sum(value > 0 for value in entering_test) > EMPTY_COLUMNS + z:
                        continue

                    predecessor = canonical_state(
                        debts,
                        (
                            (color, cap)
                            for color, caps in enumerate(caps_by_color)
                            for cap in caps
                        ),
                    )
                    if algebraically_consistent(predecessor, z):
                        predecessors.add(predecessor)
    return tuple(sorted(predecessors, key=state_key))


@lru_cache(maxsize=None)
def reverse_exhausting_candidates(terminal: State) -> tuple[State, ...]:
    """Return labeled candidates for the first-exhaustion bridge into Tq.

    The returned canonical predecessor states intentionally retain duplicate
    entries.  Their length is the pre-symmetry candidate count; callers may
    take a set for canonical predecessor or predecessor-terminal counts.
    """

    candidates: list[State] = []
    for old_cap in range(1, HEIGHT):
        for old_color in range(COLORS):
            for final_color in range(COLORS):
                if final_color == old_color:
                    continue
                debts = [debt for debt, _ in terminal]
                caps_by_color = [list(caps) for _, caps in terminal]
                debts[old_color] -= old_cap
                debts[final_color] -= HEIGHT - old_cap
                caps_by_color[old_color].append(old_cap)

                entering_test = debts.copy()
                entering_test[old_color] += old_cap
                if sum(value > 0 for value in entering_test) > EMPTY_COLUMNS:
                    continue

                predecessor = canonical_state(
                    debts,
                    (
                        (color, cap)
                        for color, caps in enumerate(caps_by_color)
                        for cap in caps
                    ),
                )
                if algebraically_consistent(predecessor, z=0):
                    candidates.append(predecessor)
    return tuple(sorted(candidates, key=state_key))


def state_to_json(state: State) -> list[dict[str, object]]:
    return [
        {"debt": debt, "caps": list(caps), "exposed": debt + sum(caps)}
        for debt, caps in state
    ]


def _family_z(family: str) -> int:
    return 1 if family == "tq" else 0


def build_report(max_reverse_depth: int = 1) -> dict[str, object]:
    if max_reverse_depth not in (0, 1):
        raise ValueError("this first reconnaissance supports reverse depth 0 or 1")

    terminals = enumerate_terminals()
    terminal_counts = {family: len(states) for family, states in terminals.items()}
    terminal_counts["total"] = sum(terminal_counts.values())

    terminal_records: list[dict[str, object]] = []
    terminal_ids: dict[tuple[str, State], str] = {}
    for family in ("tq", "d2_3_1", "d2_2_2"):
        for ordinal, state in enumerate(terminals[family]):
            terminal_id = f"{family}-t{ordinal:04d}"
            terminal_ids[(family, state)] = terminal_id
            terminal_records.append(
                {
                    "id": terminal_id,
                    "family": family,
                    "z": _family_z(family),
                    "state": state_to_json(state),
                }
            )

    terminal_verification = {
        "all_algebraically_consistent": all(
            algebraically_consistent(state, _family_z(family))
            for family, states in terminals.items()
            for state in states
        ),
        "all_deadlocked": all(
            is_deadlock(state, _family_z(family))
            for family, states in terminals.items()
            for state in states
        ),
        "all_classified": all(
            classify_terminal(state, _family_z(family)) == family
            for family, states in terminals.items()
            for state in states
        ),
        "families_disjoint": len(
            {(_family_z(family), state) for family, states in terminals.items() for state in states}
        )
        == terminal_counts["total"],
        "expected_counts_match": terminal_counts == EXPECTED_TERMINAL_COUNTS,
    }

    predecessor_records: list[dict[str, object]] = []
    edge_records: list[dict[str, object]] = []
    reverse_summary: dict[str, object] = {
        "depth": max_reverse_depth,
        "canonical_predecessors": 0,
        "canonical_edges": 0,
        "predecessor_states_with_unique_legal_source": 0,
        "predecessor_states_with_sibling_sources": 0,
        "edges_from_unique_legal_source_states": 0,
        "edges_from_states_with_sibling_sources": 0,
        "by_terminal_family": {},
        "all_predecessors_algebraically_consistent": True,
        "all_entry_actions_legal": True,
        "all_edges_replay": True,
        "tq_exhausting_bridge": {
            "labeled_candidates": 0,
            "canonical_predecessors": 0,
            "canonical_edges": 0,
            "predecessor_states_with_unique_legal_source": 0,
            "predecessor_states_with_sibling_sources": 0,
            "all_predecessors_algebraically_consistent": True,
            "all_entry_actions_legal": True,
            "all_edges_replay": True,
            "all_final_colors_isolated": True,
        },
    }

    exhausting_predecessor_records: list[dict[str, object]] = []
    exhausting_edge_records: list[dict[str, object]] = []

    if max_reverse_depth == 1:
        pairs_by_family: dict[str, set[tuple[State, State]]] = defaultdict(set)
        predecessors_by_family: dict[str, set[State]] = defaultdict(set)
        all_predecessors: set[tuple[int, State]] = set()

        for family, states in terminals.items():
            z = _family_z(family)
            for terminal in states:
                for predecessor in reverse_predecessors(terminal, z):
                    pairs_by_family[family].add((predecessor, terminal))
                    predecessors_by_family[family].add(predecessor)
                    all_predecessors.add((z, predecessor))

        predecessor_ids: dict[tuple[int, State], str] = {}
        for ordinal, (z, state) in enumerate(sorted(all_predecessors)):
            predecessor_id = f"z{z}-p{ordinal:05d}"
            predecessor_ids[(z, state)] = predecessor_id
            count = len(legal_sources(state, z))
            predecessor_records.append(
                {
                    "id": predecessor_id,
                    "z": z,
                    "legal_source_count": count,
                    "has_legal_sibling": count >= 2,
                    "state": state_to_json(state),
                }
            )

        for family in ("tq", "d2_3_1", "d2_2_2"):
            z = _family_z(family)
            pairs = sorted(pairs_by_family[family])
            unique_state_count = sum(
                len(legal_sources(state, z)) == 1 for state in predecessors_by_family[family]
            )
            sibling_state_count = sum(
                len(legal_sources(state, z)) >= 2 for state in predecessors_by_family[family]
            )
            unique_edge_count = 0
            sibling_edge_count = 0
            for predecessor, terminal in pairs:
                actions = live_actions_to(predecessor, z, terminal)
                count = len(legal_sources(predecessor, z))
                unique_edge_count += count == 1
                sibling_edge_count += count >= 2
                edge_records.append(
                    {
                        "predecessor_id": predecessor_ids[(z, predecessor)],
                        "terminal_id": terminal_ids[(family, terminal)],
                        "terminal_family": family,
                        "witness_action": list(actions[0]) if actions else None,
                    }
                )
            reverse_summary["by_terminal_family"][family] = {
                "terminal_states": len(terminals[family]),
                "canonical_predecessors": len(predecessors_by_family[family]),
                "canonical_edges": len(pairs),
                "predecessor_states_with_unique_legal_source": unique_state_count,
                "predecessor_states_with_sibling_sources": sibling_state_count,
                "edges_from_unique_legal_source_states": unique_edge_count,
                "edges_from_states_with_sibling_sources": sibling_edge_count,
            }

        all_edge_pairs = [
            (family, predecessor, terminal)
            for family, pairs in pairs_by_family.items()
            for predecessor, terminal in pairs
        ]
        reverse_summary.update(
            {
                "canonical_predecessors": len(all_predecessors),
                "canonical_edges": len(all_edge_pairs),
                "predecessor_states_with_unique_legal_source": sum(
                    len(legal_sources(state, z)) == 1 for z, state in all_predecessors
                ),
                "predecessor_states_with_sibling_sources": sum(
                    len(legal_sources(state, z)) >= 2 for z, state in all_predecessors
                ),
                "edges_from_unique_legal_source_states": sum(
                    len(legal_sources(predecessor, _family_z(family))) == 1
                    for family, predecessor, _ in all_edge_pairs
                ),
                "edges_from_states_with_sibling_sources": sum(
                    len(legal_sources(predecessor, _family_z(family))) >= 2
                    for family, predecessor, _ in all_edge_pairs
                ),
                "all_predecessors_algebraically_consistent": all(
                    algebraically_consistent(state, z) for z, state in all_predecessors
                ),
                "all_entry_actions_legal": all(
                    bool(live_actions_to(predecessor, _family_z(family), terminal))
                    for family, predecessor, terminal in all_edge_pairs
                ),
                "all_edges_replay": all(
                    apply_live_action(
                        predecessor,
                        _family_z(family),
                        live_actions_to(predecessor, _family_z(family), terminal)[0],
                    )
                    == terminal
                    for family, predecessor, terminal in all_edge_pairs
                ),
            }
        )

        tq_bridge_candidates: list[tuple[State, State]] = []
        for terminal in terminals["tq"]:
            tq_bridge_candidates.extend(
                (predecessor, terminal)
                for predecessor in reverse_exhausting_candidates(terminal)
            )
        tq_bridge_pairs = sorted(set(tq_bridge_candidates))
        tq_bridge_predecessors = sorted(
            {predecessor for predecessor, _ in tq_bridge_pairs}, key=state_key
        )
        exhausting_predecessor_ids: dict[State, str] = {}
        for ordinal, predecessor in enumerate(tq_bridge_predecessors):
            predecessor_id = f"exhaust-p{ordinal:04d}"
            exhausting_predecessor_ids[predecessor] = predecessor_id
            count = len(legal_sources(predecessor, z=0))
            exhausting_predecessor_records.append(
                {
                    "id": predecessor_id,
                    "z": 0,
                    "legal_source_count": count,
                    "has_legal_sibling": count >= 2,
                    "state": state_to_json(predecessor),
                }
            )

        bridge_witnesses: list[tuple[State, State, ExhaustingAction | None]] = []
        for predecessor, terminal in tq_bridge_pairs:
            actions = exhausting_actions_to(predecessor, z=0, successor=terminal)
            witness = actions[0] if actions else None
            bridge_witnesses.append((predecessor, terminal, witness))
            exhausting_edge_records.append(
                {
                    "predecessor_id": exhausting_predecessor_ids[predecessor],
                    "terminal_id": terminal_ids[("tq", terminal)],
                    "witness_action": list(witness) if witness else None,
                }
            )

        reverse_summary["tq_exhausting_bridge"] = {
            "labeled_candidates": len(tq_bridge_candidates),
            "canonical_predecessors": len(tq_bridge_predecessors),
            "canonical_edges": len(tq_bridge_pairs),
            "predecessor_states_with_unique_legal_source": sum(
                len(legal_sources(predecessor, z=0)) == 1
                for predecessor in tq_bridge_predecessors
            ),
            "predecessor_states_with_sibling_sources": sum(
                len(legal_sources(predecessor, z=0)) >= 2
                for predecessor in tq_bridge_predecessors
            ),
            "all_predecessors_algebraically_consistent": all(
                algebraically_consistent(predecessor, z=0)
                for predecessor in tq_bridge_predecessors
            ),
            "all_entry_actions_legal": all(witness is not None for _, _, witness in bridge_witnesses),
            "all_edges_replay": all(
                witness is not None
                and apply_exhausting_action(predecessor, z=0, action=witness) == terminal
                for predecessor, terminal, witness in bridge_witnesses
            ),
            "all_final_colors_isolated": all(
                witness is not None
                and exhausting_final_color_is_isolated(predecessor, witness)
                for predecessor, _, witness in bridge_witnesses
            ),
        }

    bridge_summary = reverse_summary["tq_exhausting_bridge"]
    verified = all(terminal_verification.values()) and all(
        bool(reverse_summary[key])
        for key in (
            "all_predecessors_algebraically_consistent",
            "all_entry_actions_legal",
            "all_edges_replay",
        )
    ) and all(
        bool(bridge_summary[key])
        for key in (
            "all_predecessors_algebraically_consistent",
            "all_entry_actions_legal",
            "all_edges_replay",
            "all_final_colors_isolated",
        )
    )
    public_counts = {
        "tq": terminal_counts["tq"],
        "d2_3plus1": terminal_counts["d2_3_1"],
        "d2_2plus2": terminal_counts["d2_2_2"],
        "total": terminal_counts["total"],
    }
    return {
        "schema_version": 1,
        "model": {
            "colors": COLORS,
            "height": HEIGHT,
            "empty_columns": EMPTY_COLUMNS,
            "scope": "numeric macro states only; no layout enumeration",
        },
        "max_reverse_depth": max_reverse_depth,
        "counts": public_counts,
        "terminal_counts": terminal_counts,
        "terminal_verification": terminal_verification,
        "reverse": reverse_summary,
        "verified": verified,
        "terminal_states": terminal_records,
        "predecessor_states": predecessor_records,
        "reverse_edges": edge_records,
        "exhausting_predecessor_states": exhausting_predecessor_records,
        "exhausting_bridge_edges": exhausting_edge_records,
        "caveat": (
            "The reverse layer is an algebraically and physically bounded local cone. "
            "A predecessor need not be globally reachable from an initial Water Sort layout."
        ),
    }


def render_markdown(report: dict[str, object]) -> str:
    counts = report["terminal_counts"]
    reverse = report["reverse"]
    by_family = reverse["by_terminal_family"]
    lines = [
        "# c4 k2 h7 macro reconnaissance",
        "",
        "This bounded run enumerates numerical top-border macro states only; it does not enumerate layouts.",
        "",
        "## Verified terminal census",
        "",
        "| Family | Canonical terminals |",
        "|---|---:|",
        f"| Tq (`z=1`) | {counts['tq']} |",
        f"| D2, top split 3+1 (`z=0`) | {counts['d2_3_1']} |",
        f"| D2, top split 2+2 (`z=0`) | {counts['d2_2_2']} |",
        f"| **Total** | **{counts['total']}** |",
        "",
        "Every retained state satisfies the physical exposed-count and hidden-suffix Hall bounds, has the required debt sum, and has no legal source under the strict positive-coordinate test.",
        "",
        "## One-step live reverse cone",
        "",
    ]
    if report["max_reverse_depth"] == 0:
        lines.append("Reverse enumeration was disabled (`--max-reverse-depth 0`).")
    else:
        lines.extend(
            [
                "| Terminal family | Canonical predecessors | Canonical edges | Unique-source predecessors | Predecessors with a sibling |",
                "|---|---:|---:|---:|---:|",
            ]
        )
        for family, label in (
            ("tq", "Tq"),
            ("d2_3_1", "D2 3+1"),
            ("d2_2_2", "D2 2+2"),
        ):
            row = by_family[family]
            lines.append(
                f"| {label} | {row['canonical_predecessors']} | {row['canonical_edges']} | "
                f"{row['predecessor_states_with_unique_legal_source']} | "
                f"{row['predecessor_states_with_sibling_sources']} |"
            )
        lines.extend(
            [
                "",
                f"Across both `z` levels there are **{reverse['canonical_predecessors']}** canonical predecessor states and **{reverse['canonical_edges']}** canonical predecessor-terminal edges.",
                f"Of the predecessor states, **{reverse['predecessor_states_with_unique_legal_source']}** have one physical legal source and **{reverse['predecessor_states_with_sibling_sources']}** have at least one legal sibling source.",
                "",
                "Each edge uses different old/new colors and `old_cap < new_cap < 7`; its entering action is legal, both endpoints obey the physical F bounds, and the stored witness was replayed forward.",
                "",
                "### First-exhaustion bridge into Tq",
                "",
                f"Separately from the same-`z` live counts, the bridge has **{reverse['tq_exhausting_bridge']['labeled_candidates']}** labeled candidates, **{reverse['tq_exhausting_bridge']['canonical_predecessors']}** canonical predecessors, and **{reverse['tq_exhausting_bridge']['canonical_edges']}** canonical edges.",
                "Every stored bridge witness replays from `z=0` to `z=1`, and its final-run color is isolated in the resulting Tq state.",
            ]
        )
    lines.extend(
        [
            "",
            "## Status",
            "",
            f"Overall verification: **{'PASS' if report['verified'] else 'FAIL'}**.",
            "",
            "> The reverse cone is local: these numerical predecessors are not asserted to be globally reachable from a fixed balanced layout.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, dest="json_path", help="write the JSON report")
    parser.add_argument("--markdown", type=Path, dest="markdown_path", help="write the Markdown summary")
    parser.add_argument(
        "--max-reverse-depth",
        type=int,
        choices=(0, 1),
        default=1,
        help="bounded reverse depth (this first version supports 0 or 1)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(args.max_reverse_depth)
    json_text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    markdown_text = render_markdown(report)

    if args.json_path:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(json_text, encoding="utf-8")
    if args.markdown_path:
        args.markdown_path.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_path.write_text(markdown_text, encoding="utf-8")
    if not args.json_path and not args.markdown_path:
        print(json_text, end="")
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
