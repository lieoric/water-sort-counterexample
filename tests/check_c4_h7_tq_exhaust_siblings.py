#!/usr/bin/env python3
"""Independent audit for the c=4, k=2, h=7 first-exhaustion Tq forks.

The checker deliberately does not import the production executable or the
macro-reconnaissance script.  It reconstructs the numerical border model,
replays every exhausting entrance in the *parent's* labelled coordinates,
enumerates the committed next run of all three surviving q columns, and
counts compatible complete residual words without expanding those words.

``--program`` runs a bounded production differential.  ``--report`` checks
an existing production report, including every replayable sample.
"""

from __future__ import annotations

import argparse
import copy
import itertools
import json
import math
import subprocess
import tempfile
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Iterator, NoReturn, Sequence


HEIGHT = 7
COLORS = 4
EMPTY_COLUMNS = 2
SCOPE = "first_exhaustion_tq_sibling_next_run_forks"

EXPECTED_TERMINALS = 71
EXPECTED_LABELED_CANDIDATES = 624
EXPECTED_PARENTS = 418
EXPECTED_EDGES = 429
EXPECTED_UNIQUE_PARENTS = 6
EXPECTED_SIBLING_PARENTS = 412
EXPECTED_SIBLING_EDGES = 423
EXPECTED_A_NOT_Q_EDGES = 270
EXPECTED_A_EQ_Q_EDGES = 153
EXPECTED_RAW_INDIVIDUAL = 18_177
EXPECTED_RAW_LEGAL_JOINT = 1_220_361
EXPECTED_RAW_ALL_Q = 1_256_148
EXPECTED_NONNEGATIVE = 406_528
EXPECTED_HALL_FEASIBLE = 403_685
EXPECTED_RESIDUAL_WEIGHT = 6_131_033_832
EXPECTED_CLASS_COUNTS = {
    "two_exhaustion": 70_633,
    "live_bad_persistent": 254_899,
    "obstruction": 78_153,
}
EXPECTED_CLASS_WEIGHTS = {
    "two_exhaustion": 8_629_839,
    "live_bad_persistent": 3_235_811_235,
    "obstruction": 2_886_592_758,
}
EXPECTED_REFINED_COUNTS = {
    "direct_certified": 101_922,
    "n_ge_3_certified": 11_226,
    "n_le_2_certified": 223_321,
    "d2_reduction": 67_206,
    "tq_corner_only": 10,
}
EXPECTED_REFINED_WEIGHTS = {
    "direct_certified": 13_128_393,
    "n_ge_3_certified": 10_591_970,
    "n_le_2_certified": 3_223_219_144,
    "d2_reduction": 2_883_858_705,
    "tq_corner_only": 235_620,
}

Bucket = tuple[int, tuple[int, ...]]
State = tuple[Bucket, Bucket, Bucket, Bucket]
ExhaustingAction = tuple[int, int, int]  # old color, old cap, final color
Card = tuple[int, int]  # next color, cumulative endpoint


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def fail(message: str) -> NoReturn:
    raise AssertionError(message)


def canonical_state(
    debts: Sequence[int], columns: Iterable[tuple[int, int]]
) -> State:
    caps_by_color: list[list[int]] = [[] for _ in range(COLORS)]
    for color, cap in columns:
        caps_by_color[color].append(cap)
    result = tuple(
        sorted(
            (int(debts[color]), tuple(sorted(caps_by_color[color])))
            for color in range(COLORS)
        )
    )
    require(len(result) == COLORS, "canonical state lost a color")
    return result  # type: ignore[return-value]


def exposed_counts(state: State) -> tuple[int, int, int, int]:
    return tuple(debt + sum(caps) for debt, caps in state)  # type: ignore[return-value]


def state_is_consistent(state: State, exhausted: int) -> bool:
    if tuple(sorted(state)) != state:
        return False
    if sum(len(caps) for _, caps in state) != COLORS - exhausted:
        return False
    if sum(debt for debt, _ in state) != exhausted * HEIGHT:
        return False
    if any(cap < 1 or cap >= HEIGHT for _, caps in state for cap in caps):
        return False
    exposed = exposed_counts(state)
    multiplicity = tuple(len(caps) for _, caps in state)
    if any(
        not multiplicity[color] <= exposed[color] <= HEIGHT
        for color in range(COLORS)
    ):
        return False
    remaining = tuple(HEIGHT - count for count in exposed)
    return all(
        multiplicity[color]
        <= sum(remaining[other] for other in range(COLORS) if other != color)
        for color in range(COLORS)
    )


def source_is_legal(
    debts_or_state: Sequence[int] | State,
    exhausted: int,
    color: int,
    cap: int,
) -> bool:
    if len(debts_or_state) == COLORS and isinstance(debts_or_state[0], tuple):
        debts = [bucket[0] for bucket in debts_or_state]  # type: ignore[index]
    else:
        debts = [int(value) for value in debts_or_state]  # type: ignore[arg-type]
    debts[color] += cap
    return sum(value > 0 for value in debts) <= EMPTY_COLUMNS + exhausted


def physical_sources(state: State) -> Iterator[tuple[int, int]]:
    for color, (_, caps) in enumerate(state):
        for cap in caps:
            yield color, cap


def legal_sources(state: State, exhausted: int) -> tuple[tuple[int, int], ...]:
    return tuple(
        (color, cap)
        for color, cap in physical_sources(state)
        if source_is_legal(state, exhausted, color, cap)
    )


def enumerate_tq_terminals() -> tuple[State, ...]:
    terminals: set[State] = set()
    for magnitude in range(3):
        for caps in itertools.combinations_with_replacement(range(1, HEIGHT), 3):
            if min(caps) <= magnitude or sum(caps) - magnitude > HEIGHT:
                continue
            for positive in itertools.combinations_with_replacement(
                range(1, HEIGHT + 1), 3
            ):
                if sum(positive) - magnitude != HEIGHT:
                    continue
                state = tuple(
                    sorted(((-magnitude, caps), *((value, ()) for value in positive)))
                )
                if not state_is_consistent(state, 1):  # type: ignore[arg-type]
                    continue
                if legal_sources(state, 1):  # type: ignore[arg-type]
                    continue
                terminals.add(state)  # type: ignore[arg-type]
    return tuple(sorted(terminals))


def apply_exhausting_canonical(
    parent: State, exhausted: int, action: ExhaustingAction
) -> State | None:
    old_color, old_cap, final_color = action
    if old_color == final_color or not 1 <= old_cap < HEIGHT:
        return None
    if not 0 <= old_color < COLORS or not 0 <= final_color < COLORS:
        return None
    if old_cap not in parent[old_color][1]:
        return None
    if not source_is_legal(parent, exhausted, old_color, old_cap):
        return None
    debts = [debt for debt, _ in parent]
    caps = [list(bucket_caps) for _, bucket_caps in parent]
    caps[old_color].remove(old_cap)
    debts[old_color] += old_cap
    debts[final_color] += HEIGHT - old_cap
    successor = canonical_state(
        debts,
        ((color, cap) for color in range(COLORS) for cap in caps[color]),
    )
    return successor if state_is_consistent(successor, exhausted + 1) else None


