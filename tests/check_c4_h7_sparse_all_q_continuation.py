#!/usr/bin/env python3
"""Audit the terminal-triple lemma and the e184/e236 residual macros.

This checker deliberately performs no initial-layout solve and no successor
DP.  It reads the certified local-NO ledger, rebuilds only the exposed prefix
boxes for edges 184 and 236, and replays the symbolic run macros from the
already prescribed early-low successor.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import itertools
import json
from pathlib import Path
from typing import Iterator, Sequence


HEIGHT = 7
COLORS = 4
EMPTY = 2
Q, F, G, H = range(COLORS)
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = ROOT / "out" / "github-run-31434685211" / "report.json"

EXPECTED_LOCAL_NO = 14_784
EXPECTED_EDGE_ROWS = {184: 462, 236: 924}
EXPECTED_MACROS = {184: 6, 236: 8}
EXPECTED_PREFIXES = {184: 60, 236: 6}
EXPECTED_KERNEL_INSTANCES = {184: 924, 236: 3_696}

Debt = tuple[int, int, int, int]
Ranks = tuple[int, int, int, int]
Words = tuple[str, str, str, str]
Event = tuple[int, int, int, int]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def positive_count(values: Sequence[int]) -> int:
    return sum(value > 0 for value in values)


def source_legal(debts: Debt, color: int, cap: int, exhausted: int) -> bool:
    tested = list(debts)
    tested[color] += cap
    return positive_count(tested) <= EMPTY + exhausted


def terminal_direct(
    debts: Debt,
    sources: tuple[tuple[int, int], tuple[int, int], tuple[int, int]],
) -> bool:
    return not any(source_legal(debts, color, cap, 1) for color, cap in sources)


def terminal_formula(
    debts: Debt,
    sources: tuple[tuple[int, int], tuple[int, int], tuple[int, int]],
) -> bool:
    nonpositive = [color for color, value in enumerate(debts) if value <= 0]
    if len(nonpositive) != 1:
        return False
    common = nonpositive[0]
    return all(
        color == common and debts[common] + cap > 0
        for color, cap in sources
    )


def audit_terminal_triple() -> int:
    """Audit the exact theorem on the physical z=1 integer domain.

    At z=1, debt sums to seven.  The remaining three columns contain 21
    hosted-or-hidden units, so the inventory identity bounds each coordinate
    between 7-21=-14 and 7.
    The proof reduces the source-color product: with multiple nonpositive
    colors every source has a legal witness; with a unique nonpositive color,
    any differently colored source is a legal witness.  Only the all-common
    case needs the full cap product.
    """

    debts_checked = 0
    cap_triples_checked = 0
    for first_three in itertools.product(range(-14, 8), repeat=3):
        last = HEIGHT - sum(first_three)
        if not -14 <= last <= HEIGHT:
            continue
        debts: Debt = (*first_three, last)
        if positive_count(debts) > 3:
            continue
        debts_checked += 1
        nonpositive = [color for color, value in enumerate(debts) if value <= 0]
        require(nonpositive, "support bound lost its nonpositive coordinate")

        if len(nonpositive) > 1:
            for color in range(COLORS):
                for cap in range(1, HEIGHT):
                    require(
                        source_legal(debts, color, cap, 1),
                        "two-nonpositive state lost its legal-source witness",
                    )
            continue

        common = nonpositive[0]
        for color in range(COLORS):
            if color == common:
                continue
            for cap in range(1, HEIGHT):
                require(
                    source_legal(debts, color, cap, 1),
                    "non-common source should leave the common debt nonpositive",
                )

        for caps in itertools.product(range(1, HEIGHT), repeat=3):
            sources = tuple((common, cap) for cap in caps)
            require(
                terminal_direct(debts, sources) == terminal_formula(debts, sources),
                "terminal-triple formula differs from direct source tests",
            )
            cap_triples_checked += 1

    # Inventory form and the two-anchor consequence.
    for exposed in range(HEIGHT + 1):
        for caps in itertools.product(range(1, HEIGHT), repeat=3):
            debt_common = exposed - sum(caps)
            terminal_inequalities = all(
                debt_common + cap > 0 for cap in caps
            )
            if max(caps[0] + caps[1], caps[0] + caps[2], caps[1] + caps[2]) >= HEIGHT:
                require(
                    not terminal_inequalities,
                    "two anchors incorrectly satisfy the terminal inequalities",
                )
    return debts_checked * 1_000_000 + cap_triples_checked


@dataclass(frozen=True)
class ParentSpec:
    edge: int
    debts: Debt
    bad: tuple[int, int, int]
    q_caps: tuple[int, int, int]
    rows: int
    prefixes: int

    @property
    def caps(self) -> tuple[int, int, int, int]:
        return self.bad[1], *self.q_caps


SPECS = {
    184: ParentSpec(184, (-3, 0, 1, 2), (Q, 2, F), (2, 2, 4), 462, 60),
    236: ParentSpec(236, (-2, 0, 1, 1), (Q, 2, F), (1, 1, 3), 924, 6),
}


@dataclass(frozen=True)
class LedgerRow:
    future_index: int
    edge: int
    cards: tuple[tuple[int, int], tuple[int, int], tuple[int, int]]
    hidden_bottom_to_top: Words


def parse_int_tuple(value: object, size: int, label: str) -> tuple[int, ...]:
    require(isinstance(value, list) and len(value) == size, f"bad {label}")
    require(
        all(isinstance(item, int) and not isinstance(item, bool) for item in value),
        f"noninteger {label}",
    )
    return tuple(value)


def read_rows(report_path: Path) -> dict[int, tuple[LedgerRow, ...]]:
    require(report_path.is_file(), f"missing checkpoint report: {report_path}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    require(isinstance(report, dict), "checkpoint report is not an object")
    require(report.get("status") == "LOCAL_NO_RESIDUALS_EXPORTED", "wrong report status")
    run = report.get("run")
    require(isinstance(run, dict), "missing report run")
    require(run.get("universe_complete") is True, "checkpoint universe is incomplete")
    require(run.get("local_no") == EXPECTED_LOCAL_NO, "local-NO census drifted")
    scope = report.get("scope")
    require(isinstance(scope, dict), "missing report scope")
    require(scope.get("parent_checkpoint_only") is True, "wrong checkpoint scope")
    require(scope.get("zero_debt_past_restored") is False, "input overclaims past restoration")
    ledgers = report.get("ledgers")
    require(isinstance(ledgers, dict), "missing report ledgers")
    ledger_name = ledgers.get("local_no")
    require(isinstance(ledger_name, str), "missing local-NO ledger name")
    ledger_path = report_path.parent / ledger_name
    require(ledger_path.is_file(), f"missing local-NO ledger: {ledger_path}")

    selected: dict[int, list[LedgerRow]] = {184: [], 236: []}
    all_rows = 0
    previous = -1
    with ledger_path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            raw = json.loads(line)
            require(isinstance(raw, dict), f"line {line_number} is not an object")
            all_rows += 1
            future = raw.get("future_index")
            require(isinstance(future, int) and future > previous, "future order drifted")
            previous = future
            edge = raw.get("bridge_edge")
            if edge not in selected:
                continue
            spec = SPECS[edge]
            require(raw.get("local_status") == "NO", f"edge {edge}: row is not local NO")
            require(raw.get("safe_source_mask") == 0, f"edge {edge}: local source became safe")
            require(parse_int_tuple(raw.get("parent_debts"), 4, "parent debts") == spec.debts,
                    f"edge {edge}: parent debts drifted")
            require(parse_int_tuple(raw.get("bad_source"), 3, "bad source") == spec.bad,
                    f"edge {edge}: bad source drifted")
            require(parse_int_tuple(raw.get("q_caps"), 3, "q caps") == spec.q_caps,
                    f"edge {edge}: q caps drifted")
            raw_cards = raw.get("cards")
            require(isinstance(raw_cards, list) and len(raw_cards) == 3, "bad cards")
            cards = tuple(parse_int_tuple(card, 2, "card") for card in raw_cards)
            low_endpoint = 3 if edge == 184 else 2
            high_minimum = 5 if edge == 184 else 4
            require(
                cards[0] == cards[1] == (F, low_endpoint),
                f"edge {edge}: low cards drifted",
            )
            require(
                cards[2][0] in (G, H)
                and high_minimum <= cards[2][1] <= HEIGHT,
                f"edge {edge}: high card drifted",
            )
            raw_words = raw.get("hidden_words_bottom_to_top")
            require(isinstance(raw_words, list) and len(raw_words) == COLORS, "bad hidden words")
            words: Words = tuple(raw_words)  # type: ignore[assignment]
            for column, word in enumerate(words):
                require(isinstance(word, str) and set(word) <= set("0123"), "invalid hidden word")
                require(len(word) == HEIGHT - spec.caps[column], "hidden length drifted")
            selected[edge].append(LedgerRow(future, edge, cards, words))

    require(all_rows == EXPECTED_LOCAL_NO, "ledger row count drifted")
    result: dict[int, tuple[LedgerRow, ...]] = {}
    for edge, rows in selected.items():
        require(len(rows) == EXPECTED_EDGE_ROWS[edge], f"edge {edge}: row count drifted")
        require(len({row.cards for row in rows}) == EXPECTED_MACROS[edge],
                f"edge {edge}: card macro count drifted")
        result[edge] = tuple(rows)
    return result


def multiset_prefixes(spec: ParentSpec) -> tuple[Words, ...]:
    exposed = list(spec.debts)
    exposed[Q] += sum(spec.caps)
    exposed[Q] -= COLORS  # reserve the final q in each prefix
    free = sum(cap - 1 for cap in spec.caps)
    require(sum(exposed) == free and all(value >= 0 for value in exposed),
            f"edge {spec.edge}: bad exposed inventory")
    flat = [0] * free
    result: list[Words] = []

    def visit(position: int) -> None:
        if position == free:
            cursor = 0
            words: list[str] = []
            for cap in spec.caps:
                body = flat[cursor : cursor + cap - 1]
                cursor += cap - 1
                words.append("".join(map(str, body)) + str(Q))
            result.append(tuple(words))  # type: ignore[arg-type]
            return
        for color in range(COLORS):
            if exposed[color] == 0:
                continue
            exposed[color] -= 1
            flat[position] = color
            visit(position + 1)
            exposed[color] += 1

    visit(0)
    require(len(result) == spec.prefixes, f"edge {spec.edge}: prefix census drifted")
    require(len(set(result)) == len(result), f"edge {spec.edge}: duplicate prefix")
    return tuple(result)


def restore(row: LedgerRow, prefix: Words) -> Words:
    words = tuple(
        prefix[column] + row.hidden_bottom_to_top[column][::-1]
        for column in range(COLORS)
    )
    require(all(len(word) == HEIGHT for word in words), "restored word lost height")
    inventory = Counter(letter for word in words for letter in word)
    require(inventory == Counter({str(color): HEIGHT for color in range(COLORS)}),
            "restored kernel is not balanced")
    return words  # type: ignore[return-value]


def make_events(word: str) -> tuple[Event, ...]:
    runs: list[tuple[int, int]] = []
    cursor = 0
    while cursor < HEIGHT:
        end = cursor + 1
        while end < HEIGHT and word[end] == word[cursor]:
            end += 1
        runs.append((int(word[cursor]), end))
        cursor = end
    return tuple(
        (runs[index][0], runs[index][1], runs[index + 1][0], runs[index + 1][1])
        for index in range(len(runs) - 1)
    )


def run_count(word: str) -> int:
    return 1 + sum(left != right for left, right in zip(word, word[1:]))


class Fixture:
    def __init__(self, words: Words):
        self.words = words
        self.events = tuple(make_events(word) for word in words)

    def exhausted_count(self, ranks: Ranks) -> int:
        return sum(ranks[column] == len(self.events[column]) for column in range(COLORS))

    def debt(self, ranks: Ranks) -> Debt:
        debts = [0] * COLORS
        for column in range(COLORS):
            for old_color, old_cap, next_color, next_cap in self.events[column][:ranks[column]]:
                debts[old_color] += old_cap
                if next_cap == HEIGHT:
                    debts[next_color] += HEIGHT - old_cap
                else:
                    debts[next_color] -= old_cap
        return tuple(debts)  # type: ignore[return-value]

    def source(self, ranks: Ranks, column: int) -> tuple[int, int] | None:
        if ranks[column] == len(self.events[column]):
            return None
        event = self.events[column][ranks[column]]
        return event[0], event[1]

    def next_event(self, ranks: Ranks, column: int) -> Event:
        require(ranks[column] < len(self.events[column]), "event requested from exhausted column")
        return self.events[column][ranks[column]]

    def legal(self, ranks: Ranks, column: int) -> bool:
        source = self.source(ranks, column)
        if source is None:
            return False
        return source_legal(self.debt(ranks), source[0], source[1], self.exhausted_count(ranks))

    def advance(self, ranks: Ranks, column: int, expected: tuple[int, int] | None = None) -> Ranks:
        source = self.source(ranks, column)
        require(source is not None, "proof macro selected an exhausted column")
        if expected is not None:
            require(source == expected, f"source drifted: expected {expected}, got {source}")
        require(self.legal(ranks, column),
                "illegal proof event: "
                f"debt={self.debt(ranks)}, source={source}, "
                f"z={self.exhausted_count(ranks)}")
        child = list(ranks)
        child[column] += 1
        return tuple(child)  # type: ignore[return-value]


def early_successor(fixture: Fixture, prefix: Words, chosen: int) -> Ranks:
    ranks: Ranks = (0, 0, 0, 0)
    for _ in range(run_count(prefix[chosen])):
        ranks = fixture.advance(ranks, chosen)
    return ranks


def audit_two_anchor_state(fixture: Fixture, ranks: Ranks, columns: tuple[int, int]) -> None:
    require(fixture.exhausted_count(ranks) == 1, "two-anchor state is not z=1")
    require(positive_count(fixture.debt(ranks)) <= 3, "z=1 support invariant failed")
    sources = [fixture.source(ranks, column) for column in columns]
    require(all(source is not None for source in sources), "an anchor is exhausted")
    caps = [source[1] for source in sources if source is not None]
    require(sum(caps) >= HEIGHT, "anchor caps do not sum to seven")


def audit_edge184(row: LedgerRow, prefix: Words, chosen: int) -> int:
    words = restore(row, prefix)
    fixture = Fixture(words)
    other = 1 if chosen == 2 else 2
    ranks = early_successor(fixture, prefix, chosen)
    require(fixture.debt(ranks) == (1, -2, 1, 0), "e184 early debt drifted")
    require(fixture.source(ranks, chosen) == (F, 3), "e184 chosen source is not f3")

    ranks = fixture.advance(ranks, other, (Q, 2))
    require(fixture.source(ranks, other) == (F, 3), "e184 other low did not enter f3")
    tail_event = fixture.next_event(ranks, other)
    require(tail_event[0] == F and tail_event[1] == 3, "e184 tail source drifted")
    require(tail_event[2] in (G, H) and 4 <= tail_event[3] <= HEIGHT,
            "e184 first tail run is not a g/h cap in [4,7]")
    endpoint = tail_event[3]
    ranks = fixture.advance(ranks, other, (F, 3))

    ranks = fixture.advance(ranks, 0, (H, 1))
    ranks = fixture.advance(ranks, 0, (Q, 2))
    if endpoint == HEIGHT:
        require(fixture.exhausted_count(ranks) == 2, "e184 direct branch did not reach z=2")
    else:
        require(fixture.source(ranks, other) == (tail_event[2], endpoint),
                "e184 live tail source drifted")
        require(fixture.source(ranks, chosen) == (F, 3), "e184 f3 anchor moved")
        audit_two_anchor_state(fixture, ranks, (chosen, other))
    return 4


def audit_edge236(row: LedgerRow, prefix: Words, chosen: int) -> int:
    words = restore(row, prefix)
    fixture = Fixture(words)
    other = 1 if chosen == 2 else 2
    ranks = early_successor(fixture, prefix, chosen)
    require(fixture.debt(ranks) == (1, -1, 0, 0), "e236 early debt drifted")
    require(fixture.source(ranks, chosen) == (F, 2), "e236 chosen source is not f2")

    ranks = fixture.advance(ranks, 0, (Q, 2))
    require(fixture.exhausted_count(ranks) == 1, "e236 bad column did not exhaust first")
    require(fixture.debt(ranks) == (3, 4, 0, 0), "e236 first-exhaustion debt drifted")

    ranks = fixture.advance(ranks, chosen, (F, 2))
    require(fixture.source(ranks, chosen) == (Q, 3), "e236 chosen q is not singleton")
    chosen_tail = fixture.next_event(ranks, chosen)
    require(chosen_tail[2] in (G, H) and 4 <= chosen_tail[3] <= HEIGHT,
            "e236 chosen first tail run is invalid")
    ranks = fixture.advance(ranks, chosen, (Q, 3))
    steps = 3
    if chosen_tail[3] == HEIGHT:
        require(fixture.exhausted_count(ranks) == 2, "e236 chosen direct branch missed z=2")
        return steps

    ranks = fixture.advance(ranks, other, (Q, 1))
    ranks = fixture.advance(ranks, other, (F, 2))
    require(fixture.source(ranks, other) == (Q, 3), "e236 other q is not singleton")
    other_tail = fixture.next_event(ranks, other)
    require(other_tail[2] in (G, H) and 4 <= other_tail[3] <= HEIGHT,
            "e236 other first tail run is invalid")
    ranks = fixture.advance(ranks, other, (Q, 3))
    steps += 3
    if other_tail[3] == HEIGHT:
        require(fixture.exhausted_count(ranks) == 2, "e236 other direct branch missed z=2")
    else:
        require(fixture.source(ranks, chosen) == (chosen_tail[2], chosen_tail[3]),
                "e236 chosen anchor drifted")
        require(fixture.source(ranks, other) == (other_tail[2], other_tail[3]),
                "e236 other anchor drifted")
        audit_two_anchor_state(fixture, ranks, (chosen, other))
        require(chosen_tail[3] + other_tail[3] >= 8, "e236 anchors lost the 4+4 bound")
    return steps


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint-report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    encoded_terminal_audit = audit_terminal_triple()
    abstract_debts = encoded_terminal_audit // 1_000_000
    abstract_cap_triples = encoded_terminal_audit % 1_000_000
    rows = read_rows(args.checkpoint_report.resolve())

    prefixes184 = multiset_prefixes(SPECS[184])
    kernels184 = (
        (("30", "00", "20", "3000"), 2),
        (("30", "20", "00", "3000"), 1),
    )
    require(all(prefix in prefixes184 for prefix, _chosen in kernels184),
            "edge184 residual prefix left its balanced prefix box")

    prefixes236 = multiset_prefixes(SPECS[236])
    kernels236 = tuple(
        (prefix, chosen)
        for prefix in (("00", "0", "0", "230"), ("00", "0", "0", "320"))
        for chosen in (1, 2)
    )
    require(all(prefix in prefixes236 for prefix, _chosen in kernels236),
            "edge236 residual prefix left its balanced prefix box")

    instances = Counter()
    macro_events = Counter()
    for row in rows[184]:
        for prefix, chosen in kernels184:
            macro_events[184] += audit_edge184(row, prefix, chosen)
            instances[184] += 1
    for row in rows[236]:
        for prefix, chosen in kernels236:
            macro_events[236] += audit_edge236(row, prefix, chosen)
            instances[236] += 1

    require(dict(instances) == EXPECTED_KERNEL_INSTANCES, "kernel instance census drifted")
    print(
        "c4_h7_sparse_all_q_continuation_ok",
        f"abstract_z1_debts={abstract_debts}",
        f"all_common_cap_triples={abstract_cap_triples}",
        f"e184_prefix_box={len(prefixes184)}",
        f"e236_prefix_box={len(prefixes236)}",
        f"e184_kernel_instances={instances[184]}",
        f"e236_kernel_instances={instances[236]}",
        f"e184_macro_events={macro_events[184]}",
        f"e236_macro_events={macro_events[236]}",
        "successor_dp_states=0",
        "scope=specified_early_low_residual_kernels",
        "universal_h7_claim=false",
    )


if __name__ == "__main__":
    main()
