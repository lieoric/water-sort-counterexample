#!/usr/bin/env python3
"""Independent audit of the two-legal-source D2-reduction subfamily.

This checker deliberately imports no production code.  It rebuilds the
first-exhaustion bridge, selects the 190 legal-source-count-two decorations,
expands their 12,936 labelled fixed residual words, reconstructs all 20
reachable zero-debt histories of the common checkpoint, and runs an exact
fixed-chain game recursion on every selected layout.

``--program`` runs a bounded production differential.  ``--report`` compares
an already-produced report.  The limit unit is checkpoint fixed residual
words; each such word expands to twenty zero-debt water-sort layouts.
"""

from __future__ import annotations

import argparse
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
SCOPE = "c4_h7_d2_reduction_two_legal_source_fixed_residuals"

EXPECTED_TERMINALS = 71
EXPECTED_LABELED_CANDIDATES = 624
EXPECTED_PARENTS = 418
EXPECTED_EDGES = 429
EXPECTED_SIBLING_EDGES = 423
EXPECTED_DECORATIONS = 190
EXPECTED_RESIDUAL_WORDS = 12_936
EXPECTED_PREFIX_CANDIDATES = 1_024
EXPECTED_PREFIX_TEMPLATES = 20
EXPECTED_PREFIX_INTERLEAVINGS = 52
EXPECTED_WATER_LAYOUTS = 258_720
EXPECTED_EDGE_WORDS = {
    "exhaust-sibling-e245": 924,
    "exhaust-sibling-e246": 12_012,
}
EXPECTED_PARENT: "State" = (
    (-2, (1, 2, 3, 3)),
    (0, ()),
    (1, ()),
    (1, ()),
)

Bucket = tuple[int, tuple[int, ...]]
State = tuple[Bucket, Bucket, Bucket, Bucket]
Action = tuple[int, int, int]
Card = tuple[int, int]
Run = tuple[int, int]
LiveColumn = tuple[int, int, tuple[Run, ...]]
Columns = tuple[
    LiveColumn | None,
    LiveColumn | None,
    LiveColumn | None,
    LiveColumn | None,
]
PrefixWords = tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...], tuple[int, ...]]


