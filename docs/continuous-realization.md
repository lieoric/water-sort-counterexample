# Continuous realization of a top-border path

This note closes a distinction left open by the finite unit-scene experiments.
Those experiments rebuilt one deterministic tight physical representative at
every top-border checkpoint. A proof of Water solvability instead needs one
continuous sequence of forced maximal water moves from the real initial
configuration.

The construction below is the algorithmic form of Lemma 2, Theorem 3, and
Corollary 8 of Ito et al., [*Sorting Balls and Water: Equivalence and
Computational Complexity*](https://doi.org/10.4230/LIPIcs.FUN.2022.16), with an
extra check for this repository's locked completed-column rule.

## Locked balanced model

Every color occurs exactly `h` times and every stack has capacity `h`. A full
monochrome stack is locked and cannot be a move source.

For a top-border table `tau`, let `m_c(S)` be the number of nonempty monochrome
physical stacks of color `c`. The configuration is tight when

```text
m_c(S) = M_c(tau)
```

for every color, where `M_c` is the paper's required monochrome-bin count.

### A locked stack is never surplus

If one stack contains `h` units of color `c`, it contains every unit of that
color. Consequently there is no non-monochrome `c` host, `G_c = 0`, and all
`c` units are above the surviving borders, so `F_c = h`. Hence `M_c = 1`.
The locked stack is exactly the one required monochrome `c` stack and is never
one of the surplus stacks that tightness must empty.

It follows that Ito's tightening construction remains valid with locking. If
`m_c > M_c`, choose a surplus monochrome `c` stack. It is not full and therefore
is not locked. Repeated forced bulk moves into nonempty, nonfull stacks topped
by `c` either empty that source or fill a target. The capacity inequality in
the definition of `M_c` guarantees enough total target space.

## Realizing one border removal

Start from the actually reached tight configuration, not from a reconstructed
canonical one. For a legal source stack `b` with top color `c`:

1. If removing `b`'s `c` host does not increase `M_c`, pour its whole exposed
   top run into other nonempty `c`-topped stacks.
2. If it increases `M_c` by one, tightness guarantees an empty stack; pour the
   exposed run there.
3. Every pour is a forced maximal Water move. Continue until exactly the chosen
   original border is exposed.
4. The new physical state has at most one surplus monochrome stack. Empty
   surplus stacks by the locked-safe tightening construction above.

This produces some reachable tight realization of the successor top-border
table. Repeating it realizes an entire legal border-removal path continuously.
When two original columns are exhausted in the four-color/two-empty model,
there are at least four monochrome bins. Every remaining source demand is at
most four, so all remaining borders can be removed in arbitrary order.

## Why the canonical representative must not be used

Tight realizations of one top-border table need not be mutually reachable.
For capacity two, with columns written bottom-to-top, take

```text
S0 = (AB, AC, BC, empty, empty).
```

Both of the following are reachable and tight with the same top-border table
`(1,0,0)`:

```text
S = (AB, A,  B, CC, empty)
T = (AB, CC, B, empty, A)
```

The full `CC` stack has different labels in `S` and `T`. It is locked forever,
so neither state can reach the other. Thus Ito's lemma guarantees a reachable
tight realization, not an arbitrarily prescribed canonical realization.

`water-continuous-control` therefore preserves the real physical state across
every macro step. It verifies conserved color totals, protected original
prefixes, the exact top-border table, tight monochrome counts, maximal pour
quantities, and the locked-source rule before accepting a trace.

## Exact finite-catalog replay

GitHub Actions run
[`31334595589`](https://github.com/lieoric/water-sort-counterexample/actions/runs/31334595589)
replayed both candidate controllers on all 4,301 representatives in the
committed catalog. All **8,602/8,602** continuous runs reached the fully sorted
goal. They realized 284,154 border removals with 389,773 forced maximal bulk
moves; the checker reported zero construction gaps and zero attempts to source
a locked full stack. The longest individual trace used 184 bulk moves.

This result removes the finite experiment's former physical-realization gap.
It remains finite evidence about the two controllers, not a quantification over
all heights or all balanced initial instances.

## Remaining universal question

Continuous realization removes the physical gap between a legal border path
and Water moves. It does not prove that every arbitrary-height four-color,
two-empty initial instance has a winning border path. That remaining question
is purely the macro-level counter game: choose legal border sources until two
original columns are exhausted, for every possible hidden suffix.
