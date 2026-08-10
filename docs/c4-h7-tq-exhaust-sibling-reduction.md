# The first-exhaustion `Tq` sibling reduction at `c=4, h=7, k=2`

## Scope and status

This note studies the `z=0` parents whose **first exhausting event** enters a
`Tq` terminal at `z=1`, and only the subfamily in which the parent has a
legal source other than the exhausting source.

The result is a reduction, not an elimination theorem.  It proves several
large branches safe and isolates the branches that still require a `D2`
argument or a unique-source `Tq` argument.  In particular, this note does
**not** prove that every first-exhaustion `Tq` parent is checkpoint-YES and
does **not** prove universal solvability at height 7.

The canonical census has

```text
418 first-exhaustion Tq parents / 429 parent-terminal edges,
  6 unique-source parents       /   6 edges,
412 sibling parents             / 423 edges.
```

Inside the sibling family, 270 parents and 270 edges have bad-source top
different from the terminal top color, while 142 parents and 153 edges have
the same bad-source and terminal top color.  Eleven of the latter parents
have two canonical terminal children.

All calculations below are for one fixed future (the actual remaining run
chains).  A macro transition is not silently treated as a jointly realizable
decoration: whenever two proposed branches reserve items of the same color,
the common color budget is imposed explicitly.

## 1. Border equations and two input lemmas

For a border state let

\[
d_c=F_c-G_c,
\]

where `F_c` is the exposed amount of color `c` and `G_c` is the active host
capacity currently topped by `c`.  A source of top color `x` and current cap
`r` is legal exactly when

\[
 \#\{c:d_c+r[c=x]>0\}\le 2+z.                 \tag{1}
\]

A live event `x_r -> y_R`, with `x != y` and `r<R<7`, has debt update

\[
d'=d+r(e_x-e_y).                               \tag{2}
\]

An exhausting event whose final run has color `y` has update

\[
d'=d+r e_x+(7-r)e_y,                           \tag{3}
\]

and increments `z`.

We use two previously established facts.

1. **Debt Recovery at `z=1`.**  For a reachable height-7 state, put
   `N=-min_c d_c`.  If `N>=3`, the state is checkpoint-YES.
2. **Same-level `Tq` sibling-entry lemma.**  A live `z=1` entrance into a
   `Tq` terminal is checkpoint-YES if its parent has a legal sibling source.
   Equivalently, in the notation of that lemma, the still-unresolved entrance
   is precisely the unique-source case `p_x>r`; the sibling case is
   `p_x<=r`.

The second fact is proved in `docs/c4-h7-tq-sibling-lemma.md` by the anchor
corridor and all-anchor rotor.

## 2. Normal form of a first-exhaustion bridge

Let `D` be the `Tq` child.  Its three active columns have common top color
`q`, with caps `r_1,r_2,r_3`, and

\[
d_q(D)=-E,\qquad d_c(D)=p_c>0\quad(c\ne q),
                                                        \tag{4}
\]

where

\[
0\le E\le2,\qquad r_i>E.                       \tag{5}
\]

Let the bad first-exhausting edge be

\[
a_s\xrightarrow{\text{final }f^{\,7-s}}D,
\qquad a\ne f.                                  \tag{6}
\]

Writing its parent as `P`, inversion of (3) gives

\[
d(P)=d(D)-s e_a-(7-s)e_f.                       \tag{7}
\]

Testing the bad source at `P` gives

\[
d(P)+s e_a=d(D)-(7-s)e_f.                       \tag{8}
\]

The right side initially has the three positive non-`q` coordinates of
`D`.  Bad-source legality at `z=0` forces the subtraction to remove one of
them, so `f` is a positive-debt color.  Moreover, `P` has no `f`-top source:
its active tops are the three `q` tops and `a`, and `a!=f`.  Consequently
`G_f(P)=0`, while `F_f(P)=d_f(P)>=0`.  Equation (8) also gives
`d_f(P)<=0`.  Hence equality is forced:

\[
p_f=7-s,\qquad d_f(P)=F_f(P)=0.                 \tag{9}
\]

Thus the bad-source test has exactly two positive coordinates: the two
positive colors other than `f`.

### 2.1 The case `a != q`