def fail(message: str) -> NoReturn:
    raise AssertionError(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def canonical_state(debts: Sequence[int], columns: Iterable[tuple[int, int]]) -> State:
    caps_by_color: list[list[int]] = [[] for _ in range(COLORS)]
    for color, cap in columns:
        caps_by_color[color].append(cap)
    value = tuple(
        sorted(
            (int(debts[color]), tuple(sorted(caps_by_color[color])))
            for color in range(COLORS)
        )
    )
    require(len(value) == COLORS, "canonical state lost a color")
    return value  # type: ignore[return-value]


def exposed_counts(state: State) -> tuple[int, int, int, int]:
    return tuple(debt + sum(caps) for debt, caps in state)  # type: ignore[return-value]


def source_is_legal(
    debts_or_state: Sequence[int] | State,
    exhausted: int,
    color: int,
    cap: int,
) -> bool:
    if isinstance(debts_or_state[0], tuple):
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
        source
        for source in physical_sources(state)
        if source_is_legal(state, exhausted, source[0], source[1])
    )


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
    if any(not multiplicity[c] <= exposed[c] <= HEIGHT for c in range(COLORS)):
        return False
    remaining = tuple(HEIGHT - count for count in exposed)
    return all(
        multiplicity[c]
        <= sum(remaining[other] for other in range(COLORS) if other != c)
        for c in range(COLORS)
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
                if state_is_consistent(state, 1) and not legal_sources(state, 1):  # type: ignore[arg-type]
                    terminals.add(state)  # type: ignore[arg-type]
    return tuple(sorted(terminals))


def apply_exhausting(parent: State, exhausted: int, action: Action) -> State | None:
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


def exhausting_actions_to(parent: State, terminal: State) -> tuple[Action, ...]:
    actions: list[Action] = []
    for old_color, (_, caps) in enumerate(parent):
        for old_cap in sorted(set(caps)):
            if not source_is_legal(parent, 0, old_color, old_cap):
                continue
            for final_color in range(COLORS):
                action = old_color, old_cap, final_color
                if apply_exhausting(parent, 0, action) == terminal:
                    actions.append(action)
    return tuple(actions)


def reverse_bridge(terminals: Sequence[State]) -> tuple[int, tuple[tuple[State, State], ...]]:
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
    edge_id: str
    parent: State
    terminal: State
    action: Action
    q_color: int
    q_caps: tuple[int, int, int]
    legal_q_indices: tuple[int, ...]

    @property
    def semantic_key(self) -> tuple[object, ...]:
        return self.parent, self.terminal, self.action, self.q_color


def build_sibling_edges(pairs: Sequence[tuple[State, State]]) -> tuple[Edge, ...]:
    raw: list[tuple[State, State, Action, int, tuple[int, ...]]] = []
    for parent, terminal in pairs:
        if len(legal_sources(parent, 0)) < 2:
            continue
        actions = exhausting_actions_to(parent, terminal)
        require(len(actions) == 1, "ambiguous first-exhaustion action")
        action = actions[0]
        caps_after = [list(values) for _, values in parent]
        caps_after[action[0]].remove(action[1])
        q_candidates = [color for color, caps in enumerate(caps_after) if len(caps) == 3]
        require(len(q_candidates) == 1, "cannot identify the three q siblings")
        q_color = q_candidates[0]
        q_caps = tuple(sorted(caps_after[q_color]))
        legal_indices = tuple(
            index
            for index, cap in enumerate(q_caps)
            if source_is_legal(parent, 0, q_color, cap)
        )
        raw.append((parent, terminal, action, q_color, q_caps + legal_indices))
    edges: list[Edge] = []
    for ordinal, (parent, terminal, action, q_color, packed) in enumerate(raw):
        edges.append(
            Edge(
                f"exhaust-sibling-e{ordinal:03d}",
                parent,
                terminal,
                action,
                q_color,
                packed[:3],  # type: ignore[arg-type]
                packed[3:],
            )
        )
    return tuple(edges)


def cards(q_color: int, cap: int) -> tuple[Card, ...]:
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
        ways = math.factorial(sum(counts))
        for value in counts:
            ways //= math.factorial(value)
        total += ways
    return total


def decoration_balance(
    edge: Edge, chosen: tuple[Card, Card, Card]
) -> tuple[tuple[int, int, int, int], tuple[int, ...], int]:
    remaining = [HEIGHT - count for count in exposed_counts(edge.parent)]
    remaining[edge.action[2]] -= HEIGHT - edge.action[1]
    forbidden: list[int] = []
    for cap, (color, endpoint) in zip(edge.q_caps, chosen):
        remaining[color] -= endpoint - cap
        if endpoint < HEIGHT:
            forbidden.append(color)
    key = tuple(remaining)  # type: ignore[assignment]
    return key, tuple(forbidden), residual_count(key, tuple(forbidden))


def terminal_debts_in_parent_coordinates(edge: Edge) -> list[int]:
    debts = [debt for debt, _ in edge.parent]
    debts[edge.action[0]] += edge.action[1]
    debts[edge.action[2]] += HEIGHT - edge.action[1]
    return debts


def replay_sibling(edge: Edge, slot: int, card: Card) -> tuple[list[int], int]:
    cap = edge.q_caps[slot]
    debts = [debt for debt, _ in edge.parent]
    debts[edge.q_color] += cap
    if card[1] == HEIGHT:
        debts[card[0]] += HEIGHT - cap
        return debts, 1
    debts[card[0]] -= cap
    return debts, 0


def canonical_after_sibling_exhaust(edge: Edge, slot: int, card: Card) -> State:
    cap = edge.q_caps[slot]
    debts = [debt for debt, _ in edge.parent]
    caps = [list(values) for _, values in edge.parent]
    caps[edge.q_color].remove(cap)
    debts[edge.q_color] += cap
    debts[card[0]] += HEIGHT - cap
    return canonical_state(
        debts,
        ((color, value) for color in range(COLORS) for value in caps[color]),
    )


def is_tq_terminal(state: State) -> bool:
    if not state_is_consistent(state, 1) or legal_sources(state, 1):
        return False
    positive = [i for i, (debt, _) in enumerate(state) if debt > 0]
    nonpositive = [i for i, (debt, _) in enumerate(state) if debt <= 0]
    topped = [i for i, (_, caps) in enumerate(state) if caps]
    return len(positive) == 3 and len(nonpositive) == 1 and topped == nonpositive


def is_unique_corner(edge: Edge, slot: int, chosen: tuple[Card, Card, Card]) -> bool:
    color, endpoint = chosen[slot]
    cap = edge.q_caps[slot]
    terminal_debts = terminal_debts_in_parent_coordinates(edge)
    other = [index for index in range(3) if index != slot]
    return (
        -terminal_debts[edge.q_color] == 0
        and cap == terminal_debts[color]
        and endpoint == 3
        and all(edge.q_caps[index] == 1 for index in other)
        and all(chosen[index] == (color, 3) for index in other)
    )


def refined_class(edge: Edge, chosen: tuple[Card, Card, Card]) -> str:
    has_n_ge_3 = has_n_le_2 = has_nonhandoff = has_corner = False
    terminal_debts = terminal_debts_in_parent_coordinates(edge)
    for slot in edge.legal_q_indices:
        card = chosen[slot]
        cap = edge.q_caps[slot]
        if card[1] == HEIGHT:
            if is_tq_terminal(canonical_after_sibling_exhaust(edge, slot, card)):
                has_corner = True
            else:
                return "direct_certified"
            continue
        debts, _ = replay_sibling(edge, slot, card)
        if source_is_legal(debts, 0, edge.action[0], edge.action[1]):
            after_bad = terminal_debts.copy()
            after_bad[edge.q_color] += cap
            after_bad[card[0]] -= cap
            if -min(after_bad) >= 3:
                has_n_ge_3 = True
            elif is_unique_corner(edge, slot, chosen):
                has_corner = True
            else:
                has_n_le_2 = True
        else:
            has_nonhandoff = True
    if has_n_ge_3:
        return "n_ge_3_certified"
    if has_n_le_2:
        return "n_le_2_certified"
    if has_nonhandoff:
        return "d2_reduction"
    require(has_corner, "refined ledger has no branch")
    return "tq_corner_only"


@dataclass(frozen=True)
class Decoration:
    edge: Edge
    chosen_cards: tuple[Card, Card, Card]
    remaining: tuple[int, int, int, int]
    weight: int

    @property
    def semantic_key(self) -> tuple[object, ...]:
        return (*self.edge.semantic_key, self.chosen_cards)


def derive_decorations() -> tuple[Decoration, ...]:
    terminals = enumerate_tq_terminals()
    labelled, pairs = reverse_bridge(terminals)
    edges = build_sibling_edges(pairs)
    parents = {parent for parent, _ in pairs}
    require(len(terminals) == EXPECTED_TERMINALS, "Tq terminal census drifted")
    require(labelled == EXPECTED_LABELED_CANDIDATES, "reverse labelled census drifted")
    require(len(parents) == EXPECTED_PARENTS, "bridge parent census drifted")
    require(len(pairs) == EXPECTED_EDGES, "bridge edge census drifted")
    require(len(edges) == EXPECTED_SIBLING_EDGES, "sibling edge census drifted")

    target_edges = [edge for edge in edges if len(legal_sources(edge.parent, 0)) == 2]
    require([edge.edge_id for edge in target_edges] == list(EXPECTED_EDGE_WORDS), "two-source edge IDs drifted")
    require(all(edge.parent == EXPECTED_PARENT for edge in target_edges), "two-source P drifted")
    require(
        [edge.action for edge in target_edges] == [(0, 1, 1), (0, 2, 1)],
        "two-source bad actions drifted",
    )

    decorations: list[Decoration] = []
    for edge in target_edges:
        for chosen_raw in itertools.product(*(cards(edge.q_color, cap) for cap in edge.q_caps)):
            chosen = tuple(chosen_raw)  # type: ignore[assignment]
            remaining, _, weight = decoration_balance(edge, chosen)
            if weight and refined_class(edge, chosen) == "d2_reduction":
                decorations.append(Decoration(edge, chosen, remaining, weight))
    decorations.sort(key=lambda value: value.semantic_key)
    require(len(decorations) == EXPECTED_DECORATIONS, "D2 two-source decoration count drifted")
    require(sum(item.weight for item in decorations) == EXPECTED_RESIDUAL_WORDS, "fixed word count drifted")
    actual_edges = Counter()
    for item in decorations:
        actual_edges[item.edge.edge_id] += item.weight
    require(dict(actual_edges) == EXPECTED_EDGE_WORDS, f"per-edge word count drifted: {actual_edges}")
    return tuple(decorations)


def residual_words(decoration: Decoration) -> Iterator[tuple[tuple[int, ...], ...]]:
    lengths = tuple(HEIGHT - endpoint for _, endpoint in decoration.chosen_cards)
    starts: dict[int, int] = {}
    cursor = 0
    for slot, length in enumerate(lengths):
        if length:
            starts[cursor] = decoration.chosen_cards[slot][0]
        cursor += length
    cells = [-1] * cursor

    def visit(position: int, counts: tuple[int, int, int, int]) -> Iterator[tuple[int, ...]]:
        if position == len(cells):
            if not any(counts):
                yield tuple(cells)
            return
        for color, count in enumerate(counts):
            if not count or starts.get(position) == color:
                continue
            child = list(counts)
            child[color] -= 1
            cells[position] = color
            yield from visit(position + 1, tuple(child))  # type: ignore[arg-type]

    produced = 0
    for flat in visit(0, decoration.remaining):
        offsets = [0]
        for length in lengths:
            offsets.append(offsets[-1] + length)
        produced += 1
        yield tuple(flat[offsets[i] : offsets[i + 1]] for i in range(3))
    require(produced == decoration.weight, "residual generator disagrees with Hall weight")


def runs(cells_top_to_bottom: Iterable[int]) -> tuple[Run, ...]:
    result: list[Run] = []
    for color in cells_top_to_bottom:
        if result and result[-1][0] == color:
            result[-1] = color, result[-1][1] + 1
        else:
            result.append((color, 1))
    return tuple(result)


def prefix_debts(words: PrefixWords) -> tuple[int, int, int, int]:
    debts = [0] * COLORS
    for word in words:
        chain = runs(word)
        cap = chain[0][1]
        for index in range(len(chain) - 1):
            old_color = chain[index][0]
            next_color, length = chain[index + 1]
            debts[old_color] += cap
            debts[next_color] -= cap
            cap += length
    return tuple(debts)  # type: ignore[return-value]


@dataclass(frozen=True)
class PrefixTemplate:
    words: PrefixWords
    interleavings: int
    witness: tuple[int, ...]


def prefix_interleavings(words: PrefixWords) -> tuple[int, tuple[int, ...] | None]:
    chains = tuple(runs(word) for word in words)

    @lru_cache(maxsize=None)
    def visit(
        positions: tuple[int, int, int, int], debts: tuple[int, int, int, int]
    ) -> tuple[int, tuple[int, ...] | None]:
        if all(positions[i] == len(chains[i]) - 1 for i in range(4)):
            return 1, ()
        count = 0
        witness: tuple[int, ...] | None = None
        for source in range(4):
            position = positions[source]
            if position == len(chains[source]) - 1:
                continue
            cap = sum(length for _, length in chains[source][: position + 1])
            old_color = chains[source][position][0]
            next_color = chains[source][position + 1][0]
            child_debts = list(debts)
            child_debts[old_color] += cap
            if sum(value > 0 for value in child_debts) > EMPTY_COLUMNS:
                continue
            child_debts[next_color] -= cap
            child_positions = list(positions)
            child_positions[source] += 1
            child_count, child_witness = visit(
                tuple(child_positions),  # type: ignore[arg-type]
                tuple(child_debts),  # type: ignore[arg-type]
            )
            count += child_count
            if witness is None and child_witness is not None:
                witness = (source,) + child_witness
        return count, witness

    return visit((0, 0, 0, 0), (0, 0, 0, 0))


def derive_prefix_templates() -> tuple[PrefixTemplate, ...]:
    caps = (1, 2, 3, 3)
    templates: list[PrefixTemplate] = []
    candidates = 0
    choices = [tuple(itertools.product(range(COLORS), repeat=cap - 1)) for cap in caps]
    for heads in itertools.product(*choices):
        candidates += 1
        words = tuple(tuple(head) + (0,) for head in heads)
        if prefix_debts(words) != tuple(debt for debt, _ in EXPECTED_PARENT):
            continue
        count, witness = prefix_interleavings(words)  # type: ignore[arg-type]
        require(count > 0 and witness is not None, "debt-feasible past prefix is unreachable")
        templates.append(PrefixTemplate(words, count, witness))  # type: ignore[arg-type]
    templates.sort(key=lambda value: value.words)
    require(candidates == EXPECTED_PREFIX_CANDIDATES, "past-prefix brute-force space drifted")
    require(len(templates) == EXPECTED_PREFIX_TEMPLATES, "past-prefix template count drifted")
    require(sum(item.interleavings for item in templates) == EXPECTED_PREFIX_INTERLEAVINGS, "past-prefix interleaving count drifted")
    require(Counter(item.interleavings for item in templates) == {1: 4, 2: 6, 3: 8, 6: 2}, "past-prefix path distribution drifted")
    return tuple(templates)


def hidden_words(
    decoration: Decoration, tails: tuple[tuple[int, ...], ...]
) -> tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...], tuple[int, ...]]:
    edge = decoration.edge
    entries: list[tuple[int, int, tuple[int, ...]]] = [
        (
            edge.action[1],
            -1,
            (edge.action[2],) * (HEIGHT - edge.action[1]),
        )
    ]
    for slot, (cap, card, tail) in enumerate(zip(edge.q_caps, decoration.chosen_cards, tails)):
        color, endpoint = card
        require(len(tail) == HEIGHT - endpoint, "residual tail length drifted")
        if tail:
            require(tail[0] != color, "residual tail merged into card run")
        entries.append((cap, slot, (color,) * (endpoint - cap) + tail))
    entries.sort(key=lambda item: (item[0], item[1]))
    require([cap for cap, _, _ in entries] == [1, 2, 3, 3], "physical cap order drifted")
    return tuple(item[2] for item in entries)  # type: ignore[return-value]


