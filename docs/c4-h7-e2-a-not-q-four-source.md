# The `E=2`, `a!=q` four-source continuation

## Scope and conclusion

This note eliminates exactly the `E=2` **A-form** part of the
first-exhaustion `D2`-reduction ledger.  It covers

\[
 18\text{ active bridge edges},\qquad
 1{,}369\text{ next-card decorations},\qquad
 57{,}090\text{ compatible residual words}.                 \tag{1}
\]

Every fixed residual word in (1) has a continuation from its `z=0` bridge
parent to `z=2`.  The proof first takes the three already committed sibling
cards, then uses a finite macro-card induction.  It never expands a hidden
word.  The induction leaves one decoration of weight six; a two-cell
pigeonhole argument closes all six of its words.

This conclusion does **not** cover the `a=q` Q-form, any other energy, or all
height-seven layouts.

## 1. Normal form and the three committed cards

Use parent-coordinate colours `(q,f,a,b)`.  The bad first-exhausting event is

\[
       a_s\longrightarrow f_7,
\]

and the three sibling sources are `q_3,q_3,q_3`.  Energy-two saturation gives

\[
 F_q=7,
 \qquad
 d(P)=(-2,0,-A,A+2),
 \qquad A\ge0.                                      \tag{2}
\]

In particular, no fixed suffix contains a hidden `q` item.  A decoration in
the A-form `D2`-reduction slice commits three live cards

\[
 q_3\longrightarrow t_i{}_{R_i},
 \qquad t_i\in\{f,a,b\},
 \qquad 4\le R_i\le6.                              \tag{3}
\]

All three cards in (3) may be taken, in any order.  Initially a `q_3` test
has positive coordinates only at `q` and `b`.  Every card adds three to the
already tested `q` coordinate and subtracts three from one non-`q`
coordinate.  Thus it cannot create a new positive non-`q` coordinate, and
every untouched `q_3` source remains legal.

Let `n_f,n_a,n_b` be the target multiplicities in (3).  After all three
cards the debt is

\[
 d(M)=\bigl(7,-3n_f,-A-3n_a,A+2-3n_b\bigr).          \tag{4}
\]

There is always a legal source at `M`.

- If the bad `a_s` source is legal, take it.
- Otherwise its test has three positive coordinates.  Since the `f`
  coordinate in (4) is nonpositive, those coordinates are `q,a,b`.
  If `n_b>0`, any `b`-top sibling is legal.  If `n_b=0,n_f\ge2`, the
  `f`-energy is `3n_f\ge6`, so an `f` source of cap at most six fits.  In the
  remaining case `n_a\ge2`, and the `a`-energy
  `A+3n_a\ge6` similarly fits an `a` source.

This elementary argument is useful independently of the finite audit: the
all-card macro never starts at a terminal state.

## 2. Why the first exhaustion is enough

At `M` all three sibling caps are at least four, and later live events only
increase caps.  If the bad column exhausts first, all three siblings survive,
so any two of them have cap sum at least eight.  If a sibling exhausts first,
the other two siblings survive with the same lower bound.

The terminal-triple/pair-cap corollary at `z=1` says that two current caps
whose sum is at least seven rule out a non-goal terminal; every maximal legal
continuation then reaches `z=2`.  Consequently every first exhaustion after
the macro (3) is a certified winning leaf.

The only possible obstruction is therefore a `z=0` `D2` terminal reached
before any column exhausts.

## 3. Exact macro completion, without words

At a macro checkpoint store only

\[
 S=(d;\ (x_i,c_i)_{i=1}^3;\ H),                  \tag{5}
\]

where `(x_i,c_i)` are the three **labelled** sibling tops and caps, and `H`
is their aggregate remaining colour inventory.  The bad event
`a_s -> f_7` stays fixed and is not part of `H`.  Each sibling has
`L_i=7-c_i>=1` cells left.

A fixed completion of (5) consists of three labelled words `w_i`, with

\[
 |w_i|=L_i,qquad w_i[0]\ne x_i,qquad
 \sum_i \#w_i=H.                                  \tag{6}
\]

Its exact count can be written using only the three boundary cells:

