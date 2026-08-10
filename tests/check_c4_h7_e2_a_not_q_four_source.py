#!/usr/bin/env python3
"""Audit the E=2, a!=q four-source D2-reduction continuation.

The checker rebuilds the first-exhaustion bridge edges with the independent
``check_c4_h7_tq_exhaust_siblings`` model.  It then selects the 1,369
E=2/A-form D2-reduction decorations by an independent one-card predicate,
plays all three committed q_3 cards, and solves only the remaining tiny
macro-card game.

No residual word is expanded.  A macro state stores the three labelled
current tops/caps and one aggregate inventory.  Completion counts are checked
twice: once by exact per-column word histograms and once by assigning the
three same-column boundary cells followed by a multinomial tail.  Every live
next card leaves its boundary prohibition on the same selected column.
"""

from __future__ import annotations

import importlib.util
import itertools
import math
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Iterable, NoReturn, Sequence


HEIGHT = 7
COLORS = 4
EMPTY_COLUMNS = 2

EXPECTED_A_FORM_E2_EDGES = 21
EXPECTED_ACTIVE_EDGES = 18
EXPECTED_DECORATIONS = 1_369
EXPECTED_WEIGHT = 57_090
EXPECTED_ONLINE_DECORATIONS = 1_368
EXPECTED_ONLINE_WEIGHT = 57_084
EXPECTED_MACRO_STATES = 3_387
EXPECTED_RESIDUAL_DECORATIONS = 1
EXPECTED_RESIDUAL_WEIGHT = 6

Column = tuple[int, int]  # current top colour, cumulative cap
Card = tuple[int, int]  # next colour, cumulative endpoint
Debts = tuple[int, int, int, int]
Inventory = tuple[int, int, int, int]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def fail(message: str) -> NoReturn:
    raise AssertionError(message)


def load_fork_module() -> ModuleType:
    path = Path(__file__).with_name("check_c4_h7_tq_exhaust_siblings.py")
    require(path.is_file(), f"missing independent fork checker: {path}")
    spec = importlib.util.spec_from_file_location("c4_h7_e2_a_fork", path)
    require(spec is not None and spec.loader is not None, "cannot load fork checker")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def source_is_legal(debts: Sequence[int], colour: int, cap: int) -> bool:
    tested = list(debts)
    tested[colour] += cap
    return sum(value > 0 for value in tested) <= EMPTY_COLUMNS


def multinomial(counts: Sequence[int]) -> int:
    if any(value < 0 for value in counts):
        return 0
    result = math.factorial(sum(counts))
    for value in counts:
        result //= math.factorial(value)
    return result


def weak_compositions(total: int) -> Iterable[tuple[int, int, int, int]]:
    for a in range(total + 1):
        for b in range(total - a + 1):
            for c in range(total - a - b + 1):
                yield a, b, c, total - a - b - c


def one_column_word_count(
    length: int, counts: tuple[int, int, int, int], forbidden: int
) -> int:
    """Count labelled words with an exact histogram and first != forbidden."""

    if sum(counts) != length:
        return 0
    total = multinomial(counts)
    if counts[forbidden] == 0:
        return total
    after = list(counts)
    after[forbidden] -= 1
    return total - multinomial(after)


@lru_cache(maxsize=None)
def completion_count_by_columns(
    remaining: Inventory, columns: tuple[Column, ...]
) -> int:
    """Exact count using each labelled column's own remaining length."""

    if any(value < 0 for value in remaining):
        return 0
    if sum(remaining) != sum(HEIGHT - cap for _, cap in columns):
        return 0
    if not columns:
        return int(not any(remaining))

    top, cap = columns[0]
    length = HEIGHT - cap
    total = 0
    for used in weak_compositions(length):
        if any(used[colour] > remaining[colour] for colour in range(COLORS)):
            continue
        ways = one_column_word_count(length, used, top)
        if ways == 0:
            continue
        rest = tuple(
            remaining[colour] - used[colour] for colour in range(COLORS)
        )
        total += ways * completion_count_by_columns(rest, columns[1:])
    return total


