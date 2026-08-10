# The charged anchor-pair graph at `c=4, h=7, k=2`

## Scope and claim boundary

At a zero-exhaustion border checkpoint with exactly two positive debts, the
other two colors form an **anchor pair**.  There are six such pairs.  This
note organizes them as the octahedral graph `J(4,2)` and proves two facts.

1. A color which enters the anchor pair must receive a new exposed run.
   Therefore the six-vertex graph becomes acyclic after it is lifted by the
   four-color exposure vector.
2. In the clean two-switch rotor realized by the committed four-lock
   example, a return to the original anchor pair which is also a `D2`
   terminal saturates one anchor color at height seven.

The unweighted six-vertex graph is **not** acyclic.  The height-seven
four-lock layout has a legal projected two-cycle, and the cycle ends with
seven, not eight, exposed items of one color.  Thus neither

- "an anchor-pair cycle is impossible at height seven", nor
- "one projected cycle already charges an eighth item"

is true.  The correct statement is that a later entry of a color already at
exposure seven would require an eighth item.  This is a well-foundedness and
saturation lemma, not a proof of universal height-seven solvability.  In
particular, it does not prove that every unresolved `D2` admits the clean
switch used in Section 4.

## 1. Exact anchor checkpoints

For a color `c`, write

\[
 d_c=F_c-G_c,
\]

where `F_c` is exposed inventory and `G_c` is the sum of active host caps
currently topped by `c`.  Before the first exhaustion,

\[
 \sum_c d_c=0,
 \qquad |\operatorname{Pos}(d)|\le2.             \tag{1}
\]

A source of top color `x` and cap `s` is legal exactly when

\[
 |\operatorname{Pos}(d+s e_x)|\le2.             \tag{2}
\]

A live border event

\[
 x_s\longrightarrow y_R,
 \qquad x\ne y,quad s<R<h,
\]

has debt update

\[
 d'=d+s(e_x-e_y).                               \tag{3}
\]

Call a checkpoint **exact** when `|Pos(d)|=2`, and define its anchor pair

\[
 A(d)=C\setminus\operatorname{Pos}(d),
 \qquad |A(d)|=2.                               \tag{4}
\]

The six possible values of (4) are the vertices of `J(4,2)`, the
octahedral graph.  Two vertices are adjacent when they share one color.
The three disjoint pairs are opposite vertices.

Equation (2) gives a useful gate.  Starting with two positive coordinates,
a legal source event cannot make a nonpositive source color positive.  A
change of anchor pair must first pass through a state with at most one
positive debt.  In a basic adjacent switch

\[
 \{x,b\}\longrightarrow\{y,b\},                \tag{5}
\]

the old positive color `y` is first neutralized; only then may the old
anchor `x` become positive.  A segment whose endpoint pairs are disjoint
contains two such membership changes.  It can be accounted for as a
length-two path in the octahedron even if the intermediate pair is not an
observed exact checkpoint.

## 2. The anchor-entry charge

**Lemma 1 (entry charge).**  Let `S` and `T` be two exact checkpoints on one
legal `z=0` border path, with anchor pairs `A` and `B`.  Then

\[
 F_c(T)-F_c(S)\ge1
 \quad\text{for every }c\in B\setminus A.       \tag{6}
\]

**Proof.**  A color `c` in `B\A` has `d_c(S)>0` and `d_c(T)<=0`.  Exhausting
events never decrease a debt coordinate, and in (3) the only way to
decrease `d_c` is for `c` to be the destination of a live event.  At least
one event

\[
 u_s\longrightarrow c_R,
 \qquad R>s,
\]

must therefore occur between `S` and `T`.  It newly exposes the positive
length `R-s` run of `c`, so `F_c` increases by at least one.  Exposure never
decreases later.  This proves (6).  \(\square\)

For a sequence of exact checkpoints `S_0,...,S_m`, put `A_i=A(S_i)` and

\[
 N_c=\#\{i:c\in A_{i+1}\setminus A_i\}.         \tag{7}
\]

Summing (6) over the disjoint time segments gives the vector inequality

\[
 F_c(S_m)-F_c(S_0)\ge N_c.                      \tag{8}
\]

Consequently

\[
 \sum_{i=0}^{m-1}|A_{i+1}\setminus A_i|
 \le \sum_c (h-F_c(S_0)).                       \tag{9}
\]

The left side is the octahedral path length, counting a jump to the opposite
pair with cost two.  The residual-inventory potential