\[
 C(S)=
 \sum_{\substack{y_i\ne x_i\\H-\sum_i e_{y_i}\ge0}}
 \frac{(\sum_i(L_i-1))!}
      {\prod_c(H_c-\#\{i:y_i=c\})!}.              \tag{7}
\]

The checker independently recomputes (7) by assigning an exact histogram to
each labelled word and subtracting the words whose first cell has its
forbidden colour.  It also checks the equivalent Hall conditions

\[
 \#\{i:x_i=c\}\le \sum_{u\ne c}H_u
 \quad\text{for every colour }c.                  \tag{8}
\]

Thus an aggregate inventory is never accepted merely because its total
histogram is nonnegative.  Every boundary prohibition remains attached to
the same physical column.

Suppose sibling `i` is selected at `(x,c)`.  Its actual next maximal run has
some colour `y!=x` and length `l`.

- If `l=7-c`, the column exhausts and Section 2 applies.
- If `l<7-c`, the macro successor is

  \[
  d'=d+c(e_x-e_y),\qquad
  (x,c)\mapsto(y,c+l),\qquad
  H'=H-l e_y.                                      \tag{9}
  \]

  The run is maximal only if the next cell of this **same** column differs
  from `y`; this is precisely the new boundary condition used in (6)-(8).

Only successors with `C(S')>0` are retained.  Equation (9) increases one
cap, so the macro graph is a finite DAG.

## 4. The quantified macro induction

Define `W(S)` recursively.

1. If the fixed bad source is legal, then `W(S)` is true by exhausting it.
2. Otherwise `W(S)` is true if there is a legal sibling `i` such that, for
   **every** same-column next card of `i` admitted by (6)-(9), that card
   either exhausts the column or has a successor `S'` with `W(S')`.

The quantifiers in item 2 are deliberately strong:

\[
 \exists\text{ source }i\quad
 \forall\text{ compatible fixed next cards of }i.             \tag{10}
\]

The physical future is fixed; it is not allowed to change after a choice.
The universal quantifier in (10) is just an induction device.  The actual
next card of every fixed word satisfying (6) is one of the audited cards,
and after a live card the untouched remainder satisfies the exact successor
conditions.  Induction on the total remaining cap distance therefore proves
that `W(S)` supplies one policy valid for every fixed completion of `S`.
It is stronger than a future-aware strategy because it chooses the source
before reading that source's next card.

## 5. Exact finite result

The independent checker rebuilds 21 A-form energy-two bridge edges.  Exactly
18 have a nonempty A-form `D2`-reduction slice.  It selects that slice by the
specialized one-card condition: all three cards are live and the bad source
remains illegal after each individual card.  This agrees decoration by
decoration with the earlier independent fork ledger.

The macro induction gives

| class | decorations | residual-word weight |
|---|---:|---:|
| `W(S)` proved by (10) | 1,368 | 57,084 |
| not proved by the uniform online induction | 1 | 6 |
| **total A-form `E=2` slice** | **1,369** | **57,090** |

Across all roots, memoization visits exactly 3,387 labelled macro states.
This is a next-card/cap/balance enumeration, not a residual-word enumeration.

## 6. The unique six-word corner

The only root not certified by the strong online induction is, in normalized
coordinates,

\[
\begin{aligned}
 d(P)&=(-2,0,0,2),& a_s&=a_6,\\
 (q_3\to t_i{}_{R_i})_{i=1}^3
   &= (q_3\to f_5)^3,&
 H&=(0,0,1,5).
\end{aligned}                                             \tag{11}
\]

After the three cards,

\[
 d(M)=(7,-9,0,2),
 \qquad (x_i,c_i)=(f,5)^3.                       \tag{12}
\]

Each labelled sibling has exactly two cells left.  Those six cells contain
one `a` and five `b`, so at most one of the three two-cell tails contains the
single `a`.  At least two entire tails are therefore `bb`.  In any fixed
future choose one of those columns; its visible next maximal card is

\[
                f_5\longrightarrow b_7,
\]

which exhausts it immediately.  The two untouched siblings still have caps
`5+5=10`, so Section 2 finishes.  Formula (7) gives six fixed completions,
and the same pigeonhole argument covers all six at once.

Combining Sections 4 and 6 proves that every one of the 57,090 fixed residual
words in (1) is checkpoint-YES.  No claim is made about the separate Q-form
slice.

## 7. Reproducible audit

Run

```text
python tests/check_c4_h7_e2_a_not_q_four_source.py
```

The checker asserts the edge/decorations/weight ledger, the two independent
completion counts, Hall equivalence, same-column maximal-run updates, the
3,387-state macro induction, and the exact one-decoration/six-word corner.