def checkpoint_game(
    decoration: Decoration, tails: tuple[tuple[int, ...], ...]
) -> tuple[tuple[int, int, int, int], Columns]:
    hidden = hidden_words(decoration, tails)
    columns: list[LiveColumn] = []
    for cap, suffix in zip((1, 2, 3, 3), hidden):
        future = runs(suffix)
        require(future and cap + sum(length for _, length in future) == HEIGHT, "checkpoint column misses height 7")
        columns.append((decoration.edge.q_color, cap, future))
    return tuple(debt for debt, _ in decoration.edge.parent), tuple(columns)  # type: ignore[return-value]


def water_initial_game(
    decoration: Decoration,
    tails: tuple[tuple[int, ...], ...],
    prefix: PrefixTemplate,
) -> tuple[tuple[int, int, int, int], Columns]:
    hidden = hidden_words(decoration, tails)
    columns: list[LiveColumn] = []
    physical = Counter()
    for exposed, suffix in zip(prefix.words, hidden):
        word = exposed + suffix
        require(len(word) == HEIGHT, "restored physical column misses height 7")
        physical.update(word)
        chain = runs(word)
        columns.append((chain[0][0], chain[0][1], chain[1:]))
    require(physical == Counter({color: HEIGHT for color in range(COLORS)}), "restored layout is not color-balanced")
    initial: tuple[tuple[int, int, int, int], Columns] = ((0, 0, 0, 0), tuple(columns))  # type: ignore[arg-type]

    reached = initial
    exhausted = 0
    for source in prefix.witness:
        child = step(reached[0], exhausted, reached[1], source)
        require(child is not None and child[1] == 0, "past-prefix witness became illegal")
        reached = (child[0], child[2])
    require(reached == checkpoint_game(decoration, tails), "past-prefix witness does not reach P")
    return initial


