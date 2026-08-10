# Zero-debt past restoration for the c4/h7 D2 three-source ledger

## 1. Scope and current exact input

The completed checkpoint run classifies all `1,106,490` fixed futures at
their nonzero-debt first-exhaustion parents.  Its exact result is

\[
 1{,}091{,}706\text{ checkpoint-local YES},\qquad
 14{,}784\text{ checkpoint-local NO}.
\]

The `14,784` NO rows are **not** initial-layout counterexamples.  The next
stage restores zero-debt top prefixes, constructs balanced physical `4 x 7`
layouts, and solves those layouts from the real initial state.  This document
specifies that stage; it does not claim that the stage has run.

The formal NO distribution is:

| bridge edge | fixed futures | checkpoint-local NO |
|---:|---:|---:|
| 116 | 64,680 | 210 |
| 117 | 252,252 | 252 |
| 184 | 462 | 462 |
| 236 | 72,072 | 924 |
| 242 | 11,088 | 11,088 |
| 244 | 924 | 924 |
| 248 | 924 | 924 |
| other five selected edges | 704,088 | 0 |
| **total** | **1,106,490** | **14,784** |

The implementation must consume `report.json`, verify its ledger names and
hash, and then consume `local-no-ledger.jsonl`.  A bare ledger without the
matching complete report is not a formal input.

## 2. What a past-prefix template is

Use the report's labelled colours `(q,f,g,h)=(0,1,2,3)`.  At every selected
parent all four current sources have colour `q`.  Label the physical columns

\[
  (B,Q_0,Q_1,Q_2),
\]

where `B` is the source used by the bad exhaustion and the three `Q` columns
retain the stable slot order of `q_caps`.  Equal-cap columns remain labelled;
their fixed hidden suffixes must not be silently exchanged.

Let their current caps be

\[
  s=(s_B,s_0,s_1,s_2),
\]

let `d` be the parent debt, and let `G_c` be the total cap of current sources
of colour `c`.  The exposed inventory at the parent is

\[
  F=d+G. \tag{1}
\]

A labelled prefix candidate is a four-tuple of top-to-bottom words
`u=(u_B,u_0,u_1,u_2)` such that

1. `|u_i|=s_i`;
2. the last item of every `u_i` is `q`;
3. the combined colour histogram of the four words is exactly `F`.

Reserve the four final `q` items.  With

\[
 L=\sum_i(s_i-1),\qquad
 R_c=F_c-4[c=q], \tag{2}
\]

the number of histogram-valid labelled candidates is exactly

\[
 M(P)=\frac{L!}{\prod_c R_c!}. \tag{3}
\]

Equation (3) is the same balanced-completion count obtained by choosing the
non-`q` positions and assigning their colours.  It does **not** by itself
prove that a legal zero-debt history reaches the parent.

## 3. Exact reachability test and completeness

Compress each `u_i` into its run chain.  If a column changes from colour `a`
to colour `b` after `r` exposed items, its non-exhausting past event is

\[
 d_a\mathrel{+}=r,\qquad d_b\mathrel{-}=r. \tag{4}
\]

Starting with zero debt and `z=0`, the event is legal precisely when testing
the old source gives

\[
 \#\{c:d_c+r[c=a]>0\}\le 2. \tag{5}
\]

An exact rank DP interleaves the four per-column event chains while preserving
each chain's internal order.  A template is *parent-reachable* iff the DP has
at least one accepting interleaving.  The DP records both the number of legal
interleavings and its lexicographically first witness.

This enumeration is complete in both directions:

- Any zero-debt history reaching the labelled parent before the first
  exhaustion exposes one word of length `s_i` in each column.  Monotonic
  exposure fixes the per-column event chains, the real history is one of
  their order-preserving interleavings, and invariant (1) forces the combined
  histogram.  Therefore the history appears in (2)--(5).
- Conversely, any candidate accepted by (5) has a legal witness from zero
  debt.  The witness ends with the exact parent debts, current colours, caps,
  and labelled columns.  Appending the ledger suffixes therefore reconstructs
  a balanced initial layout that genuinely reaches that checkpoint.

There are no missing cycles or exhaustion cases: exposure in each column is
monotone, all parent caps are below seven, and the target parent still has
`z=0`.

## 4. Parent census

The following design-time census was independently regenerated from the 12
parent shapes.  `M` is the balanced histogram superset from (3), `T` is its
reachable subset from (5), and `H` is the sum of legal interleaving counts
over those `T` templates.

