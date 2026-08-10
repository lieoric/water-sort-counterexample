# Critical pairs and a past--future bypass at `c=4, h=7, k=2`

## Scope and claim boundary

This note gives a local exchange calculus for fixed border events and applies
it to the four-legal-source, all-`q`/all-`f` star that can precede a first
exhaustion `Tq` terminal.  It proves two facts.

1. Whether one live event disables another source has an exact three-clause
   test.  In particular, a direct two-color swap cannot be a mutual lock.
2. At height seven, an all-`q`/all-`f` four-way star has either a forward
   executable square or an explicit zero-debt past-prefix bypass.  The only
   combinatorial corner of the past argument is a rigid `Q=7` pattern, and it
   also has an explicit weave.

The second statement is deliberately a **local bypass theorem**.  Its output
is a legal state with a legal continuation; it does not say that this
continuation reaches `z=2`.  A later `D2` or `Tq` obstruction may still occur.
Thus this note neither eliminates the full three-/four-source `D2` remainder
nor proves universal solvability at height seven.

## 1. Border events as guarded commuting vectors

For a border state write

\[
 d_c=F_c-G_c,
\]

and let `z` be the number of exhausted original columns.  A physical source
of top color `x` and exposed host capacity `s` is legal exactly when

\[
 \left|\operatorname{Pos}(d+s e_x)\right|\le K,
 \qquad K=2+z,                                      \tag{1}
\]

where `Pos(v)={c:v_c>0}`.  A live event

\[
 A=(x_s\longrightarrow y_R),\qquad x\ne y,quad s<R<7,
\]

has debt vector

\[
 v_A=s(e_x-e_y).                                  \tag{2}
\]

Events on distinct original columns have fixed continuations and their debt
vectors add commutatively.  What can fail to commute is only the legality of
the intermediate vertex.

### Critical-pair lemma

Let `B` be a distinct source of top color `u` and cap `t`, and put

\[
 w=d+t e_u.                                      \tag{3}
\]

Assume `B` is legal before `A`.  Then taking the live event `A` makes `B`
illegal if and only if

\[
\begin{aligned}
 |\operatorname{Pos}(w)|&=K,                    &&\tag{4a}\\
 w_x&\le0<w_x+s,                                 &&\tag{4b}\\
 w_y&\le0\quad\text{or}\quad w_y>s.             &&\tag{4c}
\end{aligned}
\]

**Proof.**  The source test after `A` is

\[
 w+s e_x-s e_y.                                  \tag{5}
\]

Only coordinate `x` can become newly positive, while subtracting at `y` can
only delete a positive coordinate.  Hence a legal support can grow past `K`
only by starting with exactly `K` positives, crossing zero at `x`, and not
losing a positive at `y`.  These are exactly (4a)--(4c).  Conversely those
three conditions increase the positive support from `K` to `K+1`.  QED.

This is a dynamic trace relation: two distinct live events form an
executable commuting square precisely when neither corresponding instance of
(4) holds.

### Mutual live locks at `z=0`

Consider live events `A=(x_s -> y)` and `B=(u_t -> v)` which are both legal
at `z=0` and mutually disable one another.

If `x=u`, put `E=-d_x`.  Applying (4b) in the two directions gives

\[
 \max(s,t)\le E<s+t.                              \tag{6}
\]

The tested `x` coordinate is nonpositive in both directions, so exactly two
of the other three debts are positive and the third is nonpositive.  By
(4c), each target is either that common nonpositive anchor or a positive
coordinate whose debt is strictly larger than the corresponding old cap.

If `x!=u`, then

\[
 -s<d_x\le0,
 \qquad
 -t<d_u\le0.                                     \tag{7}
\]

Exactly one of the remaining two colors has positive debt; call it `p`, and
call the other nonpositive color `n`.  Each target must be one of:

- the common nonpositive color `n`;
- the positive reservoir `p`, with debt larger than the action cap; or
- the other action's old color, with enough positive surplus after its own
  source test.

