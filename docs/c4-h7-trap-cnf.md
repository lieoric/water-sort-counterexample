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
of colour `c>0` requires an earlier occurrence of `c-1`.  Every layout has
exactly such a colour renaming, so this removes only the `4!` duplicate names,
not any physical instance.  The constraint is disabled when a concrete
regression instance is fixed by unit clauses.

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
