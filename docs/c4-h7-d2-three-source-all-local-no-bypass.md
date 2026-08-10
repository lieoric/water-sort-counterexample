# Zero-debt bypasses for all three-source `D2` local residuals

## Scope and claim boundary

The completed `c=4,h=7,k=2` three-legal-source checkpoint experiment checks
1,106,490 labelled fixed futures.  It reports 1,091,706 local `YES` rows and
14,784 local `NO` rows.  The latter occur on seven bridge edges:

| edge | local `NO` | parent debt | bad cap | sibling `q` caps |
| ---: | ---: | --- | ---: | --- |
| 116 | 210 | `(-4,0,1,3)` | 4 | `1,1,5` |
| 117 | 252 | `(-4,0,2,2)` | 4 | `1,1,5` |
| 184 | 462 | `(-3,0,1,2)` | 2 | `2,2,4` |
| 236 | 924 | `(-2,0,1,1)` | 2 | `1,1,3` |
| 242 | 11,088 | `(-2,0,1,1)` | 2 | `1,2,3` |
| 244 | 924 | `(-2,0,1,1)` | 2 | `1,2,4` |
| 248 | 924 | `(-2,0,1,1)` | 2 | `2,2,3` |

This note restores every balanced zero-debt past compatible with these rows
and proves that each such initial layout has a legal route to two exhausted
original columns.  The proof uses only the displayed parent data and a few
next-run facts shared by the corresponding local-`NO` family; it is uniform
over the remaining hidden future.

Together with the production local-`YES` result, this removes the selected
three-source checkpoint family as a source of global counterexamples.  It
does **not** show that every height-seven checkpoint belongs to this family,
does not eliminate other source-count families, and is not a proof of the
full height-seven theorem.

## 1. Border and prefix calculus

Use colors `q,f,g,h`.  A source of color `x` and accumulated cap `s` is legal
at debt `d` and exhaustion count `z` exactly when

\[
 \left|\operatorname{Pos}(d+s e_x)\right|\le 2+z.       \tag{1}
\]

A live event `x_s -> y_R` changes the debt by

\[
 s(e_x-e_y),                                            \tag{2}
\]

and an exhausting event with final color `y` changes it by

\[
 s e_x+(7-s)e_y.                                        \tag{3}
\]

For a top-to-bottom original-column prefix `W` ending in the current source
color `x`, let `|W|=s`.  Telescoping (2) shows that the column contributes

\[
 \#W-s e_x.                                             \tag{4}
\]

Consequently, from a fixed background `b`, its source test at every run
boundary of a walked prefix is simply

\[
 b+\#W.                                                 \tag{5}
\]

Here `#W` denotes the four-coordinate color-count vector.  Formula (5) is
the main past--future exchange rule below.

There is also a useful inventory identity.  At any border state, let `H_i`
be the number of color-`i` balls hidden strictly below the active sources and
let `G_i` be the sum of the caps of active sources of color `i`.  Since each
color has inventory seven,

\[
 d_i=7-H_i-G_i.                                         \tag{6}
\]

## 2. The seven parent families and their pasts

Name the bad column `A`, the two siblings entering the common color `f`
as `C,D`, and the remaining large sibling `B`.  Their parent sources are

\[
 A:q_s,\qquad C:q_a,\qquad D:q_b,\qquad B:q_c.          \tag{7}
\]

The future of `A` is the final word `f^(7-s)`.  The next event of `B` enters
`g` or `h` and may be live or exhausting.  The common-`f` source caps reached
by `C,D` are as follows.

| edge | `(s;a,b,c)` | `C,D` common-`f` caps |
| ---: | --- | --- |
| 116,117 | `(4;1,1,5)` | `3,3` |
| 184 | `(2;2,2,4)` | `3,3` |
| 236 | `(2;1,1,3)` | `2,2` |
| 242 | `(2;1,2,3)` | `2,3` |
| 244 | `(2;1,2,4)` | `2,3` |
| 248 | `(2;2,2,3)` | `3,3` |

At the parent all four sources have color `q`.  If `Q=s+a+b+c`, the exposed
prefix inventory is `F=d+Qe_q`.  A zero-debt past is therefore a quadruple
of words of lengths `s,a,b,c`, each ending in `q`, with total count `F`.