In particular, the direct swap

\[
 x_s\longrightarrow u,
 \qquad
 u_t\longrightarrow x                              \tag{8}
\]

cannot be a mutual lock.  If the first action disabled the second, (4c)
would require `d_u+t>s`; the reverse disabling would require `d_x+s>t`.
Since `d_x,d_u<=0`, these imply both `t>s` and `s>t`.

The same direct-swap corollary holds at `z=1`.  There the distinct old colors
are the two nonpositive anchors and the remaining two colors are positive.

### First-exhaustion version

Let

\[
 A=(x_s\xrightarrow{\text{final }y^{7-s}}\varnothing)
\]

be the first exhausting event.  Its debt increment is

\[
 s e_x+(7-s)e_y,                                  \tag{9}
\]

and the threshold rises from two to three.  For a different source `B`, with
`w` as in (3), `A` disables `B` if and only if

\[
\begin{aligned}
 |\operatorname{Pos}(w)|&=2,\\
 w_x&\le0<w_x+s,\\
 w_y&\le0<w_y+(7-s).                              \tag{10}
\end{aligned}
\]

Indeed, two distinct coordinates are added and the threshold gains one, so
illegality is possible exactly when both additions create new positives on
top of an already saturated two-positive test.

There is also a useful inventory charge.  If the final `f` tail of the bad
source and `m` live sibling entries into `f` coexist in one fixed future,
with live run lengths `ell_i>=1`, then

\[
 (7-s)+\sum_{i=1}^m\ell_i\le7,
 \qquad\text{hence}\qquad
 \sum_i\ell_i\le s\quad\text{and}\quad m\le s.   \tag{11}
\]

Thus a four-way common-`f` lock (`m=3`) is impossible for `s<=2`.  It is not
impossible at height seven: `s=3` and three singleton `f` runs saturate the
budget exactly.  Section 4 gives such an example.

## 2. The four-source all-`q`/all-`f` star

Use colors `(q,f,g,h)`.  The all-`q` parent of a same-source-color first
exhaustion bridge has

\[
 d(P)=(-Q,0,p_g,p_h),
 \qquad
 Q=p_g+p_h=s+E,                                  \tag{12}
\]

where `s` is the bad cap, `0<=E<=2`, and the bad event exhausts to
`f^{7-s}`.  Let the three sibling caps be `c_1,c_2,c_3`.  In the all-`f`
star considered here, each sibling's fixed next event is live into `f`.
All four sources are legal, so their caps are at most `Q`; the three sibling
caps also satisfy `c_i>E`, because they survive in the terminal `Tq` child.

The exposed `q` count is

\[
 F_q=s+c_1+c_2+c_3-Q=c_1+c_2+c_3-E\le7.         \tag{13}
\]

Since all four current tops are `q`, there are no `f`, `g`, or `h` hosts.
Consequently the four already exposed physical prefixes contain

\[
 F_f=0,
 \qquad F_g=p_g,
 \qquad F_h=p_h.                                 \tag{14}
\]

In particular, their total non-`q` mass is exactly

\[
 F_g+F_h=Q,                                      \tag{15}
\]

and it consists only of `g` and `h`.  Every prefix ends in `q`.

### The forward cap-sum alternative

After a live sibling of cap `c_i` enters `f`, the two anchor energies are

\[
 A_q=Q-c_i,
 \qquad A_f=c_i.                                 \tag{16}
\]

An untouched `q` sibling of cap `c_j` remains legal exactly when

\[
 c_j\le Q-c_i
 \quad\Longleftrightarrow\quad
 c_i+c_j\le Q.                                  \tag{17}
\]

Thus (17) gives an executable forward square and, in particular, the first
entry does not land in an immediate `D2` terminal.

Moreover, if no pair of sibling caps satisfies (17), then `Q<=7`.  The only
possible larger value is `Q=8`.  Since `s<=6` and `E<=2`, it forces
`s=6,E=2`.  Equations (13) and `c_i>E` then give