Let `b` be the fourth color, so the colors are `q,f,a,b`, and define

\[
A=s-p_a.                                        \tag{10}
\]

Since the debts of `D` sum to 7, (9) gives

\[
p_a+p_b=s+E,\qquad p_b=A+E.                    \tag{11}
\]

In the order `(q,f,a,b)`, the parent therefore has the particularly rigid
form

\[
d(P)=(-E,0,-A,A+E).                             \tag{12}
\]

Testing any terminal `q` column of cap `r_i` makes `q` positive, because
`r_i>E`, while `b` is positive already.  It is legal exactly when `a` is
nonpositive, that is,

\[
A\ge0\quad\Longleftrightarrow\quad p_a\le s.    \tag{13}
\]

If (13) holds, **all three** `q` columns are legal.  If it fails, none is
legal.  The census has 270 sibling parents of the first kind.  The six
unique-source bridge parents are exactly the second kind; numerically they
have `E=2` and `A=-1`.

Notice also that `E=0` implies `A>=1`, because `p_b=A+E>0`.

### 2.2 The case `a=q`

Let the two positive colors other than `f` be `g,h`, and put

\[
Q=s+E=p_g+p_h.                                  \tag{14}
\]

Then, in the order `(q,f,g,h)`,

\[
d(P)=(-Q,0,p_g,p_h).                            \tag{15}
\]

A terminal `q` column of cap `r` is a legal sibling exactly when

\[
r\le Q.                                         \tag{16}
\]

Unlike (13), legality need not hold for all three terminal columns.  At the
parent level the 142 states in this case split into 129 with four legal
physical sources, 12 with three, and one with two.

## 3. A strengthened height-7 all-anchor fact

At `z=1`, suppose all three active tops have color `x` and `d_x=-M`.  If
`M>=3`, a source of cap at most `M` must exist.  Indeed, otherwise

\[
F_x=\sum_i r_i-M
    \ge3(M+1)-M=2M+3>7,                         \tag{17}
\]

contradicting the seven available `x` items.  Selecting such a source and
following the anchor corridor either exhausts it or returns to `x` with
strictly larger energy.  This is also an immediate consequence of Debt
Recovery, but (17) is useful for the low-energy boundary: an all-`x` state
with `M=2` can be terminal only when all three caps are exactly 3.

## 4. A sibling whose next event exhausts

Let a legal terminal `q` sibling of cap `r` exhaust first, with final color
`x`.  Let `u,v` be the other two terminal `q` caps.  After this event the
three surviving caps are the bad cap `s` and `u,v`.

### 4.1 If `a != q`, every exhausting sibling branch is safe

The parent has the two permanent anchors `a` and `f` from (12).  The
exhausting update can add its final run to at most one of those colors, so at
least one survives as a nonpositive coordinate at `z=1`.

If `x!=a`, use `a` as the surviving anchor.  The bad source already has top
`a`.  Bring the other two active columns to `a`, unless one exhausts first.
At the resulting all-`a` checkpoint the energy is at least

\[
M_a\ge A+u+v\ge A+2(E+1)\ge3.                  \tag{18}
\]

The last inequality uses `A>=1` when `E=0` and is stronger when `E>=1`.

If `x=a`, then `f` survives.  Bring all three active columns to `f`; the
energy is at least

\[
M_f\ge s+u+v\ge1+2(E+1)\ge3.                  \tag{19}
\]

An intermediate exhaustion is already the goal `z=2`; otherwise Debt
Recovery applies to (18) or (19).  Thus all 270 `a!=q` sibling edges are
safe whenever the chosen sibling's next event is exhausting, independently
of its final color.

### 4.2 If `a=q` and the final color is not `f`, the branch is safe

Here `f` remains a zero-debt anchor.  All three survivors still have top
`q`.  Bring them to `f`, unless one exhausts first.  The resulting energy is
at least

\[
M_f\ge s+u+v\ge3,                               \tag{20}
\]

so this branch is checkpoint-YES.

### 4.3 If `a=q` and the sibling also exhausts to `f`

This is the only low-energy direct-exhaustion branch.  Put

\[
M=Q-r=s+E-r.                                    \tag{21}
\]

After the sibling exhausts, all three surviving tops are `q`, and