@lru_cache(maxsize=None)
def completion_count_by_boundaries(
    remaining: Inventory, columns: tuple[Column, ...]
) -> int:
    """Independent boundary-cell count followed by an unrestricted tail."""

    if any(value < 0 for value in remaining):
        return 0
    if sum(remaining) != sum(HEIGHT - cap for _, cap in columns):
        return 0
    total = 0
    for firsts in itertools.product(range(COLORS), repeat=len(columns)):
        if any(
            first == columns[index][0] for index, first in enumerate(firsts)
        ):
            continue
        rest = list(remaining)
        for colour in firsts:
            rest[colour] -= 1
        total += multinomial(rest)
    return total


def hall_feasible(remaining: Inventory, columns: tuple[Column, ...]) -> bool:
    if any(value < 0 for value in remaining):
        return False
    if sum(remaining) != sum(HEIGHT - cap for _, cap in columns):
        return False
    for colour in range(COLORS):
        forbidden_sources = sum(top == colour for top, _ in columns)
        available_other = sum(
            remaining[other] for other in range(COLORS) if other != colour
        )
        if forbidden_sources > available_other:
            return False
    return True


@lru_cache(maxsize=None)
def completion_count(remaining: Inventory, columns: tuple[Column, ...]) -> int:
    by_columns = completion_count_by_columns(remaining, columns)
    by_boundaries = completion_count_by_boundaries(remaining, columns)
    require(
        by_columns == by_boundaries,
        "per-column and boundary-cell completion counts disagree",
    )
    require(
        (by_columns > 0) == hall_feasible(remaining, columns),
        "exact completion and Hall feasibility disagree",
    )
    return by_columns


def exposed_counts(edge: object) -> tuple[int, int, int, int]:
    return tuple(
        debt + sum(caps) for debt, caps in edge.parent  # type: ignore[attr-defined]
    )  # type: ignore[return-value]


def decoration_balance(
    edge: object, chosen: tuple[Card, Card, Card]
) -> tuple[Inventory, tuple[Column, ...], int]:
    """Reserve the bad f tail and the three committed q_3 cards."""

    _, bad_cap, final_colour = edge.action  # type: ignore[attr-defined]
    remaining = [HEIGHT - value for value in exposed_counts(edge)]
    remaining[final_colour] -= HEIGHT - bad_cap
    columns: list[Column] = []
    for old_cap, (new_colour, endpoint) in zip(
        edge.q_caps, chosen  # type: ignore[attr-defined]
    ):
        remaining[new_colour] -= endpoint - old_cap
        if endpoint < HEIGHT:
            columns.append((new_colour, endpoint))
    inventory = tuple(remaining)  # type: ignore[assignment]
    labelled_columns = tuple(columns)
    return inventory, labelled_columns, completion_count(inventory, labelled_columns)


def one_card_keeps_bad_illegal(edge: object, slot: int, card: Card) -> bool:
    q = edge.q_color  # type: ignore[attr-defined]
    old_bad, bad_cap, _ = edge.action  # type: ignore[attr-defined]
    old_cap = edge.q_caps[slot]  # type: ignore[attr-defined]
    new_colour, endpoint = card
    if endpoint >= HEIGHT:
        return False
    debts = [debt for debt, _ in edge.parent]  # type: ignore[attr-defined]
    debts[q] += old_cap
    debts[new_colour] -= old_cap
    return not source_is_legal(debts, old_bad, bad_cap)


def is_d2_reduction_decoration(
    edge: object, chosen: tuple[Card, Card, Card], weight: int
) -> bool:
    """A-form E=2 specialization of the earlier proof-ledger predicate."""

    return weight > 0 and all(
        one_card_keeps_bad_illegal(edge, slot, card)
        for slot, card in enumerate(chosen)
    )


@dataclass(frozen=True)
class MacroState:
    debts: Debts
    bad: tuple[int, int, int]  # old colour, cap, fixed final colour
    columns: tuple[Column, Column, Column]
    remaining: Inventory


@dataclass(frozen=True)
class MacroOutcome:
    target: int
    run_length: int
    exhausted: bool
    successor: MacroState | None