\[
 3\le c_i,
 \qquad c_1+c_2+c_3\le9,
\]

so `c_1=c_2=c_3=3`, and every sibling pair has sum `6<=8`, a contradiction.

### Solo-prefix lemma

Let `u` be one column's already exposed word in initial-top to current-border
order.  Suppose that `u` uses at most two colors.  Starting at zero debt, all
past border events of this one column may be performed before any other
column's past event.

To see this, stop at any current source in `u`, of top color `a` and cap
`r`.  Let `n_c` count exposed occurrences of color `c` in the corresponding
prefix of `u`.  This one column contributes

\[
 d_c=n_c-r[c=a].                                 \tag{18}
\]

Its source test adds back `r e_a` and is exactly the nonnegative count vector
`n`.  Its positive support is therefore the set of colors seen so far, of
size at most two.  This proves every event legal, including the source test
at the final `q` gate.

If the forward cap-sum alternative is absent, `Q<=7`.  Were all four exposed
prefixes to contain both `g` and `h`, (15) would be at least eight.  Hence at
least one prefix uses only `q` and at most one of `{g,h}` and is covered by
the solo-prefix lemma.

### When the naive early `q -> f` is itself terminal

Let a two-color prefix use `q` and `x` and omit the other color `y`.  Perform
it solo and immediately take its fixed `q -> f` event.  This may be either a
live sibling event or the bad exhaustion.

If it is live, with `m` exposed `x` items and `k` exposed `q` items, the
successor debts are

\[
 (d_q,d_f,d_x,d_y)=(k,-(k+m),m,0).              \tag{19}
\]

If it is the bad exhaustion, the successor has `z=1` and

\[
 (d_q,d_f,d_x,d_y)=(k,7-k-m,m,0).               \tag{20}
\]

For `m=0` neither state is terminal.  For `m>0`, (19) is an immediate `D2`,
or (20) an immediate `Tq`, exactly when all three other initial top colors
are `y`.  Any source already topped by a positive color remains legal.

If a second two-color prefix exists in this exceptional situation, its top
is `y`, so it omits `x`.  Choosing that second prefix instead leaves at least
two of the other sources topped by the now-positive color `y`; the early
event is not terminal.  Thus the only case not already bypassed has exactly
one two-color prefix.

By (15), this forces the following rigid pattern:

\[
 Q=7;                                            \tag{21}
\]

- the unique two-color prefix `A` contains exactly one `x` and no `y`;
- each other prefix contains exactly one `x` and one `y`; and
- all three other prefixes start with their unique `y`.

### The rigid `Q=7` weave

Choose one of the other prefixes and call it `B`.  It has the form

\[
 B=yq^a xq^b,
 \qquad a\ge0,quad b\ge1.                       \tag{22}
\]

Advance `B` only until its unique `x` becomes the current top.  If `a=0`
this is the single event `y_1 -> x_2`; otherwise it is
`y_1 -> q_{a+1} -> x_{a+2}`.  Both source tests see at most `y,q` and are
legal.  At that point `B` contributes, in order `(q,f,x,y)`,

\[
 d^{B}=(a,0,-a-1,1).                             \tag{23}
\]

Now perform all of `A`'s past events.  In any source test, let `n_q,n_x` be
the exposed counts of `A` so far.  Since `A` contains only one `x`, the test
vector is

\[
 d^{B}+(n_q,0,n_x,0),                            \tag{24}
\]

whose `x` coordinate is at most `-a` and whose only possible positive
coordinates are `q` and `y`.  Every event of `A`, and its final `q -> f`
source test, is therefore legal.

Let `c` be `A`'s cap at its `q` gate.  Immediately before the `q -> f`
event, the debts are `(a-1,0,-a,1)`.  If `A` is a live sibling, afterward

\[
 d=(a+c-1,-c,-a,1),qquad z=0.                  \tag{25}
\]

If `A` is the bad source of cap `s=c`, afterward