@lru_cache(maxsize=None)
def solve(debts: tuple[int, int, int, int], exhausted: int, columns: Columns) -> bool:
    if exhausted >= EMPTY_COLUMNS:
        return True
    for source in range(4):
        child = step(debts, exhausted, columns, source)
        if child is not None and solve(*child):
            return True
    return False


def step(
    debts: tuple[int, int, int, int], exhausted: int, columns: Columns, source: int
) -> tuple[tuple[int, int, int, int], int, Columns] | None:
    if source not in range(4) or columns[source] is None:
        return None
    column = columns[source]
    require(column is not None, "selected column vanished")
    top, cap, future = column
    if not future or not source_is_legal(debts, exhausted, top, cap):
        return None
    next_color, run_length = future[0]
    require(next_color != top and run_length > 0, "fixed chain contains a merged boundary")
    child_debts = list(debts)
    child_debts[top] += cap
    child_columns = list(columns)
    child_exhausted = exhausted
    if len(future) == 1:
        require(cap + run_length == HEIGHT, "final run does not end at height 7")
        child_debts[next_color] += run_length
        child_columns[source] = None
        child_exhausted += 1
    else:
        require(cap + run_length < HEIGHT, "nonfinal run reaches height 7")
        child_debts[next_color] -= cap
        child_columns[source] = (next_color, cap + run_length, future[1:])
    return tuple(child_debts), child_exhausted, tuple(child_columns)  # type: ignore[return-value]


