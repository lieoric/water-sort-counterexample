#!/usr/bin/env python3
"""Audit the c=4, h=7 anchor-pair potential and its bridge ledger.

This checker does not expand residual words.  It reuses the independent
first-exhaustion arithmetic in ``check_c4_h7_tq_exhaust_siblings.py`` to
reconstruct semantic bridge edges and to count a fixed card decoration by
multinomial/Hall arithmetic.  It separately reuses the integer-partition
terminal generator in ``test_c4_h7_macro_recon_independent.py``.

The input report must be the complete production first-exhaustion report.
Only the new E=2 and first-sweep D2 classifications are asserted here; this
script does not claim that the remaining D2 family is solved.
"""

from __future__ import annotations

import argparse
import importlib.util
import itertools
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from types import ModuleType
from typing import Iterable, NoReturn, Sequence


HEIGHT = 7
COLORS = 4
TESTS = Path(__file__).resolve().parent

EXPECTED_TERMINALS = {"tq": 71, "d2_3plus1": 265, "d2_2plus2": 661}
EXPECTED_TQ_ENERGY = {0: 44, 1: 20, 2: 7}
EXPECTED_D31_ENERGY = {2: 70, 3: 54, 4: 76, 5: 44, 6: 18, 7: 3}
EXPECTED_D22_ENERGY = {
    2: 117,
    3: 102,
    4: 162,
    5: 108,
    6: 93,
    7: 42,
    8: 28,
    9: 6,
    10: 3,
}

# key = (bad_source_equals_q, parent_legal_source_count, Tq energy E)
# value = (canonical edges carrying D2 cards, decorations, residual-word weight)
EXPECTED_D2_LEDGER = {
    (False, 4, 0): (154, 33_180, 2_530_458_586),
    (False, 4, 1): (72, 9_187, 24_249_002),
    (False, 4, 2): (18, 1_369, 57_090),
    (True, 2, 0): (1, 132, 12_012),
    (True, 2, 1): (1, 58, 924),
    (True, 3, 0): (11, 1_529, 1_106_028),
    (True, 3, 1): (1, 6, 462),
    (True, 4, 0): (75, 15_392, 312_621_168),
    (True, 4, 1): (40, 5_372, 15_314_415),
    (True, 4, 2): (12, 981, 39_018),
}

