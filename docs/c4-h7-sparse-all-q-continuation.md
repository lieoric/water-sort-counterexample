# Continuation after the sparse all-`q` early-low bypass

## Scope

This note supplies the continuation lemma that is missing from the early-low
bypass.  It has three parts:

1. an exact characterization of a non-goal terminal state with one exhausted
   column;
2. a two-anchor corollary and its fixed-chain rank-product version; and
3. symbolic continuations for the two residual run kernels on bridge edges
   184 and 236.

The edge-184 and edge-236 continuations use no initial-layout solver and no
successor DP.  They replay at most six fixed run events after the prescribed
early-low event and then invoke the two-anchor corollary.  The numerical
censuses that led to these two kernels are discovery data, not hypotheses in
the proof below.

The claim remains local to the specified early-low successors of the
three-source ledger.  It is not a proof that every balanced `c=4,h=7` layout
is solvable.

Throughout, colors are `(q,f,g,h)`, the column height is seven, and a source
is denoted `x_c` when its current color is `x` and its cap is `c`.  At a state
with debt vector `d`, testing `x_c` replaces `d` by

\[
 d+c e_x.                                                     \tag{1}
\]

It is legal when the number of positive coordinates in (1) is at most
`2+z`, where `z` is the number of exhausted columns.

## 1. Positive support after the first exhaustion

Suppose play starts at zero debt and the first column is exhausted by a legal
event.  Immediately before the final transfer, its source test has at most
two positive coordinates.  Completing the destination to height seven can
make at most one further coordinate positive.  Hence the successor has at
most three positive debt coordinates.

While `z=1`, a legal live event has the form

\[
 d'=(d+c e_x)-c e_y.                                         \tag{2}
\]

The subtraction in (2) cannot introduce a positive coordinate.  Therefore:

> **Positive-support invariant.**  From the first exhaustion until the
> second exhaustion, every reachable debt vector has at most three positive
> coordinates.

In particular, every non-goal state in this interval has a nonpositive debt
coordinate.

## 2. Exact terminal-triple theorem

At `z=1` there are exactly three active sources.  Write them as
`(a_i,c_i)`, `i=1,2,3`.

> **Theorem 1 (terminal triple).**  A reachable non-goal `z=1` state is
> terminal if and only if there is a color `j` such that
>
> \[
> \begin{aligned}
> &d_j\le0,\qquad d_k>0\quad(k\ne j),\\
> &a_1=a_2=a_3=j,\\
> &d_j+c_i>0\quad(i=1,2,3).
> \end{aligned}                                               \tag{3}
> \]

**Proof.**  By the positive-support invariant, choose `j` with `d_j<=0`.
If an active source has color different from `j`, its test leaves the `j`
coordinate nonpositive, so that test has at most three positive coordinates
and is legal.  Thus terminality forces all three source colors to be `j`.

If a second coordinate `k` were nonpositive, testing a `j` source would
leave `k` nonpositive and would again be legal.  Thus `j` is the unique
nonpositive coordinate.  The other three coordinates are already positive,
so a `j_{c_i}` test is illegal exactly when it makes the last coordinate
positive, namely when `d_j+c_i>0`.  This proves necessity.  Conversely, (3)
makes all four coordinates positive in every one of the three source tests,
so no source is legal.  \(\square\)

There is a useful inventory form.  Let `H_j` be the number of hidden `j`
items below the three active sources.  When all active sources have color
`j`, the inventory identity gives

\[
 F_j:=d_j+c_1+c_2+c_3=7-H_j\le7.              \tag{4}
\]

Thus the last line of (3) is equivalently

\[
 c_r+c_s<F_j
 \quad\text{for each pair }\{r,s\}\subset\{1,2,3\}.          \tag{5}
\]

## 3. Two anchors and fixed rank products

> **Corollary 2 (two anchors).**  At `z=1`, if two current active caps have
> sum at least seven, the state cannot be terminal.  Moreover every maximal
> legal continuation reaches `z=2`.

Indeed, at a hypothetical terminal the three sources have the common color
`j`.  If, say, `c_1+c_2>=7`, then (4) gives

\[
 d_j+c_3=F_j-(c_1+c_2)\le0,
\]

so the third source is legal, a contradiction.  Current caps only increase.
Until one of the two anchors exhausts, their cap sum remains at least seven;
if one exhausts, `z=2` has already been reached.  Hence no finite maximal
continuation can stop earlier.  Run ranks strictly increase, so the event DAG
is finite.