\[
 d=(a+s-1,7-s,-a,1),qquad z=1.                \tag{26}

The two untouched prefixes still start with `y`.  Since `d_y=1`, their
source tests have respectively two positives in (25) and three positives in
(26).  They are legal.  Thus neither woven successor is terminal.

### Past--future bypass theorem

For a height-seven all-`q` parent (12) with four legal sources and a fixed
all-`f` star below it, at least one of the following holds.

1. Two sibling caps have sum at most `Q`; taking the first live entry leaves
   the second source legal.
2. From the true zero-debt past, a legal prefix schedule takes one of the
   star's `q -> f` events before reaching the all-`q` parent and lands in a
   state with another legal source.

**Proof.**  If (17) holds, use the forward square.  Otherwise `Q<=7`, so a
two-color prefix exists by (15).  Its solo early event works unless it has
the exceptional terminal form described above.  A second two-color prefix
then gives a nonterminal choice.  With exactly one such prefix, (21)--(26)
give the rigid weave.  QED.

This theorem proves that the displayed local star is not an unavoidable
one-step barrier from its zero-debt past.  It does **not** prove that the
state produced in item 1 or 2 is checkpoint-YES.

## 3. A tight four-way local lock at height seven

The following balanced instance shows why the qualifier above is necessary.
Colors `q,f,g,h` are encoded as `0,1,2,3`; columns are written bottom to top.

```text
height=7
colors=4
empty=2
column=2221032
column=3321023
column=3321003
column=1111000
```

In top-to-bottom order the four words are

```text
ghqfggg
hgqfghh
hqqfghh
qqqffff
```

Each color occurs seven times.  The legal past event sequence

```text
0,1,0,1,2
```

is

```text
g1 -> h2,
h1 -> g2,
h2 -> q3,
g2 -> q3,
h1 -> q3.
```

It reaches

\[
 d(P)=(-5,0,2,3),
 \qquad \text{tops }q_3,q_3,q_3,q_3.             \tag{27}
\]

All four sources are legal.  Exhausting the last column through `f^4`
gives

\[
 z=1,qquad d=(-2,4,2,3),qquad\text{tops }q_3^3,
\]

an immediate `Tq` terminal.  Taking any of the other three `q_3 -> f_4`
events gives

\[
 z=0,qquad d=(-2,-3,2,3),
 \qquad\text{tops }f_4,q_3,q_3,q_3,
\]

an immediate `D2` terminal.  The common `f` inventory is tight:
`4+1+1+1=7`.

Nevertheless the initial layout is YES.  One complete legal border sequence
is

```text
0,0,1,0,2,2,0,1,1,1,1,2,2,3.
```

Its decisive beginning is

\[
\begin{array}{c|c}
\text{event}&d=(q,f,g,h)\\ \hline
0:g_1\to h_2&(0,0,1,-1)\\
0:h_2\to q_3&(-2,0,1,1)\\
1:h_1\to g_2&(-2,0,0,2)\\
0:q_3\to f_4&(1,-3,0,2).
\end{array}
\]

The trap path first makes both `g` and `h` positive and only then enters
`f`.  The bypass keeps `g` suppressed at zero and moves `q_3 -> f_4` early.
This is the concrete mechanism behind the solo-prefix and rigid-weave
arguments: control the zero-debt past so that the second positive color has
not yet activated when the new anchor is entered.

## 4. Independent finite checks

`tests/check_c4_h7_critical_pair_bypass.py` performs no large instance
enumeration.  It independently:

- exhausts small integer boxes to compare (4) and (10) with direct positive
  support counts;
- checks the mutual-lock consequences and the impossibility of (8);
- enumerates the height-seven cap constraints behind the `Q=8` argument and
  the color charge (11);
- enumerates all `Q<=7` distributions of `g,h` over four prefixes and checks
  the unique rigid `Q=7` corner;
- checks the rigid weave for every small word of the stated form; and
- replays the displayed instance, its route to (27), all four terminal
  children, and the complete winning border sequence.