def exhausting_actions_to(parent: State, terminal: State) -> tuple[ExhaustingAction, ...]:
    actions: list[ExhaustingAction] = []
    for old_color, (_, caps) in enumerate(parent):
        for old_cap in sorted(set(caps)):
            if not source_is_legal(parent, 0, old_color, old_cap):
                continue
            for final_color in range(COLORS):
                action = old_color, old_cap, final_color
                if apply_exhausting_canonical(parent, 0, action) == terminal:
                    actions.append(action)
    return tuple(actions)


def reverse_bridge(
    terminals: Sequence[State],
) -> tuple[int, tuple[tuple[State, State], ...]]:
    labeled: list[tuple[State, State]] = []
    for terminal in terminals:
        for old_cap in range(1, HEIGHT):
            for old_color in range(COLORS):
                for final_color in range(COLORS):
                    if old_color == final_color:
                        continue
                    debts = [debt for debt, _ in terminal]
                    caps = [list(bucket_caps) for _, bucket_caps in terminal]
                    debts[old_color] -= old_cap
                    debts[final_color] -= HEIGHT - old_cap
                    caps[old_color].append(old_cap)
                    if not source_is_legal(debts, 0, old_color, old_cap):
                        continue
                    parent = canonical_state(
                        debts,
                        ((color, cap) for color in range(COLORS) for cap in caps[color]),
                    )
                    if state_is_consistent(parent, 0):
                        labeled.append((parent, terminal))
    return len(labeled), tuple(sorted(set(labeled)))


@dataclass(frozen=True)
class Edge:
    edge_id: str
    parent: State
    terminal: State
    action: ExhaustingAction
    q_color: int
    q_caps: tuple[int, int, int]
    legal_q_indices: tuple[int, ...]

    @property
    def a_equals_q(self) -> bool:
        return self.action[0] == self.q_color


def build_sibling_edges(
    pairs: Sequence[tuple[State, State]],
) -> tuple[Edge, ...]:
    raw: list[tuple[State, State, ExhaustingAction, int, tuple[int, ...]]] = []
    for parent, terminal in pairs:
        if len(legal_sources(parent, 0)) < 2:
            continue
        actions = exhausting_actions_to(parent, terminal)
        require(len(actions) == 1, "bridge edge does not have one canonical action")
        action = actions[0]
        old_color, old_cap, final_color = action

        # Keep this derivation in the parent's coordinates.  Canonicalizing
        # the terminal may permute color indices, so its q-bucket index is not
        # a sound coordinate for replaying the bad action.
        caps_after = [list(caps) for _, caps in parent]
        caps_after[old_color].remove(old_cap)
        q_candidates = [color for color, caps in enumerate(caps_after) if len(caps) == 3]
        require(len(q_candidates) == 1, "cannot identify the three surviving q columns")
        q_color = q_candidates[0]
        q_caps = tuple(sorted(caps_after[q_color]))
        require(len(q_caps) == 3, "wrong surviving q multiplicity")
        legal_q_indices = tuple(
            index
            for index, cap in enumerate(q_caps)
            if source_is_legal(parent, 0, q_color, cap)
        )
        require(legal_q_indices, "sibling parent has no legal q sibling")

        # Isolated-final-color identity, checked before canonicalization.
        replay_debts = [debt for debt, _ in parent]
        replay_caps = [list(caps) for _, caps in parent]
        replay_caps[old_color].remove(old_cap)
        replay_debts[old_color] += old_cap
        replay_debts[final_color] += HEIGHT - old_cap
        require(
            replay_debts[final_color] == HEIGHT - old_cap
            and not replay_caps[final_color],
            "final color is not isolated in parent coordinates",
        )
        raw.append((parent, terminal, action, q_color, q_caps + legal_q_indices))

    edges: list[Edge] = []
    for ordinal, (parent, terminal, action, q_color, packed) in enumerate(raw):
        q_caps = packed[:3]
        legal_indices = packed[3:]
        edges.append(
            Edge(
                f"edge-{ordinal:03d}",
                parent,
                terminal,
                action,
                q_color,
                q_caps,  # type: ignore[arg-type]
                legal_indices,
            )
        )
    return tuple(edges)


def cards(q_color: int, cap: int) -> tuple[Card, ...]:
    # Color-major order is deliberately different from production's expected
    # endpoint-major order; report matching uses semantic keys, not ordinals.
    return tuple(
        (color, endpoint)
        for color in range(COLORS)
        if color != q_color
        for endpoint in range(cap + 1, HEIGHT + 1)
    )


@lru_cache(maxsize=None)
def residual_count(
    remaining: tuple[int, int, int, int], forbidden: tuple[int, ...]
) -> int:
    """Count fillings by explicitly assigning the at-most-three boundary cells."""

    if any(value < 0 for value in remaining):
        return 0
    total = 0
    for chosen in itertools.product(range(COLORS), repeat=len(forbidden)):
        if any(color == blocked for color, blocked in zip(chosen, forbidden)):
            continue
        counts = list(remaining)
        for color in chosen:
            counts[color] -= 1
        if any(value < 0 for value in counts):
            continue
        unrestricted = sum(counts)
        ways = math.factorial(unrestricted)
        for value in counts:
            ways //= math.factorial(value)
        total += ways
    return total


def decoration_balance(
    edge: Edge, chosen_cards: tuple[Card, Card, Card]
) -> tuple[tuple[int, int, int, int], tuple[int, ...], int]:
    old_color, old_cap, final_color = edge.action
    del old_color
    remaining = [HEIGHT - count for count in exposed_counts(edge.parent)]
    remaining[final_color] -= HEIGHT - old_cap
    forbidden: list[int] = []
    for cap, (color, endpoint) in zip(edge.q_caps, chosen_cards):
        remaining[color] -= endpoint - cap
        if endpoint < HEIGHT:
            forbidden.append(color)
    key = tuple(remaining)  # type: ignore[assignment]
    weight = residual_count(key, tuple(forbidden))
    return key, tuple(forbidden), weight


def replay_sibling_in_parent_coordinates(
    edge: Edge, q_index: int, card: Card
) -> tuple[list[int], int]:
    """Apply a sibling event without allowing canonicalization to relabel a/b/q."""

    cap = edge.q_caps[q_index]
    next_color, endpoint = card
    debts = [debt for debt, _ in edge.parent]
    debts[edge.q_color] += cap
    if endpoint == HEIGHT:
        debts[next_color] += HEIGHT - cap
        exhausted = 1
    else:
        debts[next_color] -= cap
        exhausted = 0
    return debts, exhausted


