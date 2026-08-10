# First-exhaustion Tq sibling checker: implementation design

## Claim boundary

This checker concerns only the `z=0 -> z=1` exhausting entrances into a
`Tq` terminal that have another legal source at the parent.  The already
verified numerical bridge has:

- 71 canonical `Tq` terminals;
- 624 labeled reverse candidates;
- 418 canonical parent states and 429 canonical parent-terminal edges;
- 6 unique-source parents; and
- 412 sibling parents carried by 423 canonical edges.

A census of committed next runs is not a census of complete residual words.
Accordingly, completing the proposed first implementation must not by itself
claim that the 412-parent entry family is eliminated, and says nothing about
all balanced height-seven layouts.

## Two exact edge types

For an exhausting edge let the bad source be `a_s`, its isolated final color
be `b`, and let the other three current sources have the common `Tq` top
color `q`.  The source test of the bad edge is

```text
d(P) + s e_a = d(D) - (7-s) e_b.
```

It has exactly the two non-`q`, non-`b` positive coordinates.  The 423
sibling edges split into two useful, independently checkable types:

- `a != q`: 270 edges.  Here `a` is one of those two positive colors in
  `D`; sibling legality forces `d_a(P) <= 0`, while `d_b(P) = 0`.  All three
  `q` columns are legal, so the parent has four legal physical sources.
- `a == q`: 153 edges.  All four current tops are `q`; there are 137 edges
  with four legal sources, 14 with three, and 2 with two.

The corresponding sibling-parent state distribution is one state with two
legal sources, twelve with three, and 399 with four.  State and edge
distributions must be reported separately.

## The smallest sound decoration

The bad column has no undecided future: its entire hidden prefix is
`b^(7-s)`.  A decoration must commit the actual next run of **all three**
remaining `q` columns, including a currently illegal column.  Recording only
the currently legal siblings is enough to discuss the first move, but is not
enough to replay a continuation on one fixed layout.

For a `q` column of current cap `r`, a card `(x,u)` has

```text
x != q,  r < u <= 7.
```

It forces `x^(u-r)` at the top of that column's hidden prefix.  If `u < 7`,
the next lower cell must differ from `x`, so that `u` is the exact endpoint
rather than merely a lower bound.

The raw, pre-balance sizes are:

| object | count |
|---|---:|
| individual cards of currently legal siblings | 18,177 |
| joint cards of currently legal siblings | 1,220,361 |
| joint cards of all three fixed `q` columns | 1,256,148 |

The last count is the preferred production universe.

## Exact color-feasibility without residual-word expansion

After subtracting the fixed bad tail and the three forced card runs from
`7-F_c(P)`, let `m_i=7-u_i` be the uncommitted length of `q` column `i`.
For each `m_i>0`, reserve its top uncommitted cell and forbid the card color
there.  There are at most three such distinguished cells.  Enumerate their
allowed colors (at most `3^3=27` assignments); all remaining cells are
unrestricted labeled positions.  If their remaining color multiplicities
are `n_c`, that assignment contributes

```text
N! / product_c(n_c!)
```

complete residual words, where `N=sum_c n_c`.  This gives both an exact
existence test and an exact residual-word weight for every one-layer
decoration, without enumerating the words themselves.

A read-only prototype, not yet an independently certified project constant,
gave:

| prototype quantity | count |
|---|---:|
| color-feasible all-`q` decorations | 403,685 |
| edge-summed complete residual words represented | 6,131,033,832 |
| smallest / largest per-edge residual count | 924 / 344,323,980 |

The 6.13-billion figure is why the same-z app's explicit residual loop should
not be copied into this checker.

## First-layer classifications

For each currently legal sibling card, replay its exact live or exhausting
debt update and retest the bad source with the correct host threshold:

- `two_exhaustion`: the sibling exhausts and the bad source is then legal at
  `z=1`; the two fixed events reach `z=2`.
- `live_bad_persistent`: the sibling moves live and the bad source remains
  legal at `z=0`.  Taking it next reaches a nonterminal `z=1` checkpoint, not
  the goal.  This is only a handoff, not an elimination proof.
- `obstruction`: no currently legal sibling has either property.

With precedence `two_exhaustion > live_bad_persistent > obstruction`, the
same provisional prototype produced:

