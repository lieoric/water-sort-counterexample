# Rainbow deletion and token lifting for four colours

This note develops a route from the known universal height-six result toward
the unresolved balanced four-colour, height-seven, two-empty-column case.  It
does **not** prove that every height-seven layout is solvable.  Its purpose is
to isolate a global piece of structure that is absent from the current
terminal-state census and to state exactly what remains to be proved.

Columns are labelled $0,1,2,3$, colours are labelled $0,1,2,3$, every
column has height $H$, and every colour occurs $H$ times.  A *cell* below
always means a labelled physical occurrence, not merely a column-colour pair.

## 1. Seven disjoint rainbow deletions

For a layout $I$, let

\[
n_{ic}=\#\{\text{cells of colour }c\text{ in column }i\}.
\]

Make a bipartite multigraph $B_I$.  Its left vertices are the four columns,
its right vertices are the four colours, and each physical $c$-cell in
column $i$ is one edge from $i$ to $c$.  Every vertex has degree $H$:
a column contains $H$ cells, and balance gives $H$ cells of every colour.

### Rainbow-factorization lemma

The $4H$ physical cells of every balanced layout can be partitioned into
$H$ sets

\[
T_1,\ldots,T_H,
\]

such that every $T_r$ contains exactly one cell from each column and exactly
one cell of each colour.

**Proof.**  For any set $X$ of column vertices, $H|X|$ edges leave $X$.
They end in $N(X)$, whose total degree is $H|N(X)|$.  Hence
$H|X|\le H|N(X)|$, so Hall's condition holds and $B_I$ has a perfect
matching.  Delete that matching.  Every vertex degree decreases by one, so
the remainder is $(H-1)$-regular.  Repeat.  After $H$ rounds no edge
remains.  QED.

Deleting one $T_r$ removes one cell from every column and one occurrence of
every colour.  The result $I-T_r$ is therefore a balanced height-$(H-1)$
layout.  In particular, every balanced $4\times7$ layout has seven labelled
balanced height-six children.

This is already a useful change of quantifiers.  Since every balanced
height-six child is YES, a hypothetical height-seven NO layout must defeat
the lifting of a height-six winning path for **each of seven disjoint cell
transversals**.  Merely observing that the children are YES is not enough:
solvability is not known to be monotone under arbitrary internal insertion.

## 2. Thick transversals and the exact Hall alternative

A selected cell is *thick* if its maximal monochrome run in the parent has
length at least two.  Deleting one cell from such a run shortens the run but
does not change the sequence of run colours.  A transversal is thick if all
four of its cells are thick.

Define a simple bipartite graph $B_I^{\rm thick}$: column $i$ is adjacent
to colour $c$ exactly when column $i$ has a $c$-run of length at least
two.

### Thick-transversal dichotomy

Exactly one of the following holds.

1. $B_I^{\rm thick}$ has a perfect matching.  Choosing one cell from the
   corresponding thick run in each column gives a run-skeleton-preserving
   rainbow deletion.
2. There is a nonempty colour set $S$ for which

   \[
   |N_{B_I^{\rm thick}}(S)|<|S|.
   \]

**Proof.**  This is Hall's theorem applied to the four-by-four thick support
graph.  The two cases are mutually exclusive and exhaustive.  QED.

The second case is not a failure of the method.  It is a small structural
branch: every rainbow transversal must use at least one singleton occurrence
from the Hall-deficient colours.  The witness consists of at most four
colours and at most three neighbouring columns.

Singletons must not be hidden inside a claimed lift.  Deleting an endpoint
singleton removes one parent border.  Deleting an internal singleton removes
one border when its two neighbours have different colours and two borders
when the neighbours have the same colour.  Thus a height-six edge need not be
one parent edge.  A separate one- or two-border local detour is required.
The same $F-G$ bookkeeping can be re-derived at an individually aligned
checkpoint, but there is no canonical edge-by-edge child path through the
extra parent borders.  Accordingly, the checker below does not apply the
token-lift lemma to a singleton transversal; it reports that branch for a
separate detour proof.

## 3. Exact perturbation made by four thick tokens

Let $J$ have height $h$, let $I$ have height $H=h+1$, and suppose
$J$ is obtained from $I$ by deleting a thick rainbow transversal.  The
two layouts have identical run-colour skeletons.  Index a common top-border
checkpoint by the number of exposed runs in each column.

For a checkpoint $x$, write:

- $E(x)$ for the columns whose selected token lies in an exposed run;
- $A(x)$ for the active, non-exhausted columns;
- $t_j$ for the token colour in column $j$;
- $a_j(x)$ for the current top-border colour of active column $j$;
- $e_c$ for the unit vector of colour $c$.

For a candidate active source $i$, let

\[
D_i=d+s_i e_{a_i}
\]

be its Ito source-test vector.  The source is legal precisely when

\[
|\operatorname{pos}(D_i)|\le 2+z,
\]

where $z$ is the common number of exhausted original columns.

### Token-error lemma

At every common checkpoint and for every active source $i$,

\[
\boxed{
D_i^{I}-D_i^{J}
=
\sum_{j\in E(x)} e_{t_j}
-
\sum_{j\in E(x)\cap A(x),\ j\ne i} e_{a_j(x)}.
}
\tag{1}
\]

**Proof.**  Every exposed token contributes one item of its own colour, so

\[
F^{I}-F^{J}=\sum_{j\in E(x)}e_{t_j}.
\]

If column $j$ is active and its token is exposed, its exposed host capacity
is one larger in $I$, assigned to its current top colour.  Therefore

\[
G^{I}-G^{J}
=\sum_{j\in E(x)\cap A(x)}e_{a_j(x)}.
\]