def classify_decoration(edge: Edge, chosen: tuple[Card, Card, Card]) -> str:
    old_color, old_cap, _ = edge.action
    has_live_handoff = False
    for index in edge.legal_q_indices:
        debts, exhausted = replay_sibling_in_parent_coordinates(edge, index, chosen[index])
        if not source_is_legal(debts, exhausted, old_color, old_cap):
            continue
        if exhausted == 1:
            return "two_exhaustion"
        has_live_handoff = True
    return "live_bad_persistent" if has_live_handoff else "obstruction"


def terminal_debts_in_parent_coordinates(edge: Edge) -> list[int]:
    debts = [debt for debt, _ in edge.parent]
    old_color, old_cap, final_color = edge.action
    debts[old_color] += old_cap
    debts[final_color] += HEIGHT - old_cap
    return debts


def is_tq_terminal(state: State) -> bool:
    if not state_is_consistent(state, 1) or legal_sources(state, 1):
        return False
    positive = [index for index, (debt, _) in enumerate(state) if debt > 0]
    nonpositive = [index for index, (debt, _) in enumerate(state) if debt <= 0]
    topped = [index for index, (_, caps) in enumerate(state) if caps]
    return len(positive) == 3 and len(nonpositive) == 1 and topped == nonpositive


def immediate_tq_after_sibling_exhaust(edge: Edge, slot: int, card: Card) -> bool:
    if card[1] != HEIGHT:
        return False
    cap = edge.q_caps[slot]
    debts = [debt for debt, _ in edge.parent]
    caps = [list(values) for _, values in edge.parent]
    caps[edge.q_color].remove(cap)
    debts[edge.q_color] += cap
    debts[card[0]] += HEIGHT - cap
    successor = canonical_state(
        debts,
        ((color, value) for color in range(COLORS) for value in caps[color]),
    )
    return is_tq_terminal(successor)


def is_unique_tq_handoff_corner(
    edge: Edge,
    slot: int,
    chosen: tuple[Card, Card, Card],
) -> bool:
    """Check equation (37) of the reduction note on one fixed decoration."""

    color, endpoint = chosen[slot]
    cap = edge.q_caps[slot]
    if endpoint >= HEIGHT:
        return False
    terminal_debts = terminal_debts_in_parent_coordinates(edge)
    energy = -terminal_debts[edge.q_color]
    p_x = terminal_debts[color]
    other_slots = [index for index in range(3) if index != slot]
    return (
        energy == 0
        and cap == p_x
        and endpoint == 3
        and all(edge.q_caps[index] == 1 for index in other_slots)
        and all(chosen[index] == (color, 3) for index in other_slots)
    )


def refined_classify_decoration(
    edge: Edge,
    chosen: tuple[Card, Card, Card],
) -> str:
    """Apply the proof ledger's strategy precedence to one fixed decoration."""

    has_n_ge_3 = False
    has_n_le_2 = False
    has_d2_reduction = False
    has_tq_corner = False
    terminal_debts = terminal_debts_in_parent_coordinates(edge)
    for slot in edge.legal_q_indices:
        card = chosen[slot]
        cap = edge.q_caps[slot]
        if card[1] == HEIGHT:
            if immediate_tq_after_sibling_exhaust(edge, slot, card):
                # A feasible joint decoration already enforces the shared-f
                # budget (24), so every such terminal is the low-energy corner.
                has_tq_corner = True
            else:
                return "direct_certified"
            continue

        debts_after_live, _ = replay_sibling_in_parent_coordinates(edge, slot, card)
        if source_is_legal(
            debts_after_live, 0, edge.action[0], edge.action[1]
        ):
            successor_debts = terminal_debts.copy()
            successor_debts[edge.q_color] += cap
            successor_debts[card[0]] -= cap
            energy = -min(successor_debts)
            if energy >= 3:
                has_n_ge_3 = True
            elif is_unique_tq_handoff_corner(edge, slot, chosen):
                has_tq_corner = True
            else:
                has_n_le_2 = True
        else:
            has_d2_reduction = True

    if has_n_ge_3:
        return "n_ge_3_certified"
    if has_n_le_2:
        return "n_le_2_certified"
    if has_d2_reduction:
        return "d2_reduction"
    require(has_tq_corner, "refined proof ledger found no applicable branch")
    return "tq_corner_only"


def direct_corner_card_census(edges: Sequence[Edge]) -> dict[str, object]:
    cards_count = 0
    edge_keys: set[tuple[State, State, ExhaustingAction]] = set()
    parents: set[State] = set()
    energy_distribution: Counter[int] = Counter()
    for edge in edges:
        for slot in edge.legal_q_indices:
            cap = edge.q_caps[slot]
            for card in cards(edge.q_color, cap):
                if not immediate_tq_after_sibling_exhaust(edge, slot, card):
                    continue
                # Exact joint fixed-decoration budget (24).
                if cap < HEIGHT - edge.action[1]:
                    continue
                cards_count += 1
                edge_keys.add((edge.parent, edge.terminal, edge.action))
                parents.add(edge.parent)
                terminal_debts = terminal_debts_in_parent_coordinates(edge)
                q_energy = -terminal_debts[edge.q_color]
                energy_distribution[edge.action[1] + q_energy - cap] += 1
    return {
        "physical_cards": cards_count,
        "canonical_edges": len(edge_keys),
        "canonical_parents": len(parents),
        "m_distribution": {str(key): value for key, value in sorted(energy_distribution.items())},
    }


def state_json(state: State) -> list[dict[str, object]]:
    return [
        {"debt": debt, "caps": list(caps), "exposed": debt + sum(caps)}
        for debt, caps in state
    ]


def edge_key_from_json(row: dict[str, object]) -> tuple[State, State, ExhaustingAction]:
    def parse_state(value: object) -> State:
        require(isinstance(value, list) and len(value) == COLORS, "invalid state JSON")
        result: list[Bucket] = []
        for bucket in value:
            require(isinstance(bucket, dict), "state bucket must be an object")
            debt = bucket.get("debt")
            caps = bucket.get("caps")
            require(isinstance(debt, int), "state debt must be an integer")
            require(isinstance(caps, list) and all(isinstance(x, int) for x in caps), "invalid caps")
            result.append((debt, tuple(caps)))
        return tuple(result)  # type: ignore[return-value]

    action = row.get("bad_action", row.get("action"))
    require(
        isinstance(action, list)
        and len(action) == 3
        and all(isinstance(value, int) for value in action),
        "invalid bad action",
    )
    return (
        parse_state(row.get("parent")),
        parse_state(row.get("terminal")),
        tuple(action),  # type: ignore[arg-type]
    )


