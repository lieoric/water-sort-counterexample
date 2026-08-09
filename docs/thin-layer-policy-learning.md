# Thin-layer policy learning

This experiment searches for a finite conditional policy for fixed color and
empty-column counts. It works on Ito top-border states rather than committing
to one concrete Water move sequence.

For every top-border state of an instance, `BorderOracle::policy_table()`
computes the exact set of columns whose next border removal still admits a
complete solution. Only states that are both reachable from the initial state
and solvable are used as observations.

`water-policy-learn` describes each observation using:

- the top `d` remaining color boundaries of every original column;
- whether the unseen suffix continues below that window;
- the number of currently available monochrome buffers;
- per-color deficient/hosted flags from Ito's `F` and `G` quantities; and
- the buffer count needed to remove each candidate source border, capped above
  the largest relevant buffer count.

Color names and full-column order are canonicalized. Observations with the same
signature are merged by intersecting their exact safe-action masks.

- A nonzero intersection is a candidate local rule observed to work for every
  concrete state in that signature class.
- An empty intersection is a conflict: the current signature or observation
  depth has merged states that require incompatible choices.

This is a counterexample-guided discovery experiment, not yet an all-height
proof. Finite samples can propose rules and disprove insufficient signatures.
A universal theorem additionally needs a symbolic checker proving that every
possible hidden suffix is covered and that each certified macro rule decreases
a well-founded measure such as the number of remaining original borders.

## Four-color, two-empty frontier

For four colors and two initially empty columns, it is enough to reach a
top-border state in which at least two original columns have no borders left.
If `r` columns are exhausted, Ito's capacity test has `2 + r` monochrome bins.
Each of the four colors needs at most one such bin, so at `r >= 2` every
remaining border is removable.

The focused experiment therefore uses `--goal-exhausted 2`. Its safe mask
means "can still reach two exhausted columns," rather than "can still reach
the fully sorted border table." This removes the already-trivial suffix from
the proof obligation.

`--tail-mutations N --tail-swaps M` creates related balanced instances by
protecting the visible top runs and swapping items only in deeper hidden tails.
The variants make one thin signature encounter different hidden completions
and are intended to expose action conflicts quickly.

The `Attack c4 k2 frontier policy` workflow merges signatures per height and
again across every requested height. A cross-height conflict is a finite scene
summary for which the observed hidden completions share no frontier-winning
action.

## Controlled reachability

The all-state merge is deliberately severe: it requires one action to work in
every reachable solvable state with the same signature, including states that
a sensible controller could avoid. `water-policy-control` asks the more useful
question. It assigns one action to each depth-`d` signature, simulates only the
trajectories induced by those assignments, and repairs or restarts whenever a
new induced state invalidates an assignment.

The supplied `conflicts.tsv` is diagnostic only. A formerly conflicting
signature may be used if the chosen trajectories encounter a compatible
subset of its concrete states. Every transition is checked against the exact
frontier-winning action table for that particular instance.

This remains randomized finite-catalog synthesis:

- success is a replayable policy certificate for every catalog row;
- failure only means that the restart budget found no shared controller; and
- an all-height theorem still needs a symbolic closure proof over every
  possible hidden suffix.

### Default rule plus exceptions

The full sampled controller can be represented more compactly by first trying
a deterministic local rule and storing a table only where that rule must be
overridden. The current best baseline selects the last legal source in
canonical column order. On the 3,501 sampled initial instances, two independent
controllers each reach the frontier with 114 exception signatures. Their stable
intersection has 109 signatures and their union has 119; every resulting
trajectory is replayed from scratch.

This is a useful conjecture generator: exceptions can be grouped into a small
number of deficient/hosted and visible-column shapes. It is not a proof that
only those exceptions exist at untested heights.

## Expanding a border action into one-item moves

`water-unit-scenes` tests whether the macro controller also suggests a small
finite program at the physical move level. At each controlled top-border state
it constructs a deterministic tight configuration from the exact `F_c` totals.
A chosen safe border action is then expanded into legal one-item moves, keeping
the source fixed until its current top-color run is gone.