| edge | caps `(B,Q0,Q1,Q2)` | parent debt `(q,f,g,h)` | `F` | `M` | `T` | `H` |
|---:|---|---|---|---:|---:|---:|
| 116 | `(4,1,1,5)` | `(-4,0,1,3)` | `(7,0,1,3)` | 140 | 140 | 1,184 |
| 117 | `(4,1,1,5)` | `(-4,0,2,2)` | `(7,0,2,2)` | 210 | 210 | 2,076 |
| 174 | `(3,1,1,4)` | `(-3,0,1,2)` | `(6,0,1,2)` | 30 | 30 | 135 |
| 175 | `(3,1,1,5)` | `(-3,0,1,2)` | `(7,0,1,2)` | 60 | 45 | 177 |
| 178 | `(3,1,2,4)` | `(-3,0,1,2)` | `(7,0,1,2)` | 60 | 60 | 458 |
| 184 | `(2,2,2,4)` | `(-3,0,1,2)` | `(7,0,1,2)` | 60 | 60 | 348 |
| 236 | `(2,1,1,3)` | `(-2,0,1,1)` | `(5,0,1,1)` | 6 | 6 | 12 |
| 237 | `(2,1,1,4)` | `(-2,0,1,1)` | `(6,0,1,1)` | 12 | 8 | 14 |
| 238 | `(2,1,1,5)` | `(-2,0,1,1)` | `(7,0,1,1)` | 20 | 10 | 16 |
| 242 | `(2,1,2,3)` | `(-2,0,1,1)` | `(6,0,1,1)` | 12 | 12 | 26 |
| 244 | `(2,1,2,4)` | `(-2,0,1,1)` | `(7,0,1,1)` | 20 | 16 | 30 |
| 248 | `(2,2,2,3)` | `(-2,0,1,1)` | `(7,0,1,1)` | 20 | 20 | 44 |

The distinction `M != T` is material.  For example, the four histogram-valid
but unreachable edge-244 prefixes are

| `B` | `Q0` | `Q1` | `Q2` |
|---|---|---|---|
| `qq` | `q` | `qq` | `gqhq` |
| `qq` | `q` | `qq` | `qghq` |
| `qq` | `q` | `qq` | `hqgq` |
| `qq` | `q` | `qq` | `qhgq` |

In each case the only nontrivial event chain eventually tests a third positive
debt coordinate, so (5) rejects it.  Thus the 20 edge-244 candidates must not
be described as 20 reachable pasts.

## 5. Exact second-stage universes

For an edge with `N_e` checkpoint-local-NO rows, define

\[
 U_{\rm balanced}=\sum_e N_eM_e,
 \qquad
 U_{\rm reachable}=\sum_e N_eT_e. \tag{6}
\]

For the formal ledger:

| edge | `N_e` | `M_e` | balanced completions | `T_e` | reachable restorations |
|---:|---:|---:|---:|---:|---:|
| 116 | 210 | 140 | 29,400 | 140 | 29,400 |
| 117 | 252 | 210 | 52,920 | 210 | 52,920 |
| 184 | 462 | 60 | 27,720 | 60 | 27,720 |
| 236 | 924 | 6 | 5,544 | 6 | 5,544 |
| 242 | 11,088 | 12 | 133,056 | 12 | 133,056 |
| 244 | 924 | 20 | 18,480 | 16 | 14,784 |
| 248 | 924 | 20 | 18,480 | 20 | 18,480 |
| **total** | **14,784** |  | **285,600** |  | **281,904** |

Both numbers should be retained:

- `285,600` is the exact balanced-completion **superset**.  Solving all of it
  is cheap enough and gives a stronger finite-family result that does not rely
  on the prefix-reachability implementation.
- `281,904` is the exact subset connected to the checkpoint ledger by a legal
  zero-debt past.  The remaining `3,696` pairs are precisely the four
  unreachable edge-244 templates times its 924 NO futures.

Every `(future,prefix)` pair gives a distinct ordered labelled layout in the
reachable subset.  A lightweight symmetry census, without running the
initial solver, found:

| edge | labelled reachable layouts | after column symmetry | after column + colour symmetry |
|---:|---:|---:|---:|
| 116 | 29,400 | 15,400 | 15,400 |
| 117 | 52,920 | 27,720 | 13,860 |
| 184 | 27,720 | 14,036 | 14,036 |
| 236 | 5,544 | 2,904 | 1,452 |
| 242 | 133,056 | 133,056 | 66,528 |
| 244 | 14,784 | 14,784 | 7,392 |
| 248 | 18,480 | 9,372 | 4,686 |
| **total** | **281,904** | **217,272** | **123,354** |

No colour-and-column canonical class was shared by two of the seven edge
families in this census.  Production must regenerate these counts rather than
treating the table as an oracle.

