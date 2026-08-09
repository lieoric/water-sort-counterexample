# Three balanced colors with two empty columns

This note proves a universal result for the balanced Water Sort model with
three colors, three initially full columns, two initially empty columns, and
column capacity `h`:

> **Theorem.** Every such instance is solvable for `h <= 8`.

The argument is analytic.  The complete height-7 computation recorded in the
repository is an independent check, not a premise of the proof.  No claim is
made here for `h >= 9`.

## 1. Model and top-border state

Each color occurs exactly `h` times.  A Water move transfers the forced
maximal top run to an empty column or to a column with the same top color,
subject to capacity.  A completed full monochrome column is locked.

The lock does not change solvability in this balanced setting.  A full
monochrome column contains all `h` items of its color.  Its only possible
outgoing Water move transfers all `h` items to an empty column, merely
exchanging the names of a completed column and an empty column.  Such swaps
can be deleted, up to relabeling columns.  We may therefore use the standard
top-border characterization of Water Sort solvability.

Fix a top-border table.  Let `z` be the number of original columns whose
remaining border rank is zero.  For every active original column `i`, write

```text
a_i = color at its current top border,
s_i = h - tau_i,
```

where `tau_i` is the position of that border.  Thus `s_i` is the capacity of
the exposed host above that border.  For every color `c`, let

```text
F_c = number of exposed c-items,
G_c = sum_{i : a_i=c} s_i,
d_c = F_c - G_c.
```

If source `i` is selected, its own host is unavailable.  Its deficit for
color `c` is therefore

```text
Delta_i(c) = d_c + 1[c=a_i] s_i.
```

The number of monochrome columns required for that color is

```text
M_i(c) = max(0, ceil(Delta_i(c) / h)).
```

Because the instance contains only `h` items of each color, `F_c <= h`.
The usable host capacity subtracted from `F_c` is nonnegative, so
`Delta_i(c) <= h`.  Consequently

```text
M_i(c) = 1[Delta_i(c) > 0].
```

There are `2+z` available empty or monochrome columns.  Hence source `i` is
legal exactly when

```text
N_i := sum_c 1[d_c + 1[c=a_i] s_i > 0] <= 2+z.       (1)
```

Eliminating one border strictly decreases the total number of remaining
original borders.

## 2. Why only the first exhausted column matters

There are only three colors, and therefore `N_i <= 3` for every source.  As
soon as `z >= 1`, the right side of (1) is at least three.  Every remaining
border is then legal, so all remaining borders can be eliminated.

Thus, at every height, the whole problem reduces to this question:

> Can a legal border sequence exhaust the first original column?

This reduction is valid for arbitrary `h`; the height restriction enters
only when we prove that the first exhaustion can always be reached.

## 3. Exact characterization of local border deadlocks

Until the first exhaustion, `z=0`, all three original columns are active and

```text
sum_c d_c = 0.                                      (2)
```

Call such a state a *border deadlock* if all three sources violate (1).
This is a dead end in the top-border graph; it need not be a physical state
with no harmless Water move.

### Deadlock lemma

A `z=0` state is a border deadlock if and only if there are colors `q,p,r`
such that

```text
a_1 = a_2 = a_3 = q,
d_p > 0,
d_r > 0,
E := d_p+d_r = -d_q,
s_i > E for i=1,2,3.                                (3)
```

**Proof.** If source `i` is illegal, both colors other than `a_i` have
positive deficit and `d_{a_i}+s_i>0`.  If two sources had different top
colors, their two conditions together would make all three `d` values
positive, contradicting (2).  Thus every top color is a common color `q`.
The other deficits are positive; call their colors `p,r`.  Equation (2) gives
`d_q=-(d_p+d_r)=-E`, and illegality of each source gives `s_i>E`.
The converse follows immediately from (1).  QED.

This characterization also gives a sharp lower bound on the height of any
local deadlock.  In (3), `G_p=G_r=0`, so

```text
E = F_p+F_r.
```

Also `G_q=sum_i s_i`, and hence

```text
F_q = sum_i s_i - E <= h.
```

All quantities are integral, `E>=2`, and every `s_i>=E+1`.  Therefore

```text
h >= 3(E+1)-E = 2E+3 >= 7.                          (4)
```

It follows immediately that no local deadlock exists for `h<=6`.  At those
heights any legal choice can be repeated until one column is exhausted, so
every instance is solvable.

## 4. The height-7 and height-8 bypass

For `h` equal to 7 or 8, (4) forces `E=2`.  Since `d_p,d_r` are positive
integers,

```text
(d_q,d_p,d_r) = (-2,1,1)                            (5)
```

at every deadlock.

### Two-step bypass lemma

Let a legal border elimination `P --i--> D` lead from a `z=0` state to a
deadlock at height 7 or 8.  Then an alternative source `j != i` is legal in
`P`.  If eliminating `j` does not already exhaust it, source `i` is still
legal afterward; eliminating `i` then reaches a non-deadlock state with two
fewer remaining borders.

**Proof.** In `D` all top colors are `q`.  Immediately before the transition,
source `i` has some other top color `a` and exposed capacity `u>=1`; let `b`
be the third color.  The fixed transition of column `i` changes `a` to `q`.
For a non-exhausting border elimination the deficit update is