Every intermediate state is recorded at three observation windows: the top 2,
3, and 4 items of every labeled stack. The signature also records whether each
stack has an unresolved original boundary below the visible items, whether it
is empty, partial, full, or locked, and whether a source is already active. For
equal signatures, the analyzer intersects all exact safe unit actions.

- A conflict at window `d` proves that this particular `d`-item scene summary
  cannot choose one action for all sampled occurrences.
- No conflict supplies a candidate finite rule for the sampled macro-local
  traces; it is not by itself a universal proof.

The scope limitation is explicit. After one original border is removed, the
next macro checkpoint is rebuilt as a canonical tight representative rather
than reached by a continuous physical rearrangement. The report counts every
such `retightening_gap`. Closing those gaps, and proving closure over arbitrary
hidden suffixes, are separate proof obligations.

### Current finite-catalog result

The two compressed controllers were expanded over all 3,501 catalog instances
(heights 4, 5, 6, 7, 8, 9, 12, and 16). The merged run replayed 156,873 macro
checkpoints and 607,860 legal one-item moves, and witnessed all 119 exception
signatures from the union of the two macro policies.

| Visible top items | Distinct unit scenes | Conflicts |
|---:|---:|---:|
| 2 | 66,503 | 38 |
| 3 | 151,240 | 5 |
| 4 | 229,128 | 0 |

All five window-3 conflicts occur in the idle phase, before choosing the next
source. They split into only 29 window-4 refinements, each with a nonempty
common safe action. This supports a compact layered candidate: inspect three
items normally and consult the fourth item only for five ambiguous three-item
patterns. It is materially smaller than treating all 229,128 window-4 scenes
as unrelated rules.

These are exact intersections for the finite catalog and the chosen canonical
tight representatives, not an all-height theorem. There are 149,871 explicit
connections still to replace with continuous physical traces or a general
retightening lemma. The complete result is retained by GitHub Actions run
[`31331083596`](https://github.com/lieoric/water-sort-counterexample/actions/runs/31331083596).

## Local use

Collect observations:

```bash
./build/water-policy-learn \
  --colors 4 --height 9 --empty 2 \
  --depth 3 --samples 1000 --seed 1 \
  --out out/policy-d3
```

The observation output directory contains:

- `report.json`: sample and coverage totals;
- `signatures.tsv`: one row per canonical scene signature;
- `conflicts.tsv`: signatures whose observed safe-action intersection is empty;
- `instances.tsv`: exact initial columns keyed by the fingerprints used in
  signature witnesses, so a conflict can be reconstructed; and
- `counterexample.txt` and `counterexample.wscert`, if sampling finds a NO
  instance.

Search a shared controller over a merged catalog:

```bash
./build/water-policy-control \
  --catalog merged/instances.tsv \
  --conflicts merged/conflicts.tsv \
  --depth 3 --goal-exhausted 2 \
  --restarts 256 --repair-passes 128 --seed 1 \
  --out out/controlled
```

Compress the same controller around a finite default rule:

```bash
./build/water-policy-control \
  --catalog merged/instances.tsv \
  --conflicts merged/conflicts.tsv \
  --depth 3 --goal-exhausted 2 \
  --default-heuristic last \
  --restarts 64 --repair-passes 128 --seed 1 \
  --out out/compressed
```

Compare top-item windows 2, 3, and 4 on one or more compressed policies:

```bash
./build/water-unit-scenes \
  --catalog merged/instances.tsv \
  --policy compressed-0/policy.tsv \
  --policy compressed-1/policy.tsv \
  --goal-exhausted 2 \
  --out out/unit-scenes
```

The `Attack c4 k2 frontier policy` workflow collects exact observations and
the `Synthesize c4 k2 controlled policy` workflow launches independent
controlled-policy attempts over the resulting catalog. `Analyze c4 k2 unit
scenes` expands both compressed last-rule controllers and merges their unit
scene intersections over parallel catalog shards.
