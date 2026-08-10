#!/usr/bin/env python3
"""Independent fixed-word audit for the h=7 first-exhaustion Tq corner.

This file intentionally imports neither a production executable nor the
first-exhaustion reconnaissance checker.  It rebuilds the border-state
universe, derives the ten low-energy decorations from equation (37), expands
their 235,620 labelled residual words, and solves each fixed run-chain game
by an independent memoized checkpoint recursion.

``--program`` executes a bounded production differential.  ``--report``
strictly compares a production report with the independently rebuilt prefix.
A run without either option writes (or prints) the independent audit itself.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
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
SCOPE = "c4_h7_first_exhaustion_tq_low_energy_corners"

EXPECTED_TERMINALS = 71
EXPECTED_LABELED_CANDIDATES = 624
EXPECTED_PARENTS = 418
EXPECTED_EDGES = 429
EXPECTED_SIBLING_EDGES = 423
EXPECTED_DECORATIONS = 10
EXPECTED_DECORATION_EDGES = 9
EXPECTED_RESIDUAL_WORDS = 235_620
EXPECTED_PER_DECORATION_WEIGHTS = (
    13_860,
    27_720,
    34_650,
    27_720,
    13_860,
    13_860,
    27_720,
    34_650,
    27_720,
    13_860,
)

Bucket = tuple[int, tuple[int, ...]]
State = tuple[Bucket, Bucket, Bucket, Bucket]
ExhaustingAction = tuple[int, int, int]
Card = tuple[int, int]
Run = tuple[int, int]
LiveColumn = tuple[int, int, tuple[Run, ...]]
Columns = tuple[
    LiveColumn | None,
    LiveColumn | None,
    LiveColumn | None,
    LiveColumn | None,
]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def fail(message: str) -> NoReturn:
    raise AssertionError(message)


def canonical_state(debts: Sequence[int], columns: Iterable[tuple[int, int]]) -> State:
    caps_by_color: list[list[int]] = [[] for _ in range(COLORS)]
    for color, cap in columns:
        caps_by_color[color].append(cap)
    state = tuple(
        sorted(
            (int(debts[color]), tuple(sorted(caps_by_color[color])))
            for color in range(COLORS)
        )
    )
    require(len(state) == COLORS, "canonical state lost a color")
    return state  # type: ignore[return-value]


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
    for energy in range(3):
        for caps in itertools.combinations_with_replacement(range(1, HEIGHT), 3):
            if min(caps) <= energy or sum(caps) - energy > HEIGHT:
                continue
            for positive in itertools.combinations_with_replacement(
                range(1, HEIGHT + 1), 3
            ):
                if sum(positive) - energy != HEIGHT:
                    continue
                state = tuple(
                    sorted(((-energy, caps), *((value, ()) for value in positive)))
                )
                if not state_is_consistent(state, 1):  # type: ignore[arg-type]
                    continue
                if legal_sources(state, 1):  # type: ignore[arg-type]
                    continue
                terminals.add(state)  # type: ignore[arg-type]
    return tuple(sorted(terminals))


def apply_exhausting(
    parent: State, exhausted: int, action: ExhaustingAction
) -> State | None:
    old_color, old_cap, final_color = action
    if old_color == final_color or old_cap not in range(1, HEIGHT):
        return None
    if old_cap not in parent[old_color][1]:
        return None
    if not source_is_legal(parent, exhausted, old_color, old_cap):
        return None
    debts = [debt for debt, _ in parent]
    caps = [list(values) for _, values in parent]
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
                if apply_exhausting(parent, 0, action) == terminal:
                    actions.append(action)
    return tuple(actions)


def reverse_bridge(
    terminals: Sequence[State],
) -> tuple[int, tuple[tuple[State, State], ...]]:
    labelled: list[tuple[State, State]] = []
    for terminal in terminals:
        for old_cap in range(1, HEIGHT):
            for old_color in range(COLORS):
                for final_color in range(COLORS):
                    if old_color == final_color:
                        continue
                    debts = [debt for debt, _ in terminal]
                    caps = [list(values) for _, values in terminal]
                    debts[old_color] -= old_cap
                    debts[final_color] -= HEIGHT - old_cap
                    caps[old_color].append(old_cap)
                    if not source_is_legal(debts, 0, old_color, old_cap):
                        continue
                    parent = canonical_state(
                        debts,
                        (
                            (color, cap)
                            for color in range(COLORS)
                            for cap in caps[color]
                        ),
                    )
                    if state_is_consistent(parent, 0):
                        labelled.append((parent, terminal))
    return len(labelled), tuple(sorted(set(labelled)))


@dataclass(frozen=True)
class Edge:
    parent: State
    terminal: State
    action: ExhaustingAction
    q_color: int
    q_caps: tuple[int, int, int]
    legal_q_indices: tuple[int, ...]

    @property
    def semantic_key(self) -> tuple[State, State, ExhaustingAction, int]:
        return self.parent, self.terminal, self.action, self.q_color


def build_sibling_edges(pairs: Sequence[tuple[State, State]]) -> tuple[Edge, ...]:
    edges: list[Edge] = []
    for parent, terminal in pairs:
        if len(legal_sources(parent, 0)) < 2:
            continue
        actions = exhausting_actions_to(parent, terminal)
        require(len(actions) == 1, "bridge edge has an ambiguous bad action")
        action = actions[0]
        old_color, old_cap, final_color = action
        caps_after = [list(values) for _, values in parent]
        caps_after[old_color].remove(old_cap)
        candidates = [color for color, caps in enumerate(caps_after) if len(caps) == 3]
        require(len(candidates) == 1, "cannot identify the three q columns")
        q_color = candidates[0]
        q_caps = tuple(sorted(caps_after[q_color]))
        legal_indices = tuple(
            index
            for index, cap in enumerate(q_caps)
            if source_is_legal(parent, 0, q_color, cap)
        )
        require(legal_indices, "sibling edge has no legal q source")

        # Recheck the isolated final-color identity without canonical relabeling.
        debts = [debt for debt, _ in parent]
        debts[old_color] += old_cap
        debts[final_color] += HEIGHT - old_cap
        require(
            debts[final_color] == HEIGHT - old_cap
            and not caps_after[final_color],
            "bad final color is not isolated",
        )
        edges.append(
            Edge(
                parent,
                terminal,
                action,
                q_color,
                q_caps,  # type: ignore[arg-type]
                legal_indices,
            )
        )
    return tuple(edges)


def terminal_debts_in_parent_coordinates(edge: Edge) -> tuple[int, int, int, int]:
    debts = [debt for debt, _ in edge.parent]
    old_color, old_cap, final_color = edge.action
    debts[old_color] += old_cap
    debts[final_color] += HEIGHT - old_cap
    return tuple(debts)  # type: ignore[return-value]


@dataclass(frozen=True)
class Corner:
    edge: Edge
    anchor_color: int
    remaining: tuple[int, int, int, int]

    @property
    def cards(self) -> tuple[Card, Card, Card]:
        return ((self.anchor_color, 3),) * 3

    @property
    def semantic_key(self) -> tuple[object, ...]:
        return (*self.edge.semantic_key, self.anchor_color)


def count_tail_words(remaining: tuple[int, int, int, int], blocked: int) -> int:
    """Count three labelled length-four tails by a direct cell recursion."""

    forbidden = (blocked, None, None, None) * 3

    @lru_cache(maxsize=None)
    def visit(position: int, counts: tuple[int, int, int, int]) -> int:
        if position == len(forbidden):
            return int(not any(counts))
        total = 0
        for color, count in enumerate(counts):
            if count == 0 or color == forbidden[position]:
                continue
            child = list(counts)
            child[color] -= 1
            total += visit(position + 1, tuple(child))  # type: ignore[arg-type]
        return total

    return visit(0, remaining)


def derive_corners(edges: Sequence[Edge]) -> tuple[Corner, ...]:
    """Derive equation (37), including the fixed color budget, from scratch."""

    corners: list[Corner] = []
    for edge in edges:
        terminal_debts = terminal_debts_in_parent_coordinates(edge)
        if edge.q_caps != (1, 1, 1):
            continue
        if terminal_debts[edge.q_color] != 0:
            continue
        if edge.legal_q_indices != (0, 1, 2):
            continue
        for anchor in range(COLORS):
            if anchor == edge.q_color or terminal_debts[anchor] != 1:
                continue
            remaining = [HEIGHT - count for count in exposed_counts(edge.parent)]
            old_color, old_cap, final_color = edge.action
            del old_color
            remaining[final_color] -= HEIGHT - old_cap
            remaining[anchor] -= 3 * (3 - 1)
            if any(value < 0 for value in remaining) or sum(remaining) != 12:
                continue
            remaining_tuple = tuple(remaining)  # type: ignore[assignment]
            if count_tail_words(remaining_tuple, anchor) == 0:
                continue

            # Independent replay of the low handoff identities E=N=0.
            after_live = [debt for debt, _ in edge.parent]
            after_live[edge.q_color] += 1
            after_live[anchor] -= 1
            if not source_is_legal(
                after_live, 0, edge.action[0], edge.action[1]
            ):
                continue
            if anchor == final_color:
                continue
            corners.append(Corner(edge, anchor, remaining_tuple))

    corners.sort(key=lambda corner: corner.semantic_key)
    require(len(corners) == EXPECTED_DECORATIONS, "corner-decoration count mismatch")
    require(
        len({corner.edge.semantic_key for corner in corners})
        == EXPECTED_DECORATION_EDGES,
        "corner-edge count mismatch",
    )
    weights = tuple(
        count_tail_words(corner.remaining, corner.anchor_color)
        for corner in corners
    )
    require(weights == EXPECTED_PER_DECORATION_WEIGHTS, f"corner weights drifted: {weights}")
    require(sum(weights) == EXPECTED_RESIDUAL_WORDS, "corner word total mismatch")
    return tuple(corners)


def tail_words(corner: Corner) -> Iterator[tuple[tuple[int, ...], ...]]:
    """Yield the three top-to-bottom residual tails in lexicographic order."""

    forbidden = (corner.anchor_color, None, None, None) * 3
    cells = [-1] * 12

    def visit(
        position: int, counts: tuple[int, int, int, int]
    ) -> Iterator[tuple[int, ...]]:
        if position == len(cells):
            if not any(counts):
                yield tuple(cells)
            return
        for color, count in enumerate(counts):
            if count == 0 or color == forbidden[position]:
                continue
            child = list(counts)
            child[color] -= 1
            cells[position] = color
            yield from visit(position + 1, tuple(child))  # type: ignore[arg-type]

    for flat in visit(0, corner.remaining):
        yield flat[0:4], flat[4:8], flat[8:12]


def runs(cells_top_to_bottom: Iterable[int]) -> tuple[Run, ...]:
    result: list[Run] = []
    for color in cells_top_to_bottom:
        if result and result[-1][0] == color:
            result[-1] = color, result[-1][1] + 1
        else:
            result.append((color, 1))
    return tuple(result)


def parent_checkpoint_game(corner: Corner, tails: tuple[tuple[int, ...], ...]) -> tuple[
    tuple[int, int, int, int], Columns
]:
    edge = corner.edge
    old_color, old_cap, final_color = edge.action
    columns: list[LiveColumn] = [
        (old_color, old_cap, ((final_color, HEIGHT - old_cap),))
    ]
    for tail in tails:
        require(len(tail) == 4 and tail[0] != corner.anchor_color, "bad residual tail")
        future = (corner.anchor_color, corner.anchor_color, *tail)
        columns.append((edge.q_color, 1, runs(future)))
    require(len(columns) == 4, "initial game lost a column")
    return (
        tuple(debt for debt, _ in edge.parent),  # type: ignore[return-value]
        tuple(columns),  # type: ignore[return-value]
    )


def water_initial_game(corner: Corner, tails: tuple[tuple[int, ...], ...]) -> tuple[
    tuple[int, int, int, int], Columns
]:
    """Restore the zero-debt water-sort layout before the edge-parent prefix.

    In every equation-(37) corner the reported bridge parent P was reached by
    one live event b_r -> a_s on the bad column.  Its debt vector therefore
    has d_a=-r and d_b=+r.  Treating P as the initial layout is unsound; this
    function restores b^r a^(s-r) before the fixed final f^(7-s) run.
    """

    edge = corner.edge
    old_color, old_cap, final_color = edge.action
    debts_at_parent = tuple(debt for debt, _ in edge.parent)
    prefix_cap = -debts_at_parent[old_color]
    require(0 < prefix_cap < old_cap, "bad-column live prefix has invalid length")
    previous = [
        color
        for color, debt in enumerate(debts_at_parent)
        if color != old_color and debt == prefix_cap
    ]
    require(len(previous) == 1, "bad-column live prefix color is ambiguous")
    previous_color = previous[0]
    require(
        all(
            debt == 0
            for color, debt in enumerate(debts_at_parent)
            if color not in (old_color, previous_color)
        ),
        "corner parent needs more than one historical live event",
    )
    columns: list[LiveColumn] = [
        (
            previous_color,
            prefix_cap,
            (
                (old_color, old_cap - prefix_cap),
                (final_color, HEIGHT - old_cap),
            ),
        )
    ]
    for tail in tails:
        future = (corner.anchor_color, corner.anchor_color, *tail)
        columns.append((edge.q_color, 1, runs(future)))
    initial: tuple[tuple[int, int, int, int], Columns] = (
        (0, 0, 0, 0),
        tuple(columns),  # type: ignore[arg-type]
    )

    physical = Counter({previous_color: prefix_cap, edge.q_color: 3})
    physical[old_color] += old_cap - prefix_cap
    physical[final_color] += HEIGHT - old_cap
    for tail in tails:
        physical[corner.anchor_color] += 2
        physical.update(tail)
    require(
        all(physical[color] == HEIGHT for color in range(COLORS)),
        "restored zero-debt water layout is not exactly color-balanced",
    )

    # Mechanically prove that the restored first border event reaches P.
    reached = step(initial[0], 0, initial[1], 0)
    require(reached is not None, "restored bad-prefix event is illegal")
    reached_debts, reached_z, reached_columns = reached
    parent_debts, parent_columns = parent_checkpoint_game(corner, tails)
    require(
        reached_z == 0
        and reached_debts == parent_debts
        and reached_columns == parent_columns,
        "restored water initial layout does not reach bridge parent P",
    )
    return initial


@lru_cache(maxsize=None)
def solve(
    debts: tuple[int, int, int, int],
    exhausted: int,
    columns: Columns,
) -> bool:
    """Existential exact recursion on one fixed set of future run chains."""

    if exhausted >= EMPTY_COLUMNS or sum(column is None for column in columns) >= EMPTY_COLUMNS:
        return True
    for source, column in enumerate(columns):
        if column is None:
            continue
        top, cap, future = column
        if not source_is_legal(debts, exhausted, top, cap):
            continue
        require(future, "active fixed-chain column has no future")
        next_color, run_length = future[0]
        require(next_color != top and run_length > 0, "fixed chain has a merged boundary")
        child_debts = list(debts)
        child_debts[top] += cap
        child_columns = list(columns)
        child_exhausted = exhausted
        if len(future) == 1:
            require(cap + run_length == HEIGHT, "final run misses the column bottom")
            child_debts[next_color] += run_length
            child_columns[source] = None
            child_exhausted += 1
        else:
            require(cap + run_length < HEIGHT, "nonfinal run exhausts a column")
            child_debts[next_color] -= cap
            child_columns[source] = (next_color, cap + run_length, future[1:])
        if solve(
            tuple(child_debts),  # type: ignore[arg-type]
            child_exhausted,
            tuple(child_columns),  # type: ignore[arg-type]
        ):
            return True
    return False


def step(
    debts: tuple[int, int, int, int],
    exhausted: int,
    columns: Columns,
    source: int,
) -> tuple[tuple[int, int, int, int], int, Columns] | None:
    if source not in range(4) or columns[source] is None:
        return None
    column = columns[source]
    require(column is not None, "selected source vanished")
    top, cap, future = column
    if not source_is_legal(debts, exhausted, top, cap):
        return None
    next_color, run_length = future[0]
    child_debts = list(debts)
    child_debts[top] += cap
    child_columns = list(columns)
    if len(future) == 1:
        child_debts[next_color] += run_length
        child_columns[source] = None
        exhausted += 1
    else:
        child_debts[next_color] -= cap
        child_columns[source] = (next_color, cap + run_length, future[1:])
    return (
        tuple(child_debts),  # type: ignore[return-value]
        exhausted,
        tuple(child_columns),  # type: ignore[return-value]
    )


def safe_first_mask(
    debts: tuple[int, int, int, int], exhausted: int, columns: Columns
) -> int:
    mask = 0
    for source in range(4):
        child = step(debts, exhausted, columns, source)
        if child is not None and solve(*child):
            mask |= 1 << source
    return mask


def winning_path(
    debts: tuple[int, int, int, int], exhausted: int, columns: Columns
) -> tuple[int, ...] | None:
    if exhausted >= EMPTY_COLUMNS:
        return ()
    for source in range(4):
        child = step(debts, exhausted, columns, source)
        if child is None or not solve(*child):
            continue
        suffix = winning_path(*child)
        require(suffix is not None, "winning child has no path witness")
        return (source,) + suffix
    return None


def all_anchor_checkpoint(
    debts: tuple[int, int, int, int], exhausted: int, columns: Columns
) -> tuple[tuple[int, int, int, int], int, Columns]:
    """Replay the proof corridor that sends all three q columns to x_3."""

    for source in (1, 2, 3):
        child = step(debts, exhausted, columns, source)
        require(child is not None, "equation-(37) all-anchor prefix became illegal")
        debts, exhausted, columns = child
    return debts, exhausted, columns


def audit_126_checkpoint_kernel(corners: Sequence[Corner]) -> dict[str, int]:
    """Mechanically replay the predicted 126-word local-NO kernel and escape.

    The local checkpoint is reached after q1->a3 on all three siblings.  It
    is genuinely NO.  From the original parent, however, the fixed uniform
    escape continues each sibling once more to f4, then exhausts two f
    columns.  This function checks every one of the 9!/(4!5!) labelled tails,
    including legality of every event; it does not infer parent-YES merely
    from the general solver.
    """

    candidates = [
        corner
        for corner in corners
        if corner.anchor_color == corner.edge.action[0]
        and corner.edge.action[1] == 3
    ]
    require(len(candidates) == 1, "126-word kernel does not have one decoration")
    corner = candidates[0]
    final_color = corner.edge.action[2]
    residual_color = next(
        color
        for color in range(COLORS)
        if color
        not in (
            corner.anchor_color,
            corner.edge.q_color,
            final_color,
        )
    )
    kernel = checkpoint_no = escaped = 0
    for tails in tail_words(corner):
        if not all(tail[0] == final_color for tail in tails):
            continue
        require(
            Counter(color for tail in tails for color in tail[1:])
            == Counter({corner.edge.q_color: 4, residual_color: 5}),
            "126-word kernel does not have q^4 b^5 below the f boundary",
        )
        kernel += 1
        solve.cache_clear()
        parent = parent_checkpoint_game(corner, tails)
        require(not solve(parent[0], 0, parent[1]), "predicted kernel contains a parent-checkpoint YES")
        checkpoint_no += 1

        # Start from the true zero-debt layout, not P.  Do not expose the bad
        # b2->a3 prefix.  Send q1->a3->f4 on each sibling instead.
        debts, columns = water_initial_game(corner, tails)
        exhausted = 0
        for source in (1, 2, 3):
            child = step(debts, exhausted, columns, source)
            require(child is not None, "uniform escape q1->a3 is illegal")
            debts, exhausted, columns = child
            child = step(debts, exhausted, columns, source)
            require(child is not None, "uniform escape a3->f4 is illegal")
            debts, exhausted, columns = child

        # The tails can temporarily block a single fixed f column.  Extract an
        # actual legal switching/rotor continuation from this common state and
        # replay every event, instead of assuming one column can be followed
        # monotonically to the bottom.
        continuation = winning_path(debts, exhausted, columns)
        require(continuation is not None, "uniform prefix has no legal rotor continuation")
        for source in continuation:
            child = step(debts, exhausted, columns, source)
            require(child is not None, "extracted rotor continuation is not replayable")
            debts, exhausted, columns = child
        require(exhausted == 2, "uniform kernel strategy did not reach z=2")
        water_debts, water_columns = water_initial_game(corner, tails)
        require(solve(water_debts, 0, water_columns), "kernel water initial state is not YES")
        escaped += 1

    require(kernel == 126, f"predicted checkpoint kernel has {kernel}, not 126 words")
    require(checkpoint_no == kernel and escaped == kernel, "126-word kernel audit is incomplete")
    return {
        "kernel_words": kernel,
        "checkpoint_local_no": checkpoint_no,
        "uniform_initial_escape_verified": escaped,
    }


def state_json(state: State) -> list[dict[str, object]]:
    return [
        {"debt": debt, "caps": list(caps)}
        for debt, caps in state
    ]


def corner_key_json(corner: Corner) -> dict[str, object]:
    return {
        "parent": state_json(corner.edge.parent),
        "terminal": state_json(corner.edge.terminal),
        "bad_action": list(corner.edge.action),
        "q_color": corner.edge.q_color,
        "anchor_color": corner.anchor_color,
    }


def prefix_audit(limit: int | None) -> dict[str, object]:
    terminals = enumerate_tq_terminals()
    labelled, pairs = reverse_bridge(terminals)
    edges = build_sibling_edges(pairs)
    parents = {parent for parent, _ in pairs}
    require(len(terminals) == EXPECTED_TERMINALS, "Tq terminal count mismatch")
    require(labelled == EXPECTED_LABELED_CANDIDATES, "labelled reverse count mismatch")
    require(len(parents) == EXPECTED_PARENTS, "bridge parent count mismatch")
    require(len(pairs) == EXPECTED_EDGES, "bridge edge count mismatch")
    require(len(edges) == EXPECTED_SIBLING_EDGES, "sibling-edge count mismatch")
    corners = derive_corners(edges)
    kernel_audit = audit_126_checkpoint_kernel(corners)

    target = EXPECTED_RESIDUAL_WORDS if limit is None else limit
    require(0 < target <= EXPECTED_RESIDUAL_WORDS, "limit is outside the corner universe")
    checked = parent_yes = parent_no = 0
    water_checked = water_yes = water_no = 0
    digest = hashlib.sha256()
    first_no: dict[str, object] | None = None
    first_checkpoint_no: dict[str, object] | None = None
    rows: list[dict[str, object]] = []
    checked_prefix: list[dict[str, object]] = []
    bounded_prefix = target < EXPECTED_RESIDUAL_WORDS
    for ordinal, corner in enumerate(corners):
        row_checked = row_parent_yes = row_parent_no = 0
        row_water_checked = row_water_yes = row_water_no = 0
        expected = count_tail_words(corner.remaining, corner.anchor_color)
        for tails in tail_words(corner):
            # Fixed words rarely share complete recursive states.  Retaining
            # every prior layout would make the formal 235,620-word audit use
            # unbounded memory without strengthening the comparison.
            solve.cache_clear()
            parent_debts, parent_columns = parent_checkpoint_game(corner, tails)
            parent_winning = solve(parent_debts, 0, parent_columns)
            parent_mask = safe_first_mask(parent_debts, 0, parent_columns) if bounded_prefix else 0
            parent_path = winning_path(parent_debts, 0, parent_columns) if bounded_prefix else None
            require(
                not bounded_prefix or (bool(parent_mask) == parent_winning),
                "parent-checkpoint result and safe mask disagree",
            )
            water_winning: bool | None = None
            mask = 0
            path: tuple[int, ...] | None = None
            if not parent_winning:
                water_debts, water_columns = water_initial_game(corner, tails)
                water_winning = solve(water_debts, 0, water_columns)
                mask = safe_first_mask(water_debts, 0, water_columns)
                require(bool(mask) == water_winning, "water-initial result and safe mask disagree")
                path = winning_path(water_debts, 0, water_columns)
                require((path is not None) == water_winning, "water-initial path extraction disagrees")
            record = {
                "corner": corner_key_json(corner),
                "tails_top_to_bottom": [list(tail) for tail in tails],
                "parent_checkpoint_solvable": parent_winning,
                "parent_safe_mask": parent_mask,
                "parent_escape_columns": list(parent_path) if parent_path is not None else None,
                "water_initial_solvable": water_winning,
                "water_initial_safe_mask": mask,
                "water_initial_escape_columns": list(path) if path is not None else None,
            }
            digest.update(
                json.dumps(record, separators=(",", ":"), sort_keys=True).encode("ascii")
            )
            checked += 1
            row_checked += 1
            parent_yes += int(parent_winning)
            row_parent_yes += int(parent_winning)
            parent_no += int(not parent_winning)
            row_parent_no += int(not parent_winning)
            if water_winning is not None:
                water_checked += 1
                row_water_checked += 1
                water_yes += int(water_winning)
                row_water_yes += int(water_winning)
                water_no += int(not water_winning)
                row_water_no += int(not water_winning)
            if bounded_prefix:
                checked_prefix.append(record)
            if water_winning is False and first_no is None:
                first_no = {
                    **record,
                    "decoration_ordinal": ordinal,
                    "scope_note": "local fixed-word residual only; not a global layout counterexample",
                }
            if not parent_winning and first_checkpoint_no is None:
                first_checkpoint_no = {
                    **record,
                    "decoration_ordinal": ordinal,
                    "scope_note": "bridge-parent checkpoint only; restored water initial layout may be solvable",
                }
            if checked == target:
                rows.append(
                    {
                        "decoration_ordinal": ordinal,
                        **corner_key_json(corner),
                        "cards": [list(card) for card in corner.cards],
                        "remaining_color_counts": list(corner.remaining),
                        "residual_words_expected": expected,
                        "residual_words_checked": row_checked,
                        "parent_checkpoint_yes": row_parent_yes,
                        "parent_checkpoint_local_no": row_parent_no,
                        "water_initial_checked": row_water_checked,
                        "water_initial_yes": row_water_yes,
                        "water_initial_no": row_water_no,
                    }
                )
                for later_ordinal, later in enumerate(
                    corners[ordinal + 1 :], start=ordinal + 1
                ):
                    rows.append(
                        {
                            "decoration_ordinal": later_ordinal,
                            **corner_key_json(later),
                            "cards": [list(card) for card in later.cards],
                            "remaining_color_counts": list(later.remaining),
                            "residual_words_expected": count_tail_words(
                                later.remaining, later.anchor_color
                            ),
                            "residual_words_checked": 0,
                            "parent_checkpoint_yes": 0,
                            "parent_checkpoint_local_no": 0,
                            "water_initial_checked": 0,
                            "water_initial_yes": 0,
                            "water_initial_no": 0,
                        }
                    )
                return {
                    "schema_version": 1,
                    "coverage_scope": SCOPE,
                    "corner_decorations_expected": EXPECTED_DECORATIONS,
                    "corner_edges_expected": EXPECTED_DECORATION_EDGES,
                    "residual_words_expected": EXPECTED_RESIDUAL_WORDS,
                    "residual_words_checked": checked,
                    "parent_checkpoint_yes_count": parent_yes,
                    "parent_checkpoint_local_no_count": parent_no,
                    "parent_local_no_mapped_to_water_initial": parent_no,
                    "unresolved_parent_local_no_count": 0,
                    "water_initial_layouts_checked": water_checked,
                    "water_initial_yes_count": water_yes,
                    "water_initial_no_count": water_no,
                    "water_initial_witnesses_replayed": water_yes,
                    "local_no_count": water_no,
                    "global_no_count": 0,
                    "predicted_126_kernel_audit": kernel_audit,
                    "prefix_sha256": digest.hexdigest(),
                    "universe_complete": checked == EXPECTED_RESIDUAL_WORDS,
                    "per_decoration": rows,
                    "checked_prefix": checked_prefix,
                    "first_local_no": first_no,
                    "first_parent_checkpoint_local_no": first_checkpoint_no,
                }
        rows.append(
            {
                "decoration_ordinal": ordinal,
                **corner_key_json(corner),
                "cards": [list(card) for card in corner.cards],
                "remaining_color_counts": list(corner.remaining),
                "residual_words_expected": expected,
                "residual_words_checked": row_checked,
                "parent_checkpoint_yes": row_parent_yes,
                "parent_checkpoint_local_no": row_parent_no,
                "water_initial_checked": row_water_checked,
                "water_initial_yes": row_water_yes,
                "water_initial_no": row_water_no,
            }
        )
    fail("prefix audit fell off the residual universe")


def parse_report(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), "report root is not an object")
    return value


def normalized_corner_key(row: object) -> str:
    require(isinstance(row, dict), "decoration row is not an object")
    fields = {
        name: row.get(name)
        for name in ("parent", "terminal", "bad_action", "q_color")
    }
    fields["target_color"] = row.get("target_color", row.get("anchor_color"))
    require(all(value is not None for value in fields.values()), "decoration key is incomplete")
    return json.dumps(fields, separators=(",", ":"), sort_keys=True)


def compare_report(report: dict[str, object], audit: dict[str, object]) -> None:
    require(report.get("schema_version") == 1, "bad report schema version")
    require(report.get("coverage_scope") == SCOPE, "bad report scope")
    require(
        report.get("corner_edges_expected") == audit.get("corner_edges_expected")
        and report.get("corner_edge_count") == audit.get("corner_edges_expected"),
        "corner-edge coverage mismatch",
    )
    require(
        report.get("bridge")
        == {
            "terminal_count": EXPECTED_TERMINALS,
            "labeled_reverse_candidates": EXPECTED_LABELED_CANDIDATES,
            "canonical_parent_count": EXPECTED_PARENTS,
            "canonical_edge_count": EXPECTED_EDGES,
            "sibling_parent_count": 412,
            "sibling_edge_count": EXPECTED_SIBLING_EDGES,
        },
        "bridge constants differ from the independent reconstruction",
    )
    for field in (
        "corner_decorations_expected",
        "residual_words_expected",
        "residual_words_checked",
        "parent_checkpoint_yes_count",
        "parent_checkpoint_local_no_count",
        "parent_local_no_mapped_to_water_initial",
        "unresolved_parent_local_no_count",
        "water_initial_layouts_checked",
        "water_initial_yes_count",
        "water_initial_no_count",
        "water_initial_witnesses_replayed",
        "local_no_count",
        "global_no_count",
    ):
        require(report.get(field) == audit.get(field), f"report {field} mismatch")
    require(
        int(report["water_initial_yes_count"]) + int(report["water_initial_no_count"])
        == int(report["water_initial_layouts_checked"]),
        "water-initial fallback classifications do not partition mapped layouts",
    )
    require(
        int(report["parent_checkpoint_yes_count"])
        + int(report["parent_checkpoint_local_no_count"])
        == int(report["residual_words_checked"]),
        "parent-checkpoint classifications do not partition checked words",
    )

    expected_complete = audit.get("universe_complete") is True
    for field in ("universe_complete", "residual_word_universe_complete"):
        require(report.get(field) is expected_complete, f"report {field} mismatch")
    require(report.get("full_residual_word_coverage") is expected_complete, "coverage flag mismatch")
    require(report.get("entry_family_eliminated") is False, "corner report claims the bridge family")
    require(report.get("full_layout_coverage") is False, "corner report claims all layouts")
    require(report.get("global_no_count", 0) == 0, "local search claims a global NO")

    status = report.get("status")
    if not expected_complete:
        require(status == "INCOMPLETE", "bounded run has a terminal status")
        require(report.get("verified") is False, "bounded report is verified")
    elif int(audit["water_initial_no_count"]) == 0:
        require(status == "CORNER_FAMILY_ELIMINATED", "all-YES full run lacks elimination status")
        require(report.get("verified") is True, "full all-YES report is not verified")
        require(
            report.get("parent_local_no_mapped_to_water_initial")
            == audit.get("parent_checkpoint_local_no_count"),
            "checkpoint-local-NO mapping is incomplete",
        )
        require(
            report.get("water_initial_witnesses_replayed")
            == audit.get("parent_checkpoint_local_no_count"),
            "checkpoint-local-NO escape replay is incomplete",
        )
    else:
        require(status == "LOCAL_NO_RESIDUALS_EXPORTED", "local NO status is unsafe")
        require(report.get("verified") is True, "complete local-NO export is not verified")

    report_rows = report.get("per_decoration")
    audit_rows = audit.get("per_decoration")
    require(isinstance(report_rows, list) and isinstance(audit_rows, list), "missing per-decoration rows")
    actual = {normalized_corner_key(row): row for row in report_rows}
    expected = {normalized_corner_key(row): row for row in audit_rows}
    require(set(actual) == set(expected), "per-decoration semantic coverage mismatch")
    for key, expected_row in expected.items():
        actual_row = actual[key]
        require(isinstance(actual_row, dict) and isinstance(expected_row, dict), "bad row")
        for field in (
            "residual_words_expected",
            "residual_words_checked",
        ):
            require(actual_row.get(field) == expected_row.get(field), f"row {field} mismatch")
        target = actual_row.get("target_color")
        require(actual_row.get("q_caps") == [1, 1, 1], "corner row lost the q1,q1,q1 shape")
        require(
            isinstance(target, int)
            and actual_row.get("cards") == [[target, 3], [target, 3], [target, 3]],
            "corner row does not commit all three q1->x3 cards",
        )
        field_pairs = (
            ("parent_checkpoint_yes_count", "parent_checkpoint_yes"),
            ("parent_checkpoint_local_no_count", "parent_checkpoint_local_no"),
            ("water_initial_layouts_checked", "water_initial_checked"),
            ("water_initial_yes_count", "water_initial_yes"),
            ("water_initial_no_count", "water_initial_no"),
        )
        for actual_field, expected_field in field_pairs:
            require(
                actual_row.get(actual_field) == expected_row.get(expected_field),
                f"row {actual_field} mismatch",
            )

    # A shared digest is optional for forward compatibility, but if production
    # emits one it must agree exactly with the independently ordered prefix.
    if "prefix_sha256" in report:
        require(report.get("prefix_sha256") == audit.get("prefix_sha256"), "prefix digest mismatch")

    if "checked_prefix" in report:
        actual_prefix = report.get("checked_prefix")
        expected_prefix = audit.get("checked_prefix")
        require(isinstance(actual_prefix, list) and isinstance(expected_prefix, list), "bad prefix")
        require(len(actual_prefix) == len(expected_prefix), "bounded prefix length mismatch")
        key_to_ordinal = {
            normalized_corner_key(row): row["decoration_ordinal"]
            for row in audit_rows
            if isinstance(row, dict)
        }

        def path_digits(value: object) -> list[int] | None:
            if value is None:
                return None
            require(isinstance(value, str), "production path is not a string")
            return [int(character) for character in value] if value else None

        for actual_record, expected_record in zip(actual_prefix, expected_prefix):
            require(isinstance(actual_record, dict) and isinstance(expected_record, dict), "bad prefix row")
            expected_ordinal = key_to_ordinal[normalized_corner_key(expected_record["corner"])]
            require(actual_record.get("decoration_index") == expected_ordinal, "prefix decoration mismatch")
            raw_tails = actual_record.get("free_tails_top_to_bottom")
            require(
                isinstance(raw_tails, list)
                and all(isinstance(word, str) for word in raw_tails),
                "production prefix has bad tails",
            )
            actual_tails = [[int(character) for character in word] for word in raw_tails]
            require(actual_tails == expected_record.get("tails_top_to_bottom"), "prefix tails mismatch")
            require(
                actual_record.get("parent_checkpoint_solvable")
                == expected_record.get("parent_checkpoint_solvable"),
                "prefix parent result mismatch",
            )
            require(actual_record.get("parent_safe_mask") == expected_record.get("parent_safe_mask"), "prefix parent mask mismatch")
            require(
                path_digits(actual_record.get("parent_escape_columns"))
                == expected_record.get("parent_escape_columns"),
                "prefix parent path mismatch",
            )
            require(
                actual_record.get("water_initial_solvable")
                == expected_record.get("water_initial_solvable"),
                "prefix water-initial result mismatch",
            )
            require(
                actual_record.get("water_initial_safe_mask")
                == expected_record.get("water_initial_safe_mask"),
                "prefix water-initial mask mismatch",
            )
            require(
                path_digits(actual_record.get("water_initial_escape_columns"))
                == expected_record.get("water_initial_escape_columns"),
                "prefix water-initial path mismatch",
            )


def schema_negative_tests(report: dict[str, object], audit: dict[str, object]) -> None:
    for mutation, label in (
        ({"entry_family_eliminated": True}, "bridge overclaim"),
        ({"full_layout_coverage": True}, "layout overclaim"),
        ({"global_no_count": 1}, "global-NO overclaim"),
    ):
        broken = dict(report)
        broken.update(mutation)
        try:
            compare_report(broken, audit)
        except AssertionError:
            continue
        fail(f"schema negative test accepted {label}")


def run_program(program: Path, limit: int) -> tuple[dict[str, object], dict[str, object]]:
    audit = prefix_audit(limit)
    with tempfile.TemporaryDirectory(prefix="c4-h7-tq-low-corners-") as directory:
        output = Path(directory)
        subprocess.run(
            [str(program), "--output-dir", str(output), "--limit", str(limit)],
            check=True,
        )
        report = parse_report(output / "report.json")
        compare_report(report, audit)
        schema_negative_tests(report, audit)
    return report, audit


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--program", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    if args.program is not None:
        require(args.limit is not None, "--program requires a bounded --limit")
        report, audit = run_program(args.program.resolve(), args.limit)
        del report
    else:
        audit = prefix_audit(args.limit)
        if args.report is not None:
            report = parse_report(args.report)
            compare_report(report, audit)
            schema_negative_tests(report, audit)

    rendered = json.dumps(audit, indent=2, sort_keys=True) + "\n"
    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    print(
        f"independent corner audit: water initial {audit['water_initial_yes_count']}/"
        f"{audit['water_initial_layouts_checked']} YES; parent-checkpoint-local-NO="
        f"{audit['parent_checkpoint_local_no_count']}; water-initial-NO="
        f"{audit['water_initial_no_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
