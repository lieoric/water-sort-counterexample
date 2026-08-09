# Bounded counter game for four colors and two empty columns

`apps/counter_game.cpp` is a finite-height research tool for the remaining
macro-level question.  It supports two observation games:

- `q`: the controller observes only a counter state `Q`, chooses a source, and
  only then is told the next hidden color run in that source;
- `next-run`: before choosing, the controller sees the already committed next
  maximal run (color and length) of every active source.  After the move, the
  environment commits only the newly exposed third run of the chosen source.

It does **not** claim an arbitrary-height theorem.  A losing state does not, by
itself, describe an unsolvable Water Sort instance; it can instead show that
the observation `Q` is too weak for one online policy to handle every hidden
completion.

## State and legal actions

There are four balanced colors, four initially full original columns, two
initially empty columns, and capacity `h`.  At an idle tight checkpoint let

```text
Q = (z, (a_i,s_i) for active original columns i, (d_c) for colors c)
```

where:

- `z` is the number of exhausted original columns;
- `a_i` is the exposed top color of active original column `i`;
- `s_i=h-tau_i` is the number of original items already above its current
  border;
- `d_c=F_c-G_c` is the Ito capacity deficit.

The number of required monochrome hosts after choosing source `i` is

```text
N_i = sum_c 1[d_c + 1[c=a_i] s_i > 0].
```

The source is legal exactly when `N_i <= 2+z`.  Once `z>=2`, the right-hand
side is at least four, so every remaining source is legal and the state is a
goal of this bounded game.

## Exact algebraic consistency test

For each color recover its exposed count as

```text
F_c = d_c + sum_{i:a_i=c} s_i
```

and its remaining hidden count as `R_c=h-F_c`.  The enumerator retains exactly
the projected states satisfying all of the following constraints:

1. `number of active columns + z = 4`;
2. every active `s_i` satisfies `1 <= s_i < h`;
3. `count(i:a_i=c) <= F_c <= h` for every color;
4. `sum_c d_c = z*h` and therefore
   `sum_c F_c = z*h + sum_i s_i`;
5. every active hidden suffix is nonempty and its first color differs from
   `a_i`.

The last condition is checked by the four Hall inequalities

```text
count(i:a_i=c) <= sum_{x != c} R_x.
```

They are sufficient here.  A set of columns sharing forbidden color `c` can
use every remaining color except `c`; a set containing two different
forbidden colors has all four colors in the union of its allowed sets.  After
one legal first hidden item is assigned to every active column, all residual
items can occupy arbitrary residual positions.  The analogous exposed-word
condition needs only one mandatory `a_i` item per active column.

Colors and original-column labels are quotiented out.  A canonical state is a
sorted list of four color buckets, each containing `d_c` and the multiset of
the `s_i` values topped by that color.

## Environment transition

After the controller chooses source `i`, the environment reveals a color
`b != a_i` and a positive maximal run length `r`.

If `s_i+r<h`, the source remains active and

```text
s_i'       = s_i+r
d_{a_i}'   = d_{a_i}+s_i
d_b'       = d_b-s_i.
```

If `r=h-s_i`, the source is exhausted and

```text
z'         = z+1
d_{a_i}'   = d_{a_i}+s_i
d_b'       = d_b+(h-s_i).
```

A reveal is admitted only if the successor passes the same algebraic
consistency test.  This is equivalent to requiring enough remaining `b`
items for the revealed run and, when the source stays active, a different
color below that maximal run.

Every transition strictly decreases

```text
sum_active_i (h-s_i),
```

so the finite graph is acyclic.  Retrograde evaluation marks `Q` winning iff
there is a legal source for which **every** feasible environment reveal is
winning.

## Running it

The source is standalone C++17.  Once wired into the build as
`water-counter-game`, a typical run is:

```text
water-counter-game \
  --height 7 \
  --report out/counter-h7/report.json \
  --witness out/counter-h7/losing.txt \
  --self-test
```

Enumeration is intentionally guarded by `--max-states` and
`--max-candidates`.  Raise those limits explicitly for a larger run.  The JSON
report records all limits, state counts, initial projections, wins and losses.
The text witness prints the smallest losing algebraic state and, when one
exists, the smallest losing initial projection.

