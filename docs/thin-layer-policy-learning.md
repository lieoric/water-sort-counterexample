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
canonical column order. On the 3,501 sampled initial instances, it reaches the
frontier after adding 115 exception signatures; every resulting trajectory is
then replayed from scratch.

This is a useful conjecture generator: exceptions can be grouped into a small
number of deficient/hosted and visible-column shapes. It is not a proof that
only those exceptions exist at untested heights.

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

The `Attack c4 k2 frontier policy` workflow collects exact observations and
the `Synthesize c4 k2 controlled policy` workflow launches independent
controlled-policy attempts over the resulting catalog.
