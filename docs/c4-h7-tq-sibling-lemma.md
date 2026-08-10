# The same-level Tq sibling-entry lemma at c=4, h=7, k=2

## Scope

This note eliminates the **same-`z` live entrances into `Tq` that have a
legal sibling source**.  In the canonical numerical census this is the family
of 23 parents and 32 parent-terminal edges.  The argument applies to every
balanced fixed future represented by those edges; it does not depend on an
enumeration of the residual words.

This is only a local lemma.  It does not eliminate the unique-source
same-`z` entrances, the first-exhaustion entrances, the `D2` terminal family,
or all height-7 layouts.  In particular, it is not by itself a proof of
universal solvability at height 7.

## Border model

Work after one original column has already been exhausted, so `z=1` and three
original columns remain active.  For each color `c`, let

\[
d_c=F_c-G_c,
\]

where `F_c` is the exposed amount of color `c` and `G_c` is the capacity
currently hosted by active columns whose top color is `c`.  A live source of
top color `x` and cumulative cap `r` is legal exactly when

\[
\#\{c:d_c+r[c=x]>0\}\le k+z=3. \tag{1}
\]

If its next run has color `y` and ends at a live cap `R`, where
`x != y` and `r<R<7`, the debt update is

\[
d'=d+r(e_x-e_y). \tag{2}
\]

Notice that the coefficient in (2) is the **old** cap `r`, not the new
endpoint `R`.  If the next endpoint is 7, the source exhausts and the desired
`z=2` frontier has already been reached.

Every active column has one fixed finite chain of runs.  Thus repeatedly
selecting a column means following its already determined successive
endpoints; no future color or endpoint is chosen online.

## The sibling predecessor

Let `D` be a `Tq` terminal.  Its three active tops have one common color `q`.
Write

\[
d_q(D)=-E,\qquad d_c(D)>0\quad(c\ne q), \tag{3}
\]

and let the three current caps be `t,u,v`.  Terminal blockedness gives

\[
t,u,v>E. \tag{4}
\]

Suppose that `P` enters `D` by the same-level live event

\[
a_s\longrightarrow q_t,\qquad a\ne q. \tag{5}
\]

The standard entrance sandwich is

\[
1\le s\le E<t. \tag{6}
\]

The other two active columns of `P` are precisely the `q`-top columns of caps
`u` and `v`.  Put

\[
p=d_a(D)>0.
\]

Inverting (2) gives

\[
d(P)=d(D)-s e_a+s e_q,
\]

and hence

\[
d_a(P)=p-s,\qquad d_q(P)=s-E. \tag{7}
\]

Assume that `P` belongs to the sibling family, so at least one of the two
`q`-top columns is legal.  Test, for example, the column of cap `u`.  In its
source-test vector, the `q` coordinate is

\[
s-E+u>0
\]

by (4), and the two non-`q`, non-`a` coordinates are the unchanged positive
coordinates of `D`.  There are already three positive coordinates.  By (1),
the remaining `a` coordinate must be nonpositive.  Therefore

\[
p-s\le0,\qquad\text{or equivalently}\qquad p\le s. \tag{8}
\]

The same sign calculation then proves that the other `q`-top column is legal
as well.  Thus a sibling parent actually has **both** `q` siblings available.

Equation (8) is the source of the anchor used below; it is not an additional
enumerated property of the 23 parents.

## Anchor-corridor lemma

**Lemma 1 (anchor corridor).**  At `z=1`, suppose `d_a<=0`.  Any active source
whose current top color is not `a` is legal.  Moreover, that same fixed column
may be advanced until it either exhausts or first acquires top color `a`, and
`d_a` stays nonpositive throughout.

**Proof.**  Testing a source of top color different from `a` leaves the
`a` coordinate unchanged and nonpositive.  Among four coordinates there can
therefore be at most three positive ones, so (1) holds.  A live event whose
new color is not `a` leaves `d_a` unchanged by (2); the first event whose new
color is `a` subtracts its old cap from `d_a`.  Hence every intermediate
source is legal and the anchor never becomes positive.  An endpoint 7 is
already the goal.  \(\square\)

## Bringing both siblings to the anchor

At `P`, equation (8) says that `a` is a nonpositive anchor.  Start with
**either** of the two `q` siblings.  It is legal by the preceding calculation.
Apply Lemma 1 to that column until it exhausts or first reaches top color `a`.
If it exhausts, the proof is finished.  Otherwise, `d_a` has only decreased,
so Lemma 1 applies to the other `q` sibling as well.  Advance that second
column to exhaustion or to its first `a`.

It remains to consider the case in which both siblings reach live `a`
boundaries.  Together with the untouched source in (5), all three active tops
are now `a`.  Let `c_1,c_2` be the caps immediately before the two sibling
columns enter `a`.  Caps strictly increase along a fixed column, so