class MacroSolver:
    """Strong online solver: choose a source before its next card is revealed."""

    def __init__(self) -> None:
        self.memo: dict[MacroState, bool] = {}
        self.policy: dict[MacroState, tuple[str, int] | tuple[str]] = {}

    def validate_state(self, state: MacroState) -> None:
        require(sum(state.debts) == 0, "z=0 macro debt sum drifted")
        require(len(state.columns) == 3, "macro state lost a sibling column")
        require(
            all(4 <= cap < HEIGHT for _, cap in state.columns),
            "macro sibling cap left 4..6",
        )
        require(
            completion_count(state.remaining, state.columns) > 0,
            "macro state has no fixed-word completion",
        )

    def outcomes(self, state: MacroState, slot: int) -> tuple[MacroOutcome, ...]:
        """All same-column maximal next cards having a fixed completion."""

        self.validate_state(state)
        top, cap = state.columns[slot]
        length = HEIGHT - cap
        result: list[MacroOutcome] = []
        for target in range(COLORS):
            if target == top:
                continue
            for run_length in range(1, length + 1):
                if state.remaining[target] < run_length:
                    continue
                remaining = list(state.remaining)
                remaining[target] -= run_length
                inventory = tuple(remaining)  # type: ignore[assignment]
                endpoint = cap + run_length

                if endpoint == HEIGHT:
                    other_columns = state.columns[:slot] + state.columns[slot + 1 :]
                    # The chosen run occupies this same column through cap 7;
                    # only the two untouched labelled columns remain to fill.
                    if completion_count(inventory, other_columns) == 0:
                        continue
                    require(
                        sum(value for _, value in other_columns) >= HEIGHT,
                        "sibling exhaustion lacks a surviving cap pair",
                    )
                    result.append(MacroOutcome(target, run_length, True, None))
                    continue

                columns = list(state.columns)
                columns[slot] = (target, endpoint)
                labelled = tuple(columns)
                # For a live maximal run, the first still-hidden cell of this
                # same selected column is constrained to differ from target.
                if completion_count(inventory, labelled) == 0:
                    continue
                debts = list(state.debts)
                debts[top] += cap
                debts[target] -= cap
                successor = MacroState(
                    tuple(debts),  # type: ignore[arg-type]
                    state.bad,
                    labelled,  # type: ignore[arg-type]
                    inventory,
                )
                require(
                    successor.columns[slot] == (target, endpoint),
                    "next card was reassigned to a different column",
                )
                result.append(MacroOutcome(target, run_length, False, successor))

        require(result, "a completable selected column has no compatible next card")
        return tuple(result)

    def wins(self, state: MacroState) -> bool:
        if state in self.memo:
            return self.memo[state]
        self.validate_state(state)

        bad_colour, bad_cap, _ = state.bad
        if source_is_legal(state.debts, bad_colour, bad_cap):
            ordered_caps = sorted(cap for _, cap in state.columns)
            require(
                ordered_caps[0] + ordered_caps[1] >= HEIGHT,
                "bad exhaustion lacks a surviving sibling cap pair",
            )
            self.memo[state] = True
            self.policy[state] = ("bad",)
            return True

        for slot, (top, cap) in enumerate(state.columns):
            if not source_is_legal(state.debts, top, cap):
                continue
            options = self.outcomes(state, slot)
            if all(
                outcome.exhausted
                or (
                    outcome.successor is not None
                    and self.wins(outcome.successor)
                )
                for outcome in options
            ):
                self.memo[state] = True
                self.policy[state] = ("sibling", slot)
                return True

        self.memo[state] = False
        return False


def cards(q_colour: int, cap: int) -> tuple[Card, ...]:
    return tuple(
        (colour, endpoint)
        for colour in range(COLORS)
        if colour != q_colour
        for endpoint in range(cap + 1, HEIGHT + 1)
    )


def initial_macro_state(
    edge: object,
    chosen: tuple[Card, Card, Card],
    remaining: Inventory,
) -> MacroState:
    debts = [debt for debt, _ in edge.parent]  # type: ignore[attr-defined]
    q = edge.q_color  # type: ignore[attr-defined]
    columns: list[Column] = []
    for old_cap, (target, endpoint) in zip(
        edge.q_caps, chosen  # type: ignore[attr-defined]
    ):
        debts[q] += old_cap
        debts[target] -= old_cap
        columns.append((target, endpoint))
    return MacroState(
        tuple(debts),  # type: ignore[arg-type]
        edge.action,  # type: ignore[attr-defined]
        tuple(columns),  # type: ignore[arg-type]
        remaining,
    )


