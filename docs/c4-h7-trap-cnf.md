# Exact fixed-instance trap encoding for `c=4, k=2`

This experiment decides whether a balanced four-colour instance with two empty
columns can avoid ever exhausting two original columns.  It is deliberately an
encoding of one fixed instance, not an online game in which hidden runs may
change between contexts.

## Coordinates

The Boolean item variables describe four labelled columns from top to bottom.
Each column has height `h`, every position has exactly one of four colours, and
every colour occurs exactly `h` times globally.

For unrestricted searches, colours are named by order of first appearance in
the fixed flattened item order: the first item is colour 0, and an occurrence
of colour `c>0` requires an earlier occurrence of `c-1`.  In addition, the four
top-to-bottom column words are constrained to be in nondecreasing
lexicographic order.  Both constraints are disabled when a concrete regression
instance is fixed by unit clauses.

The two symmetry breakers are safe together, even though renaming colours can
change the order of columns.  Consider the full
`S_4(columns) x S_4(colours)` orbit of a layout and choose its lexicographically
least flattened top-to-bottom word.  Minimality under colour permutations gives
the first-occurrence naming rule.  Minimality under column permutations gives
the sorted column words, since swapping an adjacent inversion would make the
flattened word smaller.  Thus every joint orbit has a representative satisfying
both constraints; no physical instance is removed.

### Exact five-way `h=7` partition

The fallback workflow partitions the unrestricted, symmetry-broken `h=7`
formula by the first three cells of that same flattened top-to-bottom word.
A restricted-growth word starts at `0`, and every later value is at most one
more than the greatest earlier value.  Exhausting all `4^3 = 64` colour triples
shows that the possible length-three prefixes are exactly

```
000  001  010  011  012
```

For each shard the generator retains both symmetry breakers and adds three unit
clauses fixing one of these prefixes.  It rejects combining this option with a
fixed regression instance or with disabled symmetry breaking, so the fixed
`h=8` pipeline is unchanged.  The five shard formulas are pairwise disjoint and
their disjunction is the original symmetry-broken formula.

Consequently the global rule is exact: one independently verified SAT shard is
an unrestricted fixed-layout NO instance, while unrestricted UNSAT follows only
after all five shards have independently verified DRAT proofs.  The aggregation
script rejects missing, duplicate, unchecked, wrong-height, wrong-prefix, or
search-only summaries.  The exhaustive 64-assignment coverage check runs both
as a unit test and again inside the aggregator.  Thus the global theorem consists
of the five checked shard results together with this finite coverage lemma.

For a column, an endpoint `s` in `1..h-1` is active when positions `s-1` and
`s` have different colours.  It means that the top `s` items have been exposed
and the current source has capacity `s`.  Endpoint `h` means that the original
column has no boundary left; in the border model it contributes one additional
monochrome buffer.

For a state `s=(s_0,s_1,s_2,s_3)`, let `z` be the number of endpoints equal to
`h`.  Only states with `z <= 1` need trap variables.  Once `z >= 2`, the two
original columns plus the two initially empty columns give four buffers, so the
remaining instance is always completable.

For colour `c`, column `i` contributes

```
v_i(c) = count(c in positions 0 .. s_i-1)
         - s_i * [s_i < h and position s_i-1 has colour c].
```

Thus `d(c)=sum_i v_i(c)` is exactly the oracle's `F(c)-G(c)`.  Removing source
`i` is legal exactly when at most `2+z` colours have

```
d(c) + s_i * [source i has colour c] > 0.
```

The successor endpoint is the first later active boundary, or `h` if no later
boundary exists.

## Shared exact arithmetic

The implementation does not expand that last inequality as a separate
pseudo-Boolean formula for every source.  For each column, endpoint, and colour
it first builds one shared binary prefix count

```
C(i,s,c) = count(c in positions 0 .. s-1).
```

For a live endpoint define `Y(i,s,c)=C(i,s,c)+s(1-T(i,s,c))`, where `T` is the
current-top indicator.  For an exhausted endpoint use `Y=C`.  Then each state
and colour needs only one shared carry-save sum

```
A = sum of live endpoint capacities,
S(c) = sum_i Y(i,s_i,c) = d(c) + A.
```

The source-specific test is now just one of two constant comparisons of this
same sum:

```
T(i,s_i,c)=0:  S(c) >= A + 1,
T(i,s_i,c)=1:  S(c) >= A - s_i + 1.
```

Half adders, full adders, binary constant comparators, and the top-indicator
multiplexer are all encoded as equivalences.  State-local gates are guarded by
the corresponding trap variable: they are exact whenever that state is marked,
which is precisely when its legality and transition clauses can have an effect.
Unmarked-state arithmetic is irrelevant to every closure obligation.  This
guarding therefore preserves the SAT-if-and-only-if-counterexample statement.

## Closed trap

For every non-goal endpoint tuple the encoding has a variable `L_s`.  It
requires:

1. the unique initial endpoint tuple belongs to `L`;
2. every live endpoint in a marked tuple is a real boundary; and
3. every legal fixed-instance successor of a marked tuple is also marked.

Transitions into `z >= 2` are forbidden.  Therefore a satisfying assignment
contains a forward-closed, goal-free set for one concrete balanced layout.

Conversely, if a concrete layout is unsolvable, mark every state reachable
from its initial tuple.  The marked set satisfies the same clauses.  Hence the
CNF is satisfiable if and only if a real fixed-layout counterexample exists.

This equivalence is why an adaptive next-run game is not used as the final
test: here all contexts share the same item variables and therefore the same
future in every column.

## Independent evidence

The GitHub workflow uses two separate validation paths:

- For `SAT`, the model is decoded to the repository's bottom-to-top instance
  format.  `water-oracle` must report `UNSOLVABLE`, emit a `.wscert`, and
  `water-verify` must accept that certificate.
- For `UNSAT`, CaDiCaL writes a proof and `drat-trim`, built independently from
  a pinned revision, must validate it against the exact archived DIMACS file.

The workflow first runs the known `h=8` SAT regression before attempting the
`h=6` and `h=7` proof jobs.  Solver output alone is never treated as a proof.

The separate `c4-h7-five-shards.yml` fallback builds the same pinned tools once,
runs the five `h=7` shards in parallel, archives every DIMACS/proof or SAT
witness, and publishes a small aggregate result.  Every shard must have either
an accepted DRAT check or both independent Water Sort SAT-witness checks before
the workflow can accept the aggregate.