\[
d_q=-M,\qquad d_f=7-r>0,\qquad d_g,d_h>0.       \tag{22}
\]

Thus the resulting state is immediately `Tq` precisely when

\[
\min\{s,u,v\}>M.                                \tag{23}
\]

If `M>=3`, Debt Recovery proves YES.  For `M<=2`, condition (23) is the
exact immediate-terminal test.

There is an additional fixed-decoration constraint.  The bad edge already
reserves `7-s` hidden items of color `f`, and this alternative exhausting
sibling would reserve another `7-r`.  Equation (9) says that all seven `f`
items are hidden at `P`.  The two tails coexist in one fixed future exactly
when

\[
(7-s)+(7-r)\le7
\quad\Longleftrightarrow\quad
r\ge7-s.                                        \tag{24}
\]

This is not implied by checking the alternative successor macro state in
isolation.

Under (24), an immediate terminal with `M=2` is impossible.  If it existed,
then `s,u,v>=3`.  Since the `q`-exposed count in `D` gives

\[
r+u+v-E\le7                                    \tag{25}
\]

and `r=s+E-2`, we would have `s+u+v<=9`.  Hence
`s=u=v=3` and `r=E+1`.  But (24) would require `r>=4`, contradicting
`E<=2`.

Consequently the jointly realizable direct terminals are exactly

\[
\begin{array}{ll}
M=0, &\text{or}\\
M=1\text{ and }\min\{s,u,v\}\ge2,
\end{array}                                      \tag{26}
\]

together with (21) and (24).

If `M<=2` but (23) fails, the branch is safe.  The only nontrivial case is
`M=1`, where a surviving cap 1 can be selected.  A return to `q` with old
cap at least 3 raises the energy to at least 3.  A return with old cap 2
raises it to 2.  Were that new all-`q` state terminal, (17) at equality
would force all three caps to be 3.  The selected cap 1 cannot be the bad
cap, since `s=1` and `M=1` would give `r=E`, contrary to `r>E`.  Hence
`E=0`; the two unchanged caps being 3 would force `s=3,r=2`, contradicting
the joint budget `r>=7-s=4`.  Thus another legal source remains and the next
return raises the energy to at least 3.

Here is the implicit low-energy dichotomy used in that paragraph.  If some
color other than `q` is nonpositive, use it as a fresh anchor; bringing all
three columns to it contributes at least three units of energy.  Otherwise
the other three debts are positive, so nonterminality of the all-`q` state
forces a current `q` cap at most `M`.  This is the source used for the return
argument above.

#### Why the macro count is 41/79 but the decoration count is 12

With the stored canonical bad-edge witness, an isolated macro replay finds
41 `a=q` edges and 79 physical sibling-source cards whose exhaustion to `f`
would by itself produce `Tq`.  Of those 79 cards, 67 violate (24): they
cannot coexist with the bad tail that defines the bridge.  They are not
removed by choosing another strategy; they are absent from the joint fixed
decoration universe.

After (24), 12 physical cards remain, on 12 canonical edges and 10 canonical
parents.  Eight have `M=0` and four have `M=1`.  These are precisely the
low-energy direct-terminal corner (26).  If all color-symmetric labeled bad
actions are retained instead of the report's one stored witness, the same
corner has 17 labeled action identities; the canonical-witness count used
here is 12.

For completeness, after reserving both `f` tails the two untouched `q`
columns have residual color counts

\[
\begin{aligned}
R_q&=7-r-u-v+E,\\
R_f&=s+r-7,\\
R_g&=7-p_g,\\
R_h&=7-p_h.
\end{aligned}                                    \tag{27}
\]

They sum to `14-u-v`.  The first is nonnegative by (25), the second exactly
by (24), and

\[
R_g+R_h=14-(s+E)\ge6.                            \tag{28}
\]

Thus the two residual words can both start with a non-`q` color.  In this
normal form, (24) is the exact extra decoration-level obstruction, rather
than merely a necessary color count.

## 5. A sibling whose next event is live

Let the live event be

\[
q_r\longrightarrow x_R,\qquad r<R<7.          \tag{29}
\]

### 5.1 Exact handoff criterion to the original bad exhaustion

Testing the bad source after (29), and using (8), gives

