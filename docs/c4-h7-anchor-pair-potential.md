# Anchor-pair potentials at `c=4, h=7, k=2`

## Scope and claim boundary

This note develops a two-dimensional replacement for the one-color debt
rotor used in the three-color proof.  It applies at `z=0`, before the first
original column has been exhausted, and proves four facts.

1. In a rich two-anchor state, source legality is exactly a two-bin fitting
   test.
2. A genuine excursion through a complement color has a strictly increasing
   scalar energy and a coordinatewise increasing **complement-exposure
   vector**.  A direct anchor-to-anchor edge is a separate zero-cost
   transfer.
3. A first-exhaustion `Tq` state of energy two has already exposed all seven
   items of its top color.
4. A `2+2` `D2` terminal created on the first two-anchor sweep satisfies
   inequalities which exclude energy two and make energy one rigid.

These are reduction lemmas, not a proof that every height-7 layout is
solvable.  At `z=0`, an excursion can end by exhausting the first original
column; unlike the three-color problem, that is not yet the goal.  A rotor can
also end at a genuine `D2` terminal.  Finally, a losing nonzero-debt
checkpoint is not a losing zero-debt initial layout.

The accompanying checker enumerates numerical macro types and committed
next-run cards only.  It counts compatible residual words combinatorially and
never expands them.

## 1. Border equations

At a border checkpoint write

\[
 d_c=F_c-G_c,
\]

where `F_c` is the number of exposed items of color `c` and `G_c` is the sum
of the active host capacities currently topped by `c`.  At `z=0`,

\[
 \sum_c d_c=0.
\]

A source of top color `x` and cumulative cap `r` is legal exactly when

\[
 \#\{c:d_c+r[c=x]>0\}\le2.                 \tag{1}
\]

A live event

\[
 x_r\longrightarrow y_R,\qquad x\ne y,\quad r<R<7,
\]

has debt update

\[
 d'=d+r(e_x-e_y).                            \tag{2}
\]

The coefficient in (2) is the **old** cap `r`, not the new endpoint `R`.
This distinction is important in the rotor calculation below.

## 2. Rich two-anchor states are a two-bin fitting problem

Fix four distinct color names `(alpha,beta,x,y)`.  Consider a state

\[
 d=(-A,-B,X,Y),\qquad A,B\ge0,\quad X,Y>0,
                                                        \tag{3}
\]

in that color order, and suppose every active top color belongs to
`{alpha,beta}`.  Equation `sum d=0` gives

\[
 A+B=X+Y.                                      \tag{4}
\]

Call `alpha,beta` the anchors and `x,y` the complement colors.

**Lemma 1 (two-bin source test).**  An `alpha` source of cap `c` is legal if
and only if `c<=A`.  A `beta` source of cap `c` is legal if and only if
`c<=B`.

**Proof.**  Testing the `alpha` source changes only the first coordinate of
(3), from `-A` to `-A+c`.  The two complement coordinates are already
positive and the `beta` coordinate is nonpositive.  Thus (1) holds precisely
when `-A+c<=0`.  The `beta` statement is symmetric.  \(\square\)

The interpretation is exact: `A,B` are two bin capacities and every
anchor-top source is an item which must fit in the bin named by its current
top color.  A state of the form (3) is terminal exactly when no current item
fits.

At height 7 a terminal of this form cannot have top multiplicity `4+0`.
Indeed, the unused anchor has no host, so its nonpositive debt must be zero.
The occupied-anchor energy is then `A=X+Y>=2`.  Four caps strictly greater
than `A` would give

\[
 F_{\alpha}=G_{\alpha}-A
 \ge4(A+1)-A=3A+4\ge10>7.                    \tag{5}
\]

Consequently the only terminal multiplicities are `3+1` and `2+2`.

## 3. The anchor corridor and its vector potential

Suppose an `alpha_c` source is legal, so `c<=A`, and its next run is a
complement color.  Follow that same fixed column.  If it does not exhaust,
stop at the first later event which enters either anchor.  Write that final
event as

\[
 z_w\longrightarrow \delta_T,
 \qquad z\in\{x,y\},\quad
 \delta\in\{\alpha,\beta\},\quad c<w<T.
                                                        \tag{6}
\]

There can be any fixed sequence of `x` and `y` runs between the departure
from `alpha` and (6).

**Lemma 2 (two-anchor corridor).**  Every event on this fixed-column
corridor is legal.  Both anchor debts remain nonpositive until the return.

**Proof.**  Departure from `alpha` changes its debt to `-A+c<=0` and leaves
the `beta` debt equal to `-B<=0`.  While the column top is outside the anchor
pair, testing it leaves both anchor coordinates untouched.  Hence among four
coordinates at most the two complement coordinates can be positive, and
(1) holds.  Entering an anchor subtracts the old cap `w` from that anchor's
debt, so it cannot make the anchor positive.  \(\square\)