def safe_first_mask(debts: tuple[int, int, int, int], exhausted: int, columns: Columns) -> int:
    mask = 0
    for source in range(4):
        child = step(debts, exhausted, columns, source)
        if child is not None and solve(*child):
            mask |= 1 << source
    return mask


def winning_path(debts: tuple[int, int, int, int], exhausted: int, columns: Columns) -> tuple[int, ...] | None:
    if exhausted >= EMPTY_COLUMNS:
        return ()
    for source in range(4):
        child = step(debts, exhausted, columns, source)
        if child is None or not solve(*child):
            continue
        suffix = winning_path(*child)
        require(suffix is not None, "winning child has no replayable path")
        return (source,) + suffix
    return None


def replay_path(
    debts: tuple[int, int, int, int], exhausted: int, columns: Columns, path: Sequence[int]
) -> bool:
    for source in path:
        child = step(debts, exhausted, columns, source)
        if child is None:
            return False
        debts, exhausted, columns = child
    return exhausted >= EMPTY_COLUMNS


def columns_as_words(prefix: PrefixTemplate, decoration: Decoration, tails: tuple[tuple[int, ...], ...]) -> list[str]:
    return [
        "".join(str(color) for color in exposed + suffix)
        for exposed, suffix in zip(prefix.words, hidden_words(decoration, tails))
    ]