# value = (edges, parents, decorations, residual-word weight, signatures)
EXPECTED_FIRST_SWEEP = {
    0: (41, 41, 304, 322_825, 133),
    1: (9, 9, 17, 242, 9),
    2: (0, 0, 0, 0, 0),
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def fail(message: str) -> NoReturn:
    raise AssertionError(message)


def load_module(name: str, path: Path) -> ModuleType:
    require(path.is_file(), f"missing shared checker module: {path}")
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    # Dataclasses resolve forward annotations through sys.modules while the
    # module body is executing.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def read_report(path: Path) -> dict[str, object]:
    require(path.is_file(), f"missing first-exhaustion report: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), "report root must be an object")
    return value


def check_two_anchor_integer_box(fork: ModuleType) -> dict[str, int]:
    """Exhaust the tiny debt/cap box behind Lemmas 1 and 2."""

    source_tests = 0
    live_returns = 0
    vector_splits = 0
    direct_anchor_transfers = 0
    for energy_a in range(HEIGHT + 1):
        for energy_b in range(HEIGHT + 1):
            total = energy_a + energy_b
            for exposed_x in range(1, HEIGHT + 1):
                exposed_y = total - exposed_x
                if not 1 <= exposed_y <= HEIGHT:
                    continue
                debts = [-energy_a, -energy_b, exposed_x, exposed_y]
                for color, energy in ((0, energy_a), (1, energy_b)):
                    for cap in range(1, HEIGHT):
                        actual = fork.source_is_legal(debts, 0, color, cap)
                        require(
                            actual == (cap <= energy),
                            "two-anchor fitting test failed",
                        )
                        source_tests += 1

                for departure in range(1, min(energy_a, HEIGHT - 1) + 1):
                    # w is the old cap of the final non-anchor -> anchor edge.
                    # w<=5 leaves room for a live endpoint T with w<T<7.
                    for return_old_cap in range(departure + 1, HEIGHT - 1):
                        increment = return_old_cap - departure
                        same = (
                            energy_a - departure + return_old_cap,
                            energy_b,
                        )
                        cross = (
                            energy_a - departure,
                            energy_b + return_old_cap,
                        )
                        for after in (same, cross):
                            require(min(after) >= 0, "anchor energy became negative")
                            require(
                                sum(after) == total + increment,
                                "anchor energy increment used the wrong endpoint",
                            )
                            live_returns += 1
                        for delta_x in range(increment + 1):
                            delta_y = increment - delta_x
                            after_vector = (
                                exposed_x + delta_x,
                                exposed_y + delta_y,
                            )
                            require(
                                after_vector[0] >= exposed_x
                                and after_vector[1] >= exposed_y
                                and sum(after_vector)
                                == exposed_x + exposed_y + increment,
                                "complement vector is not coordinatewise monotone",
                            )
                            vector_splits += 1

                    # Direct alpha -> beta: the endpoint advances, but debt
                    # transfer uses the old cap and complement exposure is
                    # unchanged.
                    for endpoint in range(departure + 1, HEIGHT):
                        after = (energy_a - departure, energy_b + departure)
                        require(min(after) >= 0, "direct transfer went negative")
                        require(
                            sum(after) == total,
                            "direct transfer changed total anchor energy",
                        )
                        require(endpoint > departure, "direct border did not advance")
                        direct_anchor_transfers += 1

                # Symmetric beta -> alpha direct transfers.
                for departure in range(1, min(energy_b, HEIGHT - 1) + 1):
                    for endpoint in range(departure + 1, HEIGHT):
                        after = (energy_a + departure, energy_b - departure)
                        require(min(after) >= 0, "direct transfer went negative")
                        require(
                            sum(after) == total,
                            "direct transfer changed total anchor energy",
                        )
                        require(endpoint > departure, "direct border did not advance")
                        direct_anchor_transfers += 1
    require(
        source_tests > 0 and live_returns > 0 and direct_anchor_transfers > 0,
        "integer box was empty",
    )
    return {
        "source_tests": source_tests,
        "live_return_formulas": live_returns,
        "complement_increment_splits": vector_splits,
        "direct_anchor_transfers": direct_anchor_transfers,
    }


def check_terminal_macros(macro: ModuleType) -> dict[str, object]:
    tq = macro.tq_types()
    d31 = macro.d2_3plus1_types()
    d22 = macro.d2_2plus2_types()
    require(
        (len(tq), len(d31), len(d22))
        == (
            EXPECTED_TERMINALS["tq"],
            EXPECTED_TERMINALS["d2_3plus1"],
            EXPECTED_TERMINALS["d2_2plus2"],
        ),
        "terminal macro census drifted",
    )

    for _, state in (*tq, *d31, *d22):
        require(
            macro.physical_consistency_errors(state) == (),
            "terminal macro failed physical checks",
        )
        require(
            not any(
                macro.legal_source(state, source)
                for source in range(len(state.active))
            ),
            "enumerated terminal has a legal source",
        )

    tq_energy = Counter(energy for energy, _ in tq)
    d31_energy = Counter(energy for energy, _ in d31)
    d22_energy = Counter(energy for energy, _ in d22)
    require(dict(tq_energy) == EXPECTED_TQ_ENERGY, "Tq energy distribution drifted")
    require(dict(d31_energy) == EXPECTED_D31_ENERGY, "3+1 energy distribution drifted")
    require(dict(d22_energy) == EXPECTED_D22_ENERGY, "2+2 energy distribution drifted")

    e2_types = []
    for energy, state in tq:
        if energy != 2:
            continue
        caps = tuple(cap for _, cap in state.active)
        exposed = macro.exposed_counts(state)
        require(caps == (3, 3, 3), "E=2 Tq caps are not 3,3,3")
        require(exposed[0] == HEIGHT, "E=2 Tq did not saturate q")
        e2_types.append(state)
    require(len(e2_types) == 7, "wrong number of E=2 Tq macro types")

    saturated_d31 = [
        state
        for _, state in d31
        if HEIGHT in [value for value in state.d if value > 0]
    ]
    saturated_d22 = [
        state
        for _, state in d22
        if HEIGHT in [value for value in state.d if value > 0]
    ]
    require(not saturated_d31, "a saturated-positive 3+1 D2 escaped the bound")
    require(
        len(saturated_d22) == 10,
        "saturated-positive 2+2 D2 count drifted",
    )
    return {
        "terminal_types": EXPECTED_TERMINALS,
        "tq_energy_distribution": dict(sorted(tq_energy.items())),
        "d2_3plus1_energy_distribution": dict(sorted(d31_energy.items())),
        "d2_2plus2_energy_distribution": dict(sorted(d22_energy.items())),
        "e2_tq_types": len(e2_types),
        "saturated_positive_d2_3plus1": len(saturated_d31),
        "saturated_positive_d2_2plus2": len(saturated_d22),
    }


def reconstruct_edges(fork: ModuleType):
    terminals = fork.enumerate_tq_terminals()
    _, pairs = fork.reverse_bridge(terminals)
    edges = fork.build_sibling_edges(pairs)
    require(len(edges) == 423, "sibling bridge edge count drifted")
    e2_edges = []
    for edge in edges:
        terminal_debts = fork.terminal_debts_in_parent_coordinates(edge)
        energy = -terminal_debts[edge.q_color]
        require(0 <= energy <= 2, "bridge Tq energy is outside 0..2")
        if energy != 2:
            continue
        require(edge.q_caps == (3, 3, 3), "E=2 bridge q caps drifted")
        require(
            fork.exposed_counts(edge.parent)[edge.q_color] == HEIGHT,
            "E=2 bridge parent has a hidden q item",
        )
        e2_edges.append(edge)
    require(len(e2_edges) == 36, "E=2 sibling bridge edge count drifted")
    return edges


def report_d2_ledger(
    report: dict[str, object], fork: ModuleType, edges: Sequence[object]
) -> tuple[dict[tuple[bool, int, int], tuple[int, int, int]], dict[str, int]]:
    require(
        report.get("coverage_scope")
        == "first_exhaustion_tq_sibling_next_run_forks",
        "wrong report scope",
    )
    require(report.get("status") == "NEXT_RUN_CENSUS_COMPLETE", "report is not complete")
    require(report.get("next_run_universe_complete") is True, "report lacks completion flag")
    rows = report.get("per_edge")
    require(isinstance(rows, list) and len(rows) == 423, "report must contain 423 edges")

    by_key = {
        (edge.parent, edge.terminal, edge.action): edge  # type: ignore[attr-defined]
        for edge in edges
    }
    seen = set()
    grouped_edges: Counter[tuple[bool, int, int]] = Counter()
    grouped_decorations: Counter[tuple[bool, int, int]] = Counter()
    grouped_words: Counter[tuple[bool, int, int]] = Counter()
    for raw in rows:
        require(isinstance(raw, dict), "per_edge row must be an object")
        semantic = fork.edge_key_from_json(raw)
        require(semantic in by_key and semantic not in seen, "unknown/duplicate report edge")
        seen.add(semantic)
        edge = by_key[semantic]
        legal_count = len(fork.legal_sources(edge.parent, 0))
        require(raw.get("legal_source_count") == legal_count, "legal-source count drifted")
        terminal_debts = fork.terminal_debts_in_parent_coordinates(edge)
        energy = -terminal_debts[edge.q_color]
        refined = raw.get("refined")
        require(isinstance(refined, dict), "missing refined per-edge ledger")
        d2 = refined.get("d2_reduction")
        require(isinstance(d2, dict), "missing per-edge D2 ledger")
        decorations = d2.get("decorations")
        words = d2.get("residual_words")
        require(
            isinstance(decorations, int)
            and decorations >= 0
            and isinstance(words, int)
            and words >= 0,
            "invalid D2 counts",
        )
        if decorations == 0:
            require(words == 0, "zero-decoration D2 row has nonzero weight")
            continue
        key = (edge.a_equals_q, legal_count, energy)
        grouped_edges[key] += 1
        grouped_decorations[key] += decorations
        grouped_words[key] += words
    require(seen == set(by_key), "report edge coverage is incomplete")

    ledger = {
        key: (grouped_edges[key], grouped_decorations[key], grouped_words[key])
        for key in grouped_edges
    }
    require(ledger == EXPECTED_D2_LEDGER, "D2 E/source ledger drifted")
    totals = {
        "edges_with_d2": sum(value[0] for value in ledger.values()),
        "decorations": sum(value[1] for value in ledger.values()),
        "residual_word_weight": sum(value[2] for value in ledger.values()),
        "e2_edges": sum(value[0] for key, value in ledger.items() if key[2] == 2),
        "e2_decorations": sum(value[1] for key, value in ledger.items() if key[2] == 2),
        "e2_residual_word_weight": sum(
            value[2] for key, value in ledger.items() if key[2] == 2
        ),
    }
    require(
        totals
        == {
            "edges_with_d2": 385,
            "decorations": 67_206,
            "residual_word_weight": 2_883_858_705,
            "e2_edges": 30,
            "e2_decorations": 2_350,
            "e2_residual_word_weight": 96_108,
        },
        "D2 totals drifted",
    )
    return ledger, totals


def raw_first_sweep_is_d2(
    edge: object, chosen: tuple[tuple[int, int], ...]
) -> bool:
    debts = [debt for debt, _ in edge.parent]  # type: ignore[attr-defined]
    caps = [list(values) for _, values in edge.parent]  # type: ignore[attr-defined]
    q_color = edge.q_color  # type: ignore[attr-defined]
    for old_cap, (new_color, endpoint) in zip(edge.q_caps, chosen):  # type: ignore[attr-defined]
        caps[q_color].remove(old_cap)
        caps[new_color].append(endpoint)
        debts[q_color] += old_cap
        debts[new_color] -= old_cap

    positive = {color for color, debt in enumerate(debts) if debt > 0}
    nonpositive = set(range(COLORS)) - positive
    topped = {color for color, values in enumerate(caps) if values}
    if len(positive) != 2 or len(nonpositive) != 2 or topped != nonpositive:
        return False
    if sorted(len(caps[color]) for color in nonpositive) != [2, 2]:
        return False
    for color in nonpositive:
        for cap in caps[color]:
            adjusted = debts.copy()
            adjusted[color] += cap
            if sum(value > 0 for value in adjusted) <= 2:
                return False

    exposed = [debts[color] + sum(caps[color]) for color in range(COLORS)]
    multiplicity = [len(caps[color]) for color in range(COLORS)]
    if any(
        not multiplicity[color] <= exposed[color] <= HEIGHT
        for color in range(COLORS)
    ):
        return False
    remaining = [HEIGHT - value for value in exposed]
    return all(
        multiplicity[color]
        <= sum(remaining[other] for other in range(COLORS) if other != color)
        for color in range(COLORS)
    )


def theoretical_first_sweep_signatures() -> dict[int, set[tuple[object, ...]]]:
    result = {0: set(), 1: set(), 2: set()}
    for energy in range(3):
        for bad_cap, anchor_a, old_a, old_f1, old_f2, end_a, end_f1, end_f2 in itertools.product(
            range(1, HEIGHT),
            range(HEIGHT),
            range(energy + 1, HEIGHT),
            range(energy + 1, HEIGHT),
            range(energy + 1, HEIGHT),
            range(1, HEIGHT),
            range(1, HEIGHT),
            range(1, HEIGHT),
        ):
            anchor_f = old_f1 + old_f2
            if not (old_a < end_a and old_f1 < end_f1 and old_f2 < end_f2):
                continue
            if not (
                anchor_a + energy > 0
                and 1 <= bad_cap - anchor_a <= HEIGHT
                and old_a + old_f1 + old_f2 - energy <= HEIGHT
            ):
                continue
            if not (
                bad_cap > anchor_a + old_a
                and end_a > anchor_a + old_a
                and end_f1 > anchor_f
                and end_f2 > anchor_f
            ):
                continue
            if (end_f1 - old_f1) + (end_f2 - old_f2) > bad_cap:
                continue
            if end_a - old_a > HEIGHT - (bad_cap - anchor_a):
                continue
            result[energy].add(
                (
                    bad_cap,
                    anchor_a,
                    old_a,
                    end_a,
                    tuple(sorted(((old_f1, end_f1), (old_f2, end_f2)))),
                )
            )
    return result


def first_sweep_ledger(fork: ModuleType, edges: Sequence[object]) -> dict[str, object]:
    counts: Counter[int] = Counter()
    weights: Counter[int] = Counter()
    edge_sets: dict[int, set[object]] = defaultdict(set)
    parent_sets: dict[int, set[object]] = defaultdict(set)
    signatures: dict[int, set[tuple[object, ...]]] = defaultdict(set)

    for edge in edges:
        if edge.a_equals_q:  # type: ignore[attr-defined]
            continue
        terminal_debts = fork.terminal_debts_in_parent_coordinates(edge)
        energy = -terminal_debts[edge.q_color]  # type: ignore[attr-defined]
        anchor_a, bad_cap, anchor_f = edge.action  # type: ignore[attr-defined]
        anchor_a_energy = -edge.parent[anchor_a][0]  # type: ignore[attr-defined]
        fourth = next(
            color
            for color in range(COLORS)
            if color not in (edge.q_color, anchor_a, anchor_f)  # type: ignore[attr-defined]
        )

        for a_slot in range(3):
            f_slots = [slot for slot in range(3) if slot != a_slot]
            card_sets = []
            for slot, old_cap in enumerate(edge.q_caps):  # type: ignore[attr-defined]
                target = anchor_a if slot == a_slot else anchor_f
                card_sets.append(
                    tuple((target, endpoint) for endpoint in range(old_cap + 1, HEIGHT))
                )
            for chosen in itertools.product(*card_sets):
                chosen = tuple(chosen)
                _, _, weight = fork.decoration_balance(edge, chosen)
                if weight == 0:
                    continue

                old_a = edge.q_caps[a_slot]  # type: ignore[attr-defined]
                end_a = chosen[a_slot][1]
                old_f1, old_f2 = (edge.q_caps[slot] for slot in f_slots)  # type: ignore[attr-defined]
                end_f1, end_f2 = (chosen[slot][1] for slot in f_slots)
                anchor_f_energy = old_f1 + old_f2
                formula = (
                    edge.parent[edge.q_color][0]  # type: ignore[attr-defined]
                    + sum(edge.q_caps)  # type: ignore[attr-defined]
                    > 0
                    and edge.parent[fourth][0] > 0  # type: ignore[attr-defined]
                    and bad_cap > anchor_a_energy + old_a
                    and end_a > anchor_a_energy + old_a
                    and end_f1 > anchor_f_energy
                    and end_f2 > anchor_f_energy
                    and (end_f1 - old_f1) + (end_f2 - old_f2) <= bad_cap
                )
                actual = raw_first_sweep_is_d2(edge, chosen)
                require(actual == formula, "first-sweep D2 inequalities are not exact")
                if not actual:
                    continue

                require(
                    fork.refined_classify_decoration(edge, chosen) == "d2_reduction",
                    "first-sweep D2 escaped the production proof-ledger class",
                )
                require(
                    bad_cap >= anchor_a_energy + old_a + 1,
                    "first-sweep a bound failed",
                )
                require(
                    bad_cap >= old_f1 + old_f2 + 2 >= 2 * energy + 4,
                    "first-sweep f/E bound failed",
                )
                require(energy <= 1, "E=2 first-sweep D2 survived")

                if energy == 1:
                    require(
                        (
                            bad_cap,
                            old_f1,
                            old_f2,
                            end_f1,
                            end_f2,
                        )
                        == (6, 2, 2, 5, 5),
                        "E=1 first-sweep f signature is not rigid",
                    )
                    require(
                        end_a - old_a == anchor_a_energy + 1,
                        "E=1 a card did not consume all remaining a",
                    )
                    parent_exposed = fork.exposed_counts(edge.parent)
                    require(
                        parent_exposed[anchor_a] + end_a - old_a == HEIGHT,
                        "E=1 first sweep did not saturate a",
                    )
                    require(
                        (end_f1 - old_f1) + (end_f2 - old_f2) == 6
                        and HEIGHT - bad_cap == 1,
                        "E=1 f inventory is not six exposed plus one bad-tail item",
                    )

                signature = (
                    bad_cap,
                    anchor_a_energy,
                    old_a,
                    end_a,
                    tuple(sorted(((old_f1, end_f1), (old_f2, end_f2)))),
                )
                counts[energy] += 1
                weights[energy] += weight
                edge_sets[energy].add((edge.parent, edge.terminal, edge.action))  # type: ignore[attr-defined]
                parent_sets[energy].add(edge.parent)  # type: ignore[attr-defined]
                signatures[energy].add(signature)

    theoretical = theoretical_first_sweep_signatures()
    for energy in range(3):
        require(
            signatures[energy] == theoretical[energy],
            f"E={energy} numerical signature cover is incomplete",
        )
        actual = (
            len(edge_sets[energy]),
            len(parent_sets[energy]),
            counts[energy],
            weights[energy],
            len(signatures[energy]),
        )
        require(actual == EXPECTED_FIRST_SWEEP[energy], "first-sweep ledger drifted")

    return {
        "by_energy": {
            str(energy): {
                "edges": len(edge_sets[energy]),
                "parents": len(parent_sets[energy]),
                "decorations": counts[energy],
                "residual_word_weight": weights[energy],
                "numerical_signatures": len(signatures[energy]),
            }
            for energy in range(3)
        },
        "totals": {
            "edges": sum(len(edge_sets[energy]) for energy in range(3)),
            "parents": sum(len(parent_sets[energy]) for energy in range(3)),
            "decorations": sum(counts.values()),
            "residual_word_weight": sum(weights.values()),
            "numerical_signatures": sum(len(values) for values in signatures.values()),
        },
    }


def ledger_json(
    ledger: dict[tuple[bool, int, int], tuple[int, int, int]]
) -> dict[str, object]:
    return {
        f"a_eq_q={str(equal).lower()},legal={legal},E={energy}": {
            "edges": values[0],
            "decorations": values[1],
            "residual_word_weight": values[2],
        }
        for (equal, legal, energy), values in sorted(ledger.items())
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report",
        type=Path,
        required=True,
        help="complete c4-h7 first-exhaustion report.json",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    fork = load_module(
        "c4_h7_tq_exhaust_shared_audit",
        TESTS / "check_c4_h7_tq_exhaust_siblings.py",
    )
    macro = load_module(
        "c4_h7_macro_shared_audit",
        TESTS / "test_c4_h7_macro_recon_independent.py",
    )
    report = read_report(args.report.resolve())
    terminal_summary = check_terminal_macros(macro)
    potential_summary = check_two_anchor_integer_box(fork)
    edges = reconstruct_edges(fork)
    d2_ledger, d2_totals = report_d2_ledger(report, fork, edges)
    first_sweep = first_sweep_ledger(fork, edges)

    result = {
        "status": "ANCHOR_PAIR_REDUCTION_VERIFIED",
        "claim_boundary": {
            "h7_universal_solvability_proved": False,
            "all_d2_eliminated": False,
            "zero_debt_initial_layouts_checked": False,
            "residual_words_expanded": False,
        },
        "terminal_macro_audit": terminal_summary,
        "two_anchor_integer_box": potential_summary,
        "bridge": {
            "sibling_edges": len(edges),
            "e2_sibling_edges": 36,
            "d2_ledger": ledger_json(d2_ledger),
            "d2_totals": d2_totals,
            "first_sweep_2plus2": first_sweep,
        },
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