def known_hall_counterexample_check() -> None:
    """Replay a concrete bridge decoration that is nonnegative but Hall-impossible."""

    parent: State = (
        (-8, (3, 3, 3, 6)),
        (0, ()),
        (1, ()),
        (7, ()),
    )
    terminal: State = (
        (-2, (3, 3, 3)),
        (1, ()),
        (1, ()),
        (7, ()),
    )
    edge = Edge(
        "hall-regression",
        parent,
        terminal,
        (0, 6, 1),
        0,
        (3, 3, 3),
        (0, 1, 2),
    )
    chosen: tuple[Card, Card, Card] = ((1, 4), (2, 5), (2, 7))
    require(
        apply_exhausting_canonical(parent, 0, edge.action) == terminal,
        "Hall regression is not a valid first-exhaustion edge",
    )
    remaining, forbidden, weight = decoration_balance(edge, chosen)
    require(remaining == (0, 5, 0, 0), "Hall regression residual vector drifted")
    require(forbidden == (1, 2), "Hall regression boundary constraints drifted")
    require(all(value >= 0 for value in remaining), "Hall fixture is not nonnegative")
    require(weight == 0, "known in-universe Hall obstruction was accepted")


def independent_census() -> dict[str, object]:
    known_hall_counterexample_check()
    terminals = enumerate_tq_terminals()
    labeled_count, pairs = reverse_bridge(terminals)
    parents = {parent for parent, _ in pairs}
    unique_parents = {parent for parent in parents if len(legal_sources(parent, 0)) == 1}
    sibling_parents = parents - unique_parents
    edges = build_sibling_edges(pairs)

    require(len(terminals) == EXPECTED_TERMINALS, "Tq terminal count mismatch")
    require(labeled_count == EXPECTED_LABELED_CANDIDATES, "labeled bridge count mismatch")
    require(len(parents) == EXPECTED_PARENTS, "canonical bridge parent count mismatch")
    require(len(pairs) == EXPECTED_EDGES, "canonical bridge edge count mismatch")
    require(len(unique_parents) == EXPECTED_UNIQUE_PARENTS, "unique-source parent count mismatch")
    require(len(sibling_parents) == EXPECTED_SIBLING_PARENTS, "sibling-parent count mismatch")
    require(len(edges) == EXPECTED_SIBLING_EDGES, "sibling-edge count mismatch")

    parent_distribution = Counter(len(legal_sources(parent, 0)) for parent in sibling_parents)
    edge_distribution = Counter(len(legal_sources(edge.parent, 0)) for edge in edges)
    require(parent_distribution == {2: 1, 3: 12, 4: 399}, "parent legal-source distribution mismatch")
    require(edge_distribution == {2: 2, 3: 14, 4: 407}, "edge legal-source distribution mismatch")
    require(sum(not edge.a_equals_q for edge in edges) == EXPECTED_A_NOT_Q_EDGES, "a!=q edge split mismatch")
    require(sum(edge.a_equals_q for edge in edges) == EXPECTED_A_EQ_Q_EDGES, "a==q edge split mismatch")

    raw_individual = 0
    raw_legal_joint = 0
    raw_all_q = 0
    nonnegative = 0
    feasible = 0
    residual_weight = 0
    class_counts: Counter[str] = Counter()
    class_weights: Counter[str] = Counter()
    refined_counts: Counter[str] = Counter()
    refined_weights: Counter[str] = Counter()
    type_counts: dict[str, Counter[str]] = {
        "a_equals_q": Counter(),
        "a_not_q": Counter(),
    }
    type_weights: dict[str, Counter[str]] = {
        "a_equals_q": Counter(),
        "a_not_q": Counter(),
    }
    per_edge: list[dict[str, object]] = []

    for edge in edges:
        card_sets = tuple(cards(edge.q_color, cap) for cap in edge.q_caps)
        raw_individual += sum(len(card_sets[index]) for index in edge.legal_q_indices)
        joint = math.prod(len(card_sets[index]) for index in edge.legal_q_indices)
        raw_legal_joint += joint
        edge_raw = math.prod(map(len, card_sets))
        raw_all_q += edge_raw
        row_counts: Counter[str] = Counter()
        row_weights: Counter[str] = Counter()
        row_refined_counts: Counter[str] = Counter()
        row_refined_weights: Counter[str] = Counter()
        row_nonnegative = 0
        row_feasible = 0
        row_weight = 0
        samples: dict[str, dict[str, object]] = {}

        # Iterate the last column fastest, unlike a natural nested production
        # loop over endpoints, to make accidental shared ordering less likely.
        for chosen in itertools.product(*card_sets):
            chosen = tuple(chosen)  # type: ignore[assignment]
            remaining, forbidden, weight = decoration_balance(edge, chosen)  # type: ignore[arg-type]
            if all(value >= 0 for value in remaining):
                nonnegative += 1
                row_nonnegative += 1
            if weight == 0:
                continue
            feasible += 1
            row_feasible += 1
            residual_weight += weight
            row_weight += weight
            classification = classify_decoration(edge, chosen)  # type: ignore[arg-type]
            refined = refined_classify_decoration(edge, chosen)  # type: ignore[arg-type]
            class_counts[classification] += 1
            class_weights[classification] += weight
            refined_counts[refined] += 1
            refined_weights[refined] += weight
            row_counts[classification] += 1
            row_weights[classification] += weight
            row_refined_counts[refined] += 1
            row_refined_weights[refined] += weight
            edge_type = "a_equals_q" if edge.a_equals_q else "a_not_q"
            type_counts[edge_type][classification] += 1
            type_weights[edge_type][classification] += weight
            if classification not in samples:
                samples[classification] = {
                    "cards": [list(card) for card in chosen],
                    "remaining_color_counts": list(remaining),
                    "boundary_forbidden_colors": list(forbidden),
                    "residual_word_weight": weight,
                }

        per_edge.append(
            {
                "edge_id": edge.edge_id,
                "parent": state_json(edge.parent),
                "terminal": state_json(edge.terminal),
                "bad_action": list(edge.action),
                "q_color": edge.q_color,
                "q_caps": list(edge.q_caps),
                "legal_q_indices": list(edge.legal_q_indices),
                "a_equals_q": edge.a_equals_q,
                "legal_source_count": len(legal_sources(edge.parent, 0)),
                "raw_all_q_decorations": edge_raw,
                "nonnegative_decorations": row_nonnegative,
                "hall_feasible_decorations": row_feasible,
                "residual_word_weight": row_weight,
                "classification_counts": dict(row_counts),
                "classification_weights": dict(row_weights),
                "refined_classification_counts": dict(row_refined_counts),
                "refined_classification_weights": dict(row_refined_weights),
                "samples": samples,
            }
        )

    require(raw_individual == EXPECTED_RAW_INDIVIDUAL, "raw individual-card count mismatch")
    require(raw_legal_joint == EXPECTED_RAW_LEGAL_JOINT, "raw legal-joint count mismatch")
    require(raw_all_q == EXPECTED_RAW_ALL_Q, "raw all-q count mismatch")
    require(nonnegative == EXPECTED_NONNEGATIVE, "nonnegative decoration count mismatch")
    require(feasible == EXPECTED_HALL_FEASIBLE, "Hall-feasible decoration count mismatch")
    require(residual_weight == EXPECTED_RESIDUAL_WEIGHT, "residual-word weight mismatch")
    require(dict(class_counts) == EXPECTED_CLASS_COUNTS, f"classification counts mismatch: {class_counts}")
    require(dict(class_weights) == EXPECTED_CLASS_WEIGHTS, f"classification weights mismatch: {class_weights}")
    require(dict(refined_counts) == EXPECTED_REFINED_COUNTS, f"refined counts mismatch: {refined_counts}")
    require(dict(refined_weights) == EXPECTED_REFINED_WEIGHTS, f"refined weights mismatch: {refined_weights}")
    require(sum(class_counts.values()) == feasible, "classification counts do not partition feasible decorations")
    require(sum(class_weights.values()) == residual_weight, "classification weights do not partition residual words")
    require(sum(refined_counts.values()) == feasible, "refined counts do not partition feasible decorations")
    require(sum(refined_weights.values()) == residual_weight, "refined weights do not partition residual words")

    corner_cards = direct_corner_card_census(edges)
    require(
        corner_cards
        == {
            "physical_cards": 12,
            "canonical_edges": 12,
            "canonical_parents": 10,
            "m_distribution": {"0": 8, "1": 4},
        },
        f"direct Tq-corner card census mismatch: {corner_cards}",
    )

    return {
        "schema_version": 1,
        "coverage_scope": SCOPE,
        "terminal_count": len(terminals),
        "labeled_reverse_candidates": labeled_count,
        "canonical_parent_count": len(parents),
        "canonical_edge_count": len(pairs),
        "unique_source_parent_count": len(unique_parents),
        "sibling_parent_count": len(sibling_parents),
        "sibling_edge_count": len(edges),
        "a_not_q_edge_count": sum(not edge.a_equals_q for edge in edges),
        "a_equals_q_edge_count": sum(edge.a_equals_q for edge in edges),
        "parent_legal_source_distribution": {str(k): v for k, v in sorted(parent_distribution.items())},
        "edge_legal_source_distribution": {str(k): v for k, v in sorted(edge_distribution.items())},
        "raw_individual_legal_sibling_cards": raw_individual,
        "raw_joint_legal_sibling_decorations": raw_legal_joint,
        "raw_all_q_next_run_decorations": raw_all_q,
        "nonnegative_decorations": nonnegative,
        "hall_feasible_decorations": feasible,
        "residual_word_weight": residual_weight,
        "classification_counts": dict(class_counts),
        "classification_weights": dict(class_weights),
        "refined_classification_counts": dict(refined_counts),
        "refined_classification_weights": dict(refined_weights),
        "classification_counts_by_edge_type": {
            key: dict(value) for key, value in type_counts.items()
        },
        "classification_weights_by_edge_type": {
            key: dict(value) for key, value in type_weights.items()
        },
        "known_hall_counterexample_checked": True,
        "direct_tq_corner_card_census": corner_cards,
        "per_edge": per_edge,
    }