\[
T_B=d(D)-(7-s)e_f+r e_q-r e_x.                 \tag{30}
\]

The `q` coordinate is `r-E>0`.  If `x=f`, the two other positive
coordinates of `D` remain positive, so (30) has three positive coordinates
and the bad source is illegal at `z=0`.

If `x` is one of the two positive colors different from `f`, say its
terminal debt is `p_x`, then (30) has at most two positive coordinates
exactly when

\[
r\ge p_x.                                       \tag{31}
\]

Therefore the live-to-bad handoff is legal exactly under (31), with
`x!=f`.

After taking the bad exhaustion, live and exhausting debt updates commute,
and the `z=1` state is

\[
C=D+r e_q-r e_x.                                \tag{32}
\]

It has active tops `x_R,q_u,q_v` and debts

\[
d_x(C)=-(r-p_x)=-N,\qquad
d_q(C)=r-E>0,                                   \tag{33}
\]

while the other two non-`x` debts are positive.  Hence

\[
N=r-p_x.                                        \tag{34}
\]

If `N>=3`, Debt Recovery immediately proves checkpoint-YES.

### 5.2 The exact low-energy handoff corner

For `N<=2`, use `x` as an anchor and advance the two `q` columns to `x` or
to exhaustion.  If their old caps at first entry into `x` are `c_1,c_2`,
the all-`x` energy is

\[
M=N+c_1+c_2\ge N+2(E+1).                       \tag{35}
\]

Debt Recovery handles `M>=3`.  Equality below 3 is possible only when

\[
E=0,\qquad N=0,\qquad c_1=c_2=1.               \tag{36}
\]

Thus `r=p_x`, the two remaining terminal `q` caps are both 1, and their
entries into `x` are direct.  At energy 2, an all-`x` terminal would have to
have caps exactly `(3,3,3)` by (17).  Consequently the full corner is

\[
\begin{gathered}
E=0,\quad r=p_x,\quad u=v=1,\\
q_r\to x_3,\quad q_1\to x_3,\quad q_1\to x_3.
                                                        \tag{37}
\end{gathered}
\]

The last entrance in (37) is a **unique-source** same-level `Tq` entrance.
Immediately before it, `d_x=-1`; testing either existing `x_3` source makes
all four coordinates positive, whereas the final `q_1` source is legal.
Therefore the same-level sibling lemma does not eliminate (37).  If the
all-`x` state is not terminal, a cap at most 2 remains legal and one more
anchor cycle raises the energy to at least 3.

The color accounting in (37) is tight rather than spurious: `F_x(P)=p_x=r`,
and the three displayed `x` runs consume

\[
(3-r)+2+2=7-r
\]

hidden `x` items, exactly the remaining supply.

## 6. Live events without a bad-source handoff

### 6.1 Persistence when `a != q`

At a parent of form (12), an untouched `q_u` sibling remains legal after
any live event (29).  Before the event its source test already has positive
`q` and `b` coordinates.  The change `+r e_q-r e_x` cannot introduce a new
positive coordinate at `q`, and the subtraction cannot introduce one
anywhere.  Thus all untouched `q` siblings persist.

The colors `a` and `f` remain nonpositive anchors.  A moved column whose top
is neither can be followed until it exhausts or first reaches `a` or `f`.
Process the three `q` siblings in this way.  If one exhausts during this
first sweep, one of `a,f` survives at `z=1`.  Bringing the two other sibling
columns to `a` gives the lower bound (18), or bringing all three survivors
to `f` gives (19); hence that branch is safe.

If no sibling exhausts, all four active tops lie in `{a,f}`.

### 6.2 The two-anchor reduction

Consider a `z=0` state with

\[
d_\alpha=-A\le0,\qquad d_\beta=-B\le0,         \tag{38}
\]

and all active tops in `{alpha,beta}`.  If the other two debts are positive,
an `alpha` source of cap `c` is legal exactly when `c<=A`, and a `beta`
source is legal exactly when `c<=B`.

If those two debts are not both positive, there is at most one positive
coordinate.  Then the still-reserved bad source is legal.  In this bridge
application its old and final colors are exactly the two original anchors.
Exhaust it immediately; the third nonpositive coordinate is untouched and
survives at `z=1`.