At the next all-anchor checkpoint the anchor energies are

\[
 (A',B')=
 \begin{cases}
 (A-c+w,\ B),&\delta=\alpha,\\
 (A-c,\ B+w),&\delta=\beta.
 \end{cases}                                    \tag{7}
\]

In both cases

\[
 A'+B'=A+B+(w-c)>A+B.                           \tag{8}
\]

The more informative invariant is the complement-exposure vector.  At an
all-anchor checkpoint the complement colors have no hosts, so

\[
 (d_x,d_y)=(F_x,F_y).                            \tag{9}
\]

The portion of the chosen column strictly between caps `c` and `w` consists
only of complement colors.  If it contains `u_x` items of `x` and `u_y`
items of `y`, then

\[
 (F'_x,F'_y)=(F_x+u_x,F_y+u_y),
 \qquad u_x,u_y\ge0,
 \qquad u_x+u_y=w-c\ge1.                        \tag{10}
\]

Equations (8) and (10) agree through (4):

\[
 A'+B'=F'_x+F'_y.
\]

Thus `(F_x,F_y)` increases coordinatewise and strictly in at least one
coordinate.  Equivalently, the hidden-inventory vector

\[
 (7-F_x,7-F_y)                                  \tag{11}
\]

decreases coordinatewise and strictly in at least one coordinate.

There is one zero-cost case which must not be hidden in the word
"excursion".  If the selected source moves directly between anchors,

\[
 \alpha_c\longrightarrow\beta_R,
\]

then

\[
 (A',B')=(A-c,B+c),\qquad
 (F'_x,F'_y)=(F_x,F_y).                         \tag{12}
\]

Thus total energy and the complement vector are unchanged.  The transition
still makes irreversible progress because the fixed column cap advances
from `c` to `R>c`.  The symmetric `beta -> alpha` formula is identical.

**Corollary 3 (finite two-anchor rotor).**  Repeatedly choose a fitting
anchor source.  Apply Lemma 2 when it enters a complement color, and apply
(12) when it enters the other anchor directly.  The process reaches either

1. the first exhausted original column; or
2. an all-anchor state with no fitting source, which is a `D2` terminal.

It cannot cycle because every selected fixed-column boundary advances.
Starting from `(F_x,F_y)`, it makes at most `14-F_x-F_y` **genuine
complement excursions** before one of those outcomes.  Direct anchor
transfers are additional zero-cost events, but their number is bounded by
the finite remaining border count.

This is the useful replacement for a scalar debt rotor.  On genuine
excursions the scalar `A+B` proves progress, while the vector (10) records
*which* of the two complement inventories paid for that progress.  The
complement part of a suffix can therefore be compressed to a monotone path
in a `7 x 7` grid; direct anchor transfers retain only their finite endpoint
sequence.

## 4. Energy-two `Tq` saturation

At `z=1`, a `Tq` terminal has three active `q` tops.  Write

\[
 d_q=-E,
 \qquad d_c>0\quad(c\ne q),
\]

and let the three `q` caps be `r_1,r_2,r_3`.  Terminal blockedness gives
`r_i>E`, and physical balance gives

\[
 F_q=r_1+r_2+r_3-E\le7.                         \tag{13}
\]

**Lemma 4 (`E=2` saturation).**  If `E=2`, then

\[
 (r_1,r_2,r_3)=(3,3,3),
 \qquad F_q=7.                                  \tag{14}
\]

**Proof.**  Integrality and `r_i>2` give `sum r_i>=9`.  Substitution in
(13) gives `F_q>=7`.  Both inequalities must be equalities.  \(\square\)

The first-exhausting event which enters this `Tq` terminal does not expose
new `q` items: its isolated final run has another color.  Hence the `z=0`
bridge parent also has `F_q=7`.  No compatible residual suffix contains a
hidden `q` item.

This has two different consequences in the two bridge normal forms.

- If the bad source color is not `q`, the two-anchor sweep uses the bad
  source color and the isolated final color as anchors.  Then `q` is a
  complement color fixed at exposure seven.  Any later `D2` has positive
  mass at least `7+1=8`.  A `3+1` `D2` is impossible: the three-source
  anchor has energy at most 2 by (5), while the one-source anchor has energy
  at most 5, so their total is at most 7.  Only a `2+2` terminal can remain.
- If the bad source color is `q`, then `q` is itself an anchor after a live
  sibling move.  Saturation still says that a column which leaves `q` can
  never encounter another hidden `q`, but the preceding positive-mass
  argument does not apply because `q` is hosted.

The numerical terminal census reflects the same bounds.  The 265 canonical
`3+1` types have total anchor energy at most 7.  The 661 canonical `2+2`
types have energy at most 10; exactly ten of them have one positive
coordinate equal to seven.