def partition_stats(
    value: object,
    label: str,
    names: Iterable[str],
) -> tuple[dict[str, int], dict[str, int]]:
    require(isinstance(value, dict), f"{label} must be an object")
    required_names = set(names)
    require(set(value) == required_names, f"{label} has wrong class keys")
    counts: dict[str, int] = {}
    weights: dict[str, int] = {}
    for name, raw in value.items():
        require(isinstance(raw, dict), f"{label}.{name} must be an object")
        require(isinstance(raw.get("decorations"), int), f"{label}.{name}.decorations invalid")
        require(isinstance(raw.get("residual_words"), int), f"{label}.{name}.residual_words invalid")
        counts[name] = int(raw["decorations"])
        weights[name] = int(raw["residual_words"])
    return counts, weights


def class_stats(value: object, label: str) -> tuple[dict[str, int], dict[str, int]]:
    return partition_stats(value, label, EXPECTED_CLASS_COUNTS)


def refined_stats(value: object, label: str) -> tuple[dict[str, int], dict[str, int]]:
    return partition_stats(value, label, EXPECTED_REFINED_COUNTS)


def independent_edges() -> tuple[Edge, ...]:
    _, pairs = reverse_bridge(enumerate_tq_terminals())
    return build_sibling_edges(pairs)


def prefix_census(limit: int) -> dict[str, object]:
    """Independently rescan exactly the documented edge/card prefix."""

    edges = independent_edges()
    rows: dict[tuple[State, State, ExhaustingAction], dict[str, object]] = {}
    for edge in edges:
        rows[(edge.parent, edge.terminal, edge.action)] = {
            "raw_checked": 0,
            "nonnegative": 0,
            "feasible": 0,
            "infeasible": 0,
            "residual_words": 0,
            "counts": Counter(),
            "weights": Counter(),
            "refined_counts": Counter(),
            "refined_weights": Counter(),
        }
    checked = nonnegative = feasible = residual_words = 0
    counts: Counter[str] = Counter()
    weights: Counter[str] = Counter()
    refined_counts: Counter[str] = Counter()
    refined_weights: Counter[str] = Counter()
    prefix_keys: list[
        tuple[tuple[State, State, ExhaustingAction], tuple[Card, Card, Card]]
    ] = []
    stop = False
    for edge in edges:
        row = rows[(edge.parent, edge.terminal, edge.action)]
        card_sets = tuple(cards(edge.q_color, cap) for cap in edge.q_caps)
        for chosen in itertools.product(*card_sets):
            if checked >= limit:
                stop = True
                break
            checked += 1
            prefix_keys.append(
                ((edge.parent, edge.terminal, edge.action), tuple(chosen))  # type: ignore[arg-type]
            )
            row["raw_checked"] = int(row["raw_checked"]) + 1
            remaining, _, weight = decoration_balance(edge, chosen)  # type: ignore[arg-type]
            if all(value >= 0 for value in remaining):
                nonnegative += 1
                row["nonnegative"] = int(row["nonnegative"]) + 1
            if weight == 0:
                row["infeasible"] = int(row["infeasible"]) + 1
                continue
            feasible += 1
            residual_words += weight
            row["feasible"] = int(row["feasible"]) + 1
            row["residual_words"] = int(row["residual_words"]) + weight
            classification = classify_decoration(edge, chosen)  # type: ignore[arg-type]
            refined = refined_classify_decoration(edge, chosen)  # type: ignore[arg-type]
            counts[classification] += 1
            weights[classification] += weight
            refined_counts[refined] += 1
            refined_weights[refined] += weight
            row_counts: Counter[str] = row["counts"]  # type: ignore[assignment]
            row_weights: Counter[str] = row["weights"]  # type: ignore[assignment]
            row_refined_counts: Counter[str] = row["refined_counts"]  # type: ignore[assignment]
            row_refined_weights: Counter[str] = row["refined_weights"]  # type: ignore[assignment]
            row_counts[classification] += 1
            row_weights[classification] += weight
            row_refined_counts[refined] += 1
            row_refined_weights[refined] += weight
        if stop:
            break
    return {
        "checked": checked,
        "nonnegative": nonnegative,
        "feasible": feasible,
        "infeasible": checked - feasible,
        "residual_words": residual_words,
        "counts": dict(counts),
        "weights": dict(weights),
        "refined_counts": dict(refined_counts),
        "refined_weights": dict(refined_weights),
        "rows": rows,
        "prefix_keys": prefix_keys,
    }