\[
c_1\ge u,\qquad c_2\ge v. \tag{9}
\]

Starting from `d_a(P)=p-s`, the two first entries into `a` subtract `c_1` and
`c_2`.  No earlier event on either corridor changes `d_a`.  At the resulting
all-`a` checkpoint `A`,

\[
d_a(A)=p-s-c_1-c_2.
\]

Define its `a`-energy by `M=-d_a(A)`.  Equations (4), (6), (8), and (9) give

\[
M=s+c_1+c_2-p
 \ge c_1+c_2
 \ge u+v
 \ge4. \tag{10}
\]

The lower bound 4 is the height-7 leverage: a same-level entrance has
`E>=1`, while both terminal sibling caps are integers strictly larger than
`E`.

## The all-anchor rotor

**Lemma 2 (high-energy all-anchor rotor).**  In a balanced height-7 state at
`z=1`, suppose all three active tops are `a` and

\[
d_a=-M,\qquad M\ge4.
\]

Then the fixed chains have a legal path to `z=2`.

**Proof.**  Let the three current caps be `r_1,r_2,r_3`.  Since all three tops
are `a`, the debt definition gives

\[
F_a=r_1+r_2+r_3-M. \tag{11}
\]

There are exactly seven items of color `a`, hence `F_a<=7`.  If every cap were
strictly larger than `M`, integrality and (11) would imply

\[
F_a\ge3(M+1)-M=2M+3\ge11,
\]

a contradiction.  Therefore some current cap `r` satisfies `r<=M`.  That
`a`-source is legal because its adjusted `a` debt is `-M+r<=0`.

Take this source.  If its next event exhausts the column, `z=2` is reached.
Otherwise it leaves `a`; immediately after that live event the anchor debt is

\[
d_a=-M+r\le0.
\]

Apply Lemma 1 to the same column until it exhausts or first returns to `a`.
If it returns, let `w` be its cap immediately before the return event.  The
cap has strictly advanced, so `w>r`.  Departure from `a` added `r` to `d_a`,
the intermediate non-`a` events did not touch `d_a`, and return to `a`
subtracts `w`.  The new all-`a` energy is therefore

\[
M'=M+w-r>M. \tag{12}
\]

It is still at least 4, so the argument repeats.  Every repetition strictly
advances at least one fixed column cap.  The three chains have only finitely
many boundaries, and no cap ever decreases.  Consequently the construction
cannot return to an all-`a` checkpoint forever; one of its corridor events
must eventually have endpoint 7.  \(\square\)

## Main conclusion

**Theorem (same-level `Tq` sibling-entry elimination).**  Every balanced
fixed future realizing a same-`z` live entrance (5) into `Tq` with a legal
sibling source is checkpoint-YES: from `P`, a second original column can be
exhausted.  In fact, the next event of **either** `q` sibling is a safe first
move.

**Proof.**  Equation (8) supplies the anchor.  Starting from either sibling,
the two applications of Lemma 1 either reach `z=2` directly or reach the
all-`a` checkpoint whose energy satisfies (10).  Lemma 2 finishes the latter
case.  The construction uses only the actual successive runs in the fixed
chains, so it applies independently to every choice of residual words.
\(\square\)

## Audit of the shorter persistence formula

There is also a correct one-event persistence observation.  If the sibling of
cap `u` moves live from `q` to `x`, testing the untouched sibling of cap `v`
uses

\[
d(P)+(u+v)e_q-u e_x. \tag{13}
\]

The informal statement that the subtraction in (13) cannot create a positive
coordinate needs one explicit premise: adding `u` must not make `q` newly
positive relative to the original test of the `v` sibling.  Here that premise
holds because

\[
d_q(P)+v=s-E+v>0
\]

by (4) and (7).  Thus the additional `u e_q` does not change the sign of `q`,
and `-u e_x` can only remove a positive coordinate.  If the sibling event has
endpoint 7, it reaches the goal and no persistence claim is needed.

The persistence formula is therefore sound on this family, but it alone only
justifies the commuting first layer.  The anchor-corridor and all-anchor rotor
arguments are what prove eventual exhaustion for arbitrary fixed suffixes.

## Role of the exhaustive machine run

The independent census identifies 23 canonical sibling parents, 32 bad
edges, and 10,073,448 labeled balanced residual fixed futures.  An exhaustive
checkpoint DP over those futures is useful as an independent implementation
check: it can catch an incorrect transition, scope mismatch, or transcription
error in this note.

It is not a logical premise of the theorem.  The proof above quantifies over
an arbitrary balanced fixed future and supplies a legal terminating strategy
directly.  Therefore the machine run should be reported as corroborating
full-universe verification, not as 10,073,448 unrelated searches on which the
lemma depends.