| class | feasible decorations | represented residual words |
|---|---:|---:|
| two-exhaustion | 70,633 | 8,629,839 |
| live handoff | 254,899 | 3,235,811,235 |
| obstruction | 78,153 | 2,886,592,758 |

These figures are reconnaissance only until a separate checker derives them.
In particular, the large obstruction class prevents a first-layer
persistence census from supporting `ENTRY_FAMILY_ELIMINATED`.

## Minimal production interface

The first executable should have one fixed scope rather than a mode whose
meaning can drift:

```text
water-c4-h7-tq-exhaust-siblings
    --output-dir DIR
    [--limit N]
    [--self-test]
```

`--limit` counts raw all-three-`q` decorations in deterministic
edge/card order.  A bare `--self-test` may run structural assertions and a
small bounded prefix without writing output.

The first report should use:

```text
coverage_scope = "first_exhaustion_tq_sibling_next_run_forks"
limit_unit = "raw_all_q_next_run_decorations"
```

and contain at least:

- the 71/624/418/429/6/412/423 bridge census;
- parent and edge legal-source distributions;
- action uniqueness and isolated-final-color checks;
- 18,177 / 1,220,361 / 1,256,148 raw counts;
- feasible/infeasible decoration counts and residual-word weights;
- the three first-layer classifications, split by `a==q` and `a!=q`;
- per-edge counts plus replayable samples; and
- explicit coverage flags.

Required flags are:

```text
next_run_universe_complete
full_residual_word_coverage = false
entry_family_eliminated = false
full_layout_coverage = false
```

Suggested statuses are:

- `NEXT_RUN_CENSUS_COMPLETE`: the bounded mathematical object above is fully
  checked;
- `REDUCTION_CERTIFIED`: reserved for a later theorem whose targets and
  dependencies are explicitly named;
- `ENTRY_FAMILY_ELIMINATED`: reserved for a genuine universal fixed-future
  argument;
- `INCOMPLETE`: any limited run.

`verified=true` means only that the declared `coverage_scope` is complete.
The strict validator must reject `ENTRY_FAMILY_ELIMINATED` while
`full_residual_word_coverage=false` unless the report names and verifies a
separate universal strategy certificate.

## Minimal code reuse

Do not copy the complete same-z application.  Once the bridge mathematics is
stable, move only these family-neutral pieces into an app-internal header:

- `Bucket`, `State`, canonicalization, consistency, and source legality;
- fixed-run card generation and color-count keys; and
- the fixed-chain checkpoint recursion used for bounded differential samples.

Keep terminal/edge enumeration, classification, report writing, and all
expected constants family-specific.  The same-z executable and its
independent report checker must remain regression-identical after the
extraction.

## Independent checker

`tests/check_c4_h7_tq_exhaust_siblings.py` must not import either production
app or `scripts/c4_h7_macro_recon.py`.  It should independently:

1. reconstruct the 71 terminals and the 624/418/429 bridge;
2. replay all 429 actions and the isolated-final-color identity;
3. reproduce the unique/sibling split and both legal-source distributions;
4. enumerate all-three-`q` cards in a different loop order;
5. test feasibility with a small max-flow or explicit distinguished-cell
   assignment, rather than production's implementation;
6. replay all report samples with an independent debt recursion; and
7. run bounded production differentials and schema-negative tests.

The artifact validator should additionally enforce status/coverage
compatibility and reject missing per-edge coverage.

## GitHub Actions shape

Use two jobs initially:

1. `build-and-audit`: GCC Release build, focused CTest, bare self-test,
   bounded production/independent differential, and sanitizer or Clang smoke.
2. `next-run-census`: complete 1,256,148-decoration census, independent report
   validation, deterministic hashes, and artifact upload.

Do not add a job that loops over the 6.13-billion residual words.  Add a
separate proof job only after the anchor/all-`q` case split has a stable
universal strategy or a proof-producing symbolic encoding.  The workflow
must fail if a next-run-only report claims entry-family elimination.

## Mathematical next decision

The 270 `a!=q` edges have two nonpositive anchors (`a` and the isolated
color `b`) and all three `q` siblings legal.  Advancing columns through the
two-anchor corridor can end at a two-anchor, all-top state, which has the
shape of the unresolved `D2` family.  The 153 `a==q` edges form a separate
all-`q` cap-inequality case.  The next proof step should therefore decide
whether the bridge is reduced to a named `D2` subfamily or eliminated
directly; the checker should not silently treat that reduction as a win.
