#!/usr/bin/env python3
"""Independent audit for the c=4, k=2, h=7 Tq sibling-fork census.

This file deliberately does not import the production enumerator or the
earlier macro-reconnaissance script.  It rebuilds the numerical border model
from the Ito source test, enumerates the same-z entrances to Tq, commits the
next run of both sibling sources simultaneously, and counts color-balanced
fixed futures by a separate dynamic program.

With ``--program`` the checker also runs a bounded production job, validates
its JSON report, and independently replays every concrete witness emitted by
that report.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import itertools
import json
import subprocess
import tempfile
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Iterator, Sequence


HEIGHT = 7
COLORS = 4
EMPTY_COLUMNS = 2

EXPECTED_TERMINALS = 71
EXPECTED_LIVE_PARENTS = 80
EXPECTED_LIVE_EDGES = 116
EXPECTED_SIBLING_PARENTS = 23
EXPECTED_BAD_EDGES = 32
EXPECTED_RAW_SINGLE_OUTCOMES = 840
EXPECTED_RAW_DECORATIONS = 5_526
EXPECTED_FEASIBLE_DECORATIONS = 2_958
EXPECTED_FIXED_FUTURES = 10_073_448
EXPECTED_MIN_EDGE_FUTURES = 924
EXPECTED_MAX_EDGE_FUTURES = 3_963_960
EXPECTED_CHECKPOINT_SAMPLES = 3 * EXPECTED_BAD_EDGES

Bucket = tuple[int, tuple[int, ...]]
State = tuple[Bucket, Bucket, Bucket, Bucket]
Action = tuple[int, int, int, int]  # old color/cap, new color/cap
Card = tuple[int, int]  # next color, cumulative endpoint
Run = tuple[int, int]
LiveColumn = tuple[int, int, tuple[Run, ...]]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def canonical_state(
    debts: Sequence[int], columns: Iterable[tuple[int, int]]
) -> State:
    """Quotient labeled colors and active columns by sorting their buckets."""

    caps_by_color: list[list[int]] = [[] for _ in range(COLORS)]
    for color, cap in columns:
        caps_by_color[color].append(cap)
    buckets = tuple(
        sorted(
            (int(debts[color]), tuple(sorted(caps_by_color[color])))
            for color in range(COLORS)
        )
    )
    require(len(buckets) == COLORS, "canonical state lost a color")
    return buckets  # type: ignore[return-value]


def exposed_counts(state: State) -> tuple[int, int, int, int]:
    return tuple(debt + sum(caps) for debt, caps in state)  # type: ignore[return-value]


def state_is_consistent(state: State, exhausted: int) -> bool:
    """Check all bounded numerical and hidden-suffix realization conditions."""

    if tuple(sorted(state)) != state:
        return False
    if sum(len(caps) for _, caps in state) != COLORS - exhausted:
        return False
    if sum(debt for debt, _ in state) != exhausted * HEIGHT:
        return False
    if any(cap < 1 or cap >= HEIGHT for _, caps in state for cap in caps):
        return False

    exposed = exposed_counts(state)
    top_multiplicity = tuple(len(caps) for _, caps in state)
    if any(
        not top_multiplicity[color] <= exposed[color] <= HEIGHT
        for color in range(COLORS)
    ):
        return False

    # Each active column has a nonempty suffix whose first item is different
    # from its current top.  This is a forbidden-diagonal token assignment.
    # With four colors the singleton Hall inequalities below are sufficient:
    # any set containing two different forbidden colors can use all colors.
    remaining = tuple(HEIGHT - count for count in exposed)
    return all(
        top_multiplicity[color]
        <= sum(remaining[other] for other in range(COLORS) if other != color)
        for color in range(COLORS)
    )


def source_is_legal(state: State, exhausted: int, color: int, cap: int) -> bool:
    adjusted = [debt for debt, _ in state]
    adjusted[color] += cap
    return sum(value > 0 for value in adjusted) <= EMPTY_COLUMNS + exhausted


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


def apply_live_action(state: State, action: Action) -> State | None:
    """Apply one nonexhausting border event at z=1 and recanonicalize."""

    old_color, old_cap, new_color, new_cap = action
    if old_color == new_color or not (1 <= old_cap < new_cap < HEIGHT):
        return None
    if old_color not in range(COLORS) or new_color not in range(COLORS):
        return None
    if old_cap not in state[old_color][1]:
        return None
    if not source_is_legal(state, 1, old_color, old_cap):
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
    return successor if state_is_consistent(successor, 1) else None


def actions_to(parent: State, terminal: State) -> tuple[Action, ...]:
    actions: list[Action] = []
    for old_color, (_, caps) in enumerate(parent):
        for old_cap in sorted(set(caps)):
            if not source_is_legal(parent, 1, old_color, old_cap):
                continue
            for new_color in range(COLORS):
                if new_color == old_color:
                    continue
                for new_cap in range(old_cap + 1, HEIGHT):
                    action = old_color, old_cap, new_color, new_cap
                    if apply_live_action(parent, action) == terminal:
                        actions.append(action)
    return tuple(actions)


def enumerate_tq_terminals() -> tuple[State, ...]:
    """Enumerate Tq directly from its debt and all-q-top definition."""

    terminals: set[State] = set()
    for magnitude in range(3):
        for caps in itertools.combinations_with_replacement(range(1, HEIGHT), 3):
            if min(caps) <= magnitude:
                continue
            if sum(caps) - magnitude > HEIGHT:
                continue
            for positives in itertools.combinations_with_replacement(
                range(1, HEIGHT + 1), 3
            ):
                if sum(positives) - magnitude != HEIGHT:
                    continue
                state = tuple(
                    sorted(
                        ((-magnitude, caps),)
                        + tuple((debt, ()) for debt in positives)
                    )
                )
                state = state  # retain a narrow inferred tuple type
                if not state_is_consistent(state, 1):  # type: ignore[arg-type]
                    continue
                if legal_sources(state, 1):  # type: ignore[arg-type]
                    continue
                terminals.add(state)  # type: ignore[arg-type]
    return tuple(sorted(terminals))


def reverse_live_pairs(terminals: Sequence[State]) -> tuple[tuple[State, State], ...]:
    """Invert every possible live edge and retain those that replay forward."""

    pairs: set[tuple[State, State]] = set()
    for terminal in terminals:
        q_color = next(
            color for color, (_, caps) in enumerate(terminal) if len(caps) == 3
        )
        for new_cap in sorted(set(terminal[q_color][1])):
            for old_color in range(COLORS):
                if old_color == q_color:
                    continue
                for old_cap in range(1, new_cap):
                    debts = [debt for debt, _ in terminal]
                    caps_by_color = [list(caps) for _, caps in terminal]
                    caps_by_color[q_color].remove(new_cap)
                    caps_by_color[old_color].append(old_cap)
                    debts[old_color] -= old_cap
                    debts[q_color] += old_cap
                    parent = canonical_state(
                        debts,
                        (
                            (color, cap)
                            for color, caps in enumerate(caps_by_color)
                            for cap in caps
                        ),
                    )
                    if not state_is_consistent(parent, 1):
                        continue
                    if actions_to(parent, terminal):
                        pairs.add((parent, terminal))
    return tuple(sorted(pairs))


@dataclass(frozen=True)
class BadEdge:
    parent: State
    terminal: State
    action: Action
    sibling_caps: tuple[int, int]

    def key(self) -> tuple[State, State, Action]:
        return self.parent, self.terminal, self.action


def sibling_bad_edges(
    pairs: Sequence[tuple[State, State]],
) -> tuple[BadEdge, ...]:
    result: list[BadEdge] = []
    for parent, terminal in pairs:
        legal = legal_sources(parent, 1)
        if len(legal) < 2:
            continue
        actions = actions_to(parent, terminal)
        require(len(actions) == 1, "sibling edge has ambiguous canonical action")
        action = actions[0]
        q_color = action[2]
        require(
            tuple(cap for color, cap in legal if color == q_color)
            == parent[q_color][1],
            "the two q siblings are not exactly the q-top columns",
        )
        require(len(parent[q_color][1]) == 2, "sibling parent does not have two q columns")
        require(len(legal) == 3, "sibling parent does not have exactly three legal sources")
        result.append(BadEdge(parent, terminal, action, parent[q_color][1]))
    return tuple(sorted(result, key=BadEdge.key))


def next_cards(q_color: int, cap: int) -> tuple[Card, ...]:
    return tuple(
        (color, endpoint)
        for color in range(COLORS)
        if color != q_color
        for endpoint in range(cap + 1, HEIGHT + 1)
    )


def remaining_tail_word_count(
    edge: BadEdge, cards: tuple[Card, Card]
) -> int:
    """Count labeled hidden tails realizing one simultaneous decoration.

    The bad edge commits its old source's q run.  Each card commits the next
    run of one labeled q sibling.  If a committed run is nonfinal, the first
    cell below it must have a different color; all later tail cells are free.
    """

    old_color, old_cap, q_color, q_endpoint = edge.action
    del old_color
    exposed = exposed_counts(edge.parent)
    remaining = [HEIGHT - count for count in exposed]

    remaining[q_color] -= q_endpoint - old_cap
    tails: list[tuple[int, int]] = [(HEIGHT - q_endpoint, q_color)]
    for cap, (next_color, endpoint) in zip(edge.sibling_caps, cards):
        require(next_color != q_color, "q sibling was decorated with another q run")
        require(cap < endpoint <= HEIGHT, "next-run endpoint is out of range")
        remaining[next_color] -= endpoint - cap
        tails.append((HEIGHT - endpoint, next_color))
    if any(count < 0 for count in remaining):
        return 0

    forbidden_by_position: list[int | None] = []
    for length, preceding_color in tails:
        if length == 0:
            continue
        forbidden_by_position.append(preceding_color)
        forbidden_by_position.extend([None] * (length - 1))
    if len(forbidden_by_position) != sum(remaining):
        return 0

    @lru_cache(maxsize=None)
    def count_words(position: int, counts: tuple[int, int, int, int]) -> int:
        if position == len(forbidden_by_position):
            return int(not any(counts))
        forbidden = forbidden_by_position[position]
        total = 0
        for color, count in enumerate(counts):
            if count == 0 or color == forbidden:
                continue
            child = list(counts)
            child[color] -= 1
            total += count_words(position + 1, tuple(child))  # type: ignore[arg-type]
        return total

    return count_words(0, tuple(remaining))  # type: ignore[arg-type]


def tail_problem(
    edge: BadEdge, cards: tuple[Card, Card]
) -> tuple[tuple[int, int, int, int], tuple[tuple[int, int], ...]] | None:
    """Return residual color counts and (length, forbidden-first-color) tails."""

    _, old_cap, q_color, q_endpoint = edge.action
    remaining = [HEIGHT - count for count in exposed_counts(edge.parent)]
    remaining[q_color] -= q_endpoint - old_cap
    tails: list[tuple[int, int]] = [(HEIGHT - q_endpoint, q_color)]
    for cap, (next_color, endpoint) in zip(edge.sibling_caps, cards):
        remaining[next_color] -= endpoint - cap
        tails.append((HEIGHT - endpoint, next_color))
    if any(count < 0 for count in remaining):
        return None
    if sum(length for length, _ in tails) != sum(remaining):
        return None
    return tuple(remaining), tuple(tails)  # type: ignore[return-value]


def one_tail_completion(
    edge: BadEdge, cards: tuple[Card, Card], *, reverse: bool = False
) -> tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]] | None:
    """Find the lexicographically first (or last) labeled residual words."""

    problem = tail_problem(edge, cards)
    if problem is None:
        return None
    remaining, tails = problem
    forbidden: list[int | None] = []
    for length, preceding in tails:
        if length:
            forbidden.append(preceding)
            forbidden.extend([None] * (length - 1))

    color_order = tuple(reversed(range(COLORS))) if reverse else tuple(range(COLORS))

    @lru_cache(maxsize=None)
    def suffix(
        position: int, counts: tuple[int, int, int, int]
    ) -> tuple[int, ...] | None:
        if position == len(forbidden):
            return () if not any(counts) else None
        for color in color_order:
            if counts[color] == 0 or color == forbidden[position]:
                continue
            child = list(counts)
            child[color] -= 1
            continuation = suffix(position + 1, tuple(child))  # type: ignore[arg-type]
            if continuation is not None:
                return (color,) + continuation
        return None

    word = suffix(0, remaining)
    if word is None:
        return None
    output: list[tuple[int, ...]] = []
    cursor = 0
    for length, _ in tails:
        output.append(word[cursor : cursor + length])
        cursor += length
    require(cursor == len(word), "tail completion split lost cells")
    return tuple(output)  # type: ignore[return-value]


def tail_completions(
    edge: BadEdge, cards: tuple[Card, Card]
) -> Iterator[tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]]:
    """Yield every labeled residual tuple in lexicographic cell order."""

    problem = tail_problem(edge, cards)
    if problem is None:
        return
    remaining, tails = problem
    forbidden: list[int | None] = []
    for length, preceding in tails:
        if length:
            forbidden.append(preceding)
            forbidden.extend([None] * (length - 1))

    cells = [-1] * len(forbidden)

    def visit(
        position: int, counts: tuple[int, int, int, int]
    ) -> Iterator[tuple[int, ...]]:
        if position == len(forbidden):
            if not any(counts):
                yield tuple(cells)
            return
        for color in range(COLORS):
            if counts[color] == 0 or color == forbidden[position]:
                continue
            child = list(counts)
            child[color] -= 1
            cells[position] = color
            yield from visit(position + 1, tuple(child))  # type: ignore[arg-type]

    for word in visit(0, remaining):
        output: list[tuple[int, ...]] = []
        cursor = 0
        for length, _ in tails:
            output.append(word[cursor : cursor + length])
            cursor += length
        yield tuple(output)  # type: ignore[misc]


def color_runs(word: Iterable[int]) -> tuple[Run, ...]:
    runs: list[Run] = []
    for color in word:
        if runs and runs[-1][0] == color:
            runs[-1] = color, runs[-1][1] + 1
        else:
            runs.append((color, 1))
    return tuple(runs)


def residual_checkpoint(
    edge: BadEdge,
    cards: tuple[Card, Card],
    tails: tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]],
) -> tuple[tuple[int, int, int, int], tuple[LiveColumn, LiveColumn, LiveColumn]]:
    """Build the exact three live fixed chains at the sibling parent."""

    old_color, old_cap, q_color, q_endpoint = edge.action
    hidden_words: list[tuple[int, ...]] = [
        (q_color,) * (q_endpoint - old_cap) + tails[0]
    ]
    for cap, (next_color, endpoint), tail in zip(
        edge.sibling_caps, cards, tails[1:]
    ):
        hidden_words.append((next_color,) * (endpoint - cap) + tail)
    require(
        all(len(word) == HEIGHT - cap for word, cap in zip(hidden_words, (old_cap,) + edge.sibling_caps)),
        "residual hidden word has the wrong length",
    )
    columns: tuple[LiveColumn, LiveColumn, LiveColumn] = (
        (old_color, old_cap, color_runs(hidden_words[0])),
        (q_color, edge.sibling_caps[0], color_runs(hidden_words[1])),
        (q_color, edge.sibling_caps[1], color_runs(hidden_words[2])),
    )
    require(all(column[2] for column in columns), "active residual column has no future run")
    return tuple(debt for debt, _ in edge.parent), columns  # type: ignore[return-value]


@lru_cache(maxsize=None)
def checkpoint_is_winning(
    debts: tuple[int, int, int, int],
    columns: tuple[LiveColumn | None, LiveColumn | None, LiveColumn | None],
) -> bool:
    """Independent exact fixed-chain recursion from z=1 to one more exhaustion."""

    if any(column is None for column in columns):
        return True
    for source, column in enumerate(columns):
        require(column is not None, "non-goal checkpoint unexpectedly lost a column")
        top, cap, future = column
        if not source_is_legal_from_debts(debts, 1, top, cap):
            continue
        require(future, "live checkpoint column has no future border")
        next_color, run_length = future[0]
        require(next_color != top, "fixed chain contains adjacent equal runs")
        child_debts = list(debts)
        child_debts[top] += cap
        child_columns = list(columns)
        if len(future) == 1:
            require(cap + run_length == HEIGHT, "final run does not reach the bottom")
            child_debts[next_color] += run_length
            child_columns[source] = None
        else:
            require(cap + run_length < HEIGHT, "nonfinal run exhausts its column")
            child_debts[next_color] -= cap
            child_columns[source] = (next_color, cap + run_length, future[1:])
        if checkpoint_is_winning(
            tuple(child_debts), tuple(child_columns)  # type: ignore[arg-type]
        ):
            return True
    return False


def source_is_legal_from_debts(
    debts: tuple[int, int, int, int], exhausted: int, color: int, cap: int
) -> bool:
    adjusted = list(debts)
    adjusted[color] += cap
    return sum(value > 0 for value in adjusted) <= EMPTY_COLUMNS + exhausted


def checkpoint_escape(
    debts: tuple[int, int, int, int],
    columns: tuple[LiveColumn | None, LiveColumn | None, LiveColumn | None],
) -> tuple[int, ...] | None:
    """Extract and independently replay one winning local source sequence."""

    if any(column is None for column in columns):
        return ()
    for source, column in enumerate(columns):
        require(column is not None, "unexpected absent column")
        top, cap, future = column
        if not source_is_legal_from_debts(debts, 1, top, cap):
            continue
        next_color, run_length = future[0]
        child_debts = list(debts)
        child_debts[top] += cap
        child_columns = list(columns)
        if len(future) == 1:
            child_debts[next_color] += run_length
            child_columns[source] = None
        else:
            child_debts[next_color] -= cap
            child_columns[source] = (next_color, cap + run_length, future[1:])
        child = tuple(child_columns)
        if not checkpoint_is_winning(tuple(child_debts), child):  # type: ignore[arg-type]
            continue
        suffix = checkpoint_escape(tuple(child_debts), child)  # type: ignore[arg-type]
        require(suffix is not None, "winning child has no extracted escape")
        return (source,) + suffix
    return None


def checkpoint_step(
    debts: tuple[int, int, int, int],
    columns: tuple[LiveColumn | None, LiveColumn | None, LiveColumn | None],
    source: int,
) -> tuple[
    tuple[int, int, int, int],
    tuple[LiveColumn | None, LiveColumn | None, LiveColumn | None],
] | None:
    if source not in range(3) or columns[source] is None:
        return None
    column = columns[source]
    require(column is not None, "selected checkpoint source vanished")
    top, cap, future = column
    if not source_is_legal_from_debts(debts, 1, top, cap):
        return None
    next_color, run_length = future[0]
    child_debts = list(debts)
    child_debts[top] += cap
    child_columns = list(columns)
    if len(future) == 1:
        require(cap + run_length == HEIGHT, "sample final run misses the bottom")
        child_debts[next_color] += run_length
        child_columns[source] = None
    else:
        require(cap + run_length < HEIGHT, "sample nonfinal run exhausts")
        child_debts[next_color] -= cap
        child_columns[source] = (next_color, cap + run_length, future[1:])
    return tuple(child_debts), tuple(child_columns)  # type: ignore[return-value]


def checkpoint_safe_mask(
    debts: tuple[int, int, int, int],
    columns: tuple[LiveColumn | None, LiveColumn | None, LiveColumn | None],
) -> int:
    mask = 0
    for source in range(3):
        child = checkpoint_step(debts, columns, source)
        if child is not None and checkpoint_is_winning(*child):
            mask |= 1 << source
    return mask


def replay_abstract_sample(edge: BadEdge, value: object) -> bool:
    """Replay one production residual-word witness from its sibling checkpoint."""

    if value is None:
        return False
    require(isinstance(value, dict), "per-edge sample is neither object nor null")
    words_value = value.get("hidden_words_bottom_to_top")
    require(
        isinstance(words_value, list)
        and len(words_value) == 3
        and all(isinstance(word, str) for word in words_value),
        "sample has no three hidden words",
    )
    current = (
        (edge.action[0], edge.action[1]),
        (edge.action[2], edge.sibling_caps[0]),
        (edge.action[2], edge.sibling_caps[1]),
    )
    words: list[tuple[int, ...]] = []
    for raw, (_, cap) in zip(words_value, current):
        require(len(raw) == HEIGHT - cap, "sample hidden word has wrong length")
        require(all(character in "0123" for character in raw), "sample has a bad color")
        words.append(tuple(int(character) for character in raw))
    counts = Counter(color for word in words for color in word)
    expected_remaining = Counter(
        {
            color: HEIGHT - exposed_counts(edge.parent)[color]
            for color in range(COLORS)
        }
    )
    require(counts == expected_remaining, "sample residual words violate color balance")

    live: list[LiveColumn] = []
    for (top, cap), word in zip(current, words):
        top_to_bottom = tuple(reversed(word))
        require(top_to_bottom and top_to_bottom[0] != top, "sample repeats checkpoint top")
        live.append((top, cap, color_runs(top_to_bottom)))
    bad_future = live[0][2]
    require(
        bad_future[0]
        == (edge.action[2], edge.action[3] - edge.action[1]),
        "sample bad column does not realize the stored bad edge",
    )
    debts = tuple(debt for debt, _ in edge.parent)
    columns = tuple(live)
    independent_solvable = checkpoint_is_winning(debts, columns)  # type: ignore[arg-type]
    require(value.get("solvable") is independent_solvable, "sample solvability disagrees with DP")
    safe_mask = checkpoint_safe_mask(debts, columns)  # type: ignore[arg-type]
    require(value.get("safe_source_mask") == safe_mask, "sample safe mask disagrees with DP")
    require((safe_mask & 0x6) == 0x6, "a q sibling is not independently safe")

    escape_value = value.get("escape_columns")
    require(isinstance(escape_value, str), "sample has no escape_columns string")
    require(all(character in "012" for character in escape_value), "bad local escape source")
    if not independent_solvable:
        require(escape_value == "", "losing sample carries a claimed escape")
        return True
    state_debts = debts
    state_columns = columns  # type: ignore[assignment]
    for step, character in enumerate(escape_value):
        child = checkpoint_step(state_debts, state_columns, int(character))
        require(child is not None, f"sample escape is illegal at step {step}")
        state_debts, state_columns = child
    require(any(column is None for column in state_columns), "sample escape misses z=2")
    return True


def audit_checkpoint_samples(edges: Sequence[BadEdge]) -> dict[str, int]:
    """Classify first/middle/last fixed futures for every one of the 32 edges."""

    samples = 0
    yes = 0
    no = 0
    for edge in edges:
        q_color = edge.action[2]
        feasible_cards = [
            cards
            for cards in itertools.product(
                next_cards(q_color, edge.sibling_caps[0]),
                next_cards(q_color, edge.sibling_caps[1]),
            )
            if remaining_tail_word_count(edge, cards) > 0  # type: ignore[arg-type]
        ]
        require(feasible_cards, "edge has no feasible simultaneous decoration")
        selections = (
            (feasible_cards[0], False),
            (feasible_cards[len(feasible_cards) // 2], False),
            (feasible_cards[-1], True),
        )
        for cards, reverse in selections:
            tails = one_tail_completion(edge, cards, reverse=reverse)  # type: ignore[arg-type]
            require(tails is not None, "feasible decoration has no concrete residual word")
            debts, columns = residual_checkpoint(edge, cards, tails)  # type: ignore[arg-type]
            winning = checkpoint_is_winning(debts, columns)
            escape = checkpoint_escape(debts, columns)
            require((escape is not None) == winning, "escape extraction disagrees with DP")
            samples += 1
            yes += int(winning)
            no += int(not winning)
    require(samples == EXPECTED_CHECKPOINT_SAMPLES, "checkpoint sample coverage is not 3 per edge")
    require(yes == EXPECTED_CHECKPOINT_SAMPLES and no == 0, "a fixed checkpoint sample is NO")
    return {"checkpoint_samples": samples, "checkpoint_sample_yes": yes, "checkpoint_sample_no": no}


def bounded_checkpoint_audit(edges: Sequence[BadEdge], limit: int) -> dict[str, object]:
    """Classify an independently ordered bounded prefix of all residual words."""

    require(limit > 0, "bounded checkpoint audit needs a positive limit")
    checked = 0
    yes = 0
    no = 0
    digest = hashlib.sha256()
    for edge_ordinal, edge in enumerate(edges):
        q_color = edge.action[2]
        for cards in itertools.product(
            next_cards(q_color, edge.sibling_caps[0]),
            next_cards(q_color, edge.sibling_caps[1]),
        ):
            for tails in tail_completions(edge, cards):  # type: ignore[arg-type]
                debts, columns = residual_checkpoint(edge, cards, tails)  # type: ignore[arg-type]
                winning = checkpoint_is_winning(debts, columns)
                escape = checkpoint_escape(debts, columns)
                require((escape is not None) == winning, "bounded DP extraction mismatch")
                record = {
                    "edge": edge_ordinal,
                    "cards": cards,
                    "tails": tails,
                    "winning": winning,
                    "escape": escape,
                }
                digest.update(
                    json.dumps(record, separators=(",", ":"), sort_keys=True).encode("ascii")
                )
                checked += 1
                yes += int(winning)
                no += int(not winning)
                if checked == limit:
                    return {
                        "checked": checked,
                        "yes": yes,
                        "no": no,
                        "sha256": digest.hexdigest(),
                    }
    require(False, f"bounded audit requested {limit} beyond the residual universe")
    raise AssertionError("unreachable")


def replay_persistence_formula(edge: BadEdge, sibling: int, card: Card) -> None:
    """Prove by direct source-test evaluation that the other q sibling persists."""

    q_color = edge.action[2]
    cap = edge.sibling_caps[sibling]
    other_cap = edge.sibling_caps[1 - sibling]
    next_color, endpoint = card
    if endpoint == HEIGHT:
        return  # a second original column is exhausted: the frontier is reached

    # After q_cap -> next_color, testing the untouched q source gives
    # d + (cap + other_cap)e_q - cap e_next.  The subtraction cannot create a
    # positive coordinate.  We still evaluate the exact formula, rather than
    # accepting the informal monotonicity argument alone.
    adjusted = [debt for debt, _ in edge.parent]
    adjusted[q_color] += cap + other_cap
    adjusted[next_color] -= cap
    require(
        sum(value > 0 for value in adjusted) <= EMPTY_COLUMNS + 1,
        "the untouched q sibling did not persist",
    )


def bad_source_persists(edge: BadEdge, sibling: int, card: Card) -> bool:
    """Classify the finer, nonautomatic persistence of the original bad source."""

    old_color, old_cap, q_color, _ = edge.action
    cap = edge.sibling_caps[sibling]
    next_color, endpoint = card
    if endpoint == HEIGHT:
        return False
    adjusted = [debt for debt, _ in edge.parent]
    adjusted[q_color] += cap
    adjusted[next_color] -= cap
    adjusted[old_color] += old_cap
    observed = sum(value > 0 for value in adjusted) <= EMPTY_COLUMNS + 1

    # In the (uncanonicalized) terminal coordinates the three non-q debts are
    # positive.  The sibling move makes q positive and subtracts ``cap`` from
    # exactly one of those three.  Hence the bad source persists precisely
    # when that selected terminal-positive debt is no larger than ``cap``.
    selected_terminal_debt = edge.parent[next_color][0]
    if next_color == old_color:
        selected_terminal_debt += old_cap
    predicted = selected_terminal_debt <= cap
    require(observed == predicted, "bad-source persistence formula disagrees with replay")
    return observed


def state_to_json(state: State) -> list[dict[str, object]]:
    return [
        {"debt": debt, "caps": list(caps), "exposed": debt + sum(caps)}
        for debt, caps in state
    ]


def edge_to_public_row(edge: BadEdge, ordinal: int) -> dict[str, object]:
    q_color = edge.action[2]
    raw_single = sum(len(next_cards(q_color, cap)) for cap in edge.sibling_caps)
    raw_decorations = 1
    for cap in edge.sibling_caps:
        raw_decorations *= len(next_cards(q_color, cap))

    feasible = 0
    completions = 0
    persistent_source_cards = 0
    nonpersistent_source_cards = 0
    both_bad_persistent = 0
    direct_exhaustion = 0
    bad_source_persistent_decorations = 0
    obstruction_decorations = 0
    for cards in itertools.product(
        next_cards(q_color, edge.sibling_caps[0]),
        next_cards(q_color, edge.sibling_caps[1]),
    ):
        typed_cards = cards  # narrow type for static readers
        for sibling, card in enumerate(typed_cards):
            replay_persistence_formula(edge, sibling, card)
        word_count = remaining_tail_word_count(edge, typed_cards)  # type: ignore[arg-type]
        if word_count == 0:
            continue
        feasible += 1
        completions += word_count
        bad_flags = tuple(
            bad_source_persists(edge, sibling, card)
            for sibling, card in enumerate(typed_cards)
        )
        persistent_source_cards += sum(bad_flags)
        nonpersistent_source_cards += len(bad_flags) - sum(bad_flags)
        both_bad_persistent += int(all(bad_flags))
        direct = any(card[1] == HEIGHT for card in typed_cards)
        persistent = any(bad_flags)
        direct_exhaustion += int(direct)
        bad_source_persistent_decorations += int(persistent)
        obstruction_decorations += int(not direct and not persistent)

    return {
        "id": f"edge-{ordinal:02d}",
        "parent": state_to_json(edge.parent),
        "terminal": state_to_json(edge.terminal),
        "bad_action": list(edge.action),
        "sibling_caps": list(edge.sibling_caps),
        "raw_single_next_run_outcomes": raw_single,
        "raw_simultaneous_decorations": raw_decorations,
        "feasible_decorations": feasible,
        "fixed_future_completions": completions,
        "persistent_bad_source_cards": persistent_source_cards,
        "nonpersistent_bad_source_cards": nonpersistent_source_cards,
        "both_bad_sources_persistent_decorations": both_bad_persistent,
        "direct_exhaustion_decorations": direct_exhaustion,
        "bad_source_persistent_decorations": bad_source_persistent_decorations,
        "obstruction_decorations": obstruction_decorations,
    }


def independent_census() -> dict[str, object]:
    terminals = enumerate_tq_terminals()
    require(len(terminals) == EXPECTED_TERMINALS, "Tq terminal count is not 71")
    pairs = reverse_live_pairs(terminals)
    require(len(pairs) == EXPECTED_LIVE_EDGES, "same-z live edge count is not 116")
    require(
        len({parent for parent, _ in pairs}) == EXPECTED_LIVE_PARENTS,
        "same-z live parent count is not 80",
    )
    edges = sibling_bad_edges(pairs)
    require(len(edges) == EXPECTED_BAD_EDGES, "sibling bad-edge count is not 32")
    require(
        len({edge.parent for edge in edges}) == EXPECTED_SIBLING_PARENTS,
        "sibling parent count is not 23",
    )
    require(
        all(apply_live_action(edge.parent, edge.action) == edge.terminal for edge in edges),
        "a bad-edge witness failed forward replay",
    )

    rows = [edge_to_public_row(edge, ordinal) for ordinal, edge in enumerate(edges)]
    raw_single = sum(int(row["raw_single_next_run_outcomes"]) for row in rows)
    raw_decorations = sum(int(row["raw_simultaneous_decorations"]) for row in rows)
    feasible = sum(int(row["feasible_decorations"]) for row in rows)
    completions = sum(int(row["fixed_future_completions"]) for row in rows)
    direct_exhaustion = sum(int(row["direct_exhaustion_decorations"]) for row in rows)
    persistent = sum(int(row["bad_source_persistent_decorations"]) for row in rows)
    obstruction = sum(int(row["obstruction_decorations"]) for row in rows)
    require(raw_single == EXPECTED_RAW_SINGLE_OUTCOMES, "raw single-card count is not 840")
    require(raw_decorations == EXPECTED_RAW_DECORATIONS, "raw decoration count is not 5526")
    require(feasible == EXPECTED_FEASIBLE_DECORATIONS, "feasible count is not 2958")
    require(completions == EXPECTED_FIXED_FUTURES, "fixed-future count is not 10073448")
    per_edge_futures = [int(row["fixed_future_completions"]) for row in rows]
    require(all(count > 0 for count in per_edge_futures), "a bad edge has no fixed future")
    require(
        min(per_edge_futures) == EXPECTED_MIN_EDGE_FUTURES,
        "minimum per-edge fixed-future count is not 924",
    )
    require(
        max(per_edge_futures) == EXPECTED_MAX_EDGE_FUTURES,
        "maximum per-edge fixed-future count is not 3963960",
    )
    sample_audit = audit_checkpoint_samples(edges)

    return {
        "schema_version": 1,
        "terminal_count": len(terminals),
        "same_z_live_parent_count": len({parent for parent, _ in pairs}),
        "same_z_live_edge_count": len(pairs),
        "sibling_parent_count": len({edge.parent for edge in edges}),
        "bad_edge_count": len(edges),
        "raw_single_next_run_outcomes": raw_single,
        "raw_simultaneous_decorations": raw_decorations,
        "feasible_decorations": feasible,
        "fixed_future_completions": completions,
        "direct_exhaustion_decorations": direct_exhaustion,
        "bad_source_persistent_decorations": persistent,
        "obstruction_decorations": obstruction,
        **sample_audit,
        "per_edge": rows,
        "_edges": edges,
    }


def parse_state(value: object) -> State:
    require(isinstance(value, list) and len(value) == COLORS, f"bad state: {value!r}")
    buckets: list[Bucket] = []
    for bucket in value:
        if isinstance(bucket, dict):
            debt = bucket.get("debt")
            caps = bucket.get("caps")
        else:
            require(
                isinstance(bucket, list) and len(bucket) >= 2,
                f"bad bucket: {bucket!r}",
            )
            debt, caps = bucket[0], bucket[1]
        require(isinstance(debt, int), f"bad debt in {bucket!r}")
        require(
            isinstance(caps, list) and all(isinstance(cap, int) for cap in caps),
            f"bad caps in {bucket!r}",
        )
        buckets.append((debt, tuple(caps)))
    state = tuple(buckets)
    require(tuple(sorted(state)) == state, "reported state is not canonical")
    return state  # type: ignore[return-value]


def normalized_report_edge(row: dict[str, object]) -> tuple[State, State, Action]:
    parent = parse_state(row.get("parent"))
    terminal = parse_state(row.get("terminal"))
    action_value = row.get("bad_action", row.get("action"))
    require(
        isinstance(action_value, list)
        and len(action_value) == 4
        and all(isinstance(item, int) for item in action_value),
        "edge has no four-integer bad action",
    )
    action = tuple(action_value)
    require(apply_live_action(parent, action) == terminal, "reported bad edge does not replay")
    return parent, terminal, action  # type: ignore[return-value]


def validate_report(
    report: dict[str, object],
    census: dict[str, object],
    expected_bound: int | None = None,
) -> None:
    require(report.get("schema_version") == 1, "unsupported production schema")
    for key in (
        "terminal_count",
        "sibling_parent_count",
        "bad_edge_count",
        "raw_single_next_run_outcomes",
        "raw_simultaneous_decorations",
        "feasible_decorations",
        "fixed_future_completions",
        "direct_exhaustion_decorations",
        "bad_source_persistent_decorations",
        "obstruction_decorations",
    ):
        require(report.get(key) == census[key], f"report field {key} disagrees with audit")

    require(report.get("self_checks_passed") is True, "production self-checks did not pass")
    for key in ("next_run_census_complete", "residual_word_universe_complete"):
        require(isinstance(report.get(key), bool), f"{key} is not Boolean")
    require(report.get("next_run_census_complete") is True, "next-run census is incomplete")
    residual_expected = report.get("residual_words_expected")
    require(
        residual_expected == EXPECTED_FIXED_FUTURES,
        "residual_words_expected disagrees with the independent tail DP",
    )
    checked = report.get("residual_words_checked")
    require(isinstance(checked, int) and checked > 0, "bad residual_words_checked")
    yes = report.get("checkpoint_yes_count")
    no = report.get("local_no_count")
    global_no = report.get("global_no_count")
    require(
        isinstance(yes, int) and isinstance(no, int) and isinstance(global_no, int),
        "missing checkpoint classification counts",
    )
    require(yes + no == checked, "checkpoint classifications do not sum to checked residuals")
    require(
        report.get("both_siblings_safe_count") == checked,
        "not every checked residual reports both q siblings safe",
    )

    status = report.get("status")
    allowed = {
        "ENTRY_FAMILY_ELIMINATED",
        "RESIDUALS_EXPORTED",
        "GLOBAL_NO_FOUND",
        "INCOMPLETE",
    }
    require(status in allowed, f"bad status {status!r}")
    if status == "INCOMPLETE":
        if expected_bound is not None:
            require(
                checked == min(expected_bound, EXPECTED_FIXED_FUTURES),
                "bounded job missed its requested limit",
            )
        require(report.get("verified") is False, "incomplete report claims verification")
        require(report.get("universe_complete") is False, "incomplete report claims completeness")
        require(global_no == 0, "incomplete report claims a global NO")
    elif status == "ENTRY_FAMILY_ELIMINATED":
        require(checked == EXPECTED_FIXED_FUTURES, "elimination missed residual words")
        require(yes == checked and no == 0, "elimination contains a local NO")
        require(global_no == 0, "elimination also claims a global NO")
        require(report.get("verified") is True, "elimination is not verified")
        require(report.get("universe_complete") is True, "elimination lacks completeness")
        require(
            report.get("residual_word_universe_complete") is True,
            "elimination lacks a complete residual-word universe",
        )
    elif status == "RESIDUALS_EXPORTED":
        require(checked == EXPECTED_FIXED_FUTURES, "residual export missed words")
        require(no >= 1, "residual export has no local NO")
        require(global_no == 0, "residual export incorrectly claims a global NO")
        require(report.get("verified") is True, "residual export is not verified")
        require(report.get("universe_complete") is True, "residual export lacks completeness")
        require(
            report.get("residual_word_universe_complete") is True,
            "residual export is not exhaustive",
        )
    else:
        require(global_no >= 1, "GLOBAL_NO_FOUND has no global classification")
        require(report.get("verified") is True, "global NO is not verified")

    rows_value = report.get("per_edge")
    require(isinstance(rows_value, list), "production report has no per_edge array")
    rows: list[dict[str, object]] = rows_value  # type: ignore[assignment]
    require(len(rows) == EXPECTED_BAD_EDGES, "production per_edge length is not 32")
    expected_rows: list[dict[str, object]] = census["per_edge"]  # type: ignore[assignment]
    expected_by_key = {
        (
            parse_state(row["parent"]),
            parse_state(row["terminal"]),
            tuple(row["bad_action"]),
        ): row
        for row in expected_rows
    }
    seen: set[tuple[State, State, Action]] = set()
    abstract_samples = 0
    summed_both_siblings_safe = 0
    for row in rows:
        key = normalized_report_edge(row)
        require(key in expected_by_key, "production report contains an unknown bad edge")
        require(key not in seen, "production report duplicates a bad edge")
        seen.add(key)
        expected = expected_by_key[key]
        for field, expected_field in (
            ("raw_single_next_run_outcomes", "raw_single_next_run_outcomes"),
            ("raw_simultaneous_decorations", "raw_simultaneous_decorations"),
            ("feasible_decorations", "feasible_decorations"),
            ("residual_words_expected", "fixed_future_completions"),
        ):
            require(row.get(field) == expected[expected_field], f"per-edge {field} mismatch")
        columns = row.get("columns")
        action = expected["bad_action"]
        sibling_caps = expected["sibling_caps"]
        expected_columns = [
            [action[0], action[1]],
            [action[2], sibling_caps[0]],
            [action[2], sibling_caps[1]],
        ]
        require(columns == expected_columns, "per-edge active columns mismatch")
        both = row.get("both_siblings_safe_count")
        row_checked = row.get("residual_words_checked")
        require(isinstance(both, int) and isinstance(row_checked, int), "bad per-edge checked counts")
        require(both == row_checked, "not every checked residual has both q siblings safe")
        summed_both_siblings_safe += both
        expected_edge = BadEdge(key[0], key[1], key[2], tuple(sibling_caps))  # type: ignore[arg-type]
        abstract_samples += int(replay_abstract_sample(expected_edge, row.get("sample")))
    require(len(seen) == EXPECTED_BAD_EDGES, "production edge cover is incomplete")
    require(summed_both_siblings_safe == checked, "both-sibling-safe total misses residuals")
    if status != "INCOMPLETE":
        require(abstract_samples == EXPECTED_BAD_EDGES, "complete report lacks one sample per edge")

    replay_all_witnesses(report)


def parse_columns(value: object) -> tuple[tuple[int, ...], ...]:
    if isinstance(value, str):
        value = value.split("|")
    require(isinstance(value, list) and len(value) == COLORS, f"bad columns: {value!r}")
    columns = []
    for raw in value:
        require(isinstance(raw, str) and len(raw) == HEIGHT, f"bad column {raw!r}")
        require(all(character in "0123" for character in raw), f"bad color in {raw!r}")
        columns.append(tuple(int(character) for character in raw))
    counts = Counter(color for column in columns for color in column)
    require(counts == Counter({0: 7, 1: 7, 2: 7, 3: 7}), f"unbalanced witness {counts}")
    return tuple(columns)


def column_borders(column: Sequence[int]) -> tuple[int, ...]:
    return (0,) + tuple(
        position
        for position in range(1, HEIGHT)
        if column[position - 1] != column[position]
    )


def removal_is_legal(
    columns: Sequence[Sequence[int]], ranks: Sequence[int], source: int
) -> bool:
    borders = [column_borders(column) for column in columns]
    if source not in range(COLORS) or ranks[source] == 0:
        return False
    exposed = [0] * COLORS
    hosted = [0] * COLORS
    exhausted = 0
    for column, rank in enumerate(ranks):
        if rank == 0:
            exhausted += 1
        border = borders[column][rank]
        for position in range(border, HEIGHT):
            exposed[columns[column][position]] += 1
        if rank:
            hosted[columns[column][border]] += HEIGHT - border

    border = borders[source][ranks[source]]
    top = columns[source][border]
    cap = HEIGHT - border
    adjusted = [exposed[color] - hosted[color] for color in range(COLORS)]
    adjusted[top] += cap
    return sum(value > 0 for value in adjusted) <= EMPTY_COLUMNS + exhausted


def parse_moves(value: object) -> tuple[int, ...]:
    if isinstance(value, str):
        require(all(character in "0123" for character in value), f"bad move string {value!r}")
        return tuple(int(character) for character in value)
    require(
        isinstance(value, list) and all(isinstance(move, int) for move in value),
        f"bad move sequence {value!r}",
    )
    return tuple(value)


def replay_removals(
    columns: Sequence[Sequence[int]], ranks: Sequence[int], moves: Sequence[int]
) -> tuple[int, ...]:
    borders = [column_borders(column) for column in columns]
    current = list(ranks)
    require(
        len(current) == COLORS
        and all(0 <= current[i] < len(borders[i]) for i in range(COLORS)),
        f"bad checkpoint ranks {ranks!r}",
    )
    for step, source in enumerate(moves):
        require(removal_is_legal(columns, current, source), f"illegal witness step {step}")
        current[source] -= 1
    return tuple(current)


def replay_witness(value: dict[str, object]) -> None:
    columns_value = value.get("columns", value.get("layout"))
    require(columns_value is not None, "witness has no columns")
    columns = parse_columns(columns_value)
    borders = [column_borders(column) for column in columns]
    initial_ranks = tuple(len(items) - 1 for items in borders)

    checkpoint_value = value.get("checkpoint_ranks")
    prefix_value = value.get("prefix_removal_columns", value.get("prefix_removals"))
    if checkpoint_value is None:
        checkpoint = initial_ranks
    else:
        require(
            isinstance(checkpoint_value, list)
            and len(checkpoint_value) == COLORS
            and all(isinstance(rank, int) for rank in checkpoint_value),
            "bad checkpoint_ranks",
        )
        checkpoint = tuple(checkpoint_value)
        if prefix_value is not None:
            reached = replay_removals(columns, initial_ranks, parse_moves(prefix_value))
            require(reached == checkpoint, "prefix witness does not reach checkpoint")

    move_value = next(
        (
            value[key]
            for key in (
                "removal_columns",
                "removal_sequence",
                "escape_removal_columns",
                "escape_removals",
            )
            if key in value
        ),
        None,
    )
    require(move_value is not None, "witness has no removal sequence")
    final_ranks = replay_removals(columns, checkpoint, parse_moves(move_value))
    target = value.get("target_exhausted_columns")
    if isinstance(target, int):
        require(sum(rank == 0 for rank in final_ranks) >= target, "witness misses target")
    else:
        require(
            all(rank == 0 for rank in final_ranks)
            or sum(rank == 0 for rank in final_ranks) >= 2,
            "witness reaches neither state zero nor the two-column frontier",
        )


def replay_all_witnesses(report: dict[str, object]) -> None:
    """Find and replay every nested object that declares concrete columns."""

    found = 0
    concrete_layouts = 0

    def visit(value: object) -> None:
        nonlocal found, concrete_layouts
        if isinstance(value, dict):
            layout_value = value.get("columns", value.get("layout"))
            has_columns = (
                isinstance(layout_value, str)
                and len(layout_value.split("|")) == COLORS
            ) or (
                isinstance(layout_value, list)
                and len(layout_value) == COLORS
                and all(isinstance(column, str) for column in layout_value)
            )
            has_moves = any(
                key in value
                for key in (
                    "removal_columns",
                    "removal_sequence",
                    "escape_removal_columns",
                    "escape_removals",
                )
            )
            if has_columns:
                parse_columns(layout_value)
                concrete_layouts += 1
            if has_columns and has_moves:
                replay_witness(value)
                found += 1
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(report)
    declared = report.get("witness_count")
    if isinstance(declared, int):
        require(found == declared, f"replayed {found} witnesses, report declares {declared}")
    if report.get("status") == "GLOBAL_NO_FOUND":
        # A NO certificate has no winning removal sequence to replay.  The
        # workflow separately invokes the independent oracle/verifier; here we
        # still require its complete balanced 4x7 instance to be embedded.
        require(concrete_layouts >= 1, "GLOBAL_NO_FOUND report has no complete layout")


def run_program(program: Path, census: dict[str, object], limit: int) -> None:
    edges: tuple[BadEdge, ...] = census["_edges"]  # type: ignore[assignment]
    bounded = bounded_checkpoint_audit(edges, min(limit, EXPECTED_FIXED_FUTURES))
    with tempfile.TemporaryDirectory(prefix="c4-h7-tq-sibling-audit-") as temporary:
        output = Path(temporary) / "out"
        command = [
            str(program),
            "--output-dir",
            str(output),
            "--limit",
            str(limit),
            "--self-test",
        ]
        completed = subprocess.run(command, text=True, capture_output=True, check=False)
        require(
            completed.returncode == 0,
            "production program failed:\n"
            + completed.stdout
            + ("\n" if completed.stdout and completed.stderr else "")
            + completed.stderr,
        )
        report_path = output / "report.json"
        require(report_path.is_file(), "production program did not write report.json")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        require(isinstance(report, dict), "production report root is not an object")
        validate_report(report, census, limit)
        require(
            report.get("residual_words_checked") == bounded["checked"],
            "production and independent bounded jobs checked different totals",
        )
        require(
            report.get("checkpoint_yes_count") == bounded["yes"]
            and report.get("local_no_count") == bounded["no"],
            "production bounded classifications disagree with independent DP",
        )
        if "bounded_prefix_sha256" in report:
            require(
                report["bounded_prefix_sha256"] == bounded["sha256"],
                "bounded residual prefix checksum mismatch",
            )


def read_and_validate_report(
    report_path: Path, census: dict[str, object], expected_bound: int | None = None
) -> None:
    require(report_path.is_file(), f"report not found: {report_path}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    require(isinstance(report, dict), "production report root is not an object")
    validate_report(report, census, expected_bound)


def schema_negative_tests(census: dict[str, object]) -> None:
    """Small mutation checks ensure core census fields are not accepted blindly."""

    census_rows: list[dict[str, object]] = census["per_edge"]  # type: ignore[assignment]
    production_rows: list[dict[str, object]] = []
    for index, row in enumerate(census_rows):
        action = row["bad_action"]
        sibling_caps = row["sibling_caps"]
        checked = int(index == 0)
        production_rows.append(
            {
                "edge_id": f"tq-sibling-e{index}",
                "parent": copy.deepcopy(row["parent"]),
                "terminal": copy.deepcopy(row["terminal"]),
                "bad_action": list(action),
                "columns": [
                    [action[0], action[1]],
                    [action[2], sibling_caps[0]],
                    [action[2], sibling_caps[1]],
                ],
                "raw_single_next_run_outcomes": row["raw_single_next_run_outcomes"],
                "raw_simultaneous_decorations": row["raw_simultaneous_decorations"],
                "feasible_decorations": row["feasible_decorations"],
                "residual_words_expected": row["fixed_future_completions"],
                "residual_words_checked": checked,
                "checkpoint_yes_count": checked,
                "local_no_count": 0,
                "safe_source_counts": [checked, checked, checked],
                "both_siblings_safe_count": checked,
                "sample": None,
            }
        )

    skeleton = {
        "schema_version": 1,
        "verified": False,
        "status": "INCOMPLETE",
        "universe_complete": False,
        "self_checks_passed": True,
        "next_run_census_complete": True,
        "residual_word_universe_complete": False,
        "terminal_count": census["terminal_count"],
        "sibling_parent_count": census["sibling_parent_count"],
        "bad_edge_count": census["bad_edge_count"],
        "raw_single_next_run_outcomes": census["raw_single_next_run_outcomes"],
        "raw_simultaneous_decorations": census["raw_simultaneous_decorations"],
        "feasible_decorations": census["feasible_decorations"],
        "fixed_future_completions": census["fixed_future_completions"],
        "direct_exhaustion_decorations": census["direct_exhaustion_decorations"],
        "bad_source_persistent_decorations": census["bad_source_persistent_decorations"],
        "obstruction_decorations": census["obstruction_decorations"],
        "residual_words_expected": census["fixed_future_completions"],
        "residual_words_checked": 1,
        "checkpoint_yes_count": 1,
        "local_no_count": 0,
        "global_no_count": 0,
        "both_siblings_safe_count": 1,
        "per_edge": production_rows,
    }
    validate_report(skeleton, census, 1)
    for field in (
        "terminal_count",
        "sibling_parent_count",
        "bad_edge_count",
        "raw_simultaneous_decorations",
        "feasible_decorations",
        "fixed_future_completions",
    ):
        mutant = copy.deepcopy(skeleton)
        mutant[field] = int(mutant[field]) + 1
        try:
            validate_report(mutant, census, 1)
        except AssertionError:
            pass
        else:
            raise AssertionError(f"validator accepted a corrupted {field}")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--program", type=Path, help="bounded production executable")
    parser.add_argument("--report", type=Path, help="validate an existing production report")
    parser.add_argument("--limit", type=int, default=64, help="production differential bound")
    parser.add_argument("--json", type=Path, dest="json_path", help="write audit summary")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    require(args.limit > 0, "--limit must be positive")
    census = independent_census()
    schema_negative_tests(census)
    if args.program:
        require(args.program.is_file(), f"program not found: {args.program}")
        run_program(args.program.resolve(), census, args.limit)
    if args.report:
        read_and_validate_report(args.report, census)

    public = {key: value for key, value in census.items() if not key.startswith("_")}
    text = json.dumps(public, indent=2, sort_keys=True) + "\n"
    if args.json_path:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(text, encoding="utf-8")
    else:
        print(
            "PASS: "
            f"Tq={census['terminal_count']}, sibling parents={census['sibling_parent_count']}, "
            f"bad edges={census['bad_edge_count']}, decorations={census['raw_simultaneous_decorations']}, "
            f"feasible={census['feasible_decorations']}, futures={census['fixed_future_completions']}, "
            f"checkpoint samples={census['checkpoint_sample_yes']}/{census['checkpoint_samples']} YES"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