## 6. Reconstructing and validating a full layout

For one ledger row and one prefix candidate:

1. Keep physical order `(B,Q0,Q1,Q2)`.
2. Reverse each `hidden_words_bottom_to_top` word to obtain the hidden suffix
   in top-to-bottom order.
3. Concatenate `u_i + hidden_i`.
4. Require every resulting column to have length seven.
5. Require exactly seven occurrences of every colour.
6. Require the first hidden item to differ from the final prefix colour `q`;
   otherwise the reported parent cap was not an exact run boundary.
7. For a template marked reachable, replay its stored interleaving from zero
   debt and require the exact ledger parent fixture, including labelled
   sources and the complete remaining run chains.

Steps 4--6 apply to the entire balanced superset.  Step 7 defines membership
in the reachable subset.

## 7. Deduplication without losing coverage

Structural validation happens before deduplication.  Solver work may then use
the key

\[
 K(W)=\min_{\pi\in S_4}
       \operatorname{sortColumns}(\pi(W)), \tag{7}
\]

where `pi` globally relabels the four colours and every column is represented
top-to-bottom.  This quotients exactly the colour and physical-column
symmetries of the puzzle.

The report must still retain both labelled totals in (6).  Each raw pair maps
to a canonical class and records the column permutation needed to translate a
representative winning path back to the labelled layout.  Duplicate columns
use the lexicographically first valid matching.  Every translated YES path is
replayed on its labelled layout, or the report explicitly proves the symmetry
transfer and replays at least the canonical representative.

Recommended ledgers are:

- `past-prefixes.tsv`: parent key, edge, prefix words, histogram-valid flag,
  reachable flag, legal-history count, and first history witness;
- `initial-layout-map.tsv`: future index, prefix index, reachable flag,
  canonical class, and symmetry transform;
- `initial-class-results.tsv`: canonical layout, exact-DP status, safe mask,
  winning path, states, and transitions;
- `initial-no-candidates.jsonl`: full balanced layouts reported NO by the
  primary initial solver, with provenance but no self-claimed independent
  verification.

## 8. Checkpoint NO versus real initial NO

The two notions must be separate fields, never one overloaded `status`:

- `checkpoint_local_no=true` means the fixed-chain solver loses when started
  at the nonzero-debt parent after one particular history.
- `initial_status=YES` means the zero-debt solver found and replayed a path on
  the complete balanced layout.  That path may diverge before the parent; in
  that case it is exactly the desired past bypass.
- `initial_status=NO_CANDIDATE` means the primary zero-debt DP exhausted all
  legal initial choices.  It becomes a certified global counterexample only
  after an independent solver or proof-certificate verifier agrees.

Reachability classifies the checkpoint provenance; it does not weaken the
meaning of a zero-debt result.  In particular, an independently verified NO
from the 3,696 balanced-but-parent-unreachable pairs would still be a genuine
balanced c4/h7 counterexample.  It must not be discarded merely because its
prefix does not reach this checkpoint.

Safe terminal report statuses are:

- `INCOMPLETE` for a bounded prefix;
- `BALANCED_COMPLETION_SUPERSET_ELIMINATED` if all 285,600 labelled pairs are
  exact-DP YES;
- `INITIAL_NO_CANDIDATES_EXPORTED` if one or more balanced layouts are primary
  DP NO;
- `GLOBAL_NO_CERTIFIED` only in a separate independently verified artifact.

Even the all-YES status eliminates only this explicitly reconstructed finite
family.  It does not prove universal c4/h7 solvability.

## 9. Proposed command line and implementation order

Suggested executable:

```text
water-c4-h7-d2-three-source-past
  --checkpoint-report PATH
  --output-dir PATH
  [--limit-restorations N]
  [--prefix-mode both|balanced-superset|reachable-only]
  [--no-symmetry]
  [--self-test]
```

`--limit-restorations` counts deterministic `(ledger row, prefix)` pairs, not
canonical solver classes.  Default `--prefix-mode both` enumerates all
`285,600` balanced pairs, marks the `281,904` reachable ones, and solves each
canonical class once.  `--no-symmetry` is a small-test differential mode.

Implementation order after the independent checkpoint artifact is accepted:

1. parse and hash-check the complete checkpoint artifact;
2. independently regenerate all 12 `M/T/H` parent rows;
3. materialize and validate the seven nonempty NO families;
4. emit raw-to-canonical mappings and assert the exact totals in (6);
5. exact-DP solve the canonical balanced superset and replay YES witnesses;
6. export, but do not globalize, every primary initial NO;
7. add an independent checker and only then a GitHub full workflow.