| edge | exposed inventory `F` | labelled past templates |
| ---: | --- | ---: |
| 116 | `q^7 g h^3` | 140 |
| 117 | `q^7 g^2 h^2` | 210 |
| 184 | `q^7 g h^2` | 60 |
| 236 | `q^5 g h` | 6 |
| 242 | `q^6 g h` | 12 |
| 244 | `q^7 g h` | 20 |
| 248 | `q^7 g h` | 20 |

For example, after the four final `q` letters are fixed, edge 117 has seven
free positions containing `q^3g^2h^2`, hence
`7!/(3!2!2!)=210` templates.  The seven edge families total 468 past
templates.

## 3. Two common-`f` anchors

Let `U_C,U_D` be the past words of `C,D`.  After walking both words and taking
their entries into `f`, their combined debt contribution is

\[
 b=\#U_C+\#U_D-(a+b)e_f.                               \tag{8}
\]

### Anchor criterion

The two anchors can be reached using only `C,D` if and only if

\[
 \left|\operatorname{supp}(U_CU_D)\right|\le2.          \tag{9}
\]

All words end in `q`, so (9) says that their union contains at most one of
`g,h`.

If (9) holds, walk `C`, enter `f`, then walk `D` and enter `f`.  Every source
test is a prefix count from (5), plus a nonpositive `f` coordinate after the
first entry, and has at most the two colors in (9) positive.  Conversely, if
both `g,h` occur, the final live successor (8) has `q,g,h` positive.  A legal
live event at `z=0` cannot produce three positive debts, so no legal
interleaving of only those two columns reaches both anchors.

Among the 468 templates, (9) fails only for eight edge-184 templates and two
edge-248 templates.  Sections 7 and 8 handle them directly.

## 4. Compatible deep prefixes and the large-column rotor

Assume the two anchors have been reached, and let

\[
 S=\operatorname{supp}(U_CU_D).
\]

Call a deep past word `W` compatible when

\[
 |S\cup\operatorname{supp}(W)|\le2.                    \tag{10}
\]

By (5), a compatible word can be walked from (8) to its final `q` gate.

If `A` is compatible, walk it and take `q_s -> f_7`; this is a legal first
exhaustion.  Suppose instead that `B` is the compatible word.  Walk it to
`q_c` and take its next event.  If that event exhausts `B`, the first
exhaustion is done.  If it is live and enters `y in {g,h}`, its successor is

\[
 b+\#U_B-c e_y.                                        \tag{11}
\]

Now walk `A`.  On every one of the seven edges,

\[
 c>F_g\quad\text{and}\quad c>F_h.                     \tag{12}
\]

Thus the `y` coordinate in (11), even after adding all of an `A` prefix,
stays strictly negative.  Apart from `y`, only `q` and the other non-`f`
color can be positive.  Formula (5) therefore makes the entire walk of `A`
legal, and `A` exhausts.

This compatible-deep macro covers every anchor-compatible template except
72 templates on edge 117 and six templates on edge 184.  It also covers the
ordinary part of edge 236, with the refinement in Section 9.

## 5. A `z=1` pair-cap lemma

The next lemma makes the hidden tail irrelevant after the first deep
exhaustion.

**Pair-cap lemma.**  At a reachable `z=1` state, if two active source caps
have sum at least seven, every maximal legal continuation reaches `z=2`.

**Proof.**  The first exhausting successor has at most three positive debts:
its threshold-two source test had at most two, and the final-color addition
can create at most one more.  Every later live successor at `z=1` has positive
support contained in its threshold-three source test.  Hence every pre-goal
state has a color `j` with `d_j<=0`.

If a pre-goal state were terminal, all three active source tests would have
four positive coordinates.  Every active source would therefore have to
have the same color `j`, and `j` would be the unique nonpositive debt.  Let
the three caps be `c_1,c_2,c_3`, with `c_1+c_2>=7`.  From (6),

\[
 d_j+c_1+c_2+c_3=7-H_j\le7.
\]

The third source test has

\[
 d_j+c_3\le7-c_1-c_2\le0,                              \tag{13}
\]

contradicting terminality.  QED.

There is one extra inventory fact needed before applying the lemma.  Write
`s` for the bad cap, `u,v` for the two old anchor caps, and `R_1,R_2` for
their fixed `f` endpoints.  Every one of the 44 local-`NO` next-run macros
satisfies

\[
 (7-s)+(R_1-u)+(R_2-v)=7.                         \tag{13a}
\]