def parse_hidden_word(value: object, label: str) -> list[int]:
    if isinstance(value, str):
        require(all(symbol in "0123" for symbol in value), f"{label} contains a bad color")
        return [int(symbol) for symbol in value]
    require(
        isinstance(value, list)
        and all(isinstance(symbol, int) and 0 <= symbol < COLORS for symbol in value),
        f"{label} must be a color word",
    )
    return list(value)


def validate_sample(edge: Edge, sample: dict[str, object]) -> None:
    cards_json = sample.get("cards")
    require(
        isinstance(cards_json, list)
        and len(cards_json) == 3
        and all(
            isinstance(card, list)
            and len(card) == 2
            and all(isinstance(value, int) for value in card)
            for card in cards_json
        ),
        "sample has invalid cards",
    )
    chosen = tuple(tuple(card) for card in cards_json)
    for cap, card in zip(edge.q_caps, chosen):
        require(card in cards(edge.q_color, cap), "sample card is outside the edge universe")
    remaining, _, weight = decoration_balance(edge, chosen)  # type: ignore[arg-type]
    require(weight > 0, "sample decoration is Hall-infeasible")
    classification = classify_decoration(edge, chosen)  # type: ignore[arg-type]
    require(sample.get("classification") == classification, "sample classification does not replay")
    require(sample.get("completion_count") == weight, "sample completion count mismatch")
    if "free_tail_lengths" in sample:
        require(
            sample["free_tail_lengths"]
            == [HEIGHT - endpoint for _, endpoint in chosen],
            "sample free-tail lengths mismatch",
        )
    if "residual_after_forced" in sample:
        require(sample["residual_after_forced"] == list(remaining), "sample residual vector mismatch")

    words_json = sample.get("hidden_words_bottom_to_top")
    require(isinstance(words_json, list) and len(words_json) == 4, "sample must contain four hidden words")
    words = [parse_hidden_word(word, f"sample word {index}") for index, word in enumerate(words_json)]
    old_color, old_cap, final_color = edge.action
    del old_color
    require(words[0] == [final_color] * (HEIGHT - old_cap), "sample bad tail is not the fixed exhausting run")
    for index, (cap, card, word) in enumerate(zip(edge.q_caps, chosen, words[1:])):
        color, endpoint = card
        forced = endpoint - cap
        free = HEIGHT - endpoint
        require(len(word) == HEIGHT - cap, f"sample q{index} has wrong hidden length")
        require(word[free:] == [color] * forced, f"sample q{index} does not realize its card")
        if free:
            require(word[free - 1] != color, f"sample q{index} card endpoint is not exact")
    hidden_counts = Counter(symbol for word in words for symbol in word)
    required = [HEIGHT - count for count in exposed_counts(edge.parent)]
    require([hidden_counts[color] for color in range(COLORS)] == required, "sample is not color-balanced")


def audit_edge_objects(audit: dict[str, object]) -> dict[tuple[State, State, ExhaustingAction], Edge]:
    result: dict[tuple[State, State, ExhaustingAction], Edge] = {}
    for raw in audit["per_edge"]:  # type: ignore[index]
        require(isinstance(raw, dict), "independent per-edge row is invalid")
        key = edge_key_from_json(raw)
        result[key] = Edge(
            str(raw["edge_id"]), key[0], key[1], key[2], int(raw["q_color"]),
            tuple(raw["q_caps"]), tuple(raw["legal_q_indices"]),  # type: ignore[arg-type]
        )
    return result


def enforce_claim_boundary(report: dict[str, object]) -> None:
    require(report.get("full_residual_word_coverage") is False, "next-run report may not claim residual-word coverage")
    require(report.get("entry_family_eliminated") is False, "next-run report may not claim entry elimination")
    require(report.get("full_layout_coverage") is False, "next-run report may not claim full-layout coverage")


