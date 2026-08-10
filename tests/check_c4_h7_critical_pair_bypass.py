#!/usr/bin/env python3
"""Independent small checks for the c=4,h=7 critical-pair bypass note."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from itertools import product


H = 7
COLORS = 4
Q, F, G, HH = range(COLORS)


def positive_count(values: list[int] | tuple[int, ...]) -> int:
    return sum(value > 0 for value in values)


def add_at(values: tuple[int, ...], color: int, amount: int) -> tuple[int, ...]:
    result = list(values)
    result[color] += amount
    return tuple(result)


def live_after_test(
    debt: tuple[int, ...], source_color: int, source_cap: int,
    old_color: int, old_cap: int, target_color: int,
) -> tuple[int, ...]:
    tested = list(debt)
    tested[source_color] += source_cap
    tested[old_color] += old_cap
    tested[target_color] -= old_cap
    return tuple(tested)


def predicted_live_disable(
    debt: tuple[int, ...], source_color: int, source_cap: int,
    old_color: int, old_cap: int, target_color: int, threshold: int,
) -> bool:
    tested = list(debt)
    tested[source_color] += source_cap
    return (
        positive_count(tested) == threshold
        and tested[old_color] <= 0 < tested[old_color] + old_cap
        and (tested[target_color] <= 0 or tested[target_color] > old_cap)
    )


def check_live_critical_pair_formula() -> int:
    checked = 0
    debts = product(range(-3, 4), repeat=COLORS)
    for debt in debts:
        for threshold in (2, 3):
            for old_color in range(COLORS):
                for target_color in range(COLORS):
                    if target_color == old_color:
                        continue
                    for source_color in range(COLORS):
                        for old_cap in range(1, 4):
                            for source_cap in range(1, 4):
                                source_test = add_at(debt, source_color, source_cap)
                                if positive_count(source_test) > threshold:
                                    continue
                                actual = positive_count(
                                    live_after_test(
                                        debt, source_color, source_cap,
                                        old_color, old_cap, target_color,
                                    )
                                ) > threshold
                                predicted = predicted_live_disable(
                                    debt, source_color, source_cap,
                                    old_color, old_cap, target_color, threshold,
                                )
                                assert actual == predicted, (
                                    debt, threshold, old_color, old_cap,
                                    target_color, source_color, source_cap,
                                    actual, predicted,
                                )
                                checked += 1
    return checked


def live_action_legal(
    debt: tuple[int, ...], old_color: int, old_cap: int, threshold: int,
) -> bool:
    return positive_count(add_at(debt, old_color, old_cap)) <= threshold


def live_disables(
    debt: tuple[int, ...], old_color: int, old_cap: int, target_color: int,
    other_color: int, other_cap: int, threshold: int,
) -> bool:
    if not live_action_legal(debt, other_color, other_cap, threshold):
        return False
    successor_test = live_after_test(
        debt, other_color, other_cap, old_color, old_cap, target_color,
    )
    return positive_count(successor_test) > threshold


def check_mutual_lock_consequences() -> int:
    checked = 0
    for debt in product(range(-3, 4), repeat=COLORS):
        for threshold in (2, 3):
            for x in range(COLORS):
                for u in range(COLORS):
                    for y in range(COLORS):
                        if y == x:
                            continue
                        for v in range(COLORS):
                            if v == u:
                                continue
                            for s in range(1, 4):
                                for t in range(1, 4):
                                    if not live_action_legal(debt, x, s, threshold):
                                        continue
                                    if not live_action_legal(debt, u, t, threshold):
                                        continue
                                    mutual = live_disables(
                                        debt, x, s, y, u, t, threshold,
                                    ) and live_disables(
                                        debt, u, t, v, x, s, threshold,
                                    )
                                    if not mutual:
                                        continue
                                    checked += 1
                                    if x == u:
                                        energy = -debt[x]
                                        assert max(s, t) <= energy < s + t
                                        assert sum(
                                            debt[color] > 0
                                            for color in range(COLORS)
                                            if color != x
                                        ) == threshold
                                    else:
                                        assert -s < debt[x] <= 0
                                        assert -t < debt[u] <= 0
                                        assert sum(
                                            debt[color] > 0
                                            for color in range(COLORS)
                                            if color not in (x, u)
                                        ) == threshold - 1
                                        assert not (y == u and v == x), (
                                            "direct swap was mutually disabling",
                                            debt, threshold, x, s, u, t,
                                        )
    assert checked > 0
    return checked


def predicted_exhaust_disable(
    debt: tuple[int, ...], source_color: int, source_cap: int,
    old_color: int, old_cap: int, final_color: int,
) -> bool:
    tested = list(debt)
    tested[source_color] += source_cap
    return (
        positive_count(tested) == 2
        and tested[old_color] <= 0 < tested[old_color] + old_cap
        and tested[final_color] <= 0 < tested[final_color] + H - old_cap
    )


def check_exhaust_formula() -> int:
    checked = 0
    for debt in product(range(-3, 4), repeat=COLORS):
        for old_color in range(COLORS):
            for final_color in range(COLORS):
                if final_color == old_color:
                    continue
                for source_color in range(COLORS):
                    for old_cap in range(1, H):
                        for source_cap in range(1, 4):
                            tested = list(debt)
                            tested[source_color] += source_cap
                            if positive_count(tested) > 2:
                                continue
                            after = tested.copy()
                            after[old_color] += old_cap
                            after[final_color] += H - old_cap
                            actual = positive_count(after) > 3
                            predicted = predicted_exhaust_disable(
                                debt, source_color, source_cap,
                                old_color, old_cap, final_color,
                            )
                            assert actual == predicted
                            checked += 1
    return checked


def check_inventory_charge_and_cap_sum() -> tuple[int, int]:
    charge_cases = 0
    for bad_cap in range(1, H):
        for run_count in range(4):
            for lengths in product(range(1, H + 1), repeat=run_count):
                if (H - bad_cap) + sum(lengths) <= H:
                    assert sum(lengths) <= bad_cap
                    assert run_count <= bad_cap
                    charge_cases += 1
    assert not any(
        (H - bad_cap) + sum(lengths) <= H
        for bad_cap in (1, 2)
        for lengths in product(range(1, H + 1), repeat=3)
    )
    assert (H - 3) + 1 + 1 + 1 == H

    cap_cases = 0
    for energy in range(3):
        for bad_cap in range(1, H):
            total_energy = bad_cap + energy
            if total_energy > 8:
                continue
            for siblings in product(range(energy + 1, H), repeat=3):
                if sum(siblings) - energy > H:
                    continue
                cap_cases += 1
                no_pair = all(
                    siblings[i] + siblings[j] > total_energy
                    for i in range(3) for j in range(i + 1, 3)
                )
                if no_pair:
                    assert total_energy <= H
                if total_energy == 8:
                    assert bad_cap == 6 and energy == 2
                    assert siblings == (3, 3, 3)
                    assert not no_pair
    assert cap_cases > 0
    return charge_cases, cap_cases


def compositions(total: int, parts: int):
    if parts == 1:
        yield (total,)
        return
    for first in range(total + 1):
        for tail in compositions(total - first, parts - 1):
            yield (first,) + tail


def allowed_tops(g_count: int, h_count: int) -> tuple[int, ...]:
    result = [Q]
    if g_count:
        result.append(G)
    if h_count:
        result.append(HH)
    return tuple(result)


def early_terminal_for_solo(
    index: int, g_counts: tuple[int, ...], h_counts: tuple[int, ...],
    tops: tuple[int, ...],
) -> bool:
    g_count, h_count = g_counts[index], h_counts[index]
    assert g_count == 0 or h_count == 0
    if g_count == 0 and h_count == 0:
        return False
    missing = HH if g_count else G
    return all(tops[j] == missing for j in range(4) if j != index)


def check_prefix_pigeonhole_and_rigid_corner() -> tuple[int, int]:
    distributions = 0
    rigid = 0
    for total_non_q in range(H + 1):
        for counts in compositions(total_non_q, 8):
            g_counts = counts[:4]
            h_counts = counts[4:]
            solo = [
                i for i in range(4)
                if g_counts[i] == 0 or h_counts[i] == 0
            ]
            assert solo, (total_non_q, g_counts, h_counts)
            distributions += 1
            top_domains = [
                allowed_tops(g_counts[i], h_counts[i]) for i in range(4)
            ]
            for tops in product(*top_domains):
                if not all(
                    early_terminal_for_solo(i, g_counts, h_counts, tops)
                    for i in solo
                ):
                    continue
                rigid += 1
                assert total_non_q == H
                assert len(solo) == 1
                unique = solo[0]
                assert g_counts[unique] + h_counts[unique] == 1
                if g_counts[unique] == 1:
                    missing = HH
                else:
                    missing = G
                for j in range(4):
                    if j == unique:
                        continue
                    assert g_counts[j] == h_counts[j] == 1
                    assert tops[j] == missing
    assert rigid > 0
    return distributions, rigid


def runs(word: str) -> list[tuple[str, int]]:
    result: list[tuple[str, int]] = []
    for char in word:
        if result and result[-1][0] == char:
            result[-1] = (char, result[-1][1] + 1)
        else:
            result.append((char, 1))
    return result


def check_solo_prefixes_and_rigid_weave() -> tuple[int, int]:
    solo_words = 0
    alphabet = "qgh"
    index = {"q": Q, "f": F, "g": G, "h": HH}
    for length in range(1, H):
        for letters in product(alphabet, repeat=length):
            if letters[-1] != "q" or len(set(letters)) > 2:
                continue
            word = "".join(letters)
            chain = runs(word)
            debt = [0] * COLORS
            cap = chain[0][1]
            for run_index in range(len(chain) - 1):
                old = index[chain[run_index][0]]
                new = index[chain[run_index + 1][0]]
                tested = debt.copy()
                tested[old] += cap
                assert positive_count(tested) <= 2
                debt[old] += cap
                debt[new] -= cap
                cap += chain[run_index + 1][1]
            tested = debt.copy()
            tested[Q] += cap
            assert positive_count(tested) <= 2
            solo_words += 1

    weave_words = 0
    for cap in range(2, H):
        for x_position in range(cap - 1):
            a_word = ["q"] * cap
            a_word[x_position] = "x"
            assert a_word[-1] == "q"
            for a in range(0, H - 2):
                for b in range(1, H - a - 1):
                    if 2 + a + b > H:
                        continue
                    background = [a, 0, -a - 1, 1]
                    prefix_q = 0
                    prefix_x = 0
                    for char, _run_length in runs("".join(a_word)):
                        if char == "q":
                            prefix_q += _run_length
                        else:
                            prefix_x += _run_length
                        tested = background.copy()
                        tested[Q] += prefix_q
                        tested[G] += prefix_x
                        assert tested[G] <= 0
                        assert positive_count(tested) <= 2
                    live_debt = (a + cap - 1, -cap, -a, 1)
                    for y_cap in range(1, H):
                        assert positive_count(add_at(live_debt, HH, y_cap)) <= 2
                    bad_debt = (a + cap - 1, H - cap, -a, 1)
                    for y_cap in range(1, H):
                        assert positive_count(add_at(bad_debt, HH, y_cap)) <= 3
                    weave_words += 1
    assert solo_words > 0 and weave_words > 0
    return solo_words, weave_words


@dataclass
class BorderState:
    debt: list[int]
    positions: list[int]
    caps: list[int]
    exhausted: list[bool]
    z: int = 0

    def clone(self) -> "BorderState":
        return BorderState(
            self.debt.copy(), self.positions.copy(), self.caps.copy(),
            self.exhausted.copy(), self.z,
        )


CHAR_COLOR = {"q": Q, "f": F, "g": G, "h": HH}


def make_state(columns_top_to_bottom: list[str]) -> tuple[list[list[tuple[int, int]]], BorderState]:
    run_columns: list[list[tuple[int, int]]] = []
    caps: list[int] = []
    for word in columns_top_to_bottom:
        encoded = [(CHAR_COLOR[char], length) for char, length in runs(word)]
        assert len(encoded) >= 2
        run_columns.append(encoded)
        caps.append(encoded[0][1])
    return run_columns, BorderState([0] * COLORS, [0] * 4, caps, [False] * 4)


def source_test(state: BorderState, run_columns, column: int) -> tuple[int, ...]:
    assert not state.exhausted[column]
    top = run_columns[column][state.positions[column]][0]
    return add_at(tuple(state.debt), top, state.caps[column])


def legal_sources(state: BorderState, run_columns) -> list[int]:
    return [
        column for column in range(4)
        if not state.exhausted[column]
        and positive_count(source_test(state, run_columns, column)) <= 2 + state.z
    ]


def apply_event(state: BorderState, run_columns, column: int) -> tuple[str, int]:
    assert column in legal_sources(state, run_columns), (
        "illegal event", column, state,
        source_test(state, run_columns, column),
    )
    position = state.positions[column]
    old_color = run_columns[column][position][0]
    old_cap = state.caps[column]
    final = position + 1 == len(run_columns[column]) - 1
    new_color, new_length = run_columns[column][position + 1]
    if final:
        assert new_length == H - old_cap
        state.debt[old_color] += old_cap
        state.debt[new_color] += H - old_cap
        state.positions[column] += 1
        state.caps[column] = H
        state.exhausted[column] = True
        state.z += 1
        return "exhaust", old_cap
    state.debt[old_color] += old_cap
    state.debt[new_color] -= old_cap
    state.positions[column] += 1
    state.caps[column] += new_length
    return "live", old_cap


def active_tops(state: BorderState, run_columns) -> list[tuple[int, int]]:
    return [
        (run_columns[column][state.positions[column]][0], state.caps[column])
        for column in range(4) if not state.exhausted[column]
    ]


def check_four_lock_and_escape() -> tuple[int, int]:
    bottom_to_top = ["2221032", "3321023", "3321003", "1111000"]
    digit_to_char = {"0": "q", "1": "f", "2": "g", "3": "h"}
    top_to_bottom = [
        "".join(digit_to_char[digit] for digit in reversed(column))
        for column in bottom_to_top
    ]
    assert top_to_bottom == ["ghqfggg", "hgqfghh", "hqqfghh", "qqqffff"]
    counts = Counter("".join(top_to_bottom))
    assert counts == Counter({"q": H, "f": H, "g": H, "h": H})

    run_columns, initial = make_state(top_to_bottom)
    trap_parent = initial.clone()
    trap_prefix = [0, 1, 0, 1, 2]
    for column in trap_prefix:
        apply_event(trap_parent, run_columns, column)
    assert trap_parent.z == 0
    assert tuple(trap_parent.debt) == (-5, 0, 2, 3)
    assert active_tops(trap_parent, run_columns) == [(Q, 3)] * 4
    assert legal_sources(trap_parent, run_columns) == [0, 1, 2, 3]
    hosted_q = sum(cap for color, cap in active_tops(trap_parent, run_columns) if color == Q)
    exposed = trap_parent.debt.copy()
    exposed[Q] += hosted_q
    assert tuple(exposed) == (H, 0, 2, 3)

    for sibling in (0, 1, 2):
        child = trap_parent.clone()
        kind, cap = apply_event(child, run_columns, sibling)
        assert (kind, cap) == ("live", 3)
        assert tuple(child.debt) == (-2, -3, 2, 3)
        assert sorted(active_tops(child, run_columns)) == sorted(
            [(F, 4), (Q, 3), (Q, 3), (Q, 3)]
        )
        assert legal_sources(child, run_columns) == []

    bad_child = trap_parent.clone()
    kind, cap = apply_event(bad_child, run_columns, 3)
    assert (kind, cap) == ("exhaust", 3)
    assert bad_child.z == 1
    assert tuple(bad_child.debt) == (-2, 4, 2, 3)
    assert active_tops(bad_child, run_columns) == [(Q, 3)] * 3
    assert legal_sources(bad_child, run_columns) == []

    escape = initial.clone()
    escape_path = [0, 0, 1, 0, 2, 2, 0, 1, 1, 1, 1, 2, 2, 3]
    for column in escape_path:
        apply_event(escape, run_columns, column)
    assert escape.z == 4
    assert all(escape.exhausted)
    assert tuple(escape.debt) == (H, H, H, H)
    return len(trap_prefix), len(escape_path)


def main() -> None:
    live_checks = check_live_critical_pair_formula()
    mutual_checks = check_mutual_lock_consequences()
    exhaust_checks = check_exhaust_formula()
    charge_cases, cap_cases = check_inventory_charge_and_cap_sum()
    distributions, rigid_cases = check_prefix_pigeonhole_and_rigid_corner()
    solo_words, weave_words = check_solo_prefixes_and_rigid_weave()
    trap_depth, escape_depth = check_four_lock_and_escape()
    print(
        "critical_pair_bypass_ok",
        f"live_formula={live_checks}",
        f"mutual_locks={mutual_checks}",
        f"exhaust_formula={exhaust_checks}",
        f"charge_cases={charge_cases}",
        f"cap_cases={cap_cases}",
        f"prefix_distributions={distributions}",
        f"rigid_cases={rigid_cases}",
        f"solo_words={solo_words}",
        f"weave_words={weave_words}",
        f"trap_depth={trap_depth}",
        f"escape_depth={escape_depth}",
    )


if __name__ == "__main__":
    main()