To run the stronger observation in which all current next runs are committed
before source choice:

```text
water-counter-game \
  --height 5 \
  --observation next-run \
  --report out/counter-next-h5/report.json \
  --witness out/counter-next-h5/losing.txt \
  --self-test
```

## Current local finite-height results

The following complete runs used the default limits and the implementation in
this repository:

| `h` | consistent `Q` | winning `Q` | losing `Q` | initial `Q` | losing initial `Q` |
|---:|---:|---:|---:|---:|---:|
| 2 | 9 | 9 | 0 | 5 | 0 |
| 3 | 247 | 243 | 4 | 25 | 0 |
| 4 | 2,316 | 2,137 | 179 | 80 | 0 |
| 5 | 12,331 | 10,564 | 1,767 | 182 | 2 |
| 6 | 47,200 | 37,257 | 9,943 | 376 | 14 |
| 7 | 144,919 | 105,044 | 39,875 | 668 | 57 |
| 8 | 380,270 | 254,001 | 126,269 | 1,130 | 152 |
| 9 | 886,565 | 546,422 | 340,143 | 1,765 | 336 |

The first losing initial projection appears at `h=5`.  One canonical form has
four active top runs of length one, split `2+2` between two top colors.  This
is a rigorous counterexample to the proposed **Q-only online controller**: for
each source orbit the hidden environment has a response that remains losing.
It is not a Water Sort NO certificate, because a solver given the complete
initial columns may choose a source using information that `Q` intentionally
hides.

## Committed next-run comparison

The `next-run` mode uses a larger state

```text
(Q, (b_i,r_i) for every active source i),
```

where the hidden suffix of source `i` is committed to start with exactly
`r_i` copies of `b_i != a_i`.  If that run does not exhaust the source, the
item below it must differ from `b_i`.  The consistency check first subtracts
all committed runs from the remaining color counts, then applies the same Hall
test to the still-hidden third runs.  Thus the environment cannot change a
next run after seeing which source the controller selected.

All algebraically possible initial next-run observations are enumerated.  The
search then closes them under every legal source and every feasible newly
revealed third run.  Retrograde evaluation covers this entire reachable
subgraph; it does not spend memory on algebraically consistent next-run states
that no initial observation can reach.

| `h` | initial next-run observations | reachable observations | losing reachable | losing initial |
|---:|---:|---:|---:|---:|
| 2 | 9 | 15 | 0 | 0 |
| 3 | 458 | 3,188 | 7 | 0 |
| 4 | 8,367 | 152,079 | 474 | 0 |
| 5 | 68,396 | 2,545,120 | 16,026 | 0 |
| 6 | 361,334 | 23,460,258 | 231,105 | 0 |

The losing reachable observations are real local obstructions, but the
retrograde strategy avoids them from every enumerated initial observation.
In particular, committing all four next runs removes the `h=5` obstruction of
the `q`-only mode.  A complete optimized `h=5` run takes about 75 seconds and
258 MB in the current WSL/GCC build; `h=4` takes about three seconds and 36 MB.
The complete `h=6` GitHub Actions run took about six minutes including build
and tests.

These are complete finite-height results only.  They neither prove that the
same controller wins at `h=6` and beyond nor establish an induction that
collapses arbitrary run lengths to the tested state space.

## What this settles, and what it does not

For each reported `q` height, the game enumeration and retrograde result are
complete under the stated algebraic projection.  In particular, `h<=4` admits
a universal online `Q` policy and `h=5` does not.  For `next-run`, the reachable
closure from every initial observation is complete through `h=5`.

This rules out using bare `Q=(z,a_i,s_i,d_c)` as the state of an
arbitrary-height online proof.  It does not rule out:

- a strategy that inspects the known hidden suffixes of the input instance;
- a stronger finite abstraction that remembers additional run information;
- a global existence proof whose source choices depend on the whole instance;
- universal solvability of balanced four-color, two-empty Water Sort itself.

Likewise, the `next-run` successes through `h=5` are evidence for a stronger
controller, not an infinite-height proof.  A losing online game would still
not automatically be a Water Sort NO: the environment is allowed to choose a
new deeper run after each action, whereas an ordinary solver receives one
fully fixed instance and may inspect all of its suffixes before moving.