def validate_report(
    report: dict[str, object],
    audit: dict[str, object],
    *,
    bounded_limit: int | None = None,
) -> None:
    require(report.get("schema_version") == 1, "unsupported report schema")
    require(report.get("coverage_scope") == SCOPE, "wrong coverage scope")
    require(report.get("limit_unit") == "raw_all_q_next_run_decorations", "wrong limit unit")
    require(report.get("self_checks_passed") is True, "production self-checks failed")
    enforce_claim_boundary(report)

    bridge = report.get("bridge")
    raw = report.get("raw")
    census = report.get("census")
    require(isinstance(bridge, dict) and isinstance(raw, dict) and isinstance(census, dict), "missing nested census objects")
    bridge_expected = {
        "terminal_count": audit["terminal_count"],
        "labeled_candidates": audit["labeled_reverse_candidates"],
        "canonical_parents": audit["canonical_parent_count"],
        "canonical_edges": audit["canonical_edge_count"],
        "unique_source_parents": audit["unique_source_parent_count"],
        "sibling_parents": audit["sibling_parent_count"],
        "unique_source_edges": EXPECTED_EDGES - EXPECTED_SIBLING_EDGES,
        "sibling_edges": audit["sibling_edge_count"],
        "parent_legal_source_distribution": audit["parent_legal_source_distribution"],
        "edge_legal_source_distribution": audit["edge_legal_source_distribution"],
    }
    for key, value in bridge_expected.items():
        require(bridge.get(key) == value, f"production bridge.{key} disagrees with audit")
    for key in ("action_unique", "all_edges_replay", "all_final_colors_isolated"):
        require(bridge.get(key) is True, f"bridge.{key} is not true")
    raw_expected = {
        "legal_sibling_cards": audit["raw_individual_legal_sibling_cards"],
        "legal_sibling_joint_decorations": audit["raw_joint_legal_sibling_decorations"],
        "all_q_joint_decorations": audit["raw_all_q_next_run_decorations"],
    }
    for key, value in raw_expected.items():
        require(raw.get(key) == value, f"production raw.{key} disagrees with audit")

    if bounded_limit is None:
        expected_dynamic: dict[str, object] = {
            "checked": EXPECTED_RAW_ALL_Q,
            "nonnegative": audit["nonnegative_decorations"],
            "feasible": audit["hall_feasible_decorations"],
            "infeasible": EXPECTED_RAW_ALL_Q - EXPECTED_HALL_FEASIBLE,
            "residual_words": audit["residual_word_weight"],
            "counts": audit["classification_counts"],
            "weights": audit["classification_weights"],
            "refined_counts": audit["refined_classification_counts"],
            "refined_weights": audit["refined_classification_weights"],
        }
        expected_rows = {
            edge_key_from_json(row): {
                "raw_checked": row["raw_all_q_decorations"],
                "nonnegative": row["nonnegative_decorations"],
                "feasible": row["hall_feasible_decorations"],
                "infeasible": row["raw_all_q_decorations"] - row["hall_feasible_decorations"],
                "residual_words": row["residual_word_weight"],
                "counts": Counter(row["classification_counts"]),
                "weights": Counter(row["classification_weights"]),
                "refined_counts": Counter(row["refined_classification_counts"]),
                "refined_weights": Counter(row["refined_classification_weights"]),
            }
            for row in audit["per_edge"]  # type: ignore[index]
        }
    else:
        prefix = prefix_census(min(bounded_limit, EXPECTED_RAW_ALL_Q))
        expected_dynamic = prefix
        expected_rows = prefix["rows"]  # type: ignore[assignment]

    require(raw.get("checked") == expected_dynamic["checked"], "bounded/full checked count mismatch")
    require(census.get("nonnegative_decorations") == expected_dynamic["nonnegative"], "nonnegative prefix mismatch")
    require(census.get("feasible_decorations") == expected_dynamic["feasible"], "feasible prefix mismatch")
    require(census.get("infeasible_decorations") == expected_dynamic["infeasible"], "infeasible prefix mismatch")
    require(census.get("residual_words") == expected_dynamic["residual_words"], "residual-weight prefix mismatch")
    actual_counts, actual_weights = class_stats(census.get("legacy"), "census.legacy")
    expected_counts = {name: int(expected_dynamic["counts"].get(name, 0)) for name in EXPECTED_CLASS_COUNTS}  # type: ignore[union-attr]
    expected_weights = {name: int(expected_dynamic["weights"].get(name, 0)) for name in EXPECTED_CLASS_COUNTS}  # type: ignore[union-attr]
    require(actual_counts == expected_counts, "legacy classification prefix mismatch")
    require(actual_weights == expected_weights, "legacy classification-weight prefix mismatch")
    actual_refined_counts, actual_refined_weights = refined_stats(census.get("refined"), "census.refined")
    expected_refined_counts = {
        name: int(expected_dynamic["refined_counts"].get(name, 0))
        for name in EXPECTED_REFINED_COUNTS
    }  # type: ignore[union-attr]
    expected_refined_weights = {
        name: int(expected_dynamic["refined_weights"].get(name, 0))
        for name in EXPECTED_REFINED_COUNTS
    }  # type: ignore[union-attr]
    require(actual_refined_counts == expected_refined_counts, "refined classification prefix mismatch")
    require(actual_refined_weights == expected_refined_weights, "refined weight prefix mismatch")
    if "direct_tq_corner_card_census" in audit:
        independent_corner = audit["direct_tq_corner_card_census"]
        require(isinstance(independent_corner, dict), "independent corner census is invalid")
        require(
            census.get("direct_tq_corner_structure")
            == {
                "cards": independent_corner["physical_cards"],
                "edges": independent_corner["canonical_edges"],
                "parents": independent_corner["canonical_parents"],
                "m_distribution": independent_corner["m_distribution"],
            },
            "direct Tq-corner structure disagrees with independent audit",
        )
    hall = report.get("hall_regression")
    require(
        hall
        == {
            "residual_counts": [0, 5, 0, 0],
            "tail_lengths": [3, 2, 0],
            "forbidden_colors": [1, 2, None],
            "nonnegative": True,
            "feasible": False,
        },
        "Hall regression fixture drifted or was accepted",
    )

    rows = report.get("per_edge")
    require(isinstance(rows, list) and len(rows) == EXPECTED_SIBLING_EDGES, "per_edge must cover 423 edges")
    edges = audit_edge_objects(audit)
    actual_keys: set[tuple[State, State, ExhaustingAction]] = set()
    rows_by_id: dict[str, tuple[State, State, ExhaustingAction]] = {}
    sample_refs: dict[str, tuple[State, State, ExhaustingAction]] = {}
    audit_rows = {edge_key_from_json(row): row for row in audit["per_edge"]}  # type: ignore[index]
    for raw_row in rows:
        require(isinstance(raw_row, dict), "per_edge row must be an object")
        key = edge_key_from_json(raw_row)
        require(key in edges and key not in actual_keys, "unknown or duplicate per_edge row")
        actual_keys.add(key)
        expected_static = audit_rows[key]
        require(raw_row.get("q_color") == expected_static["q_color"], "per-edge q_color mismatch")
        require(raw_row.get("q_caps") == expected_static["q_caps"], "per-edge q_caps mismatch")
        require(raw_row.get("old_bad_equals_q") == expected_static["a_equals_q"], "per-edge a==q flag mismatch")
        require(raw_row.get("legal_source_count") == expected_static["legal_source_count"], "per-edge legal count mismatch")
        require(raw_row.get("raw_expected") == expected_static["raw_all_q_decorations"], "per-edge raw universe mismatch")
        expected = expected_rows[key]
        for field in ("raw_checked", "nonnegative", "feasible", "infeasible", "residual_words"):
            if field == "nonnegative" and field not in raw_row:
                continue
            require(raw_row.get(field) == expected[field], f"per-edge {field} prefix mismatch")
        counts, weights = class_stats(raw_row.get("legacy"), "per-edge legacy")
        require(counts == {name: int(expected["counts"].get(name, 0)) for name in EXPECTED_CLASS_COUNTS}, "per-edge class counts mismatch")  # type: ignore[union-attr]
        require(weights == {name: int(expected["weights"].get(name, 0)) for name in EXPECTED_CLASS_COUNTS}, "per-edge class weights mismatch")  # type: ignore[union-attr]
        row_refined_counts, row_refined_weights = refined_stats(
            raw_row.get("refined"), "per-edge refined"
        )
        require(
            row_refined_counts
            == {
                name: int(expected["refined_counts"].get(name, 0))
                for name in EXPECTED_REFINED_COUNTS
            },
            "per-edge refined counts mismatch",
        )  # type: ignore[union-attr]
        require(
            row_refined_weights
            == {
                name: int(expected["refined_weights"].get(name, 0))
                for name in EXPECTED_REFINED_COUNTS
            },
            "per-edge refined weights mismatch",
        )  # type: ignore[union-attr]
        edge_id = raw_row.get("edge_id")
        require(isinstance(edge_id, str) and edge_id not in rows_by_id, "bad or duplicate edge_id")
        rows_by_id[edge_id] = key
        sample_id = raw_row.get("sample_id")
        if sample_id is not None:
            require(isinstance(sample_id, str) and sample_id not in sample_refs, "bad or duplicate sample reference")
            sample_refs[sample_id] = key
    require(actual_keys == set(edges), "per_edge coverage is incomplete")

    checked_prefix = report.get("checked_prefix")
    require(isinstance(checked_prefix, list), "checked_prefix must be an array")
    if bounded_limit is None:
        require(not checked_prefix, "an unbounded report should not serialize a redundant full prefix")
    else:
        expected_prefix = expected_dynamic["prefix_keys"]
        require(len(checked_prefix) == len(expected_prefix), "checked_prefix length mismatch")  # type: ignore[arg-type]
        for index, (actual, expected) in enumerate(zip(checked_prefix, expected_prefix)):  # type: ignore[arg-type]
            require(isinstance(actual, dict), f"checked_prefix[{index}] must be an object")
            edge_id = actual.get("edge_id")
            cards_json = actual.get("cards")
            require(isinstance(edge_id, str) and edge_id in rows_by_id, "checked prefix names an unknown edge")
            require(rows_by_id[edge_id] == expected[0], f"checked_prefix[{index}] edge mismatch")
            require(
                isinstance(cards_json, list)
                and tuple(tuple(card) for card in cards_json) == expected[1],
                f"checked_prefix[{index}] card mismatch",
            )

    samples = report.get("replay_samples")
    require(isinstance(samples, list), "replay_samples must be an array")
    seen_samples: set[str] = set()
    for raw_sample in samples:
        require(isinstance(raw_sample, dict), "sample must be an object")
        sample_id = raw_sample.get("sample_id")
        edge_id = raw_sample.get("edge_id")
        require(isinstance(sample_id, str) and sample_id not in seen_samples, "bad or duplicate sample_id")
        require(isinstance(edge_id, str) and edge_id in rows_by_id, "sample names an unknown edge")
        key = rows_by_id[edge_id]
        require(sample_refs.get(sample_id) == key, "sample is not referenced by its edge")
        require(raw_sample.get("bad_action") == list(key[2]), "sample bad action mismatch")
        require(raw_sample.get("q_color") == edges[key].q_color, "sample q color mismatch")
        require(raw_sample.get("q_caps") == list(edges[key].q_caps), "sample q caps mismatch")
        validate_sample(edges[key], raw_sample)
        seen_samples.add(sample_id)
    require(seen_samples == set(sample_refs), "sample references and sample array disagree")

    if bounded_limit is None:
        require(report.get("status") == "NEXT_RUN_CENSUS_COMPLETE", "full report has wrong status")
        require(report.get("verified") is True, "full report must be verified")
        require(report.get("next_run_universe_complete") is True, "full report lacks universe-complete flag")
    else:
        require(report.get("status") == "INCOMPLETE", "bounded report has wrong status")
        require(report.get("verified") is False, "bounded report may not be verified")
        require(report.get("next_run_universe_complete") is False, "bounded report claims a complete universe")


