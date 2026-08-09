# Water Sort counterexample search

This repository searches for a counterexample to the claim that **every**
5-color, height-16 Water Sort instance with five full columns and two empty
columns is solvable.

Each color occurs exactly 16 times. A move pours the largest possible amount
of the source's top run into an empty destination or one with the same top
color:

```text
quantity = min(source_top_run, destination_free_space)
```

A full monochrome column is completed and locked: it cannot be used as a
source again. In this balanced setting that restriction does not change
solvability. A completed column contains every unit of its color; pouring it
into an empty column only exchanges the roles of the completed and empty
columns, which are unlabeled.

## What is implemented

- `water-oracle`: an exact top-border dynamic program based on Ito et al.
- `water-verify`: an independently coded verifier for compact NO certificates.
- `water-hunter`: a seeded, sharded mutation/hill-climbing search over valid
  5x16 arrangements.
- A literal full-state Water BFS with forced bulk moves and locked completed
  columns, used only as a small-instance reference implementation.
- Exhaustive cross-checks over 1,796 small initial arrangements, plus the
  published `h=3, k=2, n=9` no-instance from Ito et al., Figure 10(a).

## Why the oracle is exact

For each original full column, retain only its current highest original color
border. Borders disappear from top to bottom, so the state graph is a DAG.
For a top-border table `tau`, the implementation computes the paper's
`F_c(tau)`, `G_c(tau)`, and source-specific `M_c^b(tau)` capacity condition.
A transition removes exactly one current border when

```text
sum_c M_c^b(tau) <= number of monochrome bins.
```

Theorem 3 and Corollary 4 of Ito et al. equate reachability in this graph with
Water Sort solvability. For 5x16, there are at most

```text
16^5 = 1,048,576
```

top-border states. See [Sorting Balls and Water: Equivalence and Computational
Complexity](https://arxiv.org/abs/2202.09495) and the journal
[publication](https://doi.org/10.1016/j.tcs.2023.114158).

## Build and test

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel
ctest --test-dir build --output-on-failure
```

The instance format is deliberately plain text. Columns are written
**bottom-to-top**:

```text
height=16
colors=5
empty=2
column=0123401234012340
# four more column= lines
```

Run the oracle:

```bash
./build/water-oracle --input examples/5x16.txt --count 10000
```

For an unsolvable instance, write and independently check a certificate:

```bash
./build/water-oracle \
  --input candidate.txt \
  --certificate candidate.wscert

./build/water-verify \
  --input candidate.txt \
  --certificate candidate.wscert
```

The binary certificate is a bitset representing a transition-closed invariant:
it contains the initial top-border state, excludes the goal, and contains every
legal successor of every marked state. Its worst-case payload for 5x16 is only
128 KiB.

## Hunter

```bash
./build/water-hunter \
  --seed 12345 \
  --shard 0 --shards 8 \
  --seconds 900 \
  --solution-cap 10000 \
  --out out/shard-0
```

Mutations swap two differently colored cells, so every candidate always has
exactly 16 units of each color. The heuristic minimizes the number of legal
border-removal sequences, capped for speed. A count of zero is exact; all
positive capped counts are only search fitness.

The `Hunt counterexample` GitHub Actions workflow starts eight independent
shards and uploads each shard's best instance and report. If a shard finds a
NO instance, it also uploads the instance and its certificate.

## Important caveats

- Finding one verified NO instance disproves universal solvability with two
  empty columns. Failing to find one proves nothing.
- The full Water BFS is intentionally limited to small instances; the
  top-border oracle is the scalable exact decision procedure.
- A NO claim depends on the cited top-border theorem. The separate certificate
  verifier reduces implementation risk by rebuilding the transition relation
  rather than calling the oracle.
- The hunter is heuristic and does not enumerate the astronomical space of
  5x16 initial arrangements.