def edge_rows(decorations: Sequence[Decoration]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for edge_id, expected in EXPECTED_EDGE_WORDS.items():
        edge = next(item.edge for item in decorations if item.edge.edge_id == edge_id)
        rows.append(
            {
                "edge_id": edge_id,
                "bad_cap": edge.action[1],
                "q_caps": list(edge.q_caps),
                "residual_words_expected": expected,
            }
        )
    return rows


def audit_status(complete: bool, water_initial_no: int) -> str:
    """Keep a complete-layout NO stronger than any bounded-coverage qualifier."""

    if water_initial_no:
        return "GLOBAL_NO_FOUND"
    if not complete:
        return "INCOMPLETE"
    return "TWO_SOURCE_D2_FAMILY_ELIMINATED"


def independent_audit(limit: int | None) -> dict[str, object]:
    decorations = derive_decorations()
    prefixes = derive_prefix_templates()
    target = EXPECTED_RESIDUAL_WORDS if limit is None else limit
    require(0 < target <= EXPECTED_RESIDUAL_WORDS, "limit is outside the fixed-word universe")
    bounded = target < EXPECTED_RESIDUAL_WORDS

    checked = parent_yes = parent_no = 0
    recovered = unresolved = 0
    water_checked = water_yes = water_no = witnesses = 0
    checked_prefix: list[dict[str, object]] = []
    per_decoration: list[dict[str, object]] = []
    per_edge = edge_rows(decorations)
    first_parent: dict[str, object] | None = None
    first_recovery: dict[str, object] | None = None
    first_global: dict[str, object] | None = None

    for decoration_index, decoration in enumerate(decorations):
        row_checked = row_parent_yes = row_parent_no = 0
        row_water_checked = row_water_yes = row_water_no = 0
        for tails in residual_words(decoration):
            if checked == target:
                break
            solve.cache_clear()
            parent = checkpoint_game(decoration, tails)
            parent_winning = solve(parent[0], 0, parent[1])
            parent_mask = safe_first_mask(parent[0], 0, parent[1])
            require(not parent_winning and parent_mask == 0, "two-source checkpoint unexpectedly escapes")
            parent_yes += int(parent_winning)
            parent_no += int(not parent_winning)
            row_parent_yes += int(parent_winning)
            row_parent_no += int(not parent_winning)

            word_water_yes = word_water_no = 0
            for prefix_index, prefix in enumerate(prefixes):
                solve.cache_clear()
                initial = water_initial_game(decoration, tails, prefix)
                water_winning = solve(initial[0], 0, initial[1])
                mask = safe_first_mask(initial[0], 0, initial[1])
                require(bool(mask) == water_winning, "water result and safe mask disagree")
                water_checked += 1
                row_water_checked += 1
                if water_winning:
                    path = winning_path(initial[0], 0, initial[1])
                    require(path is not None and replay_path(initial[0], 0, initial[1], path), "water witness does not replay")
                    water_yes += 1
                    row_water_yes += 1
                    word_water_yes += 1
                    witnesses += 1
                    if first_recovery is None:
                        words = columns_as_words(prefix, decoration, tails)
                        first_recovery = {
                            "decoration_index": decoration_index,
                            "prefix_template_index": prefix_index,
                            "columns_top_to_bottom": words,
                            "columns_bottom_to_top": [word[::-1] for word in words],
                            "safe_mask": mask,
                            "escape_columns": "".join(str(source) for source in path),
                        }
                else:
                    water_no += 1
                    row_water_no += 1
                    word_water_no += 1
                    if first_global is None:
                        words = columns_as_words(prefix, decoration, tails)
                        first_global = {
                            "decoration_index": decoration_index,
                            "prefix_template_index": prefix_index,
                            "columns_top_to_bottom": words,
                            "columns_bottom_to_top": [word[::-1] for word in words],
                            "safe_mask": mask,
                            "escape_columns": "",
                        }
            require(word_water_yes + word_water_no == EXPECTED_PREFIX_TEMPLATES, "past-prefix partition drifted")
            if word_water_no:
                unresolved += 1
            else:
                recovered += 1

            if first_parent is None:
                first_parent = {
                    "decoration_index": decoration_index,
                    "solvable": parent_winning,
                    "safe_mask": parent_mask,
                    "escape_columns": "",
                }
            checked_prefix.append(
                {
                    "decoration_index": decoration_index,
                    "free_tails_top_to_bottom": ["".join(map(str, tail)) for tail in tails],
                    "parent_checkpoint_solvable": parent_winning,
                    "parent_safe_mask": parent_mask,
                    "parent_escape_columns": "",
                    "water_initial_layouts_checked": EXPECTED_PREFIX_TEMPLATES,
                    "water_initial_yes_count": word_water_yes,
                    "water_initial_no_count": word_water_no,
                }
            )
            checked += 1
            row_checked += 1
        per_decoration.append(
            {
                "decoration_index": decoration_index,
                "edge_id": decoration.edge.edge_id,
                "cards": [list(card) for card in decoration.chosen_cards],
                "residual_words_expected": decoration.weight,
                "residual_words_checked": row_checked,
                "parent_checkpoint_yes_count": row_parent_yes,
                "parent_checkpoint_local_no_count": row_parent_no,
                "water_initial_layouts_checked": row_water_checked,
                "water_initial_yes_count": row_water_yes,
                "water_initial_no_count": row_water_no,
            }
        )
        if checked == target:
            for later_index in range(decoration_index + 1, len(decorations)):
                later = decorations[later_index]
                per_decoration.append(
                    {
                        "decoration_index": later_index,
                        "edge_id": later.edge.edge_id,
                        "cards": [list(card) for card in later.chosen_cards],
                        "residual_words_expected": later.weight,
                        "residual_words_checked": 0,
                        "parent_checkpoint_yes_count": 0,
                        "parent_checkpoint_local_no_count": 0,
                        "water_initial_layouts_checked": 0,
                        "water_initial_yes_count": 0,
                        "water_initial_no_count": 0,
                    }
                )
            break

    for row in per_edge:
        indices = [i for i, item in enumerate(decorations) if item.edge.edge_id == row["edge_id"]]
        row["residual_words_checked"] = sum(int(per_decoration[i]["residual_words_checked"]) for i in indices)
        row["parent_checkpoint_yes_count"] = sum(int(per_decoration[i]["parent_checkpoint_yes_count"]) for i in indices)
        row["parent_checkpoint_local_no_count"] = sum(int(per_decoration[i]["parent_checkpoint_local_no_count"]) for i in indices)

    require(checked == target, "fixed-word traversal ended early")
    require(parent_yes + parent_no == checked, "parent partition mismatch")
    require(water_checked == checked * EXPECTED_PREFIX_TEMPLATES, "water expansion mismatch")
    require(water_yes + water_no == water_checked, "water partition mismatch")
    require(recovered + unresolved == parent_no, "checkpoint recovery partition mismatch")
    complete = checked == EXPECTED_RESIDUAL_WORDS
    require(audit_status(False, 1) == "GLOBAL_NO_FOUND", "bounded global-NO priority regressed")
    status = audit_status(complete, water_no)
    report: dict[str, object] = {
        "schema_version": 1,
        "coverage_scope": SCOPE,
        "status": status,
        "verified": complete,
        "global_no_independently_verified": bool(complete and water_no),
        "canonical_edge_count": 2,
        "decorations_expected": EXPECTED_DECORATIONS,
        "residual_words_expected": EXPECTED_RESIDUAL_WORDS,
        "residual_words_checked": checked,
        "parent_checkpoint_yes_count": parent_yes,
        "parent_checkpoint_local_no_count": parent_no,
        "past_prefix_candidates_enumerated": EXPECTED_PREFIX_CANDIDATES,
        "past_prefix_templates_per_edge": EXPECTED_PREFIX_TEMPLATES,
        "past_prefix_legal_interleavings": EXPECTED_PREFIX_INTERLEAVINGS,
        "parent_local_no_recovered_count": recovered,
        "unresolved_parent_local_no_count": unresolved,
        "water_initial_layouts_expected": EXPECTED_WATER_LAYOUTS,
        "water_initial_layouts_checked": water_checked,
        "water_initial_yes_count": water_yes,
        "water_initial_no_count": water_no,
        "water_initial_witnesses_replayed": witnesses,
        "local_no_count": unresolved,
        "global_no_count": water_no,
        "universe_complete": complete,
        "fixed_residual_universe_complete": complete,
        "two_source_d2_family_eliminated": bool(complete and water_no == 0),
        "d2_family_eliminated": False,
        "entry_family_eliminated": False,
        "full_layout_coverage": False,
        "per_edge": per_edge,
        "per_decoration": per_decoration,
        "checked_prefix": checked_prefix,
        "first_parent_checkpoint_local_no": first_parent,
        "first_water_initial_recovery": first_recovery,
        "first_global_no_candidate": first_global,
    }
    return report


def compare_report(report: dict[str, object], audit: dict[str, object]) -> None:
    scalar_fields = (
        "schema_version",
        "coverage_scope",
        "status",
        "canonical_edge_count",
        "decorations_expected",
        "residual_words_expected",
        "residual_words_checked",
        "parent_checkpoint_yes_count",
        "parent_checkpoint_local_no_count",
        "past_prefix_templates_per_edge",
        "parent_local_no_recovered_count",
        "unresolved_parent_local_no_count",
        "water_initial_layouts_checked",
        "water_initial_yes_count",
        "water_initial_no_count",
        "water_initial_witnesses_replayed",
        "local_no_count",
        "global_no_count",
        "universe_complete",
        "fixed_residual_universe_complete",
        "two_source_d2_family_eliminated",
        "d2_family_eliminated",
        "entry_family_eliminated",
        "full_layout_coverage",
    )
    for field in scalar_fields:
        require(report.get(field) == audit.get(field), f"production {field} differs from independent audit")
    require(report.get("source_first_exhaust_report") == {
        "legal_source_count": 2,
        "canonical_edges": 2,
        "d2_decorations": EXPECTED_DECORATIONS,
        "edge_summed_residual_words": EXPECTED_RESIDUAL_WORDS,
    }, "source census claim drifted")

    for collection in ("per_edge", "per_decoration", "checked_prefix"):
        actual = report.get(collection)
        expected = audit.get(collection)
        require(isinstance(actual, list) and isinstance(expected, list), f"{collection} is not an array")
        require(len(actual) == len(expected), f"{collection} length differs")
        for index, (actual_row, expected_row) in enumerate(zip(actual, expected)):
            require(isinstance(actual_row, dict) and isinstance(expected_row, dict), f"{collection}[{index}] is not an object")
            for key, value in expected_row.items():
                require(actual_row.get(key) == value, f"{collection}[{index}].{key} differs")
    require(report.get("verified") == audit.get("verified"), "verified flag differs")


def run_program(program: Path, limit: int) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="c4-h7-d2-two-source-") as directory:
        subprocess.run(
            [str(program), "--limit", str(limit), "--output-dir", directory],
            check=True,
        )
        report_path = Path(directory) / "report.json"
        require(report_path.is_file(), "production executable did not write report.json")
        value = json.loads(report_path.read_text(encoding="utf-8"))
        require(isinstance(value, dict), "production report root is not an object")
        return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--program", type=Path, help="production executable for a bounded differential")
    source.add_argument("--report", type=Path, help="existing production report to compare")
    parser.add_argument("--limit", type=int, help="checkpoint fixed residual words to inspect")
    parser.add_argument("--json", type=Path, help="write the independent audit JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.program is not None:
        require(args.limit is not None, "--program requires an explicit bounded --limit")
    audit = independent_audit(args.limit)
    report: dict[str, object] | None = None
    if args.program is not None:
        report = run_program(args.program, args.limit)
    elif args.report is not None:
        value = json.loads(args.report.read_text(encoding="utf-8"))
        require(isinstance(value, dict), "report root is not an object")
        report = value
    if report is not None:
        compare_report(report, audit)
    encoded = json.dumps(audit, indent=2, sort_keys=True) + "\n"
    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(encoded, encoding="utf-8")
    elif report is None:
        print(encoded, end="")
    print(
        f"independent two-source audit: P NO {audit['parent_checkpoint_local_no_count']}/"
        f"{audit['residual_words_checked']}; water YES {audit['water_initial_yes_count']}/"
        f"{audit['water_initial_layouts_checked']}; status={audit['status']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