Finally, when the source token is exposed,
$s_i^I-s_i^J=1$.  The added $e_{a_i}$ in the source term cancels the
source's own contribution in the second sum.  Substitution into
$D_i=F-G+s_ie_{a_i}$ gives (1).  QED.

The formula is sparse and contains only four labelled tokens.  It also gives
the checksum

\[
\sum_c(D_i^{I}-D_i^{J})_c
=z+\mathbf 1[i\in E(x)],
\]

because every exhausted column has exposed its token.

### Compatible-lift lemma

Suppose a common-skeleton path starts at the initial checkpoint, reaches two
exhausted columns, and at every step its chosen source is legal in $J$ and,
after applying (1), legal in $I$.  Then the same source sequence is a legal
top-border path for $I$, so $I$ is solvable.

This follows by induction over the path.  Thick deletion gives the same next
run-colour edge in both layouts, and the hypothesis gives its legality in
both.  The paths therefore remain at corresponding checkpoints until the
two-exhausted-column finishing frontier.

A convenient sufficient test at a step is that the positive part introduced
by the error vector lies entirely inside the child's existing positive
support.  More generally, it is enough that the number of newly positive
coordinates does not exceed

\[
(2+z)-|\operatorname{pos}(D_i^J)|.
\]

This is a checkable condition, not yet an existence theorem.  The missing
global assertion is:

> Every balanced height-seven layout has either a thick transversal with a
> compatible height-six winning path, or a bounded singleton detour from the
> Hall-deficient branch.

Proving that statement would settle height seven.  Failure produces a small
counter-witness: a Hall set, or four labelled tokens plus the first child-
legal/parent-illegal source test.

## 4. An independent sequential-column bypass

The deletion route also suggests a cheap global pruning lemma.  For a column
$i$, let $S_i$ be the set of all colours in it and let $U_i$ be the set
of colours above its maximal bottom run.

### Two-column support lemma

If two distinct columns $i,j$ satisfy

\[
|U_i|\le2,
\qquad
|S_i\cup U_j|\le3,
\tag{2}
\]

then the layout is solvable.

**Proof.**  First dispose of initially monochrome columns.  If there are two,
the finishing frontier is already reached.  If there is exactly one and it is
column $i$, start with the second paragraph below.  If it is a different
column, its one colour together with $U_i$ has support at most three; the
existing monochrome column supplies the third bin, so advancing $i$ alone
reaches the finishing frontier.

It remains to consider the case with no initially monochrome column, where
$d=0$.  Advance only column $i$.  Immediately before each of its borders is
removed, its source-test vector telescopes to the colour-count vector of the
currently exposed top prefix of that column.  The last test excludes the
hidden bottom run.  Condition $|U_i|\le2$ therefore makes every step legal
with the original two bins, and column $i$ is exhausted.

Now advance only column $j$.  Its source-test vector is the full colour-
count vector of exhausted column $i$, plus the colour-count vector of the
currently exposed top prefix of $j$.  Before $j$'s last border, its
positive support is contained in $S_i\cup U_j$, of size at most three.
There are $2+1=3$ bins after the first exhaustion, so every step is legal
and $j$ is exhausted.  The two-exhausted-column frontier finishes the
puzzle.  QED.

Consequently, any height-seven NO must violate (2) for all twelve ordered
column pairs.  This condition is independent of D2/Tq terminal labels and is
cheap enough to use before any suffix expansion.

## 5. What a height-seven NO would force at height eight

The balanced bottom-layer monotonicity theorem gives a second global
necessary condition.  If a balanced height-seven layout $I$ were NO, then
for every permutation $\pi$ of the four colours, inserting

\[
\pi(0),\pi(1),\pi(2),\pi(3)
\]

as a new labelled bottom layer would produce a balanced height-eight NO
layout $I^\pi$.  Thus one hypothetical labelled height-seven NO forces a
family of 24 labelled height-eight NO extensions sharing the same 28-cell
core.

This implication is one-way.  A height-eight NO can have a solvable balanced
height-seven deletion, as the committed height-eight witnesses already show.
Likewise, finding a height-seven core whose 24 extensions are NO would be a
necessary signature, not by itself a certificate that the core is NO.  On
the other hand, proving that every height-seven core has at least one YES
rainbow-bottom extension would immediately rule out a height-seven NO.

The three committed height-eight witnesses do not settle this subproblem.
Their labelled bottom-colour multiplicities are not rainbow; for the
symmetric witness the bottom row is (2,2,0,0).

## 6. Independent checker

[`check_c4_h7_rainbow_lift.py`](../tests/check_c4_h7_rainbow_lift.py)
implements the finite assertions in this note without using the production
border oracle.

For each input layout it:

1. constructs an $H$-factorization of the physical occurrence multigraph;
2. verifies that every factor deletes to a balanced height-$(H-1)$ child;
3. enumerates the thick support matchings, or emits an explicit Hall witness;
4. checks equation (1) coordinate by coordinate at every explored
   child-legal source;
5. searches for a path legal in both the child and parent skeletons;
6. reports singleton-created borders instead of treating them as common
   edges;
7. reports all ordered pairs covered by (2); and
8. for a height-seven input, exactly classifies its 24 labelled rainbow-bottom
   height-eight extensions.

The built-in regressions are the symmetric certified height-eight four-lock
NO and one true zero-debt height-seven member of the two-source D2 near-kernel.
The latter is intentionally a global YES even though its distinguished
nonzero-debt checkpoint is locally losing.

Run it with

```text
python tests/check_c4_h7_rainbow_lift.py
```

or add a plain repository instance with `--instance`.  A reported compatible
path proves that one layout is YES.  Absence of such a path proves only that
this thick-transversal lift did not close that layout; it is neither a Water
Sort NO certificate nor a universal height-seven conclusion.