## 5. First-sweep `2+2` inequalities

Consider the first-exhaustion bridge with bad source color `a!=q` and
isolated final color `f`.  In parent coordinates its normal form is

\[
 d(P)=(-E,0,-A,A+E)                             \tag{15}
\]

in color order `(q,f,a,b)`.  The active tops are the bad `a_s` source and
three `q` siblings.  Each sibling cap is strictly greater than `E`.

Suppose the **first** sweep sends exactly one sibling directly to `a` and
the other two directly to `f`:

\[
 q_u\to a_{R_a},
 \qquad q_v\to f_{R_1},
 \qquad q_w\to f_{R_2},                         \tag{16}
\]

where all endpoints are live and therefore at most 6.  Put

\[
 A'=A+u,
 \qquad B'=v+w.                                 \tag{17}
\]

After (16), the two `a` tops have caps `s,R_a`, the two `f` tops have caps
`R_1,R_2`, and the debts are

\[
 d=(-E+u+v+w,\ -B',\ -A',\ A+E).               \tag{18}
\]

The first and last coordinates in (18) are positive exactly in the genuine
`D2` case.  Lemma 1 gives the exact terminal test

\[
 s>A',\qquad R_a>A',\qquad
 R_1>B',\qquad R_2>B'.                          \tag{19}
\]

There is also a fixed-future inventory constraint.  The reserved bad tail
uses `7-s` items of color `f`, while the two live cards in (16) use
`R_1-v` and `R_2-w`.  Joint realizability therefore requires

\[
 (R_1-v)+(R_2-w)\le s.                          \tag{20}
\]

**Lemma 5 (first-sweep lower bound).**  Every jointly realizable first-sweep
`2+2` terminal satisfies

\[
 s\ge A+u+1,
 \qquad
 s\ge v+w+2\ge2E+4.                            \tag{21}
\]

**Proof.**  The first inequality is integer strictness in (19).  The last
two inequalities in (19) give `R_i>=v+w+1`; hence

\[
 (R_1-v)+(R_2-w)
 \ge2(v+w+1)-(v+w)=v+w+2.
\]

Combine this with (20).  Finally `v,w>E`, so `v+w>=2(E+1)`.  \(\square\)

Since a live bad source has `s<=6`, equation (21) proves that `E=2` can
never enter `D2` on the first sweep.  Such a branch must make at least one
further anchor excursion before a later `D2` is possible.

At `E=1`, (21) is rigid:

\[
 s=6,
 \qquad v=w=2,
 \qquad R_1=R_2=5.                              \tag{22}
\]

Moreover, parent exposure is `F_a=s-A=6-A`.  The `a` card has length
`R_a-u>A`, while only `1+A` items of `a` remain.  Therefore

\[
 R_a-u=A+1,
 \qquad F_a'=7.                                 \tag{23}
\]

The two `f` cards expose six `f` items, and the remaining one `f` item is
the reserved length-one bad tail.  Thus all `a` inventory is exposed and all
`f` inventory is already assigned, even though the bad-tail `f` is still
hidden at this `z=0` checkpoint.

## 6. Exact finite audit

`tests/check_c4_h7_anchor_pair_potential.py` performs four independent
finite checks.

1. It regenerates all `71 + 265 + 661 = 997` terminal macro types and checks
   the source thresholds, multiplicity bounds, and the seven `E=2` `Tq`
   types.
2. It exhausts the integer box of (3), (6), (7), and (12), checking the
   two-bin legality test, the strict excursion increment, and the zero-cost
   direct-anchor transfer.
3. It reads a complete first-exhaustion report and reclassifies every
   reported `D2` count by `E`, bad-source form, and parent legal-source
   count.
4. It enumerates only the direct cards in (16), counts residual words with
   multinomial/Hall arithmetic, and checks (19)-(23).  It does not enumerate
   any residual word.

For the certified first-exhaustion report, the new ledger is

| slice | edges | card decorations | residual-word weight |
|---|---:|---:|---:|
| all `E=2` `D2` reductions | 30 | 2,350 | 96,108 |
| `E=2`, bad source `a!=q` | 18 | 1,369 | 57,090 |
| `E=2`, bad source `a=q` | 12 | 981 | 39,018 |
| first-sweep `2+2`, `E=0` | 41 | 304 | 322,825 |
| first-sweep `2+2`, `E=1` | 9 | 17 | 242 |
| first-sweep `2+2`, `E=2` | 0 | 0 | 0 |

The 321 first-sweep decorations have 142 distinct numerical signatures:
133 at `E=0` and the nine rigid signatures from (22)-(23) at `E=1`.

These counts are a strict reclassification of the existing 67,206
`D2`-reduction decorations.  They do not eliminate the later-rotor `D2`
remainder, the `a=q` anchor form, the unique-source `Tq` entrances, or the
full height-7 initial-layout universe.
