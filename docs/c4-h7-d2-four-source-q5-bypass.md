# The four-source `E=2,Q=5` suppressed-color bypass

## Scope

In the four-legal-source `a=q`, `E=2` first-exhaustion ledger, the cell
`Q=5` has 57 `D2`-reduction card decorations.  Fifty-six have an immediate
`3+1` landing.  The sole later-rotor decoration has edge-summed
residual-word weight 84.  This note proves a zero-debt bypass for that one
decoration and no larger family.

The weight 84 is **edge-summed**; it is not a count of distinct physical
layouts.  The proof never reads any of those 84 residual tails.

## 1. The rigid macro

Use color order `(q,f,g,h)`.  The first-exhaustion parent and reserved bad
event are

\[
 d(P)=(-5,0,1,4),
 \qquad q_3\longrightarrow f_7.                 \tag{1}
\]

All four parent tops are `q_3`.  The three sibling cards of the unique
decoration are

\[
 q_3\longrightarrow h_4.                       \tag{2}
\]

The four zero-debt past words, written bottom to top, all have length three
and end in `q`.  Their joint inventory is

\[
 q^7g^1h^4.                                     \tag{3}
\]

After fixing the bad final run `f^4` and the three `h^1` cards in (2), the
residual inventory is `f^3g^6` in nine cells.  Hence its edge-summed weight
is

\[
 \frac{9!}{3!6!}=84.                            \tag{4}
\]

Call a past word **binary** when it avoids the unique `g`, and put

\[
 \lambda(W)=\#_q W.
\]

A binary word uses only `q,h`, ends in `q`, and has
`1<=lambda(W)<=3`.  It can therefore be walked from zero debt using only two
positive colors.  If it is a sibling `U`, taking (2) afterwards leaves

\[
 d_U=\#U-3e_h
    =\lambda(U)(e_q-e_h).                       \tag{5}
\]

## 2. The unique `g` is not in the bad past

If the bad past `B` avoids `g`, at least two siblings are binary.  Choose
distinct binary siblings `U,V`.

Walk `U` and take (2), producing (5).  Then walk `B` and take the bad
exhaustion (1).  Every source test before the exhaustion has support only in
`{q,h}`.  The final `f^4` run can create only the third positive coordinate,
so the bad event is legal and reaches `z=1`.

Now walk `V` to its `q_3` gate.  The `g` coordinate is still zero, hence each
threshold-three source test has positive support contained in `{q,h,f}` and
is legal.  The frozen source from `U` has cap four and `V` has cap three.
The `z=1` pair-cap lemma applies to `4+3=7` and forces a second exhaustion.

## 3. The unique `g` is in the bad past

Now all three siblings are binary.  Because `B` has length three and ends in
`q`, its multiset is one of

\[
 \{g,q,q\}\quad\hbox{or}\quad\{g,h,q\}.        \tag{6}
\]

Thus its ordered word is respectively `gqq` or `qgq`, or `ghq` or `hgq`.
Write

\[
 \mu=\#_qB,qquad b=\#_hB.
\]

The two cases in (6) are

\[
 (\mu,b)=(2,0)\quad\hbox{or}\quad(1,1).         \tag{7}
\]

Choose siblings `U,V` with the two largest values of `lambda`.  By (3),

\[
 \lambda(U)+\lambda(V)+\lambda(W)=7-\mu,
\]

where every summand lies in `{1,2,3}`.  Consequently

\[
 \lambda(U)+\lambda(V)\ge4.                    \tag{8}
\]

Walk `U` and take (2).  At every source test while walking `B`, the `h`
coordinate of the **source-test vector**, not merely the stored debt, is

\[
 -\lambda(U)+\#_h(B_{\rm prefix})
 \le-\lambda(U)+b\le0.                         \tag{9}
\]

Only `q,g` can therefore be positive, so the whole bad past and (1) are
legal.  Immediately after the bad exhaustion, `f` is positive.  At every
source test while walking `V`, the test-vector `h` coordinate is bounded by

\[
 -\lambda(U)+b+\#_h(V_{\rm prefix})
 \le-\lambda(U)+b+3-\lambda(V).                \tag{10}
\]

If `(mu,b)=(2,0)`, (8) makes the right side at most `-1`.  If
`(mu,b)=(1,1)`, it is at most zero.  Thus `h` never becomes a fourth positive
test coordinate: only `q,g,f` can be positive.  The complete walk of `V` to
`q_3` is legal at threshold three.

Again the frozen cap four from `U` and cap three from `V` invoke the pair-cap
lemma.  A second exhaustion follows independently of every residual tail.

## 4. Conclusion and finite audit

The two cases prove that every balanced zero-debt past compatible with the
unique macro (1)--(3) reaches `z=2`.  Therefore the one `Q=5` later-rotor
decoration, with edge-summed weight 84, is eliminated.

`tests/check_c4_h7_d2_four_source_q5_bypass.py` independently checks (4),
enumerates the 280 labelled past-prefix templates from (3), selects `U,V`
by the proof, evaluates every run-end source-test vector in (9)--(10), and
checks the cap-sum lemma over its small integer box.  It enumerates no
residual tail and runs no checkpoint DP.
