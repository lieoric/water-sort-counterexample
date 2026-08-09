# Joint SMT search for a fixed-height counterexample

`scripts/smt_counterexample.py` asks a different question from the mutation
hunter.  For one fixed `(c,h,k)`, the solver chooses every item color in every
initial full column, subject to exact balanced color totals, while Boolean
variables evaluate the complete top-border DAG of that unknown instance.

For each original column, a position is a live border exactly when the colors
immediately below and above it differ.  A symbolic state chooses one live
border position (or rank zero) per column.  The script constructs the exact
`F_c`, `G_c`, source-demand test, previous-border successor, and the acyclic
winning recurrence.  It then asks for a balanced assignment whose initial
state cannot reach the exhausted-column frontier.  In the four-color,
two-empty case the frontier is two exhausted original columns.

Global color relabeling fixes the first sorted column's bottom item to color
zero; full columns are sorted lexicographically.  This symmetry-reduced
covering is partitioned into disjoint shards by the base-`c` code of the first
column.
Consequently, all shards together cover the fixed-height universe even though
they solve independently.

## Interpreting outcomes

- `SAT` writes a concrete ordinary instance.  GitHub Actions immediately runs
  the independent C++ border oracle and transition-closure certificate
  verifier.  Only a candidate passing that check is a Water Sort NO result.
- `UNSAT` excludes a counterexample only in that finite-height shard.
- `unknown` normally means the configured solver timeout expired and leaves
  the fixed-height search incomplete.

The current encoder does not request or retain a Z3 proof object.  Thus a set
of all-UNSAT shards is a reproducible exhaustive computation, not an
independently checkable UNSAT certificate and never an arbitrary-height proof.

Two regression checks guard the model.  It reconstructs the certified
`c=2,h=4,k=1` obstruction

```text
0110 / 0110
```

as `SAT`, while the already exhaustively enumerated low four-color heights are
`UNSAT`.  Every future SAT output still goes through the separate C++ verifier.
