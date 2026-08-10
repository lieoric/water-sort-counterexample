#!/usr/bin/env python3
"""Audit the sparse all-q past bypass on the production local-NO ledger.

This checker reads the already certified report and local-NO rows.  It does
not solve Water Sort instances or expand any new residual future.
"""

from __future__ import annotations

import argparse
import itertools
import json
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Sequence


HEIGHT = 7
COLORS = 4
EMPTY = 2
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACT = ROOT / "out" / "github-run-31434685211"

EXPECTED_EDGE_ROWS = {
    116: (4, 210),
    117: (4, 252),
    184: (6, 462),
    236: (8, 924),
    242: (8, 11_088),
    244: (6, 924),
    248: (8, 924),
}
EXPECTED_ROWS = 14_784
EXPECTED_MACROS = 44
EXPECTED_PREFIX_BOXES = 7
EXPECTED_PREFIX_ASSIGNMENTS = 468
EXPECTED_PARENT_Q_SATURATED_ROWS = 2_772
EXPECTED_TRAP_ROWS = {
    "immediate_3plus1_d2": 13_398,
    "forced_two_2plus2_d2": 462,
    "forced_e2_tq_relay": 924,
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def positive_count(values: Sequence[int]) -> int:
    return sum(value > 0 for value in values)


def source_legal(debts: Sequence[int], color: int, cap: int, exhausted: int = 0) -> bool:
    tested = list(debts)
    tested[color] += cap
    return positive_count(tested) <= EMPTY + exhausted


@dataclass(frozen=True)
class Macro:
    edge: int
    decoration: int
    parent_debts: tuple[int, int, int, int]
    bad_source: tuple[int, int, int]
    q_color: int
    q_caps: tuple[int, int, int]
    cards: tuple[tuple[int, int], tuple[int, int], tuple[int, int]]


def tuple_ints(value: object, length: int, label: str) -> tuple[int, ...]:
    require(isinstance(value, list) and len(value) == length, f"bad {label}")
    require(all(isinstance(item, int) for item in value), f"noninteger {label}")
    return tuple(value)


def macro_from_row(row: dict[str, object]) -> Macro:
    raw_cards = row.get("cards")
    require(isinstance(raw_cards, list) and len(raw_cards) == 3, "bad cards")
    cards = tuple(tuple_ints(card, 2, "card") for card in raw_cards)
    return Macro(
        edge=int(row["bridge_edge"]),
        decoration=int(row["decoration_index"]),
        parent_debts=tuple_ints(row.get("parent_debts"), 4, "parent debts"),  # type: ignore[arg-type]
        bad_source=tuple_ints(row.get("bad_source"), 3, "bad source"),  # type: ignore[arg-type]
        q_color=int(row["q_color"]),
        q_caps=tuple_ints(row.get("q_caps"), 3, "q caps"),  # type: ignore[arg-type]
        cards=cards,  # type: ignore[arg-type]
    )


def read_report(path: Path) -> dict[str, object]:
    require(path.is_file(), f"missing production report: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), "report root is not an object")
    require(value.get("status") == "LOCAL_NO_RESIDUALS_EXPORTED", "wrong report status")
    run = value.get("run")
    universe = value.get("universe")
    require(isinstance(run, dict) and isinstance(universe, dict), "missing report ledger")
    require(run.get("universe_complete") is True, "production universe is incomplete")
    require(run.get("local_no") == EXPECTED_ROWS, "report local-NO count drifted")
    require(universe.get("selected_edges") == 12, "selected-edge universe drifted")
    require(universe.get("decorations") == 1_535, "production decoration count drifted")
    scope = value.get("scope")
    require(isinstance(scope, dict), "missing report scope")
    require(scope.get("parent_checkpoint_only") is True, "wrong report scope")
    require(scope.get("zero_debt_past_restored") is False, "report overclaims past restoration")
    return value


def read_ledger(path: Path) -> tuple[list[dict[str, object]], Counter[Macro]]:
    require(path.is_file(), f"missing production local-NO ledger: {path}")
    rows: list[dict[str, object]] = []
    macros: Counter[Macro] = Counter()
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            value = json.loads(line)
            require(isinstance(value, dict), f"ledger line {line_number} is not an object")
            require(value.get("local_status") == "NO", "non-NO row in local-NO ledger")
            require(value.get("safe_source_mask") == 0, "local-NO row has a safe source")
            macro = macro_from_row(value)
            require(macro.edge in EXPECTED_EDGE_ROWS, "unexpected local-NO edge")
            rows.append(value)
            macros[macro] += 1
    require(len(rows) == EXPECTED_ROWS, "local-NO ledger row count drifted")
    require(len(macros) == EXPECTED_MACROS, "canonical macro count drifted")
    return rows, macros


@dataclass(frozen=True)
class MacroFacts:
    q: int
    f: int
    positives: tuple[int, int]
    low_slots: tuple[int, int]
    high_slot: int
    exposed: tuple[int, int, int, int]
    q_energy: int
    q_saturated: bool


def validate_macro(macro: Macro) -> MacroFacts:
    debts = macro.parent_debts
    q = macro.q_color
    bad_color, bad_cap, f = macro.bad_source
    require(bad_color == q and f != q, "bad action is not q -> final f")
    require(sum(debts) == 0, "parent debt does not sum to zero")
    require(debts[q] < 0 and debts[f] == 0, "parent lacks q/f normal form")
    positives = tuple(color for color in range(COLORS) if debts[color] > 0)
    require(len(positives) == 2 and q not in positives and f not in positives,
            "parent does not have two positive complement colors")
    q_energy = -debts[q]
    require(q_energy == sum(debts[color] for color in positives) <= 4,
            "sparse all-q energy bound failed")

    all_caps = (bad_cap, *macro.q_caps)
    exposed = list(debts)
    exposed[q] += sum(all_caps)
    require(exposed[f] == 0, "parent already exposes f")
    require(all(0 <= value <= HEIGHT for value in exposed), "parent exposure is unphysical")
    require(exposed[q] >= 4, "all-q parent exposes fewer q than its four tops")

    low_slots = tuple(slot for slot, card in enumerate(macro.cards) if card[0] == f)
    require(len(low_slots) == 2, "macro does not have two low f siblings")
    high_slots = tuple(slot for slot in range(3) if slot not in low_slots)
    require(len(high_slots) == 1, "high sibling is ambiguous")
    high_slot = high_slots[0]

    require(source_legal(debts, q, bad_cap), "bad source is not parent-legal")
    for slot in low_slots:
        cap = macro.q_caps[slot]
        target, endpoint = macro.cards[slot]
        require(cap <= 2, "production low cap exceeds two")
        require(target == f and cap < endpoint < HEIGHT, "low card is not live q -> f")
        require(source_legal(debts, q, cap), "low sibling is not parent-legal")
    high_cap = macro.q_caps[high_slot]
    high_target, high_endpoint = macro.cards[high_slot]
    require(high_cap > q_energy, "high sibling is not parent-illegal")
    require(not source_legal(debts, q, high_cap), "high sibling unexpectedly legal")
    require(high_target in positives and high_cap < high_endpoint <= HEIGHT,
            "high card does not enter a complement color")
    require(
        sum(source_legal(debts, q, cap) for cap in all_caps) == 3,
        "parent does not have exactly three legal sources",
    )

    assigned_f = HEIGHT - bad_cap
    assigned_f += sum(
        macro.cards[slot][1] - macro.q_caps[slot] for slot in low_slots
    )
    require(assigned_f == HEIGHT, "bad tail and low cards do not saturate f")

    return MacroFacts(
        q=q,
        f=f,
        positives=positives,  # type: ignore[arg-type]
        low_slots=low_slots,  # type: ignore[arg-type]
        high_slot=high_slot,
        exposed=tuple(exposed),  # type: ignore[arg-type]
        q_energy=q_energy,
        q_saturated=exposed[q] == HEIGHT,
    )


def runs(word: Sequence[int]) -> tuple[tuple[int, int], ...]:
    result: list[tuple[int, int]] = []
    for color in word:
        if result and result[-1][0] == color:
            result[-1] = (color, result[-1][1] + 1)
        else:
            result.append((color, 1))
    return tuple(result)


def solo_prefix_debt(word: tuple[int, ...], q: int) -> tuple[int, int, int, int]:
    chain = runs(word)
    debt = [0, 0, 0, 0]
    top, cap = chain[0]
    for next_color, length in chain[1:]:
        require(source_legal(debt, top, cap), "two-color prefix is not solo-legal")
        debt[top] += cap
        debt[next_color] -= cap
        top = next_color
        cap += length
    require(top == q and cap == len(word), "prefix does not end at its q cap")
    counts = Counter(word)
    expected = tuple(counts[color] - len(word) * int(color == q) for color in range(COLORS))
    require(tuple(debt) == expected, "solo-prefix debt identity failed")
    return tuple(debt)  # type: ignore[return-value]


def initial_source(word: tuple[int, ...]) -> tuple[int, int]:
    first = word[0]
    length = 1
    while length < len(word) and word[length] == first:
        length += 1
    return first, length


def early_low_terminal(
    words: tuple[tuple[int, ...], ...],
    chosen_column: int,
    q: int,
    f: int,
    endpoint: int,
) -> bool:
    word = words[chosen_column]
    cap = len(word)
    debt = list(solo_prefix_debt(word, q))
    require(source_legal(debt, q, cap), "early q source is not legal")
    debt[q] += cap
    debt[f] -= cap

    sources = [(f, endpoint)]
    sources.extend(initial_source(words[column]) for column in range(4) if column != chosen_column)
    terminal = not any(source_legal(debt, color, source_cap) for color, source_cap in sources)

    non_q = [color for color in word if color != q]
    if not non_q:
        require(not terminal, "all-q early low move became terminal")
    else:
        require(len(word) == 2 and len(non_q) == 1, "low prefix is not q/qq/xq")
        x = non_q[0]
        y_candidates = [color for color in range(COLORS) if color not in (q, f, x)]
        require(len(y_candidates) == 1, "low-prefix complement is ambiguous")
        y = y_candidates[0]
        predicted = all(words[column][0] == y for column in range(4) if column != chosen_column)
        require(terminal == predicted, "early xq terminal criterion failed")
    return terminal


@lru_cache(maxsize=None)
def prefix_box(
    caps: tuple[int, int, int, int],
    exposed: tuple[int, int, int, int],
    q: int,
    f: int,
    low_columns: tuple[int, int],
    low_endpoints: tuple[int, int],
) -> tuple[int, tuple[tuple[bool, bool], ...]]:
    alphabet = tuple(color for color in range(COLORS) if color != f)
    options = tuple(
        tuple(prefix + (q,) for prefix in itertools.product(alphabet, repeat=cap - 1))
        for cap in caps
    )
    outcomes: Counter[tuple[bool, bool]] = Counter()
    assignments = 0
    for words in itertools.product(*options):
        counts = Counter(color for word in words for color in word)
        if tuple(counts[color] for color in range(COLORS)) != exposed:
            continue
        assignments += 1
        terminal = tuple(
            early_low_terminal(words, column, q, f, endpoint)
            for column, endpoint in zip(low_columns, low_endpoints)
        )
        require(terminal == (False, False), "a production early low move is terminal")
        outcomes[terminal] += 1
    require(assignments > 0, "macro has no compatible exposed-prefix assignment")
    return assignments, tuple(sorted(outcomes.items()))


def audit_prefixes(macro: Macro, facts: MacroFacts) -> dict[str, object]:
    # Column order is bad, then the three q siblings used by the ledger.
    caps = (macro.bad_source[1], *macro.q_caps)
    low_columns = tuple(slot + 1 for slot in facts.low_slots)
    low_endpoints = tuple(macro.cards[slot][1] for slot in facts.low_slots)
    assignments, raw_outcomes = prefix_box(
        caps,
        facts.exposed,
        facts.q,
        facts.f,
        low_columns,  # type: ignore[arg-type]
        low_endpoints,  # type: ignore[arg-type]
    )
    outcomes = dict(raw_outcomes)
    require(outcomes == {(False, False): assignments}, "an early low terminal escaped")
    return {
        "assignments": assignments,
        "both_nonterminal": outcomes.get((False, False), 0),
        "only_first_terminal": outcomes.get((True, False), 0),
        "only_second_terminal": outcomes.get((False, True), 0),
    }


def live_step(
    debts: tuple[int, int, int, int],
    tops: tuple[tuple[int, int], ...],
    column: int,
    target: int,
    endpoint: int,
    exhausted: int = 0,
) -> tuple[tuple[int, int, int, int], tuple[tuple[int, int], ...]]:
    source, cap = tops[column]
    require(
        source_legal(debts, source, cap, exhausted),
        "structural live step is illegal",
    )
    updated = list(debts)
    updated[source] += cap
    updated[target] -= cap
    next_tops = list(tops)
    next_tops[column] = (target, endpoint)
    return tuple(updated), tuple(next_tops)  # type: ignore[return-value]


def exhaust_step(
    debts: tuple[int, int, int, int],
    tops: tuple[tuple[int, int] | None, ...],
    column: int,
    final_color: int,
) -> tuple[tuple[int, int, int, int], tuple[tuple[int, int] | None, ...]]:
    source_info = tops[column]
    require(source_info is not None, "exhausted structural source is absent")
    source, cap = source_info
    require(source_legal(debts, source, cap), "structural exhausting step is illegal")
    updated = list(debts)
    updated[source] += cap
    updated[final_color] += HEIGHT - cap
    next_tops = list(tops)
    next_tops[column] = None
    return tuple(updated), tuple(next_tops)  # type: ignore[return-value]


def legal_top_indices(
    debts: Sequence[int], tops: Sequence[tuple[int, int] | None], exhausted: int = 0
) -> tuple[int, ...]:
    return tuple(
        index
        for index, source in enumerate(tops)
        if source is not None and source_legal(debts, source[0], source[1], exhausted)
    )


def validate_forward_trap(macro: Macro, facts: MacroFacts) -> str:
    tops: tuple[tuple[int, int], ...] = (
        (facts.q, macro.bad_source[1]),
        *((facts.q, cap) for cap in macro.q_caps),
    )
    low_columns = tuple(slot + 1 for slot in facts.low_slots)

    if macro.edge in (184, 242, 244, 248):
        for slot, column in zip(facts.low_slots, low_columns):
            after_debt, after_tops = live_step(
                macro.parent_debts,
                tops,
                column,
                facts.f,
                macro.cards[slot][1],
            )
            require(not legal_top_indices(after_debt, after_tops), "immediate D2 is not terminal")
        return "immediate_3plus1_d2"

    if macro.edge in (116, 117):
        first_slot, second_slot = facts.low_slots
        first_column, second_column = low_columns
        debt1, tops1 = live_step(
            macro.parent_debts,
            tops,
            first_column,
            facts.f,
            macro.cards[first_slot][1],
        )
        require(legal_top_indices(debt1, tops1) == (second_column,), "second low is not forced")
        debt2, tops2 = live_step(
            debt1,
            tops1,
            second_column,
            facts.f,
            macro.cards[second_slot][1],
        )
        require(not legal_top_indices(debt2, tops2), "forced-two D2 is not terminal")
        return "forced_two_2plus2_d2"

    require(macro.edge == 236, "unknown forward-trap edge")
    first_slot, second_slot = facts.low_slots
    first_column, second_column = low_columns
    debt1, tops1 = live_step(
        macro.parent_debts, tops, first_column, facts.f, macro.cards[first_slot][1]
    )
    require(legal_top_indices(debt1, tops1) == (second_column,), "edge236 second low not forced")
    debt2, tops2 = live_step(
        debt1, tops1, second_column, facts.f, macro.cards[second_slot][1]
    )
    require(set(legal_top_indices(debt2, tops2)) == set(low_columns), "edge236 f pair not forced")
    debt3, tops3 = live_step(debt2, tops2, first_column, facts.q, 3)
    require(legal_top_indices(debt3, tops3) == (0,), "edge236 bad source not forced")
    debt4, tops4 = exhaust_step(debt3, tops3, 0, facts.f)
    require(legal_top_indices(debt4, tops4, 1) == (second_column,), "edge236 last f not forced")
    debt5, tops5_live = live_step(
        debt4,
        tuple(source for source in tops4 if source is not None),  # type: ignore[arg-type]
        # Removing column zero shifts both surviving low columns down by one.
        second_column - 1,
        facts.q,
        3,
        1,
    )
    # Rebuild the final top multiset instead of relying on the shifted tuple.
    require(debt5 == (-2, 7, 1, 1), "edge236 E=2 relay debt drifted")
    require(sorted(tops5_live) == [(facts.q, 3)] * 3, "edge236 final q caps drifted")
    require(not legal_top_indices(debt5, tops5_live, 1), "edge236 E=2 Tq is not terminal")
    exposed_q = debt5[facts.q] + sum(cap for color, cap in tops5_live if color == facts.q)
    require(exposed_q == HEIGHT and debt5[facts.f] == HEIGHT,
            "edge236 relay did not saturate q and f")
    return "forced_e2_tq_relay"


def check_edge236_words(rows: Iterable[dict[str, object]], macros: dict[Macro, MacroFacts]) -> int:
    checked = 0
    for row in rows:
        if int(row["bridge_edge"]) != 236:
            continue
        macro = macro_from_row(row)
        facts = macros[macro]
        words = row.get("hidden_words_bottom_to_top")
        require(isinstance(words, list) and len(words) == 4, "edge236 row has bad words")
        for slot in facts.low_slots:
            word = words[slot + 1]
            require(isinstance(word, str), "edge236 low word is not text")
            chain = runs(tuple(int(char) for char in reversed(word)))
            require(
                len(chain) >= 2
                and chain[0] == (facts.f, 1)
                and chain[1] == (facts.q, 1),
                "edge236 local-NO word lacks singleton f -> q relay",
            )
        checked += 1
    require(checked == EXPECTED_EDGE_ROWS[236][1], "edge236 relay row count drifted")
    return checked


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_ARTIFACT / "report.json",
        help="certified production three-source report.json",
    )
    parser.add_argument(
        "--local-no-ledger",
        type=Path,
        default=DEFAULT_ARTIFACT / "local-no-ledger.jsonl",
        help="certified production local-no-ledger.jsonl",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = read_report(args.report.resolve())
    rows, macro_weights = read_ledger(args.local_no_ledger.resolve())

    report_edges = {
        int(row["bridge_edge"]): int(row["local_no"])
        for row in report["per_edge"]  # type: ignore[index]
        if int(row["local_no"]) > 0
    }
    require(
        report_edges == {edge: values[1] for edge, values in EXPECTED_EDGE_ROWS.items()},
        "report/ledger local-NO edge split drifted",
    )

    edge_macro_counts: Counter[int] = Counter()
    edge_row_counts: Counter[int] = Counter()
    validated: dict[Macro, MacroFacts] = {}
    prefix_cache_rows: dict[tuple[object, ...], dict[str, object]] = {}
    trap_rows: Counter[str] = Counter()
    saturated_rows = 0
    for macro, weight in macro_weights.items():
        facts = validate_macro(macro)
        validated[macro] = facts
        edge_macro_counts[macro.edge] += 1
        edge_row_counts[macro.edge] += weight
        if facts.q_saturated:
            saturated_rows += weight
        trap_rows[validate_forward_trap(macro, facts)] += weight

        prefix_result = audit_prefixes(macro, facts)
        prefix_key = (
            macro.parent_debts,
            macro.bad_source,
            macro.q_caps,
            facts.low_slots,
            tuple(macro.cards[slot] for slot in facts.low_slots),
        )
        previous = prefix_cache_rows.setdefault(prefix_key, prefix_result)
        require(previous == prefix_result, "equivalent prefix boxes disagree")

    require(
        {
            edge: (edge_macro_counts[edge], edge_row_counts[edge])
            for edge in EXPECTED_EDGE_ROWS
        }
        == EXPECTED_EDGE_ROWS,
        "edge macro/row census drifted",
    )
    require(saturated_rows == EXPECTED_PARENT_Q_SATURATED_ROWS,
            "parent q-saturation row count drifted")
    require(dict(trap_rows) == EXPECTED_TRAP_ROWS, "forward-trap split drifted")
    relay_rows = check_edge236_words(rows, validated)

    prefix_assignments = sum(int(row["assignments"]) for row in prefix_cache_rows.values())
    require(len(prefix_cache_rows) == EXPECTED_PREFIX_BOXES, "prefix-box count drifted")
    require(
        prefix_assignments == EXPECTED_PREFIX_ASSIGNMENTS,
        "compatible prefix-assignment count drifted",
    )
    result = {
        "status": "SPARSE_ALL_Q_BYPASS_VERIFIED",
        "claim_boundary": {
            "all_ledger_parents_have_early_low_nonterminal_bypass": True,
            "both_low_choices_nonterminal_for_every_compatible_past": True,
            "bypass_successor_proved_winning": False,
            "zero_debt_initial_layouts_solved": False,
            "universal_h7_solvability_proved": False,
            "new_residual_futures_expanded": False,
        },
        "production": {
            "local_no_rows": len(rows),
            "canonical_card_macros": len(macro_weights),
            "edges": {
                str(edge): {
                    "macros": edge_macro_counts[edge],
                    "rows": edge_row_counts[edge],
                }
                for edge in sorted(EXPECTED_EDGE_ROWS)
            },
        },
        "structure": {
            "parent_q_saturated_rows": saturated_rows,
            "parent_q_unsaturated_rows": len(rows) - saturated_rows,
            "forward_trap_rows": dict(sorted(trap_rows.items())),
            "edge236_singleton_q_relay_rows": relay_rows,
        },
        "past_prefix_audit": {
            "distinct_boxes": len(prefix_cache_rows),
            "compatible_assignments": prefix_assignments,
            "either_early_low_terminal": 0,
            "both_early_low_terminal": 0,
            "boxes": list(prefix_cache_rows.values()),
        },
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