It remains to iterate only in the region where the two non-anchor debts are
positive.  Choose a legal anchor source.  If it is the reserved bad source,
its next event exhausts and gives the first outcome below.  Otherwise its
live departure leaves its old anchor nonpositive.  If it enters a
non-anchor color, the other anchor is also unchanged, so the same column can
be followed until it exhausts or first returns to `{alpha,beta}`.  At an
all-anchor checkpoint the total anchor energy never decreases; it increases
strictly whenever the excursion has a non-anchor intermediate run.  Every
event strictly advances a fixed finite run chain.

It follows that this procedure has only two possible `z=0` outcomes:

1. a first exhaustion is reached; or
2. an all-anchor state has no legal source.

The second outcome is exactly a `D2` terminal.  In exact coordinates it has

\[
d=(-A,-B,X,Y),\qquad A+B=X+Y,qquad X,Y>0,       \tag{39}
\]

all tops in the two anchor colors, and

\[
\begin{array}{ll}
c>A &\text{for every `alpha`-top cap }c,\\
c>B &\text{for every `beta`-top cap }c.
\end{array}                                      \tag{40}
\]

The host multiplicities are `3+1` or `2+2`.  For a putative `4+0` terminal,
the unused anchor has no host and hence cannot have negative debt, so its
energy is zero.  The occupied anchor energy is then `X+Y>=2`.  Four caps
strictly above that energy would give
`F>=4(A+1)-A=3A+4>=10`, contradicting `F<=7`.

This is a genuine residual family, not an artifact of the inequalities.  For
example, the normal-form parent

\[
d_P=(0,0,-1,1),qquad
\text{tops }q_1,q_1,q_1,a_6                       \tag{41}
\]

can have its three `q` runs enter `a_3,f_3,f_3`.  The resulting state has

\[
d=(3,1,-2,-2),\qquad
\text{anchor caps }(6,3)\text{ and }(3,3),       \tag{42}
\]

and every source test has three positive coordinates.  The macro state is
physically consistent.  It also respects the reserved bad tail in the
displayed instance: the bad tail uses one `f`, and the two `q_1->f_3` runs
use four more.

For the **first** `a!=q` sweep, a terminal can only have multiplicity `2+2`.
Indeed, suppose `m` of the three siblings first enter `a`.  The anchor
energies are

\[
A'=A+\sum_{i\to a}c_i,qquad
B'=\sum_{j\to f}c_j,                             \tag{43}
\]

where every entry cap is greater than `E`.

- If `m=0`, the three `f` sources give `B'>=3`; if all their caps exceeded
  `B'`, then `F_f>=2B'+3>7`.
- If `m=2`, then `A'>=3` (using `A>=1` when `E=0`); the three `a` sources
  similarly give `F_a>7`.
- If `m=3`, the four-`a` bound is even stronger.

Thus `m=1`.  With one sibling entering `a` at old cap `c_a` and two entering
`f` at old caps `c_1,c_2`, the exact first-sweep `D2` conditions are

\[
\begin{gathered}
A'=A+c_a,\qquad B'=c_1+c_2,\\
d_q>0,qquad d_b>0,\\
s>A',\quad R_a>A',\quad R_{f,1}>B',\quad R_{f,2}>B'.
                                                        \tag{44}
\end{gathered}
\]

The first inequality also says `c_a<p_a`.  Joint compatibility with the
still-reserved bad tail requires

\[
(R_{f,1}-c_1)+(R_{f,2}-c_2)\le s.               \tag{45}
\]

Equations (39)-(45), rather than a claim of automatic solvability, are the
precise `D2` remainder of this branch.

### 6.3 What changes when `a=q`

For an untouched `q_u` source after (29), persistence is not automatic.
From (15), it remains legal exactly when

\[
\begin{cases}
r+u\le Q, & x=f,\\
r+u\le Q\ \text{or}\ r\ge p_x, & x\in\{g,h\}.
\end{cases}                                      \tag{46}
\]

If `x` is `g` or `h`, the moved source itself is legal and can be followed
through the two-anchor corridor with anchors `q,f`.

If `x=f`, the state immediately has

\[
d_q=-(Q-r),\qquad d_f=-r,\qquad d_g,d_h>0,       \tag{47}
\]

