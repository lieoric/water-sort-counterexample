#!/usr/bin/env python3
"""Independent audit of the three-legal-source c4/h7 D2 checkpoint family.

No production code is imported.  This file independently rebuilds the
first-exhaustion bridge, the 12 selected canonical edges, 1,535 next-run
decorations, and their 1,106,490 labelled fixed hidden futures.  Every checked
future is solved by a separate fixed-chain recursion and its YES/NO result,
safe-source mask, and deterministic winning path can be compared row-for-row
with the C++ ledger.

The initial debts in this experiment are generally nonzero.  A local NO is
therefore exported only as a parent-checkpoint residual.  It is never called a
balanced initial-layout counterexample.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
import itertools
import json
import math
from pathlib import Path
import subprocess
import tempfile
from typing import Iterable, Iterator, NoReturn, Sequence, TextIO


HEIGHT = 7
COLORS = 4
EMPTY = 2
EXPERIMENT = "c4_h7_d2_three_source_checkpoint"

EXPECTED_TERMINALS = 71
EXPECTED_LABELED_CANDIDATES = 624
EXPECTED_PARENTS = 418
EXPECTED_CANONICAL_EDGES = 429
EXPECTED_SIBLING_EDGES = 423
EXPECTED_DECORATIONS = 1_535
EXPECTED_FIXED_FUTURES = 1_106_490
EXPECTED_EDGE_ROWS: tuple[tuple[int, int, int], ...] = (
    (116, 198, 64_680),
    (117, 732, 252_252),
    (174, 263, 620_928),
    (175, 192, 51_744),
    (178, 104, 19_404),
    (184, 6, 462),
    (236, 8, 72_072),
    (237, 6, 11_088),
    (238, 4, 924),
    (242, 8, 11_088),
    (244, 6, 924),
    (248, 8, 924),
)

FNV_OFFSET = 1_469_598_103_934_665_603
FNV_PRIME = 1_099_511_628_211
TSV_HEADER = (
    "future_index\tdecoration_index\tbridge_edge\tcards\t"
    "hidden_words_bottom_to_top\tlocal_status\t"
    "safe_source_mask\tescape_columns"
)

Bucket = tuple[int, tuple[int, ...]]
State = tuple[Bucket, Bucket, Bucket, Bucket]
Action = tuple[int, int, int]
Card = tuple[int, int]
Source = tuple[int, int]
Run = tuple[int, int]
LiveColumn = tuple[int, int, tuple[Run, ...]]
Columns = tuple[
    LiveColumn | None,
    LiveColumn | None,
    LiveColumn | None,
    LiveColumn | None,
]


def fail(message: str) -> NoReturn:
    raise AssertionError(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def canonical_state(debts: Sequence[int], columns: Iterable[Source]) -> State:
    caps: list[list[int]] = [[] for _ in range(COLORS)]
    for color, cap in columns:
        caps[color].append(cap)
    result = tuple(
        sorted(
            (int(debts[color]), tuple(sorted(caps[color])))
            for color in range(COLORS)
        )
    )
    require(len(result) == COLORS, "canonicalization lost a colour")
    return result  # type: ignore[return-value]


def state_debts(state: State) -> tuple[int, int, int, int]:
    return tuple(bucket[0] for bucket in state)  # type: ignore[return-value]


def state_caps(state: State) -> tuple[tuple[int, ...], ...]:
    return tuple(bucket[1] for bucket in state)


def exposed_counts(state: State) -> tuple[int, int, int, int]:
    return tuple(debt + sum(caps) for debt, caps in state)  # type: ignore[return-value]


def source_legal(
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
    return sum(value > 0 for value in debts) <= EMPTY + exhausted


def physical_sources(state: State) -> Iterator[Source]:
    for color, (_debt, caps) in enumerate(state):
        for cap in caps:
            yield color, cap


def legal_sources(state: State, exhausted: int) -> tuple[Source, ...]:
    return tuple(
        source
        for source in physical_sources(state)
        if source_legal(state, exhausted, source[0], source[1])
    )


def state_consistent(state: State, exhausted: int) -> bool:
    if tuple(sorted(state)) != state:
        return False
    if sum(len(caps) for _debt, caps in state) != COLORS - exhausted:
        return False
    if sum(debt for debt, _caps in state) != exhausted * HEIGHT:
        return False
    if any(not 1 <= cap < HEIGHT for _debt, caps in state for cap in caps):
        return False
    exposed = exposed_counts(state)
    multiplicity = tuple(len(caps) for _debt, caps in state)
    if any(not multiplicity[color] <= exposed[color] <= HEIGHT
           for color in range(COLORS)):
        return False
    remaining = tuple(HEIGHT - count for count in exposed)
    return all(
        multiplicity[color]
        <= sum(remaining[other] for other in range(COLORS) if other != color)
        for color in range(COLORS)
    )


def is_tq_terminal(state: State) -> bool:
    if not state_consistent(state, 1) or legal_sources(state, 1):
        return False
    positive = [index for index, (debt, _caps) in enumerate(state) if debt > 0]
    nonpositive = [index for index, (debt, _caps) in enumerate(state) if debt <= 0]
    topped = [index for index, (_debt, caps) in enumerate(state) if caps]
    return len(positive) == 3 and len(nonpositive) == 1 and topped == nonpositive


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
                candidate = tuple(
                    sorted(((-energy, caps), *((value, ()) for value in positive)))
                )
                if is_tq_terminal(candidate):  # type: ignore[arg-type]
                    terminals.add(candidate)  # type: ignore[arg-type]
    return tuple(sorted(terminals))


def apply_exhausting(parent: State, exhausted: int, action: Action) -> State | None:
    old_color, old_cap, final_color = action
    if old_color == final_color or old_cap not in range(1, HEIGHT):
        return None
    if old_cap not in parent[old_color][1]:
        return None
    if not source_legal(parent, exhausted, old_color, old_cap):
        return None
    debts = list(state_debts(parent))
    caps = [list(values) for values in state_caps(parent)]
    caps[old_color].remove(old_cap)
    debts[old_color] += old_cap
    debts[final_color] += HEIGHT - old_cap
    successor = canonical_state(
        debts,
        ((color, cap) for color in range(COLORS) for cap in caps[color]),
    )
    return successor if state_consistent(successor, exhausted + 1) else None


def exhausting_actions_to(parent: State, terminal: State) -> tuple[Action, ...]:
    actions: set[Action] = set()
    for old_color, (_debt, caps) in enumerate(parent):
        for old_cap in sorted(set(caps)):
            for final_color in range(COLORS):
                action = old_color, old_cap, final_color
                if apply_exhausting(parent, 0, action) == terminal:
                    actions.add(action)
    return tuple(sorted(actions))


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
                    debts = list(state_debts(terminal))
                    caps = [list(values) for values in state_caps(terminal)]
                    debts[old_color] -= old_cap
                    debts[final_color] -= HEIGHT - old_cap
                    caps[old_color].append(old_cap)
                    tested = debts.copy()
                    tested[old_color] += old_cap
                    if sum(value > 0 for value in tested) > EMPTY:
                        continue
                    parent = canonical_state(
                        debts,
                        ((color, cap) for color in range(COLORS)
                         for cap in caps[color]),
                    )
                    if state_consistent(parent, 0):
                        labelled.append((parent, terminal))
    return len(labelled), tuple(sorted(set(labelled)))


@dataclass(frozen=True)
class Edge:
    ordinal: int
    parent: State
    terminal: State
    bad: Action
    terminal_debts: tuple[int, int, int, int]
    q_color: int
    q_caps: tuple[int, int, int]
    legal_source_count: int
    legal_q_slots: tuple[int, ...]


@dataclass(frozen=True)
class Bridge:
    edges: tuple[Edge, ...]
    terminal_count: int
    labelled_count: int
    parent_count: int
    canonical_edge_count: int


def build_bridge() -> Bridge:
    terminals = enumerate_tq_terminals()
    labelled_count, pairs = reverse_bridge(terminals)
    parents = {parent for parent, _terminal in pairs}
    edges: list[Edge] = []
    for parent, terminal in pairs:
        legal = legal_sources(parent, 0)
        actions = exhausting_actions_to(parent, terminal)
        require(len(actions) == 1, "bridge edge lacks one unique bad action")
        bad = actions[0]
        if len(legal) == 1:
            continue
        caps = [list(values) for values in state_caps(parent)]
        caps[bad[0]].remove(bad[1])
        labelled_debts = list(state_debts(parent))
        labelled_debts[bad[0]] += bad[1]
        labelled_debts[bad[2]] += HEIGHT - bad[1]
        require(
            canonical_state(
                labelled_debts,
                ((color, cap) for color in range(COLORS) for cap in caps[color]),
            ) == terminal,
            "labelled bad action does not replay to its terminal",
        )
        q_candidates = [color for color in range(COLORS) if len(caps[color]) == 3]
        require(len(q_candidates) == 1, "all-q sibling colour is ambiguous")
        q_color = q_candidates[0]
        require(all(not caps[color] for color in range(COLORS) if color != q_color),
                "terminal remainder is not an all-q triple")
        q_caps = tuple(sorted(caps[q_color]))
        legal_q_slots = tuple(
            slot for slot, cap in enumerate(q_caps)
            if source_legal(parent, 0, q_color, cap)
        )
        edges.append(
            Edge(
                len(edges), parent, terminal, bad,
                tuple(labelled_debts),  # type: ignore[arg-type]
                q_color, q_caps, len(legal), legal_q_slots,
            )
        )
    require(len(terminals) == EXPECTED_TERMINALS, "Tq terminal census drifted")
    require(labelled_count == EXPECTED_LABELED_CANDIDATES,
            "labelled reverse census drifted")
    require(len(parents) == EXPECTED_PARENTS, "canonical parent census drifted")
    require(len(pairs) == EXPECTED_CANONICAL_EDGES,
            "canonical edge census drifted")
    require(len(edges) == EXPECTED_SIBLING_EDGES, "sibling edge census drifted")
    return Bridge(tuple(edges), len(terminals), labelled_count, len(parents), len(pairs))


def cards_for(q_color: int, cap: int) -> tuple[Card, ...]:
    return tuple(
        (color, endpoint)
        for color in range(COLORS)
        if color != q_color
        for endpoint in range(cap + 1, HEIGHT + 1)
    )


def sibling_after_exhaust(edge: Edge, slot: int, card: Card) -> State:
    cap = edge.q_caps[slot]
    debts = list(state_debts(edge.parent))
    caps = [list(values) for values in state_caps(edge.parent)]
    caps[edge.q_color].remove(cap)
    debts[edge.q_color] += cap
    debts[card[0]] += HEIGHT - cap
    return canonical_state(
        debts,
        ((color, value) for color in range(COLORS) for value in caps[color]),
    )


def bad_legal_after_live(edge: Edge, slot: int, card: Card) -> bool:
    debts = list(state_debts(edge.parent))
    cap = edge.q_caps[slot]
    debts[edge.q_color] += cap
    debts[card[0]] -= cap
    return source_legal(debts, 0, edge.bad[0], edge.bad[1])


def exact_live_corner(
    edge: Edge, slot: int, chosen: tuple[Card, Card, Card], n_value: int
) -> bool:
    card = chosen[slot]
    if n_value != 0 or card[1] != 3:
        return False
    return all(
        edge.q_caps[other] == 1 and chosen[other] == (card[0], 3)
        for other in range(3) if other != slot
    )


def refined_d2(edge: Edge, chosen: tuple[Card, Card, Card]) -> bool:
    direct = n_ge_3 = n_le_2 = nonhandoff = False
    for slot in edge.legal_q_slots:
        card = chosen[slot]
        cap = edge.q_caps[slot]
        if card[1] == HEIGHT:
            direct = direct or not is_tq_terminal(sibling_after_exhaust(edge, slot, card))
            continue
        if not bad_legal_after_live(edge, slot, card):
            nonhandoff = True
            continue
        n_value = cap - edge.terminal_debts[card[0]]
        require(n_value >= 0, "live handoff produced negative N")
        if n_value >= 3:
            n_ge_3 = True
        elif not exact_live_corner(edge, slot, chosen, n_value):
            n_le_2 = True
    return not direct and not n_ge_3 and not n_le_2 and nonhandoff


def multinomial(counts: Sequence[int]) -> int:
    if any(value < 0 for value in counts):
        return 0
    result = math.factorial(sum(counts))
    for value in counts:
        result //= math.factorial(value)
    return result


def completion_count(
    residual: tuple[int, int, int, int],
    tails: tuple[int, int, int],
    chosen: tuple[Card, Card, Card],
) -> int:
    if any(value < 0 for value in residual) or sum(residual) != sum(tails):
        return 0
    active_slots = tuple(slot for slot, length in enumerate(tails) if length)
    result = 0
    for boundaries in itertools.product(range(COLORS), repeat=len(active_slots)):
        counts = list(residual)
        valid = True
        for slot, color in zip(active_slots, boundaries):
            if color == chosen[slot][0] or counts[color] == 0:
                valid = False
                break
            counts[color] -= 1
        if valid:
            result += multinomial(counts)
    return result


@dataclass(frozen=True)
class Decoration:
    ordinal: int
    edge: Edge
    chosen: tuple[Card, Card, Card]
    residual: tuple[int, int, int, int]
    tails: tuple[int, int, int]
    weight: int


def derive_decorations() -> tuple[Bridge, tuple[Decoration, ...]]:
    bridge = build_bridge()
    decorations: list[Decoration] = []
    rows: dict[int, list[int]] = {}
    for edge in bridge.edges:
        if edge.legal_source_count != 3:
            continue
        options = tuple(cards_for(edge.q_color, cap) for cap in edge.q_caps)
        for raw in itertools.product(*options):
            chosen = tuple(raw)  # type: ignore[assignment]
            residual = [HEIGHT - count for count in exposed_counts(edge.parent)]
            residual[edge.bad[2]] -= HEIGHT - edge.bad[1]
            tails: list[int] = []
            for cap, card in zip(edge.q_caps, chosen):
                residual[card[0]] -= card[1] - cap
                tails.append(HEIGHT - card[1])
            residual_tuple = tuple(residual)  # type: ignore[assignment]
            tails_tuple = tuple(tails)  # type: ignore[assignment]
            weight = completion_count(residual_tuple, tails_tuple, chosen)
            if not weight or not refined_d2(edge, chosen):
                continue
            decoration = Decoration(
                len(decorations), edge, chosen,
                residual_tuple, tails_tuple, weight,
            )
            decorations.append(decoration)
            row = rows.setdefault(edge.ordinal, [0, 0])
            row[0] += 1
            row[1] += weight
    require(tuple((edge, *rows.get(edge, [0, 0])) for edge, _d, _w in EXPECTED_EDGE_ROWS)
            == EXPECTED_EDGE_ROWS, "selected edge ledger drifted")
    require(len(decorations) == EXPECTED_DECORATIONS, "decoration census drifted")
    require(sum(item.weight for item in decorations) == EXPECTED_FIXED_FUTURES,
            "fixed-future weight drifted")
    return bridge, tuple(decorations)


def next_multiset_permutation(values: list[int]) -> bool:
    pivot = len(values) - 2
    while pivot >= 0 and values[pivot] >= values[pivot + 1]:
        pivot -= 1
    if pivot < 0:
        return False
    successor = len(values) - 1
    while values[successor] <= values[pivot]:
        successor -= 1
    values[pivot], values[successor] = values[successor], values[pivot]
    values[pivot + 1:] = reversed(values[pivot + 1:])
    return True


def fixed_futures(
    decoration: Decoration,
) -> Iterator[tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]]:
    remaining = list(decoration.residual)
    boundaries = [-1, -1, -1]
    produced = 0

    def choose(slot: int) -> Iterator[
        tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]
    ]:
        while slot < 3 and decoration.tails[slot] == 0:
            slot += 1
        if slot < 3:
            for color in range(COLORS):
                if color == decoration.chosen[slot][0] or remaining[color] == 0:
                    continue
                remaining[color] -= 1
                boundaries[slot] = color
                yield from choose(slot + 1)
                boundaries[slot] = -1
                remaining[color] += 1
            return

        pool = sorted(
            color for color in range(COLORS) for _ in range(remaining[color])
        )
        free_slots = sum(max(0, length - 1) for length in decoration.tails)
        require(len(pool) == free_slots, "free-tail pool size drifted")
        while True:
            cursor = 0
            words: list[tuple[int, ...]] = []
            for q_slot in range(3):
                length = decoration.tails[q_slot]
                free_top: list[int] = []
                if length:
                    require(boundaries[q_slot] >= 0, "free tail lacks boundary colour")
                    free_top.append(boundaries[q_slot])
                    free_top.extend(pool[cursor:cursor + length - 1])
                    cursor += length - 1
                cap = decoration.edge.q_caps[q_slot]
                card = decoration.chosen[q_slot]
                forced = (card[0],) * (card[1] - cap)
                words.append(tuple(reversed(free_top)) + forced)
            require(cursor == len(pool), "free-tail permutation was not consumed")
            yield tuple(words)  # type: ignore[return-value]
            if not next_multiset_permutation(pool):
                break

    for future in choose(0):
        produced += 1
        yield future
    require(produced == decoration.weight,
            f"decoration {decoration.ordinal} emitted {produced}, expected {decoration.weight}")


def runs(cells: Iterable[int]) -> tuple[Run, ...]:
    result: list[Run] = []
    for color in cells:
        if result and result[-1][0] == color:
            result[-1] = color, result[-1][1] + 1
        else:
            result.append((color, 1))
    return tuple(result)


def fixture(
    decoration: Decoration,
    q_words: tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]],
) -> tuple[tuple[int, int, int, int], tuple[Source, ...], tuple[tuple[int, ...], ...]]:
    edge = decoration.edge
    sources: tuple[Source, ...] = (
        (edge.bad[0], edge.bad[1]),
        *((edge.q_color, cap) for cap in edge.q_caps),
    )
    words: tuple[tuple[int, ...], ...] = (
        (edge.bad[2],) * (HEIGHT - edge.bad[1]),
        *q_words,
    )
    used = Counter(color for word in words for color in word)
    hidden = tuple(HEIGHT - count for count in exposed_counts(edge.parent))
    require(tuple(used[color] for color in range(COLORS)) == hidden,
            "fixture inventory does not realize its checkpoint")
    for source, word in zip(sources, words):
        require(len(word) == HEIGHT - source[1], "fixture column length drifted")
        require(word and word[-1] != source[0], "fixture merged into current top")
    return state_debts(edge.parent), sources, words


def solve_fixture(
    debts: tuple[int, int, int, int],
    sources: tuple[Source, ...],
    words_bottom_to_top: tuple[tuple[int, ...], ...],
) -> tuple[bool, int, str]:
    columns: Columns = tuple(
        (source[0], source[1], runs(reversed(word)))
        for source, word in zip(sources, words_bottom_to_top)
    )  # type: ignore[assignment]

    def step(
        current_debts: tuple[int, int, int, int],
        exhausted: int,
        current_columns: Columns,
        source_index: int,
    ) -> tuple[tuple[int, int, int, int], int, Columns] | None:
        column = current_columns[source_index]
        if column is None:
            return None
        top, cap, future = column
        if not future or not source_legal(current_debts, exhausted, top, cap):
            return None
        next_color, length = future[0]
        require(next_color != top and length > 0, "fixed chain contains a merged edge")
        child_debts = list(current_debts)
        child_debts[top] += cap
        child_columns = list(current_columns)
        child_exhausted = exhausted
        if len(future) == 1:
            require(cap + length == HEIGHT, "final run misses height seven")
            child_debts[next_color] += length
            child_columns[source_index] = None
            child_exhausted += 1
        else:
            require(cap + length < HEIGHT, "nonfinal run reaches height seven")
            child_debts[next_color] -= cap
            child_columns[source_index] = (next_color, cap + length, future[1:])
        return (
            tuple(child_debts),  # type: ignore[arg-type]
            child_exhausted,
            tuple(child_columns),  # type: ignore[arg-type]
        )

    @lru_cache(maxsize=None)
    def win(
        current_debts: tuple[int, int, int, int],
        exhausted: int,
        current_columns: Columns,
    ) -> bool:
        if exhausted >= EMPTY:
            return True
        return any(
            child is not None and win(*child)
            for source_index in range(COLORS)
            for child in (step(current_debts, exhausted, current_columns, source_index),)
        )

    solvable = win(debts, 0, columns)
    mask = 0
    for source_index in range(COLORS):
        child = step(debts, 0, columns, source_index)
        if child is not None and win(*child):
            mask |= 1 << source_index
    path: list[int] = []
    current = (debts, 0, columns)
    if solvable:
        while current[1] < EMPTY:
            advanced = False
            for source_index in range(COLORS):
                child = step(*current, source_index)
                if child is not None and win(*child):
                    path.append(source_index)
                    current = child
                    advanced = True
                    break
            require(advanced, "winning fixture has no replayable successor")
    require(bool(mask) == solvable, "safe mask disagrees with fixed-future outcome")
    if solvable:
        require(current[1] >= EMPTY and path, "winning path did not reach the goal")
    else:
        require(mask == 0 and not path, "local NO has a winning witness")
    return solvable, mask, "".join(str(source) for source in path)


def fnv_row(hash_value: int, row: str) -> int:
    for value in (row + "\n").encode("ascii"):
        hash_value ^= value
        hash_value = (hash_value * FNV_PRIME) & ((1 << 64) - 1)
    return hash_value


def sample(
    future_index: int,
    decoration: Decoration,
    words: tuple[tuple[int, ...], ...],
    solvable: bool,
    mask: int,
    path: str,
) -> dict[str, object]:
    return {
        "future_index": future_index,
        "decoration_index": decoration.ordinal,
        "bridge_edge": decoration.edge.ordinal,
        "local_status": "YES" if solvable else "NO",
        "safe_source_mask": mask,
        "escape_columns": path,
        "hidden_words_bottom_to_top": [
            "".join(str(color) for color in word) for word in words
        ],
    }


def production_no_object(
    row_sample: dict[str, object], decoration: Decoration
) -> dict[str, object]:
    edge = decoration.edge
    return {
        "future_index": row_sample["future_index"],
        "decoration_index": decoration.ordinal,
        "bridge_edge": edge.ordinal,
        "parent_debts": list(state_debts(edge.parent)),
        "bad_source": list(edge.bad),
        "q_color": edge.q_color,
        "q_caps": list(edge.q_caps),
        "cards": [list(card) for card in decoration.chosen],
        "hidden_words_bottom_to_top": row_sample["hidden_words_bottom_to_top"],
        "local_status": "NO",
        "safe_source_mask": 0,
    }


def independent_no_object(
    row_sample: dict[str, object], decoration: Decoration
) -> dict[str, object]:
    return {
        **production_no_object(row_sample, decoration),
        "scope": "nonzero_debt_parent_checkpoint_fixed_future",
        "zero_debt_past_restored": False,
        "global_counterexample": False,
    }


class ProductionRows:
    def __init__(self, tsv_path: Path | None, local_no_path: Path | None):
        self.tsv: TextIO | None = None
        self.local_no: TextIO | None = None
        if tsv_path is not None:
            self.tsv = tsv_path.open("r", encoding="utf-8", newline="")
            require(self.tsv.readline().rstrip("\r\n") == TSV_HEADER,
                    "production TSV header drifted")
        if local_no_path is not None:
            self.local_no = local_no_path.open("r", encoding="utf-8")

    def compare_row(self, expected: str) -> None:
        if self.tsv is None:
            return
        actual = self.tsv.readline()
        require(actual != "", "production TSV ended before the independent universe")
        require(actual.rstrip("\r\n") == expected,
                f"production fixed-future row differs:\nactual={actual.rstrip()}\nexpected={expected}")

    def compare_local_no(self, expected: dict[str, object]) -> None:
        if self.local_no is None:
            return
        raw = self.local_no.readline()
        require(raw != "", "production local-NO ledger ended early")
        actual = json.loads(raw)
        require(actual == expected,
                f"production local-NO row differs: {actual} != {expected}")

    def finish(self) -> None:
        if self.tsv is not None:
            require(self.tsv.readline() == "", "production TSV has unverified extra rows")
            self.tsv.close()
        if self.local_no is not None:
            require(self.local_no.readline() == "",
                    "production local-NO ledger has unverified extra rows")
            self.local_no.close()


def audit_status(complete: bool, local_no: int) -> str:
    if not complete:
        return "INCOMPLETE"
    if local_no:
        return "LOCAL_NO_RESIDUALS_EXPORTED"
    return "THREE_SOURCE_D2_CHECKPOINT_FAMILY_ELIMINATED"


def audit(
    target: int,
    production_rows: ProductionRows | None = None,
    independent_local_no: Path | None = None,
) -> dict[str, object]:
    require(0 < target <= EXPECTED_FIXED_FUTURES,
            "fixed-future limit is outside the exact universe")
    bridge, decorations = derive_decorations()
    expected_by_edge = {edge: (count, weight)
                        for edge, count, weight in EXPECTED_EDGE_ROWS}
    per_edge: dict[int, dict[str, object]] = {
        edge: {
            "bridge_edge": edge,
            "decorations": count,
            "fixed_futures_expected": weight,
            "fixed_futures_checked": 0,
            "local_yes": 0,
            "local_no": 0,
            "safe_mask_distribution": Counter(),
        }
        for edge, (count, weight) in expected_by_edge.items()
    }
    local_output: TextIO | None = None
    if independent_local_no is not None:
        independent_local_no.parent.mkdir(parents=True, exist_ok=True)
        local_output = independent_local_no.open("w", encoding="utf-8", newline="\n")

    checked = local_yes = local_no = replayed = 0
    first_yes: dict[str, object] | None = None
    first_no: dict[str, object] | None = None
    hash_value = FNV_OFFSET
    try:
        for decoration in decorations:
            if checked >= target:
                break
            emitted = 0
            for q_words in fixed_futures(decoration):
                if checked >= target:
                    break
                emitted += 1
                debts, sources, words = fixture(decoration, q_words)
                solvable, mask, path = solve_fixture(debts, sources, words)
                row_sample = sample(
                    checked, decoration, words, solvable, mask, path
                )
                cards_text = ",".join(
                    f"{color}:{endpoint}" for color, endpoint in decoration.chosen
                )
                words_text = ",".join(row_sample["hidden_words_bottom_to_top"])
                row = (
                    f"{checked}\t{decoration.ordinal}\t{decoration.edge.ordinal}\t"
                    f"{cards_text}\t{words_text}\t"
                    f"{'YES' if solvable else 'NO'}\t{mask}\t{path}"
                )
                if production_rows is not None:
                    production_rows.compare_row(row)
                hash_value = fnv_row(hash_value, row)
                edge_row = per_edge[decoration.edge.ordinal]
                edge_row["fixed_futures_checked"] += 1  # type: ignore[operator]
                masks: Counter[int] = edge_row["safe_mask_distribution"]  # type: ignore[assignment]
                masks[mask] += 1
                if solvable:
                    local_yes += 1
                    replayed += 1
                    edge_row["local_yes"] += 1  # type: ignore[operator]
                    if first_yes is None:
                        first_yes = row_sample
                else:
                    local_no += 1
                    edge_row["local_no"] += 1  # type: ignore[operator]
                    if first_no is None:
                        first_no = row_sample
                    production_object = production_no_object(row_sample, decoration)
                    if production_rows is not None:
                        production_rows.compare_local_no(production_object)
                    if local_output is not None:
                        local_output.write(json.dumps(
                            independent_no_object(row_sample, decoration),
                            sort_keys=True,
                        ) + "\n")
                checked += 1
                if checked % 100_000 == 0:
                    print(
                        f"independent progress fixed_futures={checked}/{target} "
                        f"local_no={local_no}",
                        flush=True,
                    )
            if checked < target:
                require(emitted == decoration.weight,
                        f"decoration {decoration.ordinal} coverage drifted")
    finally:
        if local_output is not None:
            local_output.close()
    require(checked == target, "independent audit stopped before its limit")
    require(local_yes + local_no == checked, "local YES/NO partition drifted")
    require(replayed == local_yes, "a local YES path was not replayed")
    if production_rows is not None:
        production_rows.finish()

    edge_rows: list[dict[str, object]] = []
    for edge, _count, _weight in EXPECTED_EDGE_ROWS:
        row = per_edge[edge]
        masks: Counter[int] = row["safe_mask_distribution"]  # type: ignore[assignment]
        row["safe_mask_distribution"] = {
            str(mask): count for mask, count in sorted(masks.items())
        }
        edge_rows.append(row)
    complete = checked == EXPECTED_FIXED_FUTURES
    return {
        "schema_version": 1,
        "experiment": "independent_c4_h7_d2_three_source_checkpoint_audit",
        "production_experiment": EXPERIMENT,
        "scope": {
            "parent_checkpoint_only": True,
            "fixed_hidden_futures": True,
            "zero_debt_past_restored": False,
            "global_counterexamples_claimed": False,
        },
        "bridge_reconstruction": {
            "tq_terminals": bridge.terminal_count,
            "labeled_candidates": bridge.labelled_count,
            "canonical_parents": bridge.parent_count,
            "canonical_edges": bridge.canonical_edge_count,
            "sibling_edges": len(bridge.edges),
        },
        "universe": {
            "selected_edges": len(EXPECTED_EDGE_ROWS),
            "decorations": len(decorations),
            "labeled_fixed_futures": sum(item.weight for item in decorations),
        },
        "run": {
            "universe_complete": complete,
            "fixed_futures_checked": checked,
            "local_yes": local_yes,
            "local_no": local_no,
            "winning_paths_replayed": replayed,
        },
        "status": audit_status(complete, local_no),
        "result_rows_fnv1a64": f"{hash_value:016x}",
        "first_local_yes": first_yes,
        "first_local_no": first_no,
        "per_edge": edge_rows,
        "claim_boundary": (
            "A local NO is only a nonzero-debt parent-checkpoint residual; "
            "no zero-debt past or balanced initial-layout NO is asserted."
        ),
    }


def load_report(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), "production report root is not an object")
    return value


def compare_report(report: dict[str, object], independent: dict[str, object]) -> None:
    require(report.get("experiment") == EXPERIMENT, "production experiment drifted")
    for field in ("bridge_reconstruction", "universe", "first_local_yes", "first_local_no"):
        require(report.get(field) == independent.get(field),
                f"production {field} differs from the independent audit")
    independent_run = independent["run"]
    production_run = report.get("run")
    require(isinstance(independent_run, dict) and isinstance(production_run, dict),
            "run section is not an object")
    for field in (
        "universe_complete", "fixed_futures_checked", "local_yes",
        "local_no", "winning_paths_replayed",
    ):
        require(production_run.get(field) == independent_run.get(field),
                f"production run.{field} differs")
    require(report.get("status") == independent.get("status"),
            "production status differs from the conservative independent status")
    ledgers = report.get("ledgers")
    require(isinstance(ledgers, dict), "production ledgers section is missing")
    require(ledgers.get("result_rows_fnv1a64") == independent.get("result_rows_fnv1a64"),
            "production fixed-future ledger hash differs")
    actual_edges = report.get("per_edge")
    expected_edges = independent.get("per_edge")
    require(isinstance(actual_edges, list) and isinstance(expected_edges, list)
            and len(actual_edges) == len(expected_edges), "per-edge rows drifted")
    for actual, expected in zip(actual_edges, expected_edges):
        require(isinstance(actual, dict) and isinstance(expected, dict),
                "per-edge row is not an object")
        for field in (
            "bridge_edge", "decorations", "fixed_futures_expected",
            "fixed_futures_checked", "local_yes", "local_no",
            "safe_mask_distribution",
        ):
            require(actual.get(field) == expected.get(field),
                    f"edge {expected.get('bridge_edge')} field {field} differs")
    scope = report.get("scope")
    claims = report.get("claims")
    require(scope == {
        "parent_checkpoint_only": True,
        "fixed_hidden_futures": True,
        "zero_debt_past_restored": False,
        "full_h7_theorem": False,
    }, "production scope overclaims coverage")
    require(isinstance(claims, dict)
            and claims.get("zero_debt_initial_family_eliminated") is False
            and claims.get("universal_c4_h7_solvability") is False,
            "production claims turn a checkpoint result into a global theorem")


def production_paths(report_path: Path) -> tuple[Path, Path]:
    report = load_report(report_path)
    ledgers = report.get("ledgers")
    require(isinstance(ledgers, dict), "report does not name its ledgers")
    tsv = ledgers.get("fixed_future_results")
    local_no = ledgers.get("local_no")
    require(isinstance(tsv, str) and isinstance(local_no, str),
            "report ledger names are invalid")
    return report_path.parent / tsv, report_path.parent / local_no


def run_program(program: Path, limit: int) -> tuple[dict[str, object], dict[str, object]]:
    with tempfile.TemporaryDirectory(prefix="c4-h7-d2-three-source-") as directory:
        output = Path(directory)
        subprocess.run(
            [str(program), "--limit", str(limit), "--output-dir", str(output)],
            check=True,
        )
        report_path = output / "report.json"
        report = load_report(report_path)
        tsv, local_no = production_paths(report_path)
        rows = ProductionRows(tsv, local_no)
        independent = audit(limit, rows)
        compare_report(report, independent)
        return report, independent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--program", type=Path,
                        help="production executable for a bounded row differential")
    source.add_argument("--report", type=Path,
                        help="existing production report and ledgers to compare")
    parser.add_argument("--limit", type=int,
                        help="fixed futures to inspect; required with --program")
    parser.add_argument("--json", type=Path, help="write the independent report")
    parser.add_argument("--local-no-ledger", type=Path,
                        help="write explicitly local-only independent NO rows")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    production: dict[str, object] | None = None
    if args.program is not None:
        require(args.limit is not None and args.limit > 0,
                "--program requires a positive --limit")
        production, independent = run_program(args.program, args.limit)
    elif args.report is not None:
        production = load_report(args.report)
        run_section = production.get("run")
        require(isinstance(run_section, dict), "production run section is missing")
        target = run_section.get("fixed_futures_checked")
        require(isinstance(target, int) and not isinstance(target, bool) and target > 0,
                "production checked count is invalid")
        tsv, local_no = production_paths(args.report)
        independent = audit(
            target,
            ProductionRows(tsv, local_no),
            args.local_no_ledger,
        )
        compare_report(production, independent)
    else:
        require(args.limit is not None and args.limit > 0,
                "standalone audit requires an explicit positive --limit")
        independent = audit(args.limit, independent_local_no=args.local_no_ledger)

    encoded = json.dumps(independent, indent=2, sort_keys=True) + "\n"
    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(encoded, encoding="utf-8")
    elif production is None:
        print(encoded, end="")
    run_section = independent["run"]
    print(
        "independent three-source checkpoint audit: "
        f"checked={run_section['fixed_futures_checked']}/"
        f"{independent['universe']['labeled_fixed_futures']} "
        f"local_yes={run_section['local_yes']} local_no={run_section['local_no']} "
        f"status={independent['status']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