The parent has `F_f(P)=0`.  The first term in (13a) is the bad final `f`
tail and the other terms are the two anchor `f` runs.  Thus these three
forced runs consume all seven `f` items: there is no other hidden `f` in a
compatible continuation.  The bad column reaches `f` only through its
final run and therefore exhausts on entry.  After a deep column has already
exhausted, the third active column consequently cannot acquire a live `f`
top.  Hence a hypothetical common-`f` terminal cannot keep either original
anchor at `f`; both anchors must first leave `f`.

After a deep column exhausts while `C,D` remain at their `f` anchors, a
common-source terminal would require both anchors to leave `f`.  Their new
caps are at least one larger than the anchor caps.  The resulting lower
bounds are `4+4=8` on edges 116,117,184,248 and `3+4=7` on edges 242,244.
The pair-cap lemma closes all of those macros, regardless of their later
hidden runs.  Edge 236 has the sole short sum `3+3=6` and is handled in
Section 9.

## 6. The 72 rigid edge-117 pasts

For edge 117 the anchor background is

\[
 b=(2,-2,0,0).                                         \tag{14}
\]

In each of the 72 templates without a compatible deep word, both `A` and
`B` contain exactly one `g` and one `h`.  Start walking `B`.  Stop after the
event which first exposes the second distinct non-`q` color, call it `y`.
Before that event every source test contains only `q` and the first non-`q`
color, so it is legal.

Let the new `y` source have cap `R`.  Since it is the second distinct
non-`q` letter, `R>=2`.  Its debt contribution is

\[
 \#W_R-R e_y,
\]

where `W_R` is the exposed `B` prefix.  Walk all of `A`.  Across both deep
words there are only two `y` letters, so every `A` source test has

\[
 d_y\le2-R\le0.
\]

Only `q` and the other non-`q` color can be positive.  Hence `A` exhausts
legally, and the pair-cap lemma applies to the two cap-three anchors.

## 7. The edge-184 rigid and anchor-incompatible pasts

### Six anchor-compatible rigid templates

Here the anchor support is `{q,g}`, while each deep word contains one `h`.
Thus `A=hq` and `B` contains `q^3h`.

If `B` does not begin with `h`, walk it until the event exposing its `h`.
The new cap `R>=2` gives `h` debt `1-R`; adding the single `h` of `A` leaves
it nonpositive.  Walk and exhaust `A`, then use the pair-cap lemma.

If `B` begins with `h`, take one event from either `f_3` anchor.  Its source
test is legal because the `f` debt in (8) is `-4`, so testing adds only to
`-1`.  If the event exhausts that anchor, walk and exhaust `A` at threshold
three to reach `z=2`.  If it is live into `t in {g,h}`, it changes (8) by

\[
 3e_f-3e_t.                                            \tag{15}
\]

The `f` debt remains negative and the total exposed count of `t` is at most
two, so `t` stays nonpositive while `A` is walked and exhausted.  The moved
anchor has cap at least four; the other anchor reaches cap at least four if
a common-source terminal is attempted, so the pair-cap lemma applies.

### Eight anchor-incompatible templates

The two anchor pasts are `gq,hq` in either order.  The large past uses only
`q,h`.  From zero debt, walk `B` to `q_4` and take its next event.

If it exhausts `B`, the exhausted column contains at most the three colors
`q,g,h`; at threshold three, `A` (which uses only `q,h`) can be walked and
exhausted to reach `z=2`.

If the event is live into `y`, equation (11) with `c=4` suppresses `y`
throughout `A`, so walk and exhaust `A`.  The surviving `B` source has cap at
least five.  Now walk either anchor past `xq` and enter `f_3`.  Both events
are legal at threshold three: `y` remains suppressed, and the other
coordinates already account for at most three positives.  The new cap three
and the cap-at-least-five `B` source invoke the pair-cap lemma.

## 8. The two anchor-incompatible edge-248 pasts

These two templates are, up to swapping `C,D`,

\[
 A=qq,\qquad B=qqq,\qquad C=gq,\qquad D=hq.             \tag{16}
\]

Exhaust `A` immediately.  The resulting state is

\[
 (2,5,0,0),\qquad z=1.                                 \tag{17}
\]

Take the next event of the source `B:q_3`.  If it exhausts, `z=2`.  If it is
live into `y`, the new `B` cap is at least four and the state changes by
`3e_q-3e_y`.  Walk either `xq` anchor and enter `f_3`.  The `x_1` test has at
most `q,f,x` positive (or leaves the suppressed `y` nonpositive), and the
following `q_2` test introduces no fourth positive coordinate.  The new cap
three and the cap-at-least-four `B` source sum to seven, so (13) finishes the
argument.