\[
 \Phi(F)=\sum_c(h-F_c)                           \tag{10}
\]

decreases on every nonconstant pair transition.  Thus the lifted graph

\[
 (A,F)\longrightarrow(B,F')                     \tag{11}
\]

is acyclic, even though its projection to the six values of `A` need not be.

For a closed projected walk `A_m=A_0`, entries and exits balance separately
for every color.  Every nonconstant closed walk charges at least two colors,
and a fixed cyclic word can be repeated at most

\[
 \min_{c:N_c>0}
 \left\lfloor\frac{h-F_c(S_0)}{N_c}\right\rfloor
                                                               \tag{12}
\]

times along one coherent history.  In particular, if `F_c=7` at height
seven, any transition with `c in B\A` would require `F_c>=8` by (6) and is
impossible.

This last statement is the precise "eighth item" obstruction.  Charges
cannot be added across counterfactual branches: all checkpoints in (8) must
belong to the same legal history and the same fixed layout.

## 3. A projected cycle at height seven

The committed balanced four-lock layout, with colors `(q,f,g,h)` encoded as
`(0,1,2,3)`, is written bottom to top as

```text
2221032
3321023
3321003
1111000
```

The legal column sequence

```text
0,0,1,0,2,1
```

contains the following exact checkpoints.

| prefix length | debt `(q,f,g,h)` | anchor pair | exposure `(Fq,Ff,Fg,Fh)` |
|---:|---|---|---|
| 2 | `(-2,0,1,1)` | `{q,f}` | `(4,0,1,3)` |
| 4 | `(1,-3,0,2)` | `{f,g}` | `(4,1,2,3)` |
| 6 | `(-2,-3,2,3)` | `{q,f}` | `(7,1,2,3)` |

Thus the projected graph has the two-cycle

\[
 \{q,f\}\longrightarrow\{f,g\}
 \longrightarrow\{q,f\}.                       \tag{13}
\]

The first edge charges the new anchor `g` once.  The second charges the new
anchor `q` three times, stronger than the one-item lower bound in (6).  The
return is not a lifted cycle because exposure has changed from
`(4,0,1,3)` to `(7,1,2,3)`.  Its final checkpoint is a `3+1` `D2` terminal
with three `q_3` tops and one `f_4` top.  A second traversal of the same
projected cycle would eventually have to re-enter `q` and expose an eighth
`q`, so that repetition is excluded, but the first terminal traversal is
real.

The complete layout is nevertheless YES.  One winning column sequence is

```text
0,0,1,0,2,2,0,1,1,1,1,2,2,3
```

Therefore a projected cycle neither implies NO nor can simply be deleted
from the proof.  It records a bad scheduling choice in a solvable layout.

## 4. Clean two-switch return saturation

The same example belongs to a more rigid normal form.  This is the part of
the graph idea that uses height seven sharply.

Use four distinct colors `(x,b,y,p)`.  Start at an exact checkpoint with

\[
 d=(-A,0,X,Y),
 \qquad X,Y\ge1,
 \qquad A=X+Y,                                  \tag{14}
\]

and top multiset

\[
 x_t,\ x_c,\ p_s,\ p_u.                         \tag{15}
\]

The zero in (14) is forced: `b` is an anchor with no current host, hence
`d_b=F_b` is both nonnegative and nonpositive.  Balance then gives
`A=X+Y`.

Consider the four live events

\[
 \begin{aligned}
 p_s&\longrightarrow y_r, & X&\le s<r<h,\\
 x_t&\longrightarrow b_R, & t&>A,\\
 p_u&\longrightarrow x_w, & u&\ge t-A,\quad u<w<h,\\
 y_r&\longrightarrow\delta_T,
       & \delta&\in\{x,b\},
 \end{aligned}                                  \tag{16}
\]

with `t<R<h` and `r<T<h`.  The first event neutralizes `y`, the second
activates `x`, the third neutralizes `x`, and the fourth activates `y`.
Every event is legal by the two-positive gate: the positive supports after
the four events alternate

\[
 \{p\},\quad\{p,x\},\quad\{p\},\quad\{p,y\}.    \tag{17}
\]

The anchor pair has therefore made a clean return

\[
 \{x,b\}\to\{y,b\}\to\{x,b\}.                 \tag{18}
\]

If `delta=x`, the final top multiset is `x_c,x_w,x_T,b_R`, of type `3+1`.
If `delta=b`, it is `x_c,x_w,b_R,b_T`, of type `2+2`.

**Theorem 2 (clean-return saturation at height seven).**  If the final state
in (16) is a physical height-seven `D2` terminal, then one anchor color has
exposure seven.

- For `delta=x`,

  \[
  E_x=A+u+r-t\ge r\ge X+1\ge2.                  \tag{19}
  \]

  The three `x` caps are all strictly greater than `E_x`, so

  \[
  F_x=c+w+T-E_x
      \ge3(E_x+1)-E_x
      =2E_x+3\ge7.                              \tag{20}
  \]

  Since only seven `x` items exist, equality holds throughout:

  \[
  E_x=2,
  \qquad(c,w,T)=(3,3,3),
  \qquad F_x=7.                                 \tag{21}
  \]

- For `delta=b`,

  \[
  E_b=t+r
      \ge(A+1)+(X+1)
      =2X+Y+2\ge5.                              \tag{22}
  \]

  The two `b` caps are strictly greater than `E_b`, hence

  \[
  F_b=R+T-E_b\ge E_b+2\ge7.                    \tag{23}
  \]

  Again physical height seven forces equality:

  \[
  E_b=5,
  \qquad(R,T)=(6,6),
  \qquad F_b=7.                                 \tag{24}
  \]

The four-lock cycle in Section 3 is the `delta=x` case.  In the notation of
(15)--(16),
`(A,X,Y;s,r;t,c;u,w;R,T)=(2,1,1;1,2;3,3;1,3;4,3)`; its three final `x`
caps are all three.

The theorem does not say that the terminal can be advanced.  It says that a
clean projected return has hit a saturated boundary.  Any later proof step
which requires that saturated color to leave the positive side and enter
the anchor pair again is ruled out by Lemma 1.  A switch which keeps the
saturated color anchored is not ruled out.

## 5. Why height eight does not obey the saturation step

At height eight, inequalities (20) and (23) permit exposure seven, leaving
one hidden item.  Two numerical macro types show the exact failure.

For `delta=x`, take

\[
 (A,X,Y;s,r;t,c;u,w;R,T)
 =(2,1,1;1,2;3,3;1,3;4,3).                     \tag{25}
\]

The final debts are `(-2,-3,2,3)`, the tops are
`x_3,x_3,x_3,b_4`, and

\[
 (F_x,F_b,F_y,F_p)=(7,1,2,3).                  \tag{26}
\]

For `delta=b`, take

\[
 (A,X,Y;s,r;t,c;u,w;R,T)
 =(2,1,1;1,2;3,1;1,2;6,6).                     \tag{27}
\]

The final `b` energy is five, its two caps are six, and `F_b=7`.  These are
physical numerical border macros, not claims that either macro alone is a
complete height-eight NO layout.

The checker exhausts this small normal-form box.  At height seven it finds
9 labelled `delta=x` terminal macros and 35 labelled `delta=b` macros; all
44 saturate the predicted color.  At height eight it finds 67 and 369,
respectively.  Sixteen of the first kind and 56 of the second kind have the
predicted exposure equal to seven rather than eight.  This is the precise
height boundary in the clean-return proof.

There is a second warning from the three committed height-eight NO fixtures.
Their reachable zero-exhaustion anchor-pair projections contain no directed
cycle in the fixed-border diagnostic.  Therefore even a proof excluding all
projected cycles would not, by itself, be a general solvability criterion.
Locks can occur before a pair cycle is formed.

## 6. Exact finite audit and remaining route

`tests/check_c4_h7_anchor_pair_graph.py` performs only small finite checks.
It

1. constructs the six-vertex octahedron and checks the vector charge on all
   closed octahedral walks of lengths two through six;
2. exhausts the labelled integer box behind Theorem 2 at heights seven and
   eight;
3. replays the height-seven projected two-cycle and the separate winning
   path; and
4. enumerates the tiny fixed-border state graphs of the three committed
   height-eight NO fixtures as a pressure diagnostic.

No residual word family or complete height-seven universe is enumerated.

The next missing mathematical statement is a **switch coverage lemma**.  It
would need to show that every unresolved reachable height-seven lock either

- has an executable commuting square or an exhaustion handoff;
- admits a clean return covered by Theorem 2; or
- changes anchor pair while paying a charge that can be continued on the
  same coherent history.

Longer pair cycles, mixed starting top multiplicities, `a=q` bridge forms,
and the passage from a nonzero checkpoint back to a zero-debt initial layout
are not covered here.  Those are genuine scope gaps, not omitted cases of
Theorem 2.
