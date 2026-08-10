# The two-legal-source D2 kernel at `c=4, h=7, k=2`

## Scope

This note isolates the part of the certified first-exhaustion `Tq` sibling
census whose parent has exactly two legal physical sources.  It proves that
all members are losing **at that parent checkpoint** and gives the exact
zero-debt prefixes that must be restored before testing the real water-sort
initial layouts.

The conclusion is deliberately local.  A losing nonzero-debt checkpoint is
not a global counterexample: the initial layout may take a different legal
history and never visit the checkpoint.

Use parent-coordinate color names `(q,f,g,h)`, where `q` is the common top
color and `f` is the isolated final color of the bad exhaustion.  The unique
macro parent is

\[
 d(P)=(-2,0,1,1),\qquad
 G_q(P)=1+2+3+3,
 \tag{1}
\]

with four `q`-top caps `(1,2,3,3)`.

## 1. Exactly two legal sources

Testing a `q_c` source at `P` replaces the `q` coordinate by `c-2`.
The `g` and `h` coordinates are already positive.  At `z=0`, legality
therefore holds exactly when

\[
 c-2\le 0.
 \tag{2}
\]

Thus `q_1` and `q_2` are the only legal physical sources; both `q_3`
sources are illegal.  The certified bridge contains the two bad actions

\[
 q_1\xrightarrow{f^6}7,
 \qquad
 q_2\xrightarrow{f^5}7.
 \tag{3}
\]

Write the bad cap as `s` and the other legal cap as `r`.  In both cases

\[
 \{s,r\}=\{1,2\},\qquad s+r=3.
 \tag{4}
\]

## 2. The D2 class forces one sibling card

Consider the unique legal sibling `q_r`.

- A live next run to `g` or `h` has terminal debt `p_x=1`, so
  `r>=p_x`.  The bad exhaustion remains legal and this is an already
  certified low-`N` handoff, not a D2-reduction decoration.
- An exhausting next run to a color other than `f` is in the certified
  direct-exhaustion branch.
- An exhausting next run to `f` cannot coexist with the bad tail: the two
  proposed final runs would reserve

  \[
  (7-s)+(7-r)=14-(s+r)=11>7
  \tag{5}
  \]

  items of color `f`.
- The low-energy handoff corner is absent: the two untouched sibling caps
  are `(3,3)`, rather than the required `(1,1)`.

Consequently every D2-reduction decoration on these two edges has the
unique legal sibling card

\[
 q_r\longrightarrow f_R,\qquad r<R<7.
 \tag{6}
\]

The two `q_3` cards and all lower suffix cells can vary, but none of them is
read in the checkpoint proof below.

## 3. Taking the sibling lands immediately in D2

After (6), the debt vector is

\[
 d_S=(-2+r,-r,1,1).
 \tag{7}
\]

The active tops are

\[
 q_s, q_3, q_3, f_R.
 \tag{8}
\]

The two nonpositive anchors are `q` and `f`, with energies

\[
 A=2-r=s-1,\qquad B=r.
 \tag{9}
\]

Every `q` cap is strictly larger than `A`, because `s>A` and `3>A`.
The singleton `f` cap is strictly larger than `B`, because `R>r`.
The other two debts are the positive values `(1,1)`.  Hence (7)-(9) are an
immediate blocked D2 state of top multiplicity `3+1`.

Explicitly,

| bad / sibling | successor debts `(q,f,g,h)` | tops |
|---|---|---|
| `s=1`, `r=2` | `(0,-2,1,1)` | `q_1,q_3,q_3,f_R` |
| `s=2`, `r=1` | `(-1,-1,1,1)` | `q_2,q_3,q_3,f_R` |

## 4. Taking the bad source lands immediately in Tq

Taking the bad exhaustion in (3) instead gives `z=1` and

\[
 d_B=(s-2,7-s,1,1).
 \tag{10}
\]

All three surviving tops are `q`, with caps `(r,3,3)`.  Their `q`-energy is

\[
 M=2-s=r-1.
 \tag{11}
\]