def read_report(path: Path) -> dict[str, object]:
    require(path.is_file(), f"missing production report: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), "report root must be an object")
    return value


def run_program(program: Path, audit: dict[str, object], limit: int) -> None:
    with tempfile.TemporaryDirectory(prefix="c4-h7-tq-exhaust-audit-") as raw_dir:
        output_dir = Path(raw_dir)
        subprocess.run(
            [str(program), "--output-dir", str(output_dir), "--limit", str(limit)],
            check=True,
        )
        report = read_report(output_dir / "report.json")
        bounded = limit if report.get("status") == "INCOMPLETE" else None
        validate_report(report, audit, bounded_limit=bounded)
        require((output_dir / "summary.md").is_file(), "production did not write summary.md")


def schema_negative_tests(audit: dict[str, object]) -> None:
    # Target each forbidden overclaim independently.  Full schema mutation is
    # additionally exercised by the artifact validator in CI.
    for key in ("full_residual_word_coverage", "entry_family_eliminated", "full_layout_coverage"):
        skeleton = {
            "full_residual_word_coverage": False,
            "entry_family_eliminated": False,
            "full_layout_coverage": False,
        }
        skeleton[key] = True
        try:
            enforce_claim_boundary(skeleton)
        except AssertionError:
            pass
        else:
            fail(f"claim-boundary checker accepted {key}=true")
    require(len(audit["per_edge"]) == EXPECTED_SIBLING_EDGES, "negative per-edge fixture has wrong base")  # type: ignore[arg-type]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--program", type=Path, help="bounded production executable")
    parser.add_argument("--report", type=Path, help="validate an existing report.json")
    parser.add_argument(
        "--audit",
        type=Path,
        help="reuse a previously generated independent census (bounded development only)",
    )
    parser.add_argument("--limit", type=int, default=257, help="bounded differential size")
    parser.add_argument("--json", type=Path, dest="json_path", help="write the independent census")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    require(args.limit > 0, "--limit must be positive")
    if args.audit:
        audit = read_report(args.audit)
        require(
            (args.program is None) != (args.report is None),
            "--audit reuse requires exactly one bounded --program or --report check",
        )
    else:
        audit = independent_census()
    schema_negative_tests(audit)
    if args.program:
        require(args.program.is_file(), f"program not found: {args.program}")
        run_program(args.program.resolve(), audit, args.limit)
    if args.report:
        production_report = read_report(args.report)
        bounded = args.limit if production_report.get("status") == "INCOMPLETE" else None
        validate_report(production_report, audit, bounded_limit=bounded)
    output = json.dumps(audit, indent=2, sort_keys=True) + "\n"
    if args.json_path:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(output, encoding="utf-8")
    else:
        print(
            "PASS: "
            f"Tq={audit['terminal_count']}, bridge={audit['labeled_reverse_candidates']}/"
            f"{audit['canonical_parent_count']}/{audit['canonical_edge_count']}, "
            f"sibling={audit['sibling_parent_count']}/{audit['sibling_edge_count']}, "
            f"decorations={audit['raw_all_q_next_run_decorations']}, "
            f"feasible={audit['hall_feasible_decorations']}, "
            f"residual-weight={audit['residual_word_weight']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