def check_all_card_orders(
    edge: object, chosen: tuple[Card, Card, Card]
) -> None:
    """Every permutation of the three committed q_3 cards is legal."""

    q = edge.q_color  # type: ignore[attr-defined]
    for order in itertools.permutations(range(3)):
        debts = [debt for debt, _ in edge.parent]  # type: ignore[attr-defined]
        for slot in order:
            old_cap = edge.q_caps[slot]  # type: ignore[attr-defined]
            target, _ = chosen[slot]
            require(
                source_is_legal(debts, q, old_cap),
                "an untouched q_3 card lost legality",
            )
            debts[q] += old_cap
            debts[target] -= old_cap


def normalized_residual(state: MacroState, edge: object) -> tuple[object, ...]:
    q = edge.q_color  # type: ignore[attr-defined]
    a, bad_cap, f = edge.action  # type: ignore[attr-defined]
    b = next(colour for colour in range(COLORS) if colour not in (q, f, a))
    order = (q, f, a, b)
    rename = {colour: index for index, colour in enumerate(order)}
    parent_debts = tuple(edge.parent[colour][0] for colour in order)  # type: ignore[attr-defined]
    return (
        parent_debts,
        bad_cap,
        tuple(sorted((rename[top], cap) for top, cap in state.columns)),
        tuple(state.debts[colour] for colour in order),
        tuple(state.remaining[colour] for colour in order),
    )


def check_unique_residual(state: MacroState, edge: object, weight: int) -> None:
    signature = normalized_residual(state, edge)
    require(
        signature
        == (
            (-2, 0, 0, 2),
            6,
            ((1, 5), (1, 5), (1, 5)),
            (7, -9, 0, 2),
            (0, 0, 1, 5),
        ),
        f"unexpected final macro residual: {signature}",
    )
    require(weight == EXPECTED_RESIDUAL_WEIGHT, "unique residual weight drifted")
    require(
        completion_count(state.remaining, state.columns) == 6,
        "unique residual does not have six fixed completions",
    )

    q = edge.q_color  # type: ignore[attr-defined]
    a, _, f = edge.action  # type: ignore[attr-defined]
    b = next(colour for colour in range(COLORS) if colour not in (q, f, a))
    require(
        state.remaining[q] == state.remaining[f] == 0
        and state.remaining[a] == 1
        and state.remaining[b] == 5,
        "unique residual inventory is not a^1 b^5",
    )
    require(
        all(HEIGHT - cap == 2 and top == f for top, cap in state.columns),
        "unique residual is not three labelled f_5 two-cell tails",
    )

    # One a can occur in at most one of the three two-cell tails.  Therefore
    # at least two whole tails are bb.  Selecting either gives the maximal
    # exhausting card f_5 -> b_7.  The two untouched siblings retain caps
    # 5+5 >= 7, which is the pair-cap continuation hypothesis at z=1.
    guaranteed_bb_tails = len(state.columns) - state.remaining[a]
    require(guaranteed_bb_tails >= 2, "pigeonhole did not force two bb tails")
    require(
        sum(cap for _, cap in state.columns[:2]) >= HEIGHT,
        "surviving sibling pair does not meet the pair-cap threshold",
    )