All three caps are strictly greater than `M`.  The other three coordinates
in (10) are positive.  Testing any surviving source therefore produces four
positive coordinates, exceeding the `z=1` threshold `k+z=3`.  Thus (10) is
an immediate `Tq` terminal.

Equations (7) and (10) cover the only two legal first moves at `P`.
Therefore every fixed future in this subfamily is `P`-local-NO.  This proof
does not inspect any suffix below the sibling boundary (6).

The certified counts are

| bad edge | D2 decorations | represented hidden futures |
|---|---:|---:|
| `q_1 -> f_7` | 58 | 924 |
| `q_2 -> f_7` | 132 | 12,012 |
| total | **190** | **12,936** |

These 190 decorations are exactly the legal-source-count-two slice of the
67,206-decoration D2-reduction census.

## 5. Why this is not a global NO certificate

The checkpoint has nonzero debt.  In particular, its exposed counts are

\[
 F=d+G=(7,0,1,1)
 \tag{12}
\]

in the order `(q,f,g,h)`.  Reaching `P` has already exposed one `g` item and
one `h` item and has arranged all four current tops to be `q`.  A true
water-sort initial state has debt zero and may order those earlier exposures
differently.  The two terminal choices at `P` say nothing about a legal move
that diverges before `P`.

Equivalently, the still-hidden inventory at `P` is

\[
 7-F=(0,7,6,6).
 \tag{13}
\]

Accordingly, a full initial layout is a global NO only after an exact
zero-debt solver has tested all its legal initial choices.  Conversely, a
winning initial path eliminates the layout even though its reachable
checkpoint `P` is losing.

## 6. Exact zero-debt past-prefix templates

Label the four physical columns by their caps at `P`:

\[
 C_1, C_2, C_3, C'_3.
\]

For the `s=1` edge, `C_1` is bad and `C_2` is the unique legal sibling;
for the `s=2` edge these two roles are reversed.  The other two columns are
the currently illegal cap-three siblings.

The two cap-three columns remain physically labeled by their fixed lower
futures; they are not silently quotiented by a swap.  For each column let
`u_C` be the already exposed word, in initial top-to-current-boundary order.
Then a zero-debt restoration reaches (1) only if

1. `|u_C|` is the displayed cap;
2. every `u_C` ends in `q`;
3. the four words together contain `q^7 g h` and no `f`;
4. the next hidden cell is not `q`, so the displayed cap is the exact end of
   the current `q` run.

Condition 4 is already enforced by every fixed next-run decoration.  The
first three conditions leave five positions before the four final `q`
cells:

\[
 \Omega=\{C_2[1],C_3[1],C_3[2],C'_3[1],C'_3[2]\}.
 \tag{14}
\]

Choose one position of `\Omega` for `g` and a distinct position for `h`;
fill every other position with `q`.  This gives exactly

\[
 |\Omega|(|\Omega|-1)=5\cdot4=20
 \tag{15}
\]

labeled past-prefix templates.  It is also sufficient: the resulting
prefixes have exactly (12), join every certified hidden future at a genuine
run boundary, and are legally reachable as shown next.

Here are all 20 templates.  The last column records the number of legal
interleavings of their per-column past event chains.

| # | `C_1` | `C_2` | `C_3` | `C'_3` | histories |
|---:|---|---|---|---|---:|
| 1 | `q` | `gq` | `hqq` | `qqq` | 2 |
| 2 | `q` | `gq` | `qhq` | `qqq` | 3 |
| 3 | `q` | `gq` | `qqq` | `hqq` | 2 |
| 4 | `q` | `gq` | `qqq` | `qhq` | 3 |
| 5 | `q` | `hq` | `gqq` | `qqq` | 2 |
| 6 | `q` | `qq` | `ghq` | `qqq` | 1 |
| 7 | `q` | `qq` | `gqq` | `hqq` | 2 |
| 8 | `q` | `qq` | `gqq` | `qhq` | 3 |
| 9 | `q` | `hq` | `qgq` | `qqq` | 3 |
| 10 | `q` | `qq` | `hgq` | `qqq` | 1 |
| 11 | `q` | `qq` | `qgq` | `hqq` | 3 |
| 12 | `q` | `qq` | `qgq` | `qhq` | 6 |
| 13 | `q` | `hq` | `qqq` | `gqq` | 2 |
| 14 | `q` | `qq` | `hqq` | `gqq` | 2 |
| 15 | `q` | `qq` | `qhq` | `gqq` | 3 |
| 16 | `q` | `qq` | `qqq` | `ghq` | 1 |
| 17 | `q` | `hq` | `qqq` | `qgq` | 3 |
| 18 | `q` | `qq` | `hqq` | `qgq` | 3 |
| 19 | `q` | `qq` | `qhq` | `qgq` | 6 |
| 20 | `q` | `qq` | `qqq` | `hgq` | 1 |