```text
d_a' = d_a+u,
d_q' = d_q-u.
```

Using (5), the deficits in `P` are therefore

```text
d_a=1-u,  d_b=1,  d_q=u-2.                          (6)
```

Choose either other column `j`.  Its top is still `q`, and its exposed
capacity `s_j` is unchanged from `D`.  By (3), `s_j>=3`.  If `j` is selected
in `P`, its three source deficits are

```text
q: u-2+s_j > 0,
a: 1-u <= 0,
b: 1 > 0.
```

Exactly two colors need hosts, so `j` is legal.  If its current border is its
last one, this move gives `z=1` and finishes the proof.  Otherwise its fixed
next color is some `c != q`.

After eliminating the border of `j`, the deficit update adds `s_j` to `d_q`
and subtracts `s_j` from `d_c`.  There are only two cases.

If `c=a`, the new deficits are

```text
d_q=u-2+s_j,  d_a=1-u-s_j,  d_b=1.
```

For source `i`, its own `a` deficit is `d_a+u=1-s_j<=0`; only `q` and `b`
are positive.  If `c=b`, the new deficits are

```text
d_q=u-2+s_j,  d_a=1-u,  d_b=1-s_j.
```

For source `i`, its own deficit is `d_a+u=1`; only `a` and `q` are positive.
Thus `i` remains legal in both cases.

The move of `j` does not change the fixed hidden continuation of column `i`,
so eliminating `i` still changes its top from `a` to `q`.  The three top
colors afterward are `(q,c,q)` in some column order.  Since `c!=q`, the
deadlock lemma says that this state is not a deadlock.  The two moves have
removed exactly two original borders.  QED.

## 5. Strong induction

For fixed `h` in `{7,8}`, let `W(R)` be the assertion that every non-deadlock
`z=0` top-border state with `R` remaining original borders can reach `z=1`.
We prove `W(R)` by strong induction.  States with too few borders to keep all
three columns active are vacuous base cases.

Take a state covered by `W(R)`.  It has a legal source `i`.

- If eliminating `i` gives `z=1`, we are done.
- If its successor is not a deadlock, it has `R-1` borders and the induction
  hypothesis applies.
- If its successor would be a deadlock, do not take that edge.  Apply the
  two-step bypass lemma in the original state: eliminate `j` and then `i`.
  This either reaches `z=1`, or reaches a non-deadlock state with `R-2`
  borders, to which the induction hypothesis applies.

At the initial top-border table, each exposed region is its original top
monochrome run, so `F_c=G_c` and `d_c=0` for every color.  The initial state is
therefore not a deadlock.  The induction reaches `z=1`, the finishing lemma
removes every remaining border, and the top-border characterization realizes
the sequence by Water moves.  Together with the `h<=6` argument (and the
trivial `h=1` case), this proves the theorem for every `h<=8`.

## 6. Why this proof stops at height 8

At `h>=9`, inequality (4) permits `E>=3`.  Then the two positive deficits need
not both equal one.  The key bypass step can fail algebraically.  For example,
at `h=9` a consistent deadlock profile can have

```text
d=(-3,2,1),  s=(4,4,4).
```

A legal predecessor may have deficits `(-2,1,1)` and tops `(p,q,q)`.  The
`p` source can enter that deadlock, while either `q` source requires all three
hosts and is illegal.  Thus the height-7/8 detour is not an all-height proof.
This is a gap in the strategy, not a counterexample to solvability.

Local traps themselves also do not imply that an initial instance is
unsolvable.  The following balanced height-7 instance (columns bottom-to-top)
is a concrete example:

```text
1122010
1122020
1122000
```

The legal border prefix `0,0,1,1` reaches

```text
a=(0,0,0),  s=(3,3,3),  F=(7,1,1),  G=(9,0,0),
d=(-2,1,1),
```

so every source needs three hosts although only two are available.  Nevertheless
the initial instance is solvable; the exact oracle returns the alternative
border sequence `0,0,0,1,1,1,0,1,2,2`.  This is why a universal proof must
construct an avoiding strategy rather than merely show that traps exist.

## 7. Relation to published and computed results

Ito et al.'s published general guarantee is

```text
k(n,h) <= ceil((h-1)n/h).
```

For `n=3` and two empty columns, that bound directly guarantees all instances
only through `h=3`; for `h>=4` its right side is three.  Their fixed-`n`
top-border algorithm decides individual inputs but is not an all-instance,
all-height solvability theorem.  See [Ito et al., FUN
2022](https://doi.org/10.4230/LIPIcs.FUN.2022.16) and the [journal
version](https://doi.org/10.1016/j.tcs.2023.114158).

Independently of the proof above, this project completely enumerated height 7
modulo column and color symmetries: 26,717,100 orderly representations and
11,094,455 exact symmetry classes, all solvable.  The run is archived as
[GitHub Actions run
31339686115](https://github.com/lieoric/water-sort-counterexample/actions/runs/31339686115).
The computation corroborates the theorem at height 7; the analytic argument
also covers height 8 without enumerating its much larger complete universe.