def independent_census() -> dict[str, int]:
    fork = load_fork_module()
    terminals = fork.enumerate_tq_terminals()
    _, pairs = fork.reverse_bridge(terminals)
    edges = fork.build_sibling_edges(pairs)

    a_form_e2 = []
    for edge in edges:
        terminal_debts = fork.terminal_debts_in_parent_coordinates(edge)
        energy = -terminal_debts[edge.q_color]
        if energy != 2 or edge.a_equals_q:
            continue
        require(edge.q_caps == (3, 3, 3), "E=2 q caps are not 3,3,3")
        require(
            exposed_counts(edge)[edge.q_color] == HEIGHT,
            "E=2 parent has a hidden q item",
        )
        a_form_e2.append(edge)
    require(
        len(a_form_e2) == EXPECTED_A_FORM_E2_EDGES,
        "A-form E=2 edge census drifted",
    )

    solver = MacroSolver()
    decorations = 0
    weight_total = 0
    online_decorations = 0
    online_weight = 0
    active_edges: set[str] = set()
    residuals: list[tuple[MacroState, object, int]] = []

    for edge in a_form_e2:
        q = edge.q_color
        a, bad_cap, f = edge.action
        b = next(colour for colour in range(COLORS) if colour not in (q, f, a))
        anchor_energy = -edge.parent[a][0]
        require(
            tuple(edge.parent[colour][0] for colour in (q, f, a, b))
            == (-2, 0, -anchor_energy, anchor_energy + 2),
            "A-form parent normal form drifted",
        )

        for chosen in itertools.product(
            *(cards(q, cap) for cap in edge.q_caps)
        ):
            chosen = tuple(chosen)
            remaining, columns, weight = decoration_balance(edge, chosen)

            # Cross-check the previously independent sibling checker, but do
            # not use it to define either balance or the A-form D2 predicate.
            old_remaining, _, old_weight = fork.decoration_balance(edge, chosen)
            require(old_remaining == remaining, "decoration balance drifted")
            require(old_weight == weight, "decoration completion weight drifted")

            selected = is_d2_reduction_decoration(edge, chosen, weight)
            require(
                selected
                == (
                    weight > 0
                    and fork.refined_classify_decoration(edge, chosen)
                    == "d2_reduction"
                ),
                "independent A-form D2 predicate disagrees with the fork ledger",
            )
            if not selected:
                continue

            require(len(columns) == 3, "D2 decoration contains an exhausting card")
            decorations += 1
            weight_total += weight
            active_edges.add(edge.edge_id)

            check_all_card_orders(edge, chosen)
            state = initial_macro_state(edge, chosen, remaining)
            require(state.debts[q] == HEIGHT, "all-card macro did not fix d_q=7")
            require(state.remaining[q] == 0, "all-card macro retained hidden q")
            require(
                all(4 <= cap <= 6 for _, cap in state.columns),
                "D2 sibling card endpoint left 4..6",
            )
            require(
                completion_count(state.remaining, state.columns) == weight,
                "initial macro completion weight drifted",
            )
            require(
                source_is_legal(state.debts, a, bad_cap)
                or any(
                    source_is_legal(state.debts, top, cap)
                    for top, cap in state.columns
                ),
                "all-card macro has no legal source",
            )

            if solver.wins(state):
                online_decorations += 1
                online_weight += weight
            else:
                residuals.append((state, edge, weight))

    require(len(active_edges) == EXPECTED_ACTIVE_EDGES, "active edge count drifted")
    require(decorations == EXPECTED_DECORATIONS, "decoration count drifted")
    require(weight_total == EXPECTED_WEIGHT, "decoration weight drifted")
    require(
        online_decorations == EXPECTED_ONLINE_DECORATIONS,
        "online macro decoration count drifted",
    )
    require(online_weight == EXPECTED_ONLINE_WEIGHT, "online macro weight drifted")
    require(len(solver.memo) == EXPECTED_MACRO_STATES, "macro state count drifted")
    require(
        len(residuals) == EXPECTED_RESIDUAL_DECORATIONS,
        "final residual decoration count drifted",
    )
    require(
        sum(weight for _, _, weight in residuals) == EXPECTED_RESIDUAL_WEIGHT,
        "final residual weight drifted",
    )

    check_unique_residual(*residuals[0])
    return {
        "a_form_e2_edges": len(a_form_e2),
        "active_edges": len(active_edges),
        "decorations": decorations,
        "residual_word_weight": weight_total,
        "online_decorations": online_decorations,
        "online_weight": online_weight,
        "macro_states": len(solver.memo),
        "pigeonhole_decorations": len(residuals),
        "pigeonhole_weight": sum(weight for _, _, weight in residuals),
    }


def main() -> int:
    report = independent_census()
    print(
        "c4_h7_e2_a_not_q_four_source_ok "
        + " ".join(f"{key}={value}" for key, value in report.items())
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
