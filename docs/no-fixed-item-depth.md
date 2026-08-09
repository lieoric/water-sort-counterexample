# No universal fixed top-item depth

This note separates two questions that the finite-scene experiments can easily
conflate.

1. Is there a constant `D` such that the next safe move is determined by the
   top `D` items of every stack for **every** frontier-winning tight
   configuration, independently of height?
2. Can one carefully controlled strategy maintain an invariant under which a
   fixed observation depth is sufficient on only the configurations that the
   strategy itself visits?

The first question has a negative answer. The second remains open.

## Observation and action sets

Fix four colors, four original stacks, two buffer stacks, and the objective of
reaching two exhausted original columns. At an idle tight checkpoint, the
depth-`D` observation records, for each labeled stack:

- its top `D` item colors, or all items if shorter;
- whether more items continue below the window;
- whether the stack is mixed or monochrome; and
- whether it is empty, partial, full, or completed and locked.

Color names are canonicalized by first visible occurrence. A safe unit action
is a legal one-item move whose source is an exact frontier-winning next-border
choice. The source mask comes from the exact top-border dynamic program, not
from a heuristic solution trace.

## A finite obstruction pair

The committed witnesses are:

| Witness | Height | Top-border state | Exact safe source | Exact safe unit action |
|---|---:|---:|---:|---:|
| `depth-obstruction-a.txt` | 38 | 489067 | stack 0 | `0 -> 2` |
| `depth-obstruction-b.txt` | 26 | 10211 | stack 1 | `1 -> 3` |

Their canonical tight representatives have the same depth-5 observation:

```text
qI|0:bf:00000+/1:bf:11111+/2:bp:00000+/3:bp:11111+/
   4:mp:22222+/5:mp:33333+
```

Here `b/m` means mixed/monochrome and `f/p` means full/partial. Their exact safe
unit-action masks are `0x4` and `0x800`, respectively. With the encoding
`bit(source * 8 + target)`, these are the two actions shown in the table, so
their intersection is empty.

`water-depth-witness` independently reconstructs both tight states, recomputes
the exact frontier policy tables, verifies the action masks, applies the
scaling construction below, and rejects the certificate unless the scaled
observations agree while the safe-action sets remain disjoint.

## Scaling lemma

For an integer `L >= 1`, replace every item in every original stack by `L`
consecutive copies. Capacity changes from `h` to `Lh`, and every color total
changes from `h` to `Lh`, so the instance remains balanced. Original color
boundaries and their rank table do not change.

At every corresponding top-border state,

```text
F'_c = L F_c,
G'_c = L G_c,
h'   = L h.
```

The source-specific subtraction inside `G_c` also scales by `L`. Therefore
every buffer demand is unchanged:

```text
ceil(max(0, F'_c - G'_c) / h')
= ceil(L max(0, F_c - G_c) / (Lh))
= ceil(max(0, F_c - G_c) / h).
```

The number of monochrome bins is unchanged. Hence the entire legal
border-transition graph, the two-exhausted-column goal set, and the exact safe
source masks are isomorphic before and after scaling.

Scale a tight physical representative in the same way. It remains tight:
original prefixes, monochrome host regions, fullness status, and top colors
are all preserved. Legal source-target compatibility is unchanged, so its
safe unit-action mask is unchanged as well.

## Theorem

There is no height-independent finite `D` for which the observation above
determines a safe unit action on every frontier-winning tight configuration.

For any proposed `D`, scale both obstruction witnesses by a factor `L >= D`.
The top `D` visible items of every nonempty stack are then copies of its former
top item. Both scaled witnesses therefore have exactly the same depth-`D`
observation, including continuation, mixed/monochrome, and fullness flags.
The scaling lemma preserves their disjoint safe-action sets. No action chosen
from that shared observation can be safe for both witnesses.

## Scope

This theorem rules out a universal rule based only on a fixed number of top
items and the listed finite flags. It does **not** rule out:

- a controller that deliberately maintains a stronger invariant and avoids
  one member of every obstruction pair;
- a policy that observes top color boundaries, exact run lengths, `F/G`
  aggregates, or a height-dependent counter; or
- a continuous retightening algorithm that carries additional finite control
  state between macro actions.

In particular, this obstruction does not survive unchanged when the observer
looks through a whole monochrome run instead of counting individual items.
`water-depth-witness` verifies that the two committed witnesses have different
top-two-run observations, even after scaling makes any prescribed finite item
window identical. This motivates treating color boundaries as the structural
units and adding only the bounded buffer-demand counters used by the exact
oracle.

The current unit-scene runs rebuild a canonical tight representative between
macro checkpoints. Consequently, the finite sampled minimum (`D = 6` on the
combined height-4-through-46 catalog) is a property of those sampled
macro-local traces, not a contradiction of the no-universal-depth theorem.