## 7. Reachability of all 20 templates

After deleting the `q`-only words, every nontrivial column has one of four
forms, for distinct `x,y` in `{g,h}`:

\[
\begin{array}{c|c}
\text{prefix}&\text{past event chain}\\ \hline
xq&x_1\to q_2\\
xqq&x_1\to q_3\\
qxq&q_1\to x_2\to q_3\\
xyq&x_1\to y_2\to q_3.
\end{array}
\tag{16}
\]

For `xyq`, the first event leaves debts `d_x=1,d_y=-1`; testing the second
event makes exactly `x` and `y` positive, so both events are legal.

If `g` and `h` lie in separate columns, consider any interleaving respecting
the two per-column orders.  An unstarted chain contributes zero.  A completed
chain for color `x` contributes

\[
 d_q=-1,\qquad d_x=1.
 \tag{17}
\]

The only possible intermediate chain is `q_1 -> x_2`; before its return it
contributes `d_q=1,d_x=-1`.  For a completely explicit legality check, let
the other color's chain be unstarted, intermediate, or completed.  The
possible positive-coordinate sets after testing the next source are

| next source | other unstarted | other intermediate | other completed |
|---|---|---|---|
| initial `x_1` | `{x}` | `{q,x}` | `{x,y}` |
| departing `q_1` | `{q}` | `{q}` | `{y}` |
| returning `x_2` | `{q,x}` | `{q,x}` | `{x,y}` |

Every set has size at most two.  Hence every order-preserving interleaving is
legal at `z=0`, and its final sum is

\[
 (-e_q+e_g)+(-e_q+e_h)=(-2,0,1,1).
 \tag{18}
\]

The history counts in the table follow immediately:

- four same-column `ghq/hgq` templates have one history;
- six templates with two one-event chains have two histories;
- eight templates with chain lengths one and two have three histories; and
- two templates with two length-two chains have six histories.

Thus there are 52 legal ordered histories across the 20 templates, but only
20 restored initial layouts per fixed labeled hidden future.

## 8. Exact next-DP universe and claim boundary

The 190 card decorations partition 12,936 compatible labeled hidden futures:
each complete future has a unique next-run card triple.  Combining each
future with the 20 templates above gives

\[
 20\cdot 924=18{,}480,
 \qquad
 20\cdot12{,}012=240{,}240,
 \tag{19}
\]

or **258,720 labeled zero-debt reconstructions** in total.  The two bridge
edge universes are disjoint: satisfying both bad tails would require eleven
`f` items.

An exact checker is complete for this kernel if it:

1. independently reconstructs the two edges and the 58/132 decoration split;
2. expands exactly the 924/12,012 hidden futures, without sampling;
3. attaches all 20 labeled prefixes in (14)-(15);
4. checks color balance, exact run boundaries, and a legal replay to `P`;
5. confirms the structural `P`-local-NO result for every future;
6. solves every restored zero-debt layout and replays every claimed winning
   path or global-NO witness.

Column/color canonicalization may deduplicate solver work, but the report
must retain the 258,720 labeled coverage total.  Until step 6 finishes, the
only valid conclusion is `TWO_SOURCE_D2_PARENT_LOCAL_NO`; neither
`GLOBAL_NO_FOUND` nor `TWO_SOURCE_D2_INITIAL_FAMILY_ELIMINATED` follows from
the checkpoint proof alone.
