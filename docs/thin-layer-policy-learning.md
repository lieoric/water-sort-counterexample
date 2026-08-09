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

## Local use

```bash
./build/water-policy-learn \
  --colors 4 --height 9 --empty 2 \
  --depth 3 --samples 1000 --seed 1 \
  --out out/policy-d3
```

The output directory contains:

- `report.json`: sample and coverage totals;
- `signatures.tsv`: one row per canonical scene signature;
- `conflicts.tsv`: signatures whose observed safe-action intersection is empty;
- `counterexample.txt` and `counterexample.wscert`, if sampling finds a NO
  instance.

The `Learn thin-layer policy` GitHub Actions workflow runs multiple observation
depths and random shards in parallel, merges equal signatures across shards,
and publishes one merged artifact per depth.
