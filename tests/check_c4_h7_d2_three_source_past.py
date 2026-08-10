#!/usr/bin/env python3
"""Independent zero-debt audit for the c4/h7 D2 three-source residuals.

This checker imports no production implementation.  It independently

* validates the complete 1,106,490-future checkpoint report and its 14,784
  local-NO rows;
* rebuilds the 285,600 balanced past restorations and marks the exact 281,904
  parent-reachable subset by an event-interleaving DP;
* solves every selected complete layout from zero debt with a separate run DP;
* replays every winning path; and
* when a production past report is supplied, compares its result ledger in
  deterministic row order.

The default is deliberately bounded.  ``--full`` is accepted only inside
GitHub Actions so an accidental local invocation cannot start the formal run.
Neither a primary nor an independent DP NO is called globally certified here;
that promotion belongs to water-oracle plus water-verify.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
from functools import lru_cache
import itertools
import json
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Iterable, Iterator, NoReturn, Sequence, TextIO


HEIGHT = 7
COLORS = 4
EMPTY = 2
CHECKPOINT_FUTURES = 1_106_490
CHECKPOINT_LOCAL_NO = 14_784
BALANCED_RESTORATIONS = 285_600
REACHABLE_RESTORATIONS = 281_904
UNREACHABLE_RESTORATIONS = 3_696
FNV_OFFSET = 1_469_598_103_934_665_603
FNV_PRIME = 1_099_511_628_211

RESULT_HEADER = (
    "restoration_index\tfuture_index\tbridge_edge\tprefix_index\t"
    "parent_reachable\tcolumns_top_to_bottom\tinitial_status\t"
    "safe_source_mask\tescape_columns"
)

Words = tuple[str, str, str, str]
Debts = tuple[int, int, int, int]
Ranks = tuple[int, int, int, int]
Event = tuple[int, int, int, int]
PastEvent = tuple[int, int, int]


def fail(message: str) -> NoReturn:
    raise AssertionError(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def integer(value: object, label: str) -> int:
    require(
        isinstance(value, int) and not isinstance(value, bool),
        f"{label} is not an integer",
    )
    return int(value)


def boolean(value: object, label: str) -> bool:
    require(isinstance(value, bool), f"{label} is not a Boolean")
    return bool(value)


@dataclass(frozen=True)
class ParentSpec:
    edge: int
    debts: Debts
    bad: tuple[int, int, int]
    q_caps: tuple[int, int, int]
    local_no_rows: int
    prefix_candidates: int
    prefix_reachable: int
    legal_histories: int

    @property
    def caps(self) -> tuple[int, int, int, int]:
        return self.bad[1], *self.q_caps


SPECS: tuple[ParentSpec, ...] = (
    ParentSpec(116, (-4, 0, 1, 3), (0, 4, 1), (1, 1, 5), 210, 140, 140, 1_184),
    ParentSpec(117, (-4, 0, 2, 2), (0, 4, 1), (1, 1, 5), 252, 210, 210, 2_076),
    ParentSpec(184, (-3, 0, 1, 2), (0, 2, 1), (2, 2, 4), 462, 60, 60, 348),
    ParentSpec(236, (-2, 0, 1, 1), (0, 2, 1), (1, 1, 3), 924, 6, 6, 12),
    ParentSpec(242, (-2, 0, 1, 1), (0, 2, 1), (1, 2, 3), 11_088, 12, 12, 26),
    ParentSpec(244, (-2, 0, 1, 1), (0, 2, 1), (1, 2, 4), 924, 20, 16, 30),
    ParentSpec(248, (-2, 0, 1, 1), (0, 2, 1), (2, 2, 3), 924, 20, 20, 44),
)
SPEC_BY_EDGE = {spec.edge: spec for spec in SPECS}


@dataclass(frozen=True)
class Prefix:
    ordinal: int
    words: Words
    reachable: bool
    histories: int
    witness: str


@dataclass(frozen=True)
class LedgerRow:
    future_index: int
    decoration_index: int
    spec: ParentSpec
    hidden_bottom_to_top: Words


@dataclass(frozen=True)
class SolveResult:
    solvable: bool
    safe_mask: int
    path: str
    states: int
    transitions: int


@dataclass(frozen=True)
class CanonicalLayout:
    words: Words
    canonical_to_original: tuple[int, int, int, int]
    key: str


@dataclass(frozen=True)
class ProductionRow:
    raw: str
    restoration_index: int
    future_index: int
    bridge_edge: int
    prefix_index: int
    parent_reachable: bool
    columns: Words
    status: str
    safe_mask: int
    path: str


def prefix_events(words: Words) -> tuple[tuple[PastEvent, ...], ...]:
    chains: list[tuple[PastEvent, ...]] = []
    for word in words:
        require(bool(word), "empty past-prefix word")
        runs: list[tuple[int, int]] = []
        cursor = 0
        while cursor < len(word):
            end = cursor + 1
            while end < len(word) and word[end] == word[cursor]:
                end += 1
            runs.append((int(word[cursor]), end))
            cursor = end
        chains.append(
            tuple(
                (runs[index][0], runs[index][1], runs[index + 1][0])
                for index in range(len(runs) - 1)
            )
        )
    return tuple(chains)


def past_reachability(words: Words) -> tuple[int, str, Debts]:
    chains = prefix_events(words)
    goal: Ranks = tuple(len(chain) for chain in chains)  # type: ignore[assignment]

    @lru_cache(maxsize=None)
    def debts_at(ranks: Ranks) -> Debts:
        debts = [0] * COLORS
        for column, rank in enumerate(ranks):
            for old_color, old_cap, next_color in chains[column][:rank]:
                debts[old_color] += old_cap
                debts[next_color] -= old_cap
        return tuple(debts)  # type: ignore[return-value]

    first: dict[Ranks, int] = {}

    @lru_cache(maxsize=None)
    def count(ranks: Ranks) -> int:
        if ranks == goal:
            return 1
        debts = debts_at(ranks)
        total = 0
        for column, rank in enumerate(ranks):
            if rank == len(chains[column]):
                continue
            old_color, old_cap, _next_color = chains[column][rank]
            tested = list(debts)
            tested[old_color] += old_cap
            if sum(value > 0 for value in tested) > EMPTY:
                continue
            child = list(ranks)
            child[column] += 1
            child_ranks: Ranks = tuple(child)  # type: ignore[assignment]
            child_count = count(child_ranks)
            if child_count and ranks not in first:
                first[ranks] = column
            total += child_count
        return total

    start: Ranks = (0, 0, 0, 0)
    histories = count(start)
    witness = ""
    ranks = start
    while histories and ranks != goal:
        require(ranks in first, "reachable prefix lost its first witness")
        column = first[ranks]
        witness += str(column)
        child = list(ranks)
        child[column] += 1
        ranks = tuple(child)  # type: ignore[assignment]
    return histories, witness, debts_at(goal)


def multiset_words(spec: ParentSpec) -> Iterator[Words]:
    exposed = list(spec.debts)
    exposed[0] += sum(spec.caps)
    exposed[0] -= COLORS  # reserve the four final q=0 balls
    require(all(value >= 0 for value in exposed), f"edge {spec.edge}: negative residual")
    free = sum(cap - 1 for cap in spec.caps)
    require(sum(exposed) == free, f"edge {spec.edge}: residual inventory drifted")
    flat = [0] * free

    def visit(position: int) -> Iterator[Words]:
        if position == free:
            cursor = 0
            words: list[str] = []
            for cap in spec.caps:
                body = flat[cursor : cursor + cap - 1]
                cursor += cap - 1
                words.append("".join(map(str, body)) + "0")
            require(cursor == free, "prefix split lost a position")
            yield tuple(words)  # type: ignore[misc]
            return
        for color in range(COLORS):
            if exposed[color] == 0:
                continue
            exposed[color] -= 1
            flat[position] = color
            yield from visit(position + 1)
            exposed[color] += 1

    yield from visit(0)


@lru_cache(maxsize=None)
def enumerate_prefixes(spec: ParentSpec) -> tuple[Prefix, ...]:
    prefixes: list[Prefix] = []
    for ordinal, words in enumerate(multiset_words(spec)):
        histories, witness, final_debts = past_reachability(words)
        require(final_debts == spec.debts, f"edge {spec.edge}: prefix debt drifted")
        prefixes.append(Prefix(ordinal, words, histories != 0, histories, witness))
    reachable = sum(prefix.reachable for prefix in prefixes)
    histories = sum(prefix.histories for prefix in prefixes)
    require(len(prefixes) == spec.prefix_candidates, f"edge {spec.edge}: M drifted")
    require(reachable == spec.prefix_reachable, f"edge {spec.edge}: T drifted")
    require(histories == spec.legal_histories, f"edge {spec.edge}: H drifted")
    return tuple(prefixes)


def rebuild_definition_census() -> dict[str, object]:
    per_edge: list[dict[str, int]] = []
    balanced = reachable = 0
    for spec in SPECS:
        prefixes = enumerate_prefixes(spec)
        edge_balanced = spec.local_no_rows * len(prefixes)
        edge_reachable = spec.local_no_rows * sum(item.reachable for item in prefixes)
        balanced += edge_balanced
        reachable += edge_reachable
        per_edge.append(
            {
                "bridge_edge": spec.edge,
                "checkpoint_local_no": spec.local_no_rows,
                "prefix_candidates": len(prefixes),
                "prefix_reachable": sum(item.reachable for item in prefixes),
                "legal_prefix_histories": sum(item.histories for item in prefixes),
                "balanced_restorations": edge_balanced,
                "reachable_restorations": edge_reachable,
            }
        )
    require(balanced == BALANCED_RESTORATIONS, "balanced universe is not 285600")
    require(reachable == REACHABLE_RESTORATIONS, "reachable universe is not 281904")
    return {
        "balanced_restorations": balanced,
        "reachable_restorations": reachable,
        "unreachable_restorations": balanced - reachable,
        "per_edge": per_edge,
    }


def load_checkpoint_report(path: Path) -> tuple[dict[str, object], Path]:
    report = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(report, dict), "checkpoint report is not an object")
    require(integer(report.get("schema_version"), "checkpoint.schema_version") == 1, "checkpoint schema drifted")
    require(report.get("experiment") == "c4_h7_d2_three_source_checkpoint", "wrong checkpoint experiment")
    require(report.get("status") == "LOCAL_NO_RESIDUALS_EXPORTED", "checkpoint is not formally complete")
    run = report.get("run")
    require(isinstance(run, dict), "checkpoint.run is not an object")
    require(boolean(run.get("universe_complete"), "checkpoint.run.universe_complete"), "checkpoint universe is incomplete")
    require(integer(run.get("fixed_futures_checked"), "checkpoint.run.fixed_futures_checked") == CHECKPOINT_FUTURES, "checkpoint future census drifted")
    require(integer(run.get("local_no"), "checkpoint.run.local_no") == CHECKPOINT_LOCAL_NO, "checkpoint local-NO census drifted")
    scope = report.get("scope")
    require(isinstance(scope, dict), "checkpoint.scope is not an object")
    require(scope.get("parent_checkpoint_only") is True, "checkpoint lost local scope")
    require(scope.get("zero_debt_past_restored") is False, "checkpoint falsely claims zero-debt restoration")
    claims = report.get("claims")
    require(isinstance(claims, dict), "checkpoint.claims is not an object")
    require(claims.get("zero_debt_initial_family_eliminated") is False, "checkpoint overclaims initial elimination")
    require(claims.get("universal_c4_h7_solvability") is False, "checkpoint overclaims h7")
    require(report.get("self_checks_passed") is True, "checkpoint self-checks failed")
    ledgers = report.get("ledgers")
    require(isinstance(ledgers, dict), "checkpoint.ledgers is not an object")
    require(ledgers.get("local_no") == "local-no-ledger.jsonl", "checkpoint local-NO filename drifted")
    return report, path.parent / "local-no-ledger.jsonl"


def parse_int_list(value: object, size: int, label: str) -> tuple[int, ...]:
    require(isinstance(value, list) and len(value) == size, f"{label} shape drifted")
    return tuple(integer(item, f"{label}[]") for item in value)


def load_local_no_rows(path: Path) -> tuple[LedgerRow, ...]:
    rows: list[LedgerRow] = []
    counts: Counter[int] = Counter()
    previous = -1
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            raw = json.loads(line)
            require(isinstance(raw, dict), f"local-NO line {line_number} is not an object")
            future = integer(raw.get("future_index"), f"local-NO[{line_number}].future_index")
            require(future > previous, "local-NO future indices are not strictly increasing")
            previous = future
            edge = integer(raw.get("bridge_edge"), f"local-NO[{line_number}].bridge_edge")
            require(edge in SPEC_BY_EDGE, f"unexpected local-NO edge {edge}")
            spec = SPEC_BY_EDGE[edge]
            require(parse_int_list(raw.get("parent_debts"), 4, "parent_debts") == spec.debts, f"edge {edge}: debt fixture drifted")
            require(parse_int_list(raw.get("bad_source"), 3, "bad_source") == spec.bad, f"edge {edge}: bad source drifted")
            require(integer(raw.get("q_color"), "q_color") == 0, f"edge {edge}: q colour drifted")
            require(parse_int_list(raw.get("q_caps"), 3, "q_caps") == spec.q_caps, f"edge {edge}: q caps drifted")
            require(raw.get("local_status") == "NO" and raw.get("safe_source_mask") == 0, f"edge {edge}: ledger row is not local NO")
            words_raw = raw.get("hidden_words_bottom_to_top")
            require(isinstance(words_raw, list) and len(words_raw) == COLORS, f"edge {edge}: hidden word shape drifted")
            words: Words = tuple(words_raw)  # type: ignore[assignment]
            hidden_counts: Counter[int] = Counter()
            for column, word in enumerate(words):
                require(isinstance(word, str) and set(word) <= set("0123"), f"edge {edge}: invalid hidden word")
                require(len(word) == HEIGHT - spec.caps[column], f"edge {edge}: hidden word length drifted")
                require(bool(word) and word[-1] != "0", f"edge {edge}: hidden suffix merges with q border")
                hidden_counts.update(map(int, word))
            require(set(words[0]) == {str(spec.bad[2])}, f"edge {edge}: bad suffix is not forced final colour")
            exposed = list(spec.debts)
            exposed[0] += sum(spec.caps)
            require(all(hidden_counts[color] == HEIGHT - exposed[color] for color in range(COLORS)), f"edge {edge}: hidden inventory is unbalanced")
            rows.append(
                LedgerRow(
                    future,
                    integer(raw.get("decoration_index"), "decoration_index"),
                    spec,
                    words,
                )
            )
            counts[edge] += 1
    require(len(rows) == CHECKPOINT_LOCAL_NO, "local-NO ledger does not contain 14784 rows")
    require(counts == Counter({spec.edge: spec.local_no_rows for spec in SPECS}), "local-NO per-edge census drifted")
    return tuple(rows)


def restore_layout(row: LedgerRow, prefix: Prefix) -> Words:
    columns: list[str] = []
    inventory: Counter[str] = Counter()
    for column in range(COLORS):
        hidden_top = row.hidden_bottom_to_top[column][::-1]
        past = prefix.words[column]
        require(len(past) == row.spec.caps[column], "past prefix cap drifted")
        require(past[-1] != hidden_top[0], "restored boundary merged")
        word = past + hidden_top
        require(len(word) == HEIGHT, "restored column is not height seven")
        columns.append(word)
        inventory.update(word)
    require(inventory == Counter({str(color): HEIGHT for color in range(COLORS)}), "restored layout is not balanced")
    return tuple(columns)  # type: ignore[return-value]


class InitialSolver:
    """Independent exact run-event DP for a complete zero-debt layout."""

    def __init__(self, words: Words):
        self.words = words
        self.events: tuple[tuple[Event, ...], ...] = tuple(self._events(word) for word in words)
        self.deltas: tuple[tuple[Debts, ...], ...] = tuple(self._deltas(chain) for chain in self.events)
        self.memo: dict[Ranks, bool] = {}
        self.states = 0
        self.transitions = 0

    @staticmethod
    def _events(word: str) -> tuple[Event, ...]:
        require(len(word) == HEIGHT and set(word) <= set("0123"), "invalid complete layout word")
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

    @staticmethod
    def _deltas(events: tuple[Event, ...]) -> tuple[Debts, ...]:
        result: list[Debts] = [(0, 0, 0, 0)]
        for old_color, old_cap, next_color, next_cap in events:
            delta = list(result[-1])
            delta[old_color] += old_cap
            if next_cap == HEIGHT:
                delta[next_color] += HEIGHT - old_cap
            else:
                delta[next_color] -= old_cap
            result.append(tuple(delta))  # type: ignore[arg-type]
        return tuple(result)

    def exhausted(self, ranks: Ranks) -> int:
        return sum(ranks[column] == len(self.events[column]) for column in range(COLORS))

    def goal(self, ranks: Ranks) -> bool:
        return self.exhausted(ranks) >= EMPTY

    def legal(self, ranks: Ranks, column: int) -> bool:
        rank = ranks[column]
        if rank == len(self.events[column]):
            return False
        debts = [0] * COLORS
        for other in range(COLORS):
            for color, value in enumerate(self.deltas[other][ranks[other]]):
                debts[color] += value
        old_color, old_cap, _next_color, _next_cap = self.events[column][rank]
        debts[old_color] += old_cap
        return sum(value > 0 for value in debts) <= EMPTY + self.exhausted(ranks)

    @staticmethod
    def child(ranks: Ranks, column: int) -> Ranks:
        values = list(ranks)
        values[column] += 1
        return tuple(values)  # type: ignore[return-value]

    def winning(self, ranks: Ranks) -> bool:
        if self.goal(ranks):
            return True
        if ranks in self.memo:
            return self.memo[ranks]
        self.states += 1
        for column in range(COLORS):
            if not self.legal(ranks, column):
                continue
            self.transitions += 1
            if self.winning(self.child(ranks, column)):
                self.memo[ranks] = True
                return True
        self.memo[ranks] = False
        return False

    def safe(self, ranks: Ranks, column: int) -> bool:
        if self.goal(ranks) or not self.legal(ranks, column):
            return False
        self.transitions += 1
        return self.winning(self.child(ranks, column))

    def solve(self) -> SolveResult:
        start: Ranks = (0, 0, 0, 0)
        solvable = self.winning(start)
        safe_mask = sum(1 << column for column in range(COLORS) if self.safe(start, column))
        path = ""
        ranks = start
        while solvable and not self.goal(ranks):
            for column in range(COLORS):
                if self.safe(ranks, column):
                    path += str(column)
                    ranks = self.child(ranks, column)
                    break
            else:
                fail("independent YES has no safe successor")
        require(not solvable or self.replay(path), "independent winning path does not replay")
        return SolveResult(solvable, safe_mask, path, self.states, self.transitions)

    def replay(self, path: str) -> bool:
        ranks: Ranks = (0, 0, 0, 0)
        for token in path:
            require(token in "0123", "winning path contains an invalid column")
            column = int(token)
            if not self.legal(ranks, column):
                return False
            ranks = self.child(ranks, column)
        return self.goal(ranks)


@lru_cache(maxsize=None)
def canonicalize(original: Words) -> CanonicalLayout:
    best: CanonicalLayout | None = None
    for recoloring in itertools.permutations(range(COLORS)):
        columns = []
        for original_column, word in enumerate(original):
            recolored = "".join(str(recoloring[int(value)]) for value in word)
            columns.append((recolored, original_column))
        columns.sort()
        key = "".join(word for word, _column in columns)
        if best is None or key < best.key:
            best = CanonicalLayout(
                tuple(word for word, _column in columns),  # type: ignore[arg-type]
                tuple(column for _word, column in columns),  # type: ignore[arg-type]
                key,
            )
    require(best is not None, "layout canonicalization failed")
    return best


def map_result(result: SolveResult, mapping: tuple[int, int, int, int]) -> SolveResult:
    mask = 0
    for canonical_column in range(COLORS):
        if result.safe_mask & (1 << canonical_column):
            mask |= 1 << mapping[canonical_column]
    path = "".join(str(mapping[int(token)]) for token in result.path)
    return SolveResult(result.solvable, mask, path, result.states, result.transitions)


def solve_layout(words: Words, cache: dict[str, SolveResult]) -> tuple[SolveResult, bool]:
    canonical = canonicalize(words)
    cached = canonical.key in cache
    if not cached:
        cache[canonical.key] = InitialSolver(canonical.words).solve()
    return map_result(cache[canonical.key], canonical.canonical_to_original), cached


def parse_production_row(line: str, line_number: int) -> ProductionRow:
    fields = line.rstrip("\n").split("\t")
    require(len(fields) == 9, f"production result line {line_number} has {len(fields)} fields")
    columns_raw = fields[5].split(",")
    require(len(columns_raw) == COLORS, f"production result line {line_number} lost columns")
    columns: Words = tuple(columns_raw)  # type: ignore[assignment]
    require(fields[4] in {"0", "1"}, f"production result line {line_number} has invalid reachability")
    require(fields[6] in {"YES", "NO"}, f"production result line {line_number} has invalid status")
    return ProductionRow(
        line.rstrip("\n"),
        int(fields[0]),
        int(fields[1]),
        int(fields[2]),
        int(fields[3]),
        fields[4] == "1",
        columns,
        fields[6],
        int(fields[7]),
        fields[8],
    )


def production_rows(path: Path) -> Iterator[ProductionRow]:
    with path.open(encoding="utf-8") as stream:
        header = stream.readline().rstrip("\n")
        require(header == RESULT_HEADER, "production initial-results.tsv header drifted")
        for line_number, line in enumerate(stream, 2):
            yield parse_production_row(line, line_number)


def fnv_update(value: int, row: str) -> int:
    for byte in (row + "\n").encode("utf-8"):
        value ^= byte
        value = (value * FNV_PRIME) & 0xFFFFFFFFFFFFFFFF
    return value


def load_production_report(path: Path) -> tuple[dict[str, object], Path]:
    report = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(report, dict), "production report is not an object")
    require(report.get("schema_version") == 1, "production past schema drifted")
    require(report.get("experiment") == "c4_h7_d2_three_source_past_restoration", "wrong production past experiment")
    require(report.get("status") in {"INCOMPLETE", "INITIAL_NO_CANDIDATES_EXPORTED", "THREE_SOURCE_PAST_FAMILY_ELIMINATED"}, "unsafe production status")
    ledgers = report.get("ledgers")
    require(isinstance(ledgers, dict), "production ledgers is not an object")
    require(ledgers.get("initial_results") == "initial-results.tsv", "production result ledger name drifted")
    return report, path.parent / "initial-results.tsv"


def launch_production(program: Path, checkpoint_report: Path, limit: int, output_dir: Path) -> Path:
    require(limit > 0, "bounded production launch requires a positive limit")
    command = [
        str(program),
        "--checkpoint-report",
        str(checkpoint_report),
        "--output-dir",
        str(output_dir),
        "--limit-restorations",
        str(limit),
        "--self-test",
    ]
    subprocess.run(command, check=True)
    return output_dir / "report.json"


def run_audit(
    checkpoint_report: Path,
    limit: int,
    production_report_path: Path | None,
) -> dict[str, object]:
    definitions = rebuild_definition_census()
    _checkpoint, ledger_path = load_checkpoint_report(checkpoint_report)
    ledger_rows = load_local_no_rows(ledger_path)
    production_report: dict[str, object] | None = None
    production_iterator: Iterator[ProductionRow] | None = None
    if production_report_path is not None:
        production_report, results_path = load_production_report(production_report_path)
        production_iterator = production_rows(results_path)

    effective_limit = min(limit, BALANCED_RESTORATIONS)
    cache: dict[str, SolveResult] = {}
    checked = reachable = initial_yes = initial_no = 0
    cache_hits = states = transitions = 0
    production_hash = FNV_OFFSET
    per_edge: defaultdict[int, Counter[str]] = defaultdict(Counter)
    first_no: dict[str, object] | None = None

    stop = False
    for ledger in ledger_rows:
        if stop:
            break
        for prefix in enumerate_prefixes(ledger.spec):
            if checked >= effective_limit:
                stop = True
                break
            columns = restore_layout(ledger, prefix)
            result, cached = solve_layout(columns, cache)
            cache_hits += int(cached)
            if not cached:
                states += result.states
                transitions += result.transitions
            labelled_replay = InitialSolver(columns)
            require(not result.solvable or labelled_replay.replay(result.path), f"row {checked}: mapped independent path failed replay")

            status = "YES" if result.solvable else "NO"
            initial_yes += int(result.solvable)
            initial_no += int(not result.solvable)
            reachable += int(prefix.reachable)
            edge_stats = per_edge[ledger.spec.edge]
            edge_stats["checked"] += 1
            edge_stats["reachable"] += int(prefix.reachable)
            edge_stats["initial_yes"] += int(result.solvable)
            edge_stats["initial_no"] += int(not result.solvable)
            if not result.solvable and first_no is None:
                first_no = {
                    "restoration_index": checked,
                    "future_index": ledger.future_index,
                    "bridge_edge": ledger.spec.edge,
                    "prefix_index": prefix.ordinal,
                    "parent_reachable": prefix.reachable,
                    "columns_top_to_bottom": list(columns),
                    "columns_bottom_to_top": [word[::-1] for word in columns],
                }

            if production_iterator is not None:
                try:
                    actual = next(production_iterator)
                except StopIteration:
                    fail(f"production result ledger stopped before independent row {checked}")
                require(actual.restoration_index == checked, f"row {checked}: restoration index differs")
                require(actual.future_index == ledger.future_index, f"row {checked}: future index differs")
                require(actual.bridge_edge == ledger.spec.edge, f"row {checked}: edge differs")
                require(actual.prefix_index == prefix.ordinal, f"row {checked}: prefix index differs")
                require(actual.parent_reachable == prefix.reachable, f"row {checked}: reachability differs")
                require(actual.columns == columns, f"row {checked}: restored layout differs")
                require(actual.status == status, f"row {checked}: zero-debt status differs")
                require(actual.safe_mask == result.safe_mask, f"row {checked}: safe-source mask differs")
                require((actual.path == "") == (actual.status == "NO"), f"row {checked}: production path/status disagree")
                require(actual.status == "NO" or labelled_replay.replay(actual.path), f"row {checked}: production path failed independent replay")
                production_hash = fnv_update(production_hash, actual.raw)
            checked += 1

    require(checked == effective_limit, "independent audit stopped before requested limit")
    if production_iterator is not None:
        try:
            extra = next(production_iterator)
        except StopIteration:
            extra = None
        require(extra is None, "production result ledger contains extra rows")

    complete = checked == BALANCED_RESTORATIONS
    if complete:
        require(reachable == REACHABLE_RESTORATIONS, "full reachable census drifted")
    status = (
        "INITIAL_NO_CANDIDATES_EXPORTED"
        if initial_no
        else "THREE_SOURCE_PAST_FAMILY_ELIMINATED"
        if complete
        else "INCOMPLETE"
    )
    if production_report is not None:
        run = production_report.get("run")
        require(isinstance(run, dict), "production run is not an object")
        require(integer(run.get("restorations_checked"), "production.run.restorations_checked") == checked, "production checked count differs")
        require(integer(run.get("reachable_checked"), "production.run.reachable_checked") == reachable, "production reachable count differs")
        require(integer(run.get("initial_yes"), "production.run.initial_yes") == initial_yes, "production YES count differs")
        require(integer(run.get("initial_no"), "production.run.initial_no") == initial_no, "production NO count differs")
        require(production_report.get("status") == status, "production terminal status differs")
        ledgers = production_report.get("ledgers")
        assert isinstance(ledgers, dict)
        require(ledgers.get("result_rows_fnv1a64") == f"{production_hash:016x}", "production row hash differs")

    return {
        "schema_version": 1,
        "experiment": "c4_h7_d2_three_source_past_independent_audit",
        "status": status,
        "scope": {
            "balanced_completion_superset_only": True,
            "full_h7_theorem": False,
            "global_no_certification": False,
        },
        "definition_census": definitions,
        "run": {
            "limit_requested": 0 if complete else limit,
            "universe_complete": complete,
            "restorations_checked": checked,
            "reachable_checked": reachable,
            "unreachable_checked": checked - reachable,
            "initial_yes": initial_yes,
            "initial_no": initial_no,
            "winning_paths_replayed": initial_yes,
            "canonical_classes_solved": len(cache),
            "symmetry_cache_hits": cache_hits,
            "states": states,
            "transitions": transitions,
            "production_rows_compared": checked if production_report is not None else 0,
            "row_by_row_agreement": production_report is not None,
        },
        "claims": {
            "restoration_family_eliminated": complete and initial_no == 0 and production_report is not None,
            "initial_no_candidates_found": initial_no != 0,
            "global_no_certified": False,
            "universal_c4_h7_solvability": False,
        },
        "first_initial_no": first_no,
        "per_edge": [
            {
                "bridge_edge": spec.edge,
                "restorations_checked": per_edge[spec.edge]["checked"],
                "reachable_checked": per_edge[spec.edge]["reachable"],
                "initial_yes": per_edge[spec.edge]["initial_yes"],
                "initial_no": per_edge[spec.edge]["initial_no"],
            }
            for spec in SPECS
        ],
        "self_checks_passed": True,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint-report", type=Path, required=True)
    parser.add_argument("--production-report", type=Path)
    parser.add_argument("--program", type=Path, help="launch a bounded production run and compare it")
    parser.add_argument("--limit", type=int, default=64, help="bounded restorations (default: 64)")
    parser.add_argument("--full", action="store_true", help="formal 285600-row GitHub Actions audit")
    parser.add_argument("--json", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    require(args.limit > 0, "--limit must be positive; use --full for the formal universe")
    if args.full:
        require(os.environ.get("GITHUB_ACTIONS") == "true", "--full is intentionally GitHub-Actions-only")
        limit = BALANCED_RESTORATIONS
    else:
        limit = args.limit
    require(not (args.program and args.production_report), "choose --program or --production-report, not both")

    temporary: tempfile.TemporaryDirectory[str] | None = None
    production_report = args.production_report
    try:
        if args.program:
            require(not args.full, "the checker never launches a full production run")
            temporary = tempfile.TemporaryDirectory(prefix="c4-h7-past-")
            production_report = launch_production(
                args.program,
                args.checkpoint_report,
                limit,
                Path(temporary.name),
            )
        result = run_audit(args.checkpoint_report, limit, production_report)
        rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
        if args.json:
            args.json.parent.mkdir(parents=True, exist_ok=True)
            args.json.write_text(rendered, encoding="utf-8")
        print(rendered, end="")
    finally:
        if temporary is not None:
            temporary.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