The same argument yields a reusable audit rule.  Fix a `z=1` state and the
three remaining run chains.  Form the Cartesian product of their remaining
nonfinal ranks (keeping the exhausted column fixed).  Debt is a
path-independent function of the rank tuple.  If no rank tuple satisfying
the positive-support invariant also satisfies (3), then no reachable branch
can terminate before `z=2`.  It is harmless that the product includes
unreachable tuples: it is a superset check, not a strategy search.  We call
this the **fixed-chain terminal-product criterion**.

## 4. The edge-184 residual closes symbolically

Up to swapping the two labelled low columns, the residual prefix is

\[
 (A,L,U,D)=(hq,\;gq,\;qq,\;hqqq),              \tag{6}
\]

where `L` is the low column whose `q_2 -> f_3` event was taken early.  Its
successor is

\[
 d=(1,-2,1,0),
 \qquad (A,L,U,D)=(h_1,f_3,q_2,h_1).            \tag{7}
\]

The other low column has a fixed `q_2 -> f_3` event.  Its first tail run is
`r_R`, where `r` is `g` or `h` and `4<=R<=7`.  Perform

\[
 U:q_2\to f_3,
 \qquad U:f_3\to r_R,
 \qquad A:h_1\to q_2,
 \qquad A:q_2\to f_7.                          \tag{8}
\]

The first two source tests in (8) see respectively
`(3,-2,1,0)` and `(3,-1,1,0)`, so they are legal at `z=0`.

If `R<7`, after the second event the debt is

\[
 (3,-1,-2,0)\quad(r=g),
 \qquad
 (3,-1,1,-3)\quad(r=h).                        \tag{9}
\]

The `h_1` and following `q_2` source tests each have at most two positive
coordinates.  The last event in (8) is the first exhaustion and leaves

\[
 (4,4,-2,1)\quad(r=g),
 \qquad
 (4,4,1,-2)\quad(r=h).                         \tag{10}
\]

Now `L` is still `f_3` and `U` is `r_R`; these are two anchors because
`3+R>=7`.  Corollary 2 reaches the second exhaustion.

If `R=7`, the second event of (8) already exhausts `U`.  The two remaining
events are legal at threshold three and exhaust `A`, so (8) reaches `z=2`
directly.  This closes both labelled forms of (6), independently of every
later run and of the high-card endpoint.

## 5. The edge-236 residual closes symbolically

The residual prefix is one of

\[
 (A,L_1,L_2,D)=(qq,q,q,ghq)
 \quad\text{or}\quad
 (qq,q,q,hgq),                                  \tag{11}
\]

and either low column may be the chosen early column `L`.  The early
`q_1 -> f_2` event leaves

\[
 d=(1,-1,0,0).                                  \tag{12}
\]

First exhaust the bad column:

\[
 A:q_2\to f_7,
 \qquad d=(3,4,0,0),\quad z=1.                 \tag{13}
\]

Every reported edge-236 low future starts `f,q` and the `q` is a singleton.
Advance the chosen low column to its first `{g,h}` tail run `x_R`:

\[
 L:f_2\to q_3,
 \qquad L:q_3\to x_R,
 \qquad 4\le R\le7.                            \tag{14}
\]

The debts before the second event and after a live second event are

\[
 (1,6,0,0),
 \qquad
 (4,6,-3e_x),                                   \tag{15}
\]

so both tests are legal at threshold three.  If `R=7`, (14) is already the
second exhaustion.

Otherwise advance the other low column `U` in the same way:

\[
 U:q_1\to f_2,
 \qquad U:f_2\to q_3,
 \qquad U:q_3\to y_S,
 \qquad 4\le S\le7.                            \tag{16}
\]

Immediately before these three events the successive debts are

\[
 (4,6,-3e_x),
 \quad(5,5,-3e_x),
 \quad(3,7,-3e_x).                              \tag{17}
\]

Every selected source test in (16) has only the positive colors `q,f`, and
is legal.  If `S=7`, the last event exhausts `U`.  Otherwise the two low
columns are current sources `x_R,y_S` with

\[
 R+S\ge4+4=8,                                   \tag{18}
\]

so Corollary 2 applies.  No branch depends on whether `x=y`, on either tail
word after its first run, or on the high column in (11).

## 6. Independent lightweight audit

`tests/check_c4_h7_sparse_all_q_continuation.py` reads the formal checkpoint
report and local-NO ledger.  It independently rebuilds the 60 edge-184 and
six edge-236 balanced prefix templates, identifies the two labelled forms of
(6) and four labelled forms of (11), and replays (8) and (13)--(16) against
every compatible ledger row.

The checker also audits Theorem 1 over the bounded physical `z=1` debt/cap
domain and verifies the inventory form of the two-anchor corollary.  It does
not start from the complete zero-debt layout, call a Water Sort solver, or
enumerate a successor game tree.  In particular its successor-DP state count
is zero; the former bounds of 15 and 11 rank states are no longer needed.
