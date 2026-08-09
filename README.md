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

### Bounded multi-stack interpretation

The puzzle is also a finite-state system of bounded stacks. Each column is a
capacity-`h` stack over a color alphabet. A move pops a maximal compatible
top run (truncated only by destination capacity) from one stack and pushes it
onto another; a completed monochrome stack is disabled. Moves whose source and
destination stack sets are disjoint commute. This makes the model a compact
case study for reachability, symmetry reduction, and partial-order reduction.
It is a finite, bounded relative of the
[multi-stack reachability models](https://doi.org/10.1016/j.ic.2020.104588)
used to study concurrent recursive programs; exploiting commuting operations
is standard in
[dynamic partial-order reduction](https://doi.org/10.1145/1040305.1040315).

The current top-border oracle goes further than merely running independent
search workers: it replaces concrete buffer-management interleavings by an
irreversible border-removal DAG. A concurrency/formal-methods treatment would
need to state that abstraction for a general class of bounded colored
multi-stack systems and compare it with standard partial-order reduction; the
fact that the implementation uses stacks or parallel GitHub jobs is not by
itself a new concurrency result.

### Balanced bottom-layer monotonicity

Let `I` have height `h`, with one full column per color and exactly `h` units
of every color. Form `I+` at height `h+1` by inserting one new bottom unit in
every full column, using every color exactly once; the old columns remain
unchanged above the new layer. Then

```text
I+ solvable  =>  I solvable,
I  NO        =>  I+ NO.
```

To project a border-removal sequence of `I+`, delete the removals of the new
bottom borders. Before any retained removal, let `r` be the number of columns
whose old borders are all gone but whose new bottom border remains. The
projected state of `I` has exactly `r` more monochrome bins. In the balanced
model each color has at most one columnful of remaining material, so its
buffer demand `M_c` is either zero or one. An old deficient color can cease to
be deficient in `I+` only if it is hosted by one of those `r` pending columns;
one pending column hosts only one color. Therefore

```text
buffers_needed(I) <= buffers_needed(I+) + r
monochrome_bins(I)  = monochrome_bins(I+) + r.
```

Every retained removal that is legal in `I+` is consequently legal in `I`.
The projected sequence removes all old borders, proving the implication. By
induction, balanced bottom layers can be added repeatedly. This closure uses
the condition that color multiplicity equals capacity; it is not asserted for
arbitrary unbalanced stack systems.

### Balanced parameter frontier

Write `E(c,h,k)` when at least one balanced NO instance exists with `c`
colors/full columns, height `h`, and `k` initially empty columns. Besides the
height implication above, existence is monotone in the number of colors:

```text
E(c,h,k) => E(c+1,h,k).
```

To construct the larger instance, add a new full monochrome column in a new
color. It is already completed and locked, so it cannot participate in a move;
deleting it projects any solution back to the original instance. Consequently,
for fixed `k`, the NO-existence region is upward closed in `(c,h)`, while the
universal-YES region is downward closed. Adding empty columns has the opposite
resource direction: an instance solvable with `k` empty columns remains
solvable when more empty columns are supplied.

For one empty column, complete scans give the three minimal NO parameter pairs

```text
(c,h) = (2,4), (3,3), (4,2).
```

The adjacent maximal safe pairs `(2,3)` and `(3,2)` have respectively 7 and 5
exact symmetry classes, all YES. The three obstruction scans contain 1 NO
among 23 classes, 7 NO among 55 classes, and 1 NO among 12 classes. Together
with parameter monotonicity, this gives the complete existence classification

```text
E(c,h,1)  <=>  c >= 2 and h >= 2 and c + h >= 6.
```

The three minimal witnesses and independently checked certificates are stored
under `experiments/`.

## What is implemented

- `water-oracle`: an exact top-border dynamic program based on Ito et al.
- `water-verify`: an independently coded verifier for compact NO certificates.
- `water-hunter`: a seeded, sharded mutation/hill-climbing search over valid
  arrangements, with configurable height, colors, and empty columns.
- `water-neighborhood`: exact, symmetry-deduplicated scanning of the committed
  seeds and their swap neighborhoods; deeper radii expand only verified NO
  frontiers and can retain a deterministic bounded frontier.
- `water-minimize`: a NO-preserving local search for simpler counterexamples.
- `water-skeleton`: constrained enumeration of positive run lengths for a
  fixed run-color skeleton, preserving both every column total and every color
  total.
- `water-universe`: complete low-height enumeration modulo all color-name and
  full-column permutations, followed by exact oracle classification.
- `water-policy-learn`: exact safe-action extraction and thin-layer scene
  conflict discovery for a candidate finite policy.
- `water-policy-control`: randomized synthesis of one shared thin-layer
  controller over an exact catalog, checking only the states induced by that
  controller.
- `water-unit-scenes`: expansion of controlled border choices into one-item
  moves, comparing finite top-item windows, top color-run windows, and
  color-run windows augmented by bounded Ito buffer-demand counters.
- `water-depth-witness`: independent verification of a scalable pair of tight
  states with identical bounded observations and disjoint safe actions.
- `water-continuous-control`: continuous realization of controlled top-border
  paths using real forced maximal bulk moves, without rebuilding a canonical
  physical state.
- `water-counter-game`: exact finite-height online-game analysis of the
  remaining four-color/two-empty macro question, with either bare counter
  observations or every current next color run committed before source choice.
- `scripts/smt_counterexample.py`: joint fixed-height SMT search over both the
  unknown balanced arrangement and its complete exact top-border winning DAG;
  SAT candidates are checked by the independent C++ certificate verifier.
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

Learn candidate thin-layer rules from exact safe actions:

```bash
./build/water-policy-learn \
  --colors 4 --height 9 --empty 2 \
  --depth 3 --samples 1000 --seed 1 \
  --out out/policy-d3
```

Equal scene signatures are merged by intersecting their exact safe next-border
choices. An empty intersection is a concrete conflict showing that the current
observation depth or signature is insufficient. A nonempty intersection is
only a candidate rule until it is proved for every possible hidden suffix. See
[the thin-layer policy design](docs/thin-layer-policy-learning.md).

For the focused four-color/two-empty proof frontier, stop when two original
columns have no borders and mutate only the hidden tails:

```bash
./build/water-policy-learn \
  --colors 4 --height 12 --empty 2 --depth 3 \
  --goal-exhausted 2 --samples 40 \
  --tail-mutations 3 --tail-swaps 3 \
  --out out/frontier-h12
```

The `Attack c4 k2 frontier policy` workflow runs this experiment across
several heights and performs a final cross-height signature merge.

The global merge can report conflicts that a deterministic controller never
needs to visit. Test that stronger, controlled-reachability question against
the merged catalog with:

```bash
./build/water-policy-control \
  --catalog out/all-heights/instances.tsv \
  --conflicts out/all-heights/conflicts.tsv \
  --depth 3 --goal-exhausted 2 \
  --restarts 256 --repair-passes 128 --seed 1 \
  --out out/controlled-policy
```

`success=true` supplies one deterministic action table that carries every
catalog instance to the two-exhausted-column frontier. It is still a finite
sample result; `success=false` only exhausts the randomized restart budget.
The `Synthesize c4 k2 controlled policy` workflow repeats the search with
independent seeds and merges their reports.

A controller can instead use a simple finite default rule and store only its
exceptions:

```bash
./build/water-policy-control \
  --catalog out/all-heights/instances.tsv \
  --conflicts out/all-heights/conflicts.tsv \
  --depth 3 --goal-exhausted 2 \
  --default-heuristic last \
  --restarts 64 --repair-passes 128 --seed 1 \
  --out out/compressed-policy
```

Here `last` means the last currently legal source in the canonical column
order. On the 3,501-instance catalog, two successful attempts each need 114
sampled exceptions instead of a rule for every observed signature; their union
contains 119. The `Compress c4 k2 controlled policy` workflow compares several
such defaults and measures whether their exception sets remain stable across
independent seeds.

Expand those macro choices into one-item moves and compare observation windows:

```bash
./build/water-unit-scenes \
  --catalog out/all-heights/instances.tsv \
  --policy out/compressed-0/policy.tsv \
  --policy out/compressed-1/policy.tsv \
  --goal-exhausted 2 \
  --out out/unit-scenes
```

The unit-scene report intersects safe next moves for equal labeled-stack
signatures at item windows 2 through 6, run windows 1 through 4, and the same
run windows with buffer-demand fields. Each border action is physically valid
and is expanded completely, but the next macro state is rebuilt in canonical
tight form. Thus this diagnoses a candidate small finite program while explicitly
counting the still-unproved connections between macro traces. See [the
thin-layer policy design](docs/thin-layer-policy-learning.md).

On the combined 4,301-instance catalog, sampled through height 46, the two
compressed controllers produce 59, 35, 6, 2, and 0 conflicts at visible-item
depths 2 through 6. Thus the sampled minimum is `D = 6`. A scalable committed
witness pair additionally proves that no height-independent item depth can
choose a safe action for every possible frontier-winning tight configuration.
A carefully controlled strategy might still avoid the obstruction family; see
[the fixed-depth obstruction and its exact scope](docs/no-fixed-item-depth.md).

A follow-up attack replaces item depth by monochrome-run depth and carries the
bounded Ito buffer-demand state into every unit scene. Across the same 4,301
instances, two visible runs without counters still have 82 conflicts, while
two visible runs plus demand counters have **zero sampled conflicts** over
241,349 macro checkpoints and 1,271,582 unit moves. This is a finite-catalog
candidate controller, not yet a symbolic all-height closure proof. See
[`31333399467`](https://github.com/lieoric/water-sort-counterexample/actions/runs/31333399467).

The remaining physical-realization gap is handled separately by
`water-continuous-control`. It keeps the actually reached tight configuration,
implements Ito's constructive border-removal and retightening steps with
forced maximal pours, and refuses to source a locked full monochrome stack.
It then removes every remaining border after the two-exhausted-column frontier
and verifies the full sorted goal. See [the continuous realization
argument](docs/continuous-realization.md).

The exact 4,301-instance catalog was replayed from its real physical initial
states under both compressed controllers: **8,602/8,602** runs reached the
fully sorted goal after 284,154 border removals and 389,773 forced maximal
bulk moves, with zero construction gaps and zero locked-source violations.
This validates physical realization on the finite catalog; it is not the
still-missing arbitrary-height macro-policy proof. See
[`31334595589`](https://github.com/lieoric/water-sort-counterexample/actions/runs/31334595589).

The remaining all-height question is also attacked as a bounded counter game.
Bare `Q=(z,a_i,s_i,d_c)` observations first lose at height 5, proving that
those counters alone cannot support one online controller. If every column's
next maximal color run is committed and visible before source choice, the
exact game has no losing initial observation through height 6. At height 6
this closes 23,460,258 reachable observations; 231,105 losing local states are
all avoidable from all 361,334 initial observations. These are finite-height
policy results, not a Water NO certificate or an induction over arbitrary
heights.
See [the bounded counter-game definition and results](docs/counter-game.md).

A complementary [joint SMT encoding](docs/smt-search.md) searches a complete
symmetry-reduced covering at one fixed height without first enumerating
arrangements.
It exactly reconstructs the known `c=2,h=4,k=1` NO witness and returns UNSAT
on the already-known low four-color safe cases. Its sharded GitHub workflow is
intended to attack height 6 next; finite UNSAT runs have no retained solver
proof object and do not establish the arbitrary-height theorem.

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

The default search remains 5x16 with two empty columns. Use `--height`,
`--colors`, and `--empty` to explore other parameter points, including the
open three-empty-column search at `--empty 3`.

Mutations swap two differently colored cells, so every candidate always has
exactly 16 units of each color. The heuristic minimizes the number of legal
border-removal sequences, capped for speed. A count of zero is exact; all
positive capped counts are only search fitness.

The `Hunt counterexample` GitHub Actions workflow starts eight independent
shards and uploads each shard's best instance and report. If a shard finds a
NO instance, it also uploads the instance and its certificate.

## Counterexample experiments

Five independently certified, pairwise inequivalent 5x16 counterexamples are
committed under `counterexamples/`. Their common terminal signature is:

```text
available buffers = 2
deficient colors  = 2
hosted colors     = 3
buffers needed after any source choice = 3,3,3,3,3
```

Analyze one directly:

```bash
./build/water-oracle \
  --input counterexamples/ce-000.txt \
  --analyze
```

Scan the seeds and every one-swap neighbor with three empty columns:

```bash
./build/water-neighborhood \
  --seed-dir counterexamples \
  --empty 3 \
  --shard 0 --shards 16 \
  --out out/threshold-0
```

Expand a bounded two-empty NO frontier to swap radius two:

```bash
./build/water-neighborhood \
  --seed-dir counterexamples \
  --empty 2 \
  --radius 2 \
  --frontier-limit 50 \
  --out out/family-radius-2
```

For radii greater than one, use a single process. A layer is classified
exactly, then at most `frontier-limit` NO representatives with the smallest
stable fingerprints are expanded into the next layer. Thus the reported
classes are exact for the explored frontier, but a bounded radius-two run is
not an exhaustive radius-two ball around every radius-one NO class.

Search for a simpler representative while preserving exact unsolvability:

```bash
./build/water-minimize \
  --input counterexamples/ce-000.txt \
  --seconds 900 \
  --out out/minimized
```

The current smallest experimental representative has 15 borders and no
singleton runs. Enumerate alternative positive run lengths for exactly that
color-block order:

```bash
./build/water-skeleton \
  --input experiments/minimized-15b.txt \
  --height 16 \
  --empty 2 \
  --candidate-limit 10000 \
  --out out/skeleton-16
```

Changing `--height` keeps the run-color order but solves new integer length
constraints, making it possible to test whether the obstruction persists at
other tube heights.

### Complete balanced-universe search

To scan any balanced parameter point exactly, supply its colors, height, and
empty-column count to the orderly enumerator:

```bash
./build/water-universe \
  --height 5 \
  --colors 4 \
  --empty 2 \
  --out out/universe-c4-h5-k2
```

Each color occurs exactly `height` times. The enumerator uses a
restricted-growth color order and sorted columns, then performs an exact
canonicality check. It writes one oracle result per equivalence class under
color renaming and full-column permutation. An unlimited run has
`stopped_early=false` in `report.json`; this flag must be checked before a
zero-counterexample result is treated as exhaustive.

For five colors and two empty columns, the complete scans establish that
height 1 has one solvable class, height 2 has
20 solvable classes, height 3 has 12,304 solvable classes, and height 4 has
21,383,163 solvable classes. There are no NO classes at any of these heights.
Four independently certified height-5 NO instances are committed under
`experiments/`, so the global minimum height is exactly

```text
h_min = 5.
```

Balanced bottom-layer monotonicity lifts a height-5 witness to every greater
height. Hence the complete existence classification is

```text
NO instances exist exactly when h >= 5.
```

Color monotonicity also turns the complete `(c,h,k)=(5,4,2)` YES result into
the safe rectangle `c<=5`, `h<=4`, `k=2`. A second complete scan at
`(c,h,k)=(4,5,2)` examined 72,345,636 orderly representations and classified
all 20,434,876 exact symmetry classes as YES. See
[GitHub Actions run 31322659737](https://github.com/lieoric/water-sort-counterexample/actions/runs/31322659737).

Thus the current two-empty safe region includes

```text
(c <= 5 and h <= 4) or (c <= 4 and h <= 5).
```

Together with a certified NO witness at `(5,5,2)`, these two safe rectangles
prove that `(5,5)` is a minimal NO-existence parameter pair for `k=2`.

The height-4 run examined 113,291,534 orderly representations before exact
symmetry canonicalization. See
[GitHub Actions run 31315095516](https://github.com/lieoric/water-sort-counterexample/actions/runs/31315095516).

For the committed 20-run skeleton, exhaustive enumeration finds no NO length
assignment at heights 5, 6, or 7, but finds exactly three NO symmetry classes
among 9,648 classes at height 8. Those three instances and their certificates
are committed under `experiments/`. This threshold is exact for the fixed
run-color skeleton only.

The `Scan known counterexample family` workflow distributes the exact
one-swap scan over 16 shards and merges the symmetry classes. The `Minimize
verified counterexamples` workflow runs four independent restarts from each
committed seed. `Expand two-empty counterexample family` performs bounded
multi-radius NO-frontier expansion, and `Scan minimized run skeleton`
distributes run-length assignments over 16 shards. A scan that finds no
three-empty-column counterexample is
evidence about this known family only; it is not a proof that every 5x16
instance is solvable with three empty columns.

`Scan complete balanced universe` accepts `colors`, `height`, `empty_columns`,
and a selectable shard count. It distributes the orderly search tree and
fails the merge if any shard reaches its candidate limit, so a successful
merged artifact is a complete classification of that parameter point.

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
- A `frontier-limit` makes deeper neighborhood expansion deliberately partial;
  all reported classifications are exact, but unexpanded NO parents can have
  additional unseen descendants.
- A run-skeleton scan varies lengths only. It says nothing about other
  run-color orders unless they are separately supplied as skeletons.
- Balanced bottom-layer monotonicity is a statement about the balanced model:
  one full column per color, color multiplicity equal to capacity, and one
  permutation of the colors added per new layer. It does not automatically
  cover unequal color totals or arbitrary padding blocks.