with one `f_R` source and the three remaining `q` sources.  The `f_R` source
is illegal because `R>r`.  A remaining `q` cap `c` is legal exactly when
`c<=Q-r`.  The bad cap is never such a source, since

\[
s-(Q-r)=r-E>0.                                  \tag{48}
\]

Therefore (47) is an immediate `D2` terminal of multiplicity `3+1`
precisely when the two other terminal caps satisfy

\[
u>Q-r,qquad v>Q-r.                              \tag{49}
\]

At decoration level the new live `f` run and the reserved bad tail coexist
only when

\[
R-r\le s.                                       \tag{50}
\]

If (49) fails, a legal `q` source remains and the same two-anchor reduction
continues.  It may still terminate at a later `D2`; no lemma in this note
eliminates that terminal.

## 7. What happens after a first exhaustion from a two-anchor path

Every legal exhaustion produced by the two-anchor procedure reaches a `z=1`
state with at least one nonpositive coordinate.  Indeed, immediately before
the final run is exposed, the source-test vector in (1) has at most two
positive coordinates.  The final run increases only its own color
coordinate, so the successor has at most three positive coordinates.  This
argument does not require the old anchor itself to remain nonpositive.

Using that coordinate as an anchor, advance every non-anchor-top source to
the anchor or to exhaustion.  If the resulting all-anchor energy is at least
3, Debt Recovery finishes.  If a second coordinate is nonpositive, use it as
a new anchor: bringing the three active columns to it, unless one exhausts,
creates energy at least 3.  We may therefore assume that the other three
debts are positive.  In that case a nonterminal all-anchor state of energy
`M` has a source cap at most `M`; otherwise all four source-test coordinates
would be positive.  For `M=2`, one departure and return raises the energy to
at least 3.  For `M=1`, the first return raises it to at least 2 and, if the
state is still nonterminal, one more return raises it to at least 3.  Thus at
energy at most 2 the only possible failures are:

1. the first exhausting event itself has produced an all-top-equal `Tq`
   terminal; or
2. the anchor corridor enters a `Tq` terminal through a same-level
   **unique-source** edge, characterized by `p_x>r`.

A same-level sibling entrance is removed by the existing sibling-entry
lemma.  A nonterminal all-anchor state of energy 2 gains energy at the next
return; an energy-1 state can require two returns, and the only terminal
created on the first return is exactly the same-level `Tq` case just listed.

Thus a live non-handoff branch is rigorously reduced to `D2` before the first
exhaustion, plus direct or unique-source low-energy `Tq` after it.  This note
does not identify those residual cases with YES.

## 8. Reduction ledger

| Branch | Strict conclusion | Input used |
|---|---|---|
| `a!=q`, sibling next event exhausts | YES | surviving anchor, energy bounds (18)-(19), Debt Recovery |
| `a=q`, sibling exhausts to `x!=f` | YES | zero `f` anchor, (20), Debt Recovery |
| `a=q`, sibling exhausts to `f`, `M>=3` | YES | Debt Recovery |
| same branch, `M<=2`, not immediately terminal | YES | low-energy anchor rotor plus joint budget (24) |
| same branch, joint immediate terminal | unresolved 12-card corner (26) | exact fixed-decoration count |
| live sibling, bad handoff, `N>=3` | YES | exact handoff (31), Debt Recovery |
| live handoff, `N<=2` | YES except the unique corner (37) | anchor corridor and same-level entrance test |
| live branch without handoff | reduces to `D2`, then possible low-energy unique `Tq` after exhaustion | two-anchor reduction and sibling-entry lemma |

The unresolved objects are therefore explicit:

- jointly realizable `D2` terminals satisfying (39)-(40), including the
  first-sweep `2+2` conditions (44)-(45) and the `a=q` `3+1` condition
  (47)-(50);
- the 12-card direct-exhaustion `Tq` corner (26);
- the unique-source same-level `Tq` corner (37), and any later unique-source
  `Tq` entrance described in Section 7.

Eliminating those objects needs an additional argument or an exact fixed-word
classification.  Nothing in this note promotes the reduction to a proof of
the whole first-exhaustion bridge family, still less to a proof for all
height-7 layouts.
