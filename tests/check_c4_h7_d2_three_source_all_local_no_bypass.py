#!/usr/bin/env python3
"""Small symbolic audit of all three-source D2 local-NO past bypasses.

Only the 468 labelled zero-debt past templates and a few generic next-run
parameters are enumerated.  No fixed hidden future is expanded and no
production checkpoint recursion is run.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from itertools import product
from pathlib import Path


HEIGHT = 7
Q, F, G, HH = range(4)
Debt = tuple[int, int, int, int]
Word = tuple[int, ...]
Pasts = tuple[Word, Word, Word, Word]


@dataclass(frozen=True)
class EdgeSpec:
    edge: int
    parent: Debt
    caps: tuple[int, int, int, int]  # bad A, anchors C,D, large B
    f_caps: tuple[int, int]
    expected_exposed: Debt
    expected_pasts: int
    local_no: int


SPECS = (
    EdgeSpec(116, (-4, 0, 1, 3), (4, 1, 1, 5), (3, 3),
             (7, 0, 1, 3), 140, 210),
    EdgeSpec(117, (-4, 0, 2, 2), (4, 1, 1, 5), (3, 3),
             (7, 0, 2, 2), 210, 252),
    EdgeSpec(184, (-3, 0, 1, 2), (2, 2, 2, 4), (3, 3),
             (7, 0, 1, 2), 60, 462),
    EdgeSpec(236, (-2, 0, 1, 1), (2, 1, 1, 3), (2, 2),
             (5, 0, 1, 1), 6, 924),
    EdgeSpec(242, (-2, 0, 1, 1), (2, 1, 2, 3), (2, 3),
             (6, 0, 1, 1), 12, 11_088),
    EdgeSpec(244, (-2, 0, 1, 1), (2, 1, 2, 4), (2, 3),
             (7, 0, 1, 1), 20, 924),
    EdgeSpec(248, (-2, 0, 1, 1), (2, 2, 2, 3), (3, 3),
             (7, 0, 1, 1), 20, 924),
)


def add(*vectors: Debt) -> Debt:
    return tuple(sum(vector[color] for vector in vectors) for color in range(4))  # type: ignore[return-value]


def basis(color: int, amount: int) -> Debt:
    values = [0, 0, 0, 0]
    values[color] = amount
    return tuple(values)  # type: ignore[return-value]


def counts(word: Word) -> Debt:
    result = Counter(word)
    return tuple(result[color] for color in range(4))  # type: ignore[return-value]


def positive_count(values: Debt) -> int:
    return sum(value > 0 for value in values)


def support(word: Word) -> set[int]:
    return set(word)


def run_ends(word: Word) -> list[int]:
    result: list[int] = []
    cursor = 0
    while cursor < len(word):
        end = cursor + 1
        while end < len(word) and word[end] == word[cursor]:
            end += 1
        result.append(end)
        cursor = end
    return result


def walk_legal(background: Debt, word: Word, threshold: int) -> bool:
    return all(
        positive_count(add(background, counts(word[:end]))) <= threshold
        for end in run_ends(word)
    )


def exposed(spec: EdgeSpec) -> Debt:
    return add(spec.parent, basis(Q, sum(spec.caps)))


def past_templates(spec: EdgeSpec) -> list[Pasts]:
    inventory = list(exposed(spec))
    inventory[Q] -= 4  # one final q in each past word
    free_positions = sum(cap - 1 for cap in spec.caps)
    wanted = Counter(
        {color: amount for color, amount in enumerate(inventory) if amount}
    )
    result: list[Pasts] = []
    for letters in product((Q, G, HH), repeat=free_positions):
        if Counter(letters) != wanted:
            continue
        words: list[Word] = []
        cursor = 0
        for cap in spec.caps:
            words.append(letters[cursor:cursor + cap - 1] + (Q,))
            cursor += cap - 1
        pasts = tuple(words)  # type: ignore[assignment]
        assert add(*(counts(word) for word in pasts)) == exposed(spec)
        result.append(pasts)
    assert len(result) == spec.expected_pasts
    assert len(set(result)) == spec.expected_pasts
    return result


def anchor_background(spec: EdgeSpec, pasts: Pasts) -> Debt:
    _a, c, d, _b = pasts
    return add(counts(c), counts(d), basis(F, -spec.caps[1] - spec.caps[2]))


def anchor_reachable(spec: EdgeSpec, pasts: Pasts) -> bool:
    _a, c, d, _b = pasts
    return len(support(c + d)) <= 2


def check_anchor_walk(spec: EdgeSpec, pasts: Pasts) -> Debt:
    _a, c, d, _b = pasts
    assert anchor_reachable(spec, pasts)
    zero: Debt = (0, 0, 0, 0)
    assert walk_legal(zero, c, 2)
    after_c = add(counts(c), basis(F, -spec.caps[1]))
    assert walk_legal(after_c, d, 2)
    background = anchor_background(spec, pasts)
    assert positive_count(background) <= 2
    return background


def compatible(background_support: set[int], word: Word) -> bool:
    return len(background_support | support(word)) <= 2


def no_third_live_f(spec: EdgeSpec) -> bool:
    """The bad tail and two anchor cards consume the entire hidden f budget."""

    assert spec.expected_exposed[F] == 0
    bad_tail = HEIGHT - spec.caps[0]
    anchor_runs = sum(
        endpoint - cap
        for cap, endpoint in zip(spec.caps[1:3], spec.f_caps)
    )
    assert bad_tail > 0
    assert bad_tail + anchor_runs == HEIGHT
    return True


def check_pair_cap_lemma() -> int:
    checked = 0
    for hidden in range(HEIGHT + 1):
        for cap_1 in range(1, HEIGHT + 1):
            for cap_2 in range(1, HEIGHT + 1):
                if cap_1 + cap_2 < HEIGHT:
                    continue
                for cap_3 in range(1, HEIGHT + 1):
                    debt_j = HEIGHT - hidden - cap_1 - cap_2 - cap_3
                    assert debt_j + cap_3 <= 0
                    checked += 1
    assert checked > 0
    return checked


def check_ordinary(spec: EdgeSpec, pasts: Pasts) -> None:
    a, _c, _d, b_word = pasts
    background = check_anchor_walk(spec, pasts)
    anchor_support = support(pasts[1] + pasts[2])
    compatible_deep = [
        column for column, word in ((0, a), (3, b_word))
        if compatible(anchor_support, word)
    ]
    assert compatible_deep

    if 0 in compatible_deep:
        assert walk_legal(background, a, 2)
    else:
        assert compatible_deep == [3]
        assert walk_legal(background, b_word, 2)
        large_cap = spec.caps[3]
        for target in (G, HH):
            assert large_cap > spec.expected_exposed[target]
            live = add(background, counts(b_word), basis(target, -large_cap))
            assert walk_legal(live, a, 2)

    assert no_third_live_f(spec)
    assert (spec.f_caps[0] + 1) + (spec.f_caps[1] + 1) >= HEIGHT


def second_non_q_exposure(word: Word) -> tuple[int, int]:
    seen: list[int] = []
    for index, color in enumerate(word):
        if color == Q or color in seen:
            continue
        seen.append(color)
        if len(seen) == 2:
            return color, index + 1
    raise AssertionError("word does not expose two distinct non-q colours")


def check_rigid_117(spec: EdgeSpec, pasts: Pasts) -> None:
    a, _c, _d, b_word = pasts
    background = check_anchor_walk(spec, pasts)
    assert background == (2, -2, 0, 0)
    assert counts(a)[G:] == (1, 1)
    assert counts(b_word)[G:] == (1, 1)

    target, cap = second_non_q_exposure(b_word)
    start = cap - 1  # both non-q letters are singletons
    assert positive_count(add(background, counts(b_word[:start]))) <= 2
    exposed_state = add(
        background, counts(b_word[:cap]), basis(target, -cap)
    )
    assert exposed_state[target] + counts(a)[target] <= 0
    assert walk_legal(exposed_state, a, 2)
    assert no_third_live_f(spec)
    assert 4 + 4 >= HEIGHT


def check_rigid_184(spec: EdgeSpec, pasts: Pasts) -> None:
    a, _c, _d, b_word = pasts
    background = check_anchor_walk(spec, pasts)
    anchor_non_q = support(pasts[1] + pasts[2]) - {Q}
    assert len(anchor_non_q) == 1
    deep_non_q = (support(a) | support(b_word)) - {Q}
    assert len(deep_non_q) == 1
    anchor_color = next(iter(anchor_non_q))
    deep_color = next(iter(deep_non_q))
    assert anchor_color != deep_color
    assert a == (deep_color, Q)
    assert counts(b_word)[deep_color] == 1

    if b_word[0] != deep_color:
        index = b_word.index(deep_color)
        cap = index + 1
        assert walk_legal(background, b_word[:index], 2)
        exposed_state = add(
            background, counts(b_word[:cap]), basis(deep_color, -cap)
        )
        assert exposed_state[deep_color] + 1 <= 0
        assert walk_legal(exposed_state, a, 2)
    else:
        assert positive_count(add(background, basis(F, 3))) <= 2
        for target in (G, HH):
            live = add(background, basis(F, 3), basis(target, -3))
            assert walk_legal(live, a, 2)

            exhaust = add(background, basis(F, 3), basis(target, 4))
            assert walk_legal(exhaust, a, 3)
        assert no_third_live_f(spec)
        assert 4 + 4 >= HEIGHT


def enter_f3_from_xq(state: Debt, word: Word, threshold: int) -> Debt:
    assert len(word) == 2 and word[-1] == Q and word[0] in (G, HH)
    old_color = word[0]
    assert positive_count(add(state, basis(old_color, 1))) <= threshold
    at_q = add(state, basis(old_color, 1), basis(Q, -1))
    assert positive_count(add(at_q, basis(Q, 2))) <= threshold
    return add(at_q, basis(Q, 2), basis(F, -2))


def check_incompatible_184(spec: EdgeSpec, pasts: Pasts) -> None:
    a, c, d, b_word = pasts
    assert not anchor_reachable(spec, pasts)
    assert {c, d} == {(G, Q), (HH, Q)}
    assert support(a) <= {Q, HH}
    assert support(b_word) <= {Q, HH}
    zero: Debt = (0, 0, 0, 0)
    assert walk_legal(zero, b_word, 2)

    for target in (G, HH):
        # q_4 exhausts into a homogeneous final run of length three.
        exhaust_b = add(counts(b_word), basis(target, 3))
        assert walk_legal(exhaust_b, a, 3)

        # Or q_4 enters a live target run; then A exhausts.
        live_b = add(counts(b_word), basis(target, -4))
        assert walk_legal(live_b, a, 2)
        after_a = add(live_b, counts(a), basis(F, 5))
        after_anchor = enter_f3_from_xq(after_a, c, 3)
        assert positive_count(after_anchor) <= 3
        assert no_third_live_f(spec)
        assert 5 + 3 >= HEIGHT


def check_incompatible_248(spec: EdgeSpec, pasts: Pasts) -> None:
    a, c, d, b_word = pasts
    assert not anchor_reachable(spec, pasts)
    assert a == (Q, Q)
    assert b_word == (Q, Q, Q)
    assert {c, d} == {(G, Q), (HH, Q)}

    after_a = add(counts(a), basis(F, 5))
    assert after_a == (2, 5, 0, 0)
    assert positive_count(add(after_a, basis(Q, 3))) <= 3
    for target in (G, HH):
        live_b = add(after_a, basis(Q, 3), basis(target, -3))
        after_anchor = enter_f3_from_xq(live_b, c, 3)
        assert positive_count(after_anchor) <= 3
        assert no_third_live_f(spec)
        assert 4 + 3 >= HEIGHT


def check_edge_236(spec: EdgeSpec, pasts: Pasts) -> str:
    a, _c, _d, b_word = pasts
    background = check_anchor_walk(spec, pasts)
    assert background == (2, -2, 0, 0)

    if len(support(b_word)) <= 2:
        assert walk_legal(background, b_word, 2)
        for target in (G, HH):
            exhaust_b = add(background, counts(b_word), basis(target, 4))
            assert walk_legal(exhaust_b, a, 3)

            live_b = add(background, counts(b_word), basis(target, -3))
            assert walk_legal(live_b, a, 2)
            after_a = add(live_b, counts(a), basis(F, 5))

            # The fixed family has f_2 -> q_3 on either anchor.
            assert positive_count(add(after_a, basis(F, 2))) <= 3
            after_f_to_q = add(after_a, basis(F, 2), basis(Q, -2))
            assert positive_count(after_f_to_q) <= 3
            assert no_third_live_f(spec)
            assert 4 + 3 >= HEIGHT
        return "edge236_large_compatible"

    assert a == (Q, Q)
    assert b_word in ((G, HH, Q), (HH, G, Q))
    after_a = add(background, counts(a), basis(F, 5))
    assert after_a == (4, 3, 0, 0)
    first, second, _q = b_word
    assert positive_count(add(after_a, basis(first, 1))) <= 3
    blocked_b = add(after_a, basis(first, 1), basis(second, -1))

    # Fixed f_2 -> q_3 rotor.
    assert positive_count(add(blocked_b, basis(F, 2))) <= 3
    after_f_to_q = add(blocked_b, basis(F, 2), basis(Q, -2))
    assert positive_count(add(after_f_to_q, basis(Q, 3))) <= 3
    for target in (G, HH):
        after_q_live = add(after_f_to_q, basis(Q, 3), basis(target, -3))
        assert positive_count(add(after_q_live, basis(second, 2))) <= 3
        assert no_third_live_f(spec)
        assert 4 + 3 >= HEIGHT
    return "edge236_short_rigid"


EXPECTED_CLASSES = Counter({
    "edge116_ordinary": 140,
    "edge117_ordinary": 138,
    "edge117_rigid": 72,
    "edge184_ordinary": 46,
    "edge184_rigid": 6,
    "edge184_anchor_incompatible": 8,
    "edge236_large_compatible": 4,
    "edge236_short_rigid": 2,
    "edge242_ordinary": 12,
    "edge244_ordinary": 20,
    "edge248_ordinary": 18,
    "edge248_anchor_incompatible": 2,
})

EXPECTED_MACROS_PER_EDGE = {
    116: 4,
    117: 4,
    184: 6,
    236: 8,
    242: 8,
    244: 6,
    248: 8,
}

EXPECTED_MACRO_ROW_MULTISETS = {
    116: Counter({28: 1, 56: 2, 70: 1}),
    117: Counter({56: 2, 70: 2}),
    184: Counter({28: 1, 56: 2, 70: 1, 126: 2}),
    236: Counter({28: 2, 56: 2, 126: 2, 252: 2}),
    242: Counter({252: 2, 588: 2, 1470: 2, 3234: 2}),
    244: Counter({84: 2, 126: 2, 252: 2}),
    248: Counter({28: 2, 56: 2, 126: 2, 252: 2}),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit the symbolic bypass and, optionally, a formal local-NO fixture."
    )
    parser.add_argument("--report", type=Path, help="complete three-source report.json")
    parser.add_argument("--ledger", type=Path, help="complete local-no-ledger.jsonl")
    args = parser.parse_args()
    if (args.report is None) != (args.ledger is None):
        parser.error("--report and --ledger must be supplied together")
    return args


def require_int(value: object, label: str) -> int:
    assert isinstance(value, int) and not isinstance(value, bool), label
    return value


def next_card_from_hidden(cap: int, word: str) -> tuple[int, int]:
    assert word and all(letter in "0123" for letter in word)
    color = int(word[-1])
    run = 1
    while run < len(word) and int(word[-run - 1]) == color:
        run += 1
    return color, cap + run


def top_to_bottom_runs(word: str) -> tuple[tuple[int, int], ...]:
    result: list[tuple[int, int]] = []
    for letter in reversed(word):
        color = int(letter)
        if result and result[-1][0] == color:
            previous, length = result[-1]
            result[-1] = previous, length + 1
        else:
            result.append((color, 1))
    return tuple(result)


def edge236_low_chain(word: str) -> bool:
    runs = top_to_bottom_runs(word)
    return (
        len(runs) >= 3
        and runs[0] == (F, 1)
        and runs[1] == (Q, 1)
        and all(color in (G, HH) for color, _ in runs[2:])
    )


def check_edge236_chain_negative_mutation() -> None:
    original = ("11111", "222201", "333201", "3332")
    mutated = ("11111", "222221", "333001", "3332")
    caps = (2, 1, 1, 3)
    assert Counter(letter for word in original for letter in word) == Counter(
        letter for word in mutated for letter in word
    )
    assert tuple(
        next_card_from_hidden(cap, word)
        for cap, word in zip(caps[1:], original[1:])
    ) == tuple(
        next_card_from_hidden(cap, word)
        for cap, word in zip(caps[1:], mutated[1:])
    )
    assert all(edge236_low_chain(word) for word in original[1:3])
    assert not edge236_low_chain(mutated[1])


def check_formal_fixture(report_path: Path, ledger_path: Path) -> tuple[int, int]:
    assert report_path.is_file(), f"missing report: {report_path}"
    assert ledger_path.is_file(), f"missing ledger: {ledger_path}"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report.get("experiment") == "c4_h7_d2_three_source_checkpoint"
    assert report.get("status") == "LOCAL_NO_RESIDUALS_EXPORTED"
    universe = report.get("universe")
    run = report.get("run")
    assert isinstance(universe, dict) and universe.get("decorations") == 1535
    assert universe.get("labeled_fixed_futures") == 1_106_490
    assert isinstance(run, dict) and run.get("universe_complete") is True
    assert run.get("fixed_futures_checked") == 1_106_490
    assert run.get("local_no") == 14_784

    reported = {}
    per_edge = report.get("per_edge")
    assert isinstance(per_edge, list)
    for row in per_edge:
        assert isinstance(row, dict)
        edge = require_int(row.get("bridge_edge"), "invalid report edge")
        local_no = require_int(row.get("local_no"), "invalid report local-NO count")
        if local_no:
            reported[edge] = local_no
    assert reported == {spec.edge: spec.local_no for spec in SPECS}

    specs = {spec.edge: spec for spec in SPECS}
    rows_per_edge: Counter[int] = Counter()
    macros: Counter[tuple[int, tuple[tuple[int, int], ...]]] = Counter()
    decoration_by_macro: dict[tuple[int, tuple[tuple[int, int], ...]], int] = {}
    future_indices: set[int] = set()
    total_rows = 0
    with ledger_path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            assert line.strip(), f"blank ledger line {line_number}"
            row = json.loads(line)
            assert isinstance(row, dict), f"non-object ledger line {line_number}"
            edge = require_int(row.get("bridge_edge"), "invalid ledger edge")
            assert edge in specs, f"unexpected local-NO edge {edge}"
            spec = specs[edge]
            assert row.get("local_status") == "NO"
            assert row.get("safe_source_mask") == 0
            assert row.get("parent_debts") == list(spec.parent)
            assert row.get("bad_source") == [Q, spec.caps[0], F]
            assert row.get("q_color") == Q
            assert row.get("q_caps") == list(spec.caps[1:])

            raw_cards = row.get("cards")
            assert (
                isinstance(raw_cards, list)
                and len(raw_cards) == 3
                and all(
                    isinstance(card, list)
                    and len(card) == 2
                    and all(isinstance(value, int) for value in card)
                    for card in raw_cards
                )
            )
            cards = tuple(tuple(card) for card in raw_cards)
            assert cards[:2] == ((F, spec.f_caps[0]), (F, spec.f_caps[1]))
            assert cards[2][0] in (G, HH)
            assert spec.caps[3] < cards[2][1] <= HEIGHT

            hidden = row.get("hidden_words_bottom_to_top")
            assert isinstance(hidden, list) and len(hidden) == 4
            assert all(isinstance(word, str) for word in hidden)
            assert [len(word) for word in hidden] == [
                HEIGHT - cap for cap in spec.caps
            ]
            assert hidden[0] == str(F) * (HEIGHT - spec.caps[0])
            assert tuple(
                next_card_from_hidden(cap, word)
                for cap, word in zip(spec.caps[1:], hidden[1:])
            ) == cards

            forced_f = (
                HEIGHT - spec.caps[0]
                + spec.f_caps[0] - spec.caps[1]
                + spec.f_caps[1] - spec.caps[2]
            )
            assert forced_f == HEIGHT
            assert hidden[1].count(str(F)) == spec.f_caps[0] - spec.caps[1]
            assert hidden[2].count(str(F)) == spec.f_caps[1] - spec.caps[2]
            assert hidden[3].count(str(F)) == 0
            assert sum(word.count(str(F)) for word in hidden) == HEIGHT
            if edge == 236:
                assert edge236_low_chain(hidden[1])
                assert edge236_low_chain(hidden[2])

            hidden_inventory = Counter(int(letter) for word in hidden for letter in word)
            assert hidden_inventory == Counter(
                {
                    color: HEIGHT - spec.expected_exposed[color]
                    for color in range(4)
                    if HEIGHT - spec.expected_exposed[color]
                }
            )

            future_index = require_int(row.get("future_index"), "invalid future index")
            decoration = require_int(
                row.get("decoration_index"), "invalid decoration index"
            )
            assert future_index not in future_indices
            future_indices.add(future_index)
            macro = edge, cards
            previous = decoration_by_macro.setdefault(macro, decoration)
            assert previous == decoration
            macros[macro] += 1
            rows_per_edge[edge] += 1
            total_rows += 1

    assert total_rows == 14_784
    assert rows_per_edge == Counter({spec.edge: spec.local_no for spec in SPECS})
    assert len(macros) == 44
    for edge, expected_count in EXPECTED_MACROS_PER_EDGE.items():
        edge_macros = {macro: count for macro, count in macros.items() if macro[0] == edge}
        assert len(edge_macros) == expected_count
        assert Counter(edge_macros.values()) == EXPECTED_MACRO_ROW_MULTISETS[edge]
    return total_rows, len(macros)


def main() -> None:
    args = parse_args()
    check_edge236_chain_negative_mutation()
    classes: Counter[str] = Counter()
    total_pasts = 0
    for spec in SPECS:
        assert exposed(spec) == spec.expected_exposed
        templates = past_templates(spec)
        total_pasts += len(templates)
        for pasts in templates:
            if not anchor_reachable(spec, pasts):
                if spec.edge == 184:
                    check_incompatible_184(spec, pasts)
                    classes["edge184_anchor_incompatible"] += 1
                elif spec.edge == 248:
                    check_incompatible_248(spec, pasts)
                    classes["edge248_anchor_incompatible"] += 1
                else:
                    raise AssertionError((spec.edge, "unexpected anchor failure"))
                continue

            if spec.edge == 236:
                classes[check_edge_236(spec, pasts)] += 1
                continue

            anchor_support = support(pasts[1] + pasts[2])
            has_compatible_deep = any(
                compatible(anchor_support, pasts[column]) for column in (0, 3)
            )
            if has_compatible_deep:
                check_ordinary(spec, pasts)
                classes[f"edge{spec.edge}_ordinary"] += 1
            elif spec.edge == 117:
                check_rigid_117(spec, pasts)
                classes["edge117_rigid"] += 1
            elif spec.edge == 184:
                check_rigid_184(spec, pasts)
                classes["edge184_rigid"] += 1
            else:
                raise AssertionError((spec.edge, "unclassified rigid past"))

    assert total_pasts == 468
    assert classes == EXPECTED_CLASSES
    assert sum(spec.local_no for spec in SPECS) == 14_784
    pair_cases = check_pair_cap_lemma()
    fixture_rows = 0
    fixture_macros = 0
    if args.report is not None:
        fixture_rows, fixture_macros = check_formal_fixture(args.report, args.ledger)
    print(
        "c4_h7_d2_three_source_all_local_no_bypass_ok",
        f"edges={len(SPECS)}",
        f"local_no_rows={sum(spec.local_no for spec in SPECS)}",
        f"past_templates={total_pasts}",
        f"macro_classes={len(classes)}",
        f"pair_cap_cases={pair_cases}",
        "f_saturation_edges=7",
        "no_third_live_f=true",
        "edge236_chain_negative_mutation=rejected",
        f"fixture_rows={fixture_rows}",
        f"fixture_macros={fixture_macros}",
        "artifact_fixture=" + ("verified" if fixture_rows else "not_provided"),
        "classes=" + ",".join(
            f"{name}:{count}" for name, count in sorted(classes.items())
        ),
        "fixed_futures_expanded=0",
        "checkpoint_dp_runs=0",
        "scope=three_source_family_only",
    )


if __name__ == "__main__":
    main()