## 9. The short pair on edge 236

The two anchor pasts are the single letter `q`, and their background is

\[
 b=(2,-2,0,0).                                         \tag{18}
\]

The next two fixed events of either anchor are

\[
 q_1\longrightarrow f_2\longrightarrow q_3,            \tag{19}
\]

after which its hidden tail uses only `g,h`.

The second arrow in (19) is a fact about the complete formal local-`NO`
ledger, not a consequence of the `f`-budget argument in Section 5.  Read an
anchor hidden word from its current top downward.  On every edge-236 ledger
row its run chain begins with `f^1,q^1`; every later run has color `g` or
`h`.  In particular the `q` singleton is present as a separate run and does
not merge with either neighbor.  The artifact-backed checker verifies this
on both low anchors in every row.  It also applies a negative mutation which
preserves the reported cards and total inventory while removing that `q`
singleton, and requires the fixture predicate to reject it.

If the large past `B` uses at most one of `g,h`, use it as the compatible
deep word.  If its `q_3` event exhausts, walk and exhaust `A` at threshold
three.  If it is live, switch to and exhaust `A` as in Section 4.  The live
`B` cap is at least four.  Event `f_2 -> q_3` on either anchor is legal because
the exhaustion of `A` has made the `f` debt positive.  Its cap three and the
live `B` cap now sum to seven.

The only remaining pasts are

\[
 A=qq,qquad B=ghq\quad\text{or}\quad B=hgq.             \tag{20}
\]

First exhaust `A`; from (18) this gives `(4,3,0,0)` at `z=1`.  Write
`B=xyq`, where `{x,y}={g,h}`.  The event `x_1 -> y_2` is legal and leaves
debts `+e_x-e_y`, but its new `y_2` source can be blocked.  On one anchor take

\[
 f_2\longrightarrow q_3,
\]

and then take its next `q_3` event.  If that event exhausts, `z=2`.  If it is
live into `t in {g,h}`, it subtracts `3e_t`.  If `t=x`, both non-`q` debts are
nonpositive; if `t=y`, only `x` remains positive.  In either case the blocked
event `y_2 -> q_3` on `B` is now legal.  The two current caps are at least
four and three, so the pair-cap lemma completes the proof.

## 10. Conclusion and finite audit

The 468 past templates partition as follows.

| class | templates |
| --- | ---: |
| ordinary compatible-deep macro | 374 |
| edge-236 large-compatible macro | 4 |
| edge-236 short-rigid macro | 2 |
| rigid edge 117 | 72 |
| rigid edge 184 | 6 |
| anchor-incompatible edge 184 | 8 |
| anchor-incompatible edge 248 | 2 |

The first two rows are the 378 compatible-deep templates: 374 use the
standard pair-cap closure and four edge-236 templates use the first part of
Section 9.  The two edge-236 templates of the form (20) are not compatible;
they are the separate short-rigid row handled by the second part of Section
9.

The accompanying checker enumerates only these 468 past templates.  It
checks the anchor and compatible-deep criteria, replays the displayed debt
formulas for every rigid macro, checks both choices of generic next color,
and exhaustively verifies the small-integer pair-cap inequality.  It does not
enumerate fixed hidden words and does not run the production checkpoint DP.
In its default mode this is deliberately only the symbolic half of the
audit.  Formal acceptance also supplies the complete production report and
local-`NO` ledger:

```text
python tests/check_c4_h7_d2_three_source_all_local_no_bypass.py \
  --report <complete-report.json> \
  --ledger <complete-local-no-ledger.jsonl>
```

That black-box fixture layer checks the complete 1,106,490-future report,
reads exactly 14,784 local-`NO` rows on the seven stated edges, folds them to
the expected 44 next-run macros, and verifies on every row the parent debts,
caps, two fixed `f` cards, third `g/h` card, hidden-word boundary runs, and
four-color inventory used in the proof.  In particular it checks (13a),
asserts that the three forced runs are the only hidden `f`, and records the
`no_third_live_f` premise at every pair-cap closure.  Supplying only one
fixture is an error; a default run reports that no artifact fixture was
provided.  For edge 236 it additionally checks the two full low-anchor run
chains stated after (19), including a card-and-inventory-preserving negative
mutation.

Therefore every one of the 14,784 exported local-`NO` futures admits a
zero-debt past bypass, uniformly for every compatible hidden continuation in
its edge family.  This closes the three-source residual family and no larger
claim.
