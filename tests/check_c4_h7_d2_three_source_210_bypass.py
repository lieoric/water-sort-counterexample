#!/usr/bin/env python3
"""Independent finite audit of the edge-116 210-row zero-debt bypass.

This checker deliberately does not rebuild or solve the full 1,106,490-row
three-source checkpoint experiment.  It enumerates only the 210 known
edge-116 local-NO futures, all 140 compatible labelled zero-debt pasts,
replays the proof's deep-anchor macro, and checks the constructive z=1
no-terminal lemma on every state reachable after that macro.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from itertools import product


HEIGHT = 7
COLORS = 4
EMPTY = 2
Q, F, G, HH = range(COLORS)

EXPECTED_FUTURES = 210
EXPECTED_PASTS = 140
EXPECTED_LAYOUTS = EXPECTED_FUTURES * EXPECTED_PASTS

Debt = tuple[int, int, int, int]
State = tuple[int, int, int, int]
Word = tuple[int, ...]


def positive_count(values: Debt | list[int]) -> int:
    return sum(value > 0 for value in values)


@dataclass(frozen=True)
class Event:
    old_color: int
    old_cap: int
    next_color: int
    next_cap: int

    @property
    def exhausts(self) -> bool:
        return self.next_cap == HEIGHT


@dataclass(frozen=True)
class Column:
    word: Word
    events: tuple[Event, ...]
    sources: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class Fixture:
    columns: tuple[Column, Column, Column, Column]


@dataclass(frozen=True)
class FixedFuture:
    small_tail_c: Word
    small_tail_d: Word
    large_tail: Word


def make_column(word: Word) -> Column:
    assert len(word) == HEIGHT
    runs: list[tuple[int, int]] = []
    cursor = 0
    while cursor < HEIGHT:
        color = word[cursor]
        end = cursor + 1
        while end < HEIGHT and word[end] == color:
            end += 1
        runs.append((color, end))
        cursor = end

    assert len(runs) >= 2, "fixtures must have an event"
    events = tuple(
        Event(runs[index][0], runs[index][1], runs[index + 1][0],
              runs[index + 1][1])
        for index in range(len(runs) - 1)
    )
    sources = tuple((color, cap) for color, cap in runs[:-1])
    assert len(events) == len(sources)
    assert events[-1].exhausts
    return Column(word, events, sources)


def fixed_futures() -> list[FixedFuture]:
    """Build the 56+70+56+28 labelled edge-116 futures."""

    required_small_g = {
        (G, HH): 5,
        (G, G): 4,
        (HH, G): 5,
        (HH, HH): 6,
    }
    expected_by_large_tail = {
        (G, HH): 56,
        (G, G): 70,
        (HH, G): 56,
        (HH, HH): 28,
    }
    result: list[FixedFuture] = []
    actual: Counter[Word] = Counter()
    for large_tail, g_count in required_small_g.items():
        for letters in product((G, HH), repeat=8):
            if letters.count(G) != g_count:
                continue
            result.append(FixedFuture(letters[:4], letters[4:], large_tail))
            actual[large_tail] += 1
    assert actual == Counter(expected_by_large_tail)
    assert len(result) == EXPECTED_FUTURES
    return result


def past_templates() -> list[tuple[Word, Word]]:
    """Build all A_4,B_5 ending-q pairs with A+B=q^5 g h^3."""

    result: list[tuple[Word, Word]] = []
    for middle in product((Q, G, HH), repeat=7):
        if Counter(middle) != Counter({Q: 3, G: 1, HH: 3}):
            continue
        a = middle[:3] + (Q,)
        b = middle[3:] + (Q,)
        assert len(a) == 4 and len(b) == 5
        assert Counter(a + b) == Counter({Q: 5, G: 1, HH: 3})
        result.append((a, b))
    assert len(result) == EXPECTED_PASTS
    assert len(set(result)) == EXPECTED_PASTS
    return result


def make_fixture(a: Word, b: Word, future: FixedFuture) -> Fixture:
    words = (
        a + (F, F, F),
        (Q, F, F) + future.small_tail_c,
        (Q, F, F) + future.small_tail_d,
        b + future.large_tail,
    )
    inventory = Counter(color for word in words for color in word)
    assert inventory == Counter({Q: HEIGHT, F: HEIGHT, G: HEIGHT, HH: HEIGHT})
    return Fixture(tuple(make_column(word) for word in words))  # type: ignore[arg-type]


def exhausted(fixture: Fixture, state: State, column: int) -> bool:
    return state[column] == len(fixture.columns[column].events)


def exhausted_count(fixture: Fixture, state: State) -> int:
    return sum(exhausted(fixture, state, column) for column in range(COLORS))


def source(fixture: Fixture, state: State, column: int) -> tuple[int, int]:
    assert not exhausted(fixture, state, column)
    return fixture.columns[column].sources[state[column]]


def debt(fixture: Fixture, state: State) -> Debt:
    values = [0] * COLORS
    for column in range(COLORS):
        for event in fixture.columns[column].events[:state[column]]:
            values[event.old_color] += event.old_cap
            if event.exhausts:
                values[event.next_color] += HEIGHT - event.old_cap
            else:
                values[event.next_color] -= event.old_cap
    return tuple(values)  # type: ignore[return-value]


def source_test(fixture: Fixture, state: State, column: int) -> Debt:
    values = list(debt(fixture, state))
    color, cap = source(fixture, state, column)
    values[color] += cap
    return tuple(values)  # type: ignore[return-value]


def legal(fixture: Fixture, state: State, column: int) -> bool:
    if exhausted(fixture, state, column):
        return False
    return positive_count(source_test(fixture, state, column)) <= (
        EMPTY + exhausted_count(fixture, state)
    )


def advance(fixture: Fixture, state: State, column: int) -> State:
    assert legal(fixture, state, column), (
        "illegal proof-macro event", state, debt(fixture, state), column,
        source(fixture, state, column), source_test(fixture, state, column),
    )
    result = list(state)
    result[column] += 1
    return tuple(result)  # type: ignore[return-value]


def remaining_inventory(fixture: Fixture, state: State) -> tuple[Debt, Debt]:
    hidden = [0] * COLORS
    hosted = [0] * COLORS
    for column in range(COLORS):
        if exhausted(fixture, state, column):
            continue
        color, cap = source(fixture, state, column)
        hosted[color] += cap
        for hidden_color in fixture.columns[column].word[cap:]:
            hidden[hidden_color] += 1
    return (
        tuple(hidden),  # type: ignore[return-value]
        tuple(hosted),  # type: ignore[return-value]
    )


def check_inventory_identity(fixture: Fixture, state: State) -> None:
    hidden, hosted = remaining_inventory(fixture, state)
    expected = tuple(
        HEIGHT - hidden[color] - hosted[color] for color in range(COLORS)
    )
    assert debt(fixture, state) == expected


def run_macro(fixture: Fixture, a: Word, b: Word) -> tuple[State, str, int]:
    """Replay the proof macro and return its z=1 state and branch name."""

    state: State = (0, 0, 0, 0)

    # The two exposed q_1 -> f_3 actions are taken before either deep prefix.
    state = advance(fixture, state, 1)
    state = advance(fixture, state, 2)
    assert debt(fixture, state) == (2, -2, 0, 0)
    assert source(fixture, state, 1) == (F, 3)
    assert source(fixture, state, 2) == (F, 3)

    steps = 2
    if G not in a:
        branch = "a_g_free"
        while not exhausted(fixture, state, 0):
            state = advance(fixture, state, 0)
            steps += 1
    else:
        assert G not in b, "the unique g must leave one deep prefix g-free"
        while source(fixture, state, 3) != (Q, 5):
            state = advance(fixture, state, 3)
            steps += 1

        # Take q_5 into its two-letter fixed future.
        state = advance(fixture, state, 3)
        steps += 1
        if exhausted(fixture, state, 3):
            branch = "b_g_free_homogeneous"
        else:
            current = source(fixture, state, 3)
            assert current in ((G, 6), (HH, 6))
            if current == (HH, 6):
                branch = "b_g_free_hg"
                state = advance(fixture, state, 3)
                steps += 1
                assert exhausted(fixture, state, 3)
            else:
                branch = "b_g_free_gh_rotor_a"
                b_h = b.count(HH)
                assert 1 <= b_h <= 3
                assert Counter(a) == Counter({Q: b_h, G: 1, HH: 3 - b_h})
                assert debt(fixture, state) == (7 - b_h, -2, -5, b_h)
                while not exhausted(fixture, state, 0):
                    state = advance(fixture, state, 0)
                    steps += 1
                assert debt(fixture, state) == (7, 1, -4, 3)

    assert exhausted_count(fixture, state) == 1
    assert source(fixture, state, 1) == (F, 3)
    assert source(fixture, state, 2) == (F, 3)
    assert positive_count(debt(fixture, state)) <= 3
    check_inventory_identity(fixture, state)
    return state, branch, steps


def no_terminal_witness(
    fixture: Fixture,
    state: State,
    values: Debt,
    active: list[tuple[int, int, int]],
    hidden: Debt,
    legal_columns: list[int],
) -> tuple[int, bool]:
    """Construct the legal source used by the z=1 no-terminal proof.

    The Boolean result records whether the final two-anchor cap inequality,
    rather than the immediate nonpositive-color argument, supplied the
    witness.
    """

    heavy = [color for color, value in enumerate(values) if value <= 0]
    assert heavy, "z=1 live successors must retain a nonpositive debt"
    assert len(active) == 3

    anchor = heavy[0]
    for column, color, _cap in active:
        if color != anchor:
            assert column in legal_columns
            return column, False

    # All source colors equal anchor.  A second nonpositive color would stay
    # nonpositive under every source test, so any source is immediately legal.
    if len(heavy) > 1:
        column = active[0][0]
        assert column in legal_columns
        return column, False

    common = anchor
    assert common in (G, HH), "small g/h tails cannot share q or f"
    assert not exhausted(fixture, state, 1)
    assert not exhausted(fixture, state, 2)
    color_c, cap_c = source(fixture, state, 1)
    color_d, cap_d = source(fixture, state, 2)
    assert color_c == color_d == common
    assert cap_c >= 4 and cap_d >= 4

    deep = 0 if not exhausted(fixture, state, 0) else 3
    assert not exhausted(fixture, state, deep)
    assert source(fixture, state, deep)[0] == common
    deep_cap = source(fixture, state, deep)[1]
    test_coordinate = values[common] + deep_cap
    assert test_coordinate == HEIGHT - hidden[common] - cap_c - cap_d
    assert test_coordinate <= -1
    assert deep in legal_columns
    return deep, True


def check_z1_suffix(fixture: Fixture, start: State) -> tuple[int, int, int]:
    """Explore every legal branch until z=2 and audit the no-terminal proof."""

    pending = [start]
    seen: set[State] = set()
    goals: set[State] = set()
    cap_witnesses = 0
    transitions = 0
    while pending:
        state = pending.pop()
        if state in seen:
            continue
        seen.add(state)
        assert sum(
            state[column] == len(fixture.columns[column].events)
            for column in range(COLORS)
        ) == 1
        values = debt(fixture, state)
        assert positive_count(values) <= 3

        hidden, hosted = remaining_inventory(fixture, state)
        assert values == tuple(
            HEIGHT - hidden[color] - hosted[color] for color in range(COLORS)
        )
        active = [
            (column, *fixture.columns[column].sources[state[column]])
            for column in range(COLORS)
            if state[column] < len(fixture.columns[column].events)
        ]
        legal_columns: list[int] = []
        for column, color, cap in active:
            tested = list(values)
            tested[color] += cap
            if positive_count(tested) <= 3:
                legal_columns.append(column)

        witness, used_cap_bound = no_terminal_witness(
            fixture, state, values, active, hidden, legal_columns,
        )
        assert witness in legal_columns
        cap_witnesses += int(used_cap_bound)
        assert legal_columns, "reachable non-goal z=1 terminal"

        for column in legal_columns:
            successor_list = list(state)
            successor_list[column] += 1
            successor = tuple(successor_list)  # type: ignore[assignment]
            transitions += 1
            if successor[column] == len(fixture.columns[column].events):
                goals.add(successor)
            else:
                pending.append(successor)
    assert goals
    return len(seen), transitions, cap_witnesses


def main() -> None:
    futures = fixed_futures()
    pasts = past_templates()
    layouts = 0
    branch_counts: Counter[str] = Counter()
    macro_steps = 0
    suffix_states = 0
    suffix_transitions = 0
    cap_witnesses = 0

    for future in futures:
        for a, b in pasts:
            fixture = make_fixture(a, b, future)
            start, branch, steps = run_macro(fixture, a, b)
            states, transitions, witnesses = check_z1_suffix(fixture, start)
            layouts += 1
            branch_counts[branch] += 1
            macro_steps += steps
            suffix_states += states
            suffix_transitions += transitions
            cap_witnesses += witnesses

    assert layouts == EXPECTED_LAYOUTS
    assert sum(branch_counts.values()) == EXPECTED_LAYOUTS
    print(
        "c4_h7_d2_three_source_210_bypass_ok",
        f"futures={len(futures)}",
        f"pasts={len(pasts)}",
        f"layouts={layouts}",
        f"macro_steps={macro_steps}",
        f"z1_states={suffix_states}",
        f"z1_transitions={suffix_transitions}",
        f"cap_witnesses={cap_witnesses}",
        "branches=" + ",".join(
            f"{name}:{count}" for name, count in sorted(branch_counts.items())
        ),
        "scope=edge116_only",
        "full_local_no=14784",
        "remaining_unhandled=14574",
    )


if __name__ == "__main__":
    main()
