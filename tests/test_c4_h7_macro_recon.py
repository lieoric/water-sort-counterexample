"""Independent checks for the bounded c4/k2/h7 macro reconnaissance."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "c4_h7_macro_recon.py"
SPEC = importlib.util.spec_from_file_location("c4_h7_macro_recon", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
recon = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = recon
SPEC.loader.exec_module(recon)


class TerminalCensusTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.terminals = recon.enumerate_terminals()

    def test_expected_terminal_counts(self) -> None:
        counts = {family: len(states) for family, states in self.terminals.items()}
        counts["total"] = sum(counts.values())
        self.assertEqual(counts, recon.EXPECTED_TERMINAL_COUNTS)

    def test_every_output_terminal_is_a_deadlock(self) -> None:
        for family, states in self.terminals.items():
            z = 1 if family == "tq" else 0
            for state in states:
                with self.subTest(family=family, state=state):
                    self.assertTrue(recon.algebraically_consistent(state, z))
                    self.assertEqual(recon.exposed_counts(state), tuple(
                        debt + sum(caps) for debt, caps in state
                    ))
                    self.assertTrue(all(0 <= value <= recon.HEIGHT for value in recon.exposed_counts(state)))
                    self.assertTrue(recon.is_deadlock(state, z))
                    self.assertEqual(recon.classify_terminal(state, z), family)


class ReverseEdgeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.terminals = recon.enumerate_terminals()

    def test_every_predecessor_edge_replays(self) -> None:
        edge_count = 0
        for family, terminals in self.terminals.items():
            z = 1 if family == "tq" else 0
            for terminal in terminals:
                for predecessor in recon.reverse_predecessors(terminal, z):
                    edge_count += 1
                    with self.subTest(family=family, predecessor=predecessor, terminal=terminal):
                        self.assertTrue(recon.algebraically_consistent(predecessor, z))
                        actions = recon.live_actions_to(predecessor, z, terminal)
                        self.assertTrue(actions)
                        for action in actions:
                            old_color, old_cap, new_color, new_cap = action
                            self.assertNotEqual(old_color, new_color)
                            self.assertLess(old_cap, new_cap)
                            self.assertTrue(recon.source_is_legal(predecessor, z, old_color, old_cap))
                            self.assertEqual(recon.apply_live_action(predecessor, z, action), terminal)
        self.assertEqual(edge_count, 12_224)

    def test_host_lower_bound_and_hidden_hall_are_enforced(self) -> None:
        # F=1 cannot support the two active tops in the first color bucket.
        host_shortfall = ((-7, (2, 6)), (0, (3, 3)), (1, ()), (6, ()))
        self.assertEqual(recon.exposed_counts(host_shortfall)[0], 1)
        self.assertFalse(recon.algebraically_consistent(host_shortfall, z=0))

        # Every color individually has F>=m, but the two columns topped by
        # color zero cannot both start their hidden suffix with another color.
        hall_shortfall = ((-9, (5, 6)), (1, (6,)), (1, (6,)), (7, ()))
        self.assertEqual(recon.exposed_counts(hall_shortfall), (2, 7, 7, 7))
        self.assertFalse(recon.algebraically_consistent(hall_shortfall, z=0))

    def test_tq_first_exhaustion_bridge_replays(self) -> None:
        labeled_count = 0
        pairs = set()
        predecessors = set()
        for terminal in self.terminals["tq"]:
            candidates = recon.reverse_exhausting_candidates(terminal)
            labeled_count += len(candidates)
            for predecessor in candidates:
                pairs.add((predecessor, terminal))
                predecessors.add(predecessor)
        self.assertEqual(labeled_count, 624)
        self.assertEqual(len(predecessors), 418)
        self.assertEqual(len(pairs), 429)
        for predecessor, terminal in pairs:
            with self.subTest(predecessor=predecessor, terminal=terminal):
                actions = recon.exhausting_actions_to(predecessor, 0, terminal)
                self.assertTrue(actions)
                for action in actions:
                    self.assertTrue(recon.source_is_legal(predecessor, 0, action[0], action[1]))
                    self.assertEqual(recon.apply_exhausting_action(predecessor, 0, action), terminal)
                    self.assertTrue(recon.exhausting_final_color_is_isolated(predecessor, action))

    def test_report_is_verified_and_deterministic(self) -> None:
        first = recon.build_report(max_reverse_depth=1)
        second = recon.build_report(max_reverse_depth=1)
        self.assertEqual(first, second)
        self.assertTrue(first["verified"])
        self.assertEqual(first["terminal_counts"], recon.EXPECTED_TERMINAL_COUNTS)
        self.assertEqual(first["reverse"]["canonical_predecessors"], 6_375)
        self.assertEqual(first["reverse"]["canonical_edges"], 12_224)
        self.assertEqual(
            {
                family: (
                    values["canonical_predecessors"],
                    values["canonical_edges"],
                )
                for family, values in first["reverse"]["by_terminal_family"].items()
            },
            {
                "tq": (80, 116),
                "d2_3_1": (632, 1_148),
                "d2_2_2": (5_798, 10_960),
            },
        )
        self.assertTrue(first["reverse"]["all_edges_replay"])
        self.assertEqual(
            first["reverse"]["tq_exhausting_bridge"],
            {
                "labeled_candidates": 624,
                "canonical_predecessors": 418,
                "canonical_edges": 429,
                "predecessor_states_with_unique_legal_source": 6,
                "predecessor_states_with_sibling_sources": 412,
                "all_predecessors_algebraically_consistent": True,
                "all_entry_actions_legal": True,
                "all_edges_replay": True,
                "all_final_colors_isolated": True,
            },
        )


if __name__ == "__main__":
    unittest.main()
