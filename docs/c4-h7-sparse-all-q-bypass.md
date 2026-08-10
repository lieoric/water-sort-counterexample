# A sparse all-`q` past bypass for the three-source local-NO ledger

## Scope and claim boundary

The complete production three-source checkpoint audit contains 14,784
parent-checkpoint local-NO fixed futures.  They lie on only seven bridge
edges and collapse to 44 canonical next-card macros.  This note proves that
none of those nonzero-debt parents is an unavoidable barrier from its true
zero-debt past.

More precisely, every compatible zero-debt past admits this bypass from
**either** of two distinguished low-cap columns: advance that column to the
parent border, take its fixed live `q -> f` event early, and the successor
still has a legal source.

This is a **nonterminal past bypass**.  It does not prove that the bypass
state is winning, restore and solve the represented initial layouts, or
prove universal height-seven solvability.  The 14,784 rows remain genuine
local NOs when play is artificially started at the reported nonzero-debt
parent with its fixed future.

## 1. The ledger collapses to one normal form

Use colors `(q,f,g,h)`.  Every one of the seven local-NO bridge edges has an
all-`q` parent

\[
 d(P)=(-Q,0,X,Y),
 \qquad X,Y>0,
 \qquad Q=X+Y\le4.                              \tag{1}
\]

All four active tops are `q`.  They consist of

- the bad source `q_s`, whose fixed event exhausts through `f^{7-s}`;
- two low siblings `q_a,q_b`, whose fixed next events are live entries into
  `f`; and
- one high sibling `q_m`, with `m>Q`, whose fixed next event enters `g` or
  `h`.

Exactly the bad source and the two low siblings are legal at `P`.  In every
macro

\[
 a,b\le2.                                       \tag{2}
\]

If the low cards are

\[
 q_a\to f_A,
 \qquad q_b\to f_B,
\]

the future `f` inventory is tight:

\[
 (7-s)+(A-a)+(B-b)=7.                           \tag{3}
\]

Since `d_f(P)=0` and no active top is `f`, the already exposed count is
`F_f(P)=0`.  Equation (3) says that the bad tail and the two low cards assign
all seven future `f` items.  No other hidden suffix contains `f`.

The exact production census is:

| edge | `d(P)` | sources `bad ; low,low ; high` | `F_q(P)` | card macros | local-NO futures |
|---:|---|---|---:|---:|---:|
| 116 | `(-4,0,1,3)` | `4 ; 1,1 ; 5` | 7 | 4 | 210 |
| 117 | `(-4,0,2,2)` | `4 ; 1,1 ; 5` | 7 | 4 | 252 |
| 184 | `(-3,0,1,2)` | `2 ; 2,2 ; 4` | 7 | 6 | 462 |
| 236 | `(-2,0,1,1)` | `2 ; 1,1 ; 3` | 5 | 8 | 924 |
| 242 | `(-2,0,1,1)` | `2 ; 1,2 ; 3` | 6 | 8 | 11,088 |
| 244 | `(-2,0,1,1)` | `2 ; 1,2 ; 4` | 7 | 6 | 924 |
| 248 | `(-2,0,1,1)` | `2 ; 2,2 ; 3` | 7 | 8 | 924 |

Thus five edges, representing 2,772 local-NO futures, already have
`F_q(P)=7`.  The two unsaturated parents are edges 236 and 242.  They have
`Q=2`, so their true past contains only one exposed `g` and one exposed `h`
among all four columns.

These parents are all in the `a=q` bridge form.  The earlier `a!=q`
first-sweep inequalities do not apply.  Their bridge terminal energy is
zero except on edge 184, where it is one; none is an `E=2` bridge parent.

## 2. Low prefixes can be performed solo

Fix a zero-debt initial layout and a legal past which reaches one of the
parents (1).  For a current column, let its **exposed prefix word** be written
from its initial top toward its current border.  Every such word ends in
`q`, because all four parent tops are `q`.  It contains no `f`, because
`F_f(P)=0`.

Consider either low column.  Its prefix length is its current cap, at most
two by (2).  Therefore its word is one of

\[
 q,
 \qquad qq,
 \qquad xq\quad(x\in\{g,h\}).                   \tag{4}
\]

Every word in (4) uses at most two colors.  Starting from zero debt, all
past border events of this one column may be performed before any event of
the other three columns.  Indeed, at any source test, adding back the current
host cap leaves exactly the nonnegative prefix-count vector, whose positive
support is contained in the colors used by the word.  Hence every source
test has at most two positive coordinates.

This is the solo-prefix lemma specialized to the production low caps.  It is
stronger here than a pigeonhole argument: **both** low columns are always
solo-executable, for every compatible past.

## 3. Exact early-event terminal test

After performing a low prefix solo, immediately take its fixed live event
`q_c -> f_R`, where `c` is one or two and `R>c`.

If the prefix is all `q`, its count vector is `c e_q`.  Immediately after
the live event the debt is

\[
 d'=c e_q-c e_f.                                \tag{5}
\]

Only `q` is positive.  The new `f_R` source is itself legal, since its test
creates only the second positive coordinate.  Thus (5) is nonterminal.

The only remaining case is the word `xq`, necessarily of length two.  Let
`y` be the other color in `{g,h}`.  Immediately after `q_2 -> f_R`,

\[
 d'=(1,-2,1,0)                                  \tag{6}
\]

in color order `(q,f,x,y)`.  The selected `f_R` source is illegal because
`R>2`: it would make `f` the third positive color.  An untouched initial
source is legal exactly when its top color is `q` or `x`; a `y` top creates
the third positive color.  No untouched top is `f`, because the exposed
prefixes contain no `f`.

Consequently:

> The early move from an `xq` low prefix is terminal if and only if all
> three other initial top colors are `y`.                         \(\tag{7}\)

## 4. Both production low moves are nonterminal

**Theorem 1 (sparse all-`q` early-low bypass).**  For every zero-debt past
compatible with any of the 44 production local-NO macros, each of the two
low columns can be performed solo and followed by its fixed live `q -> f`
event so that the successor has a legal source.

**Proof.**  Both low prefixes are solo-executable by (4).  An all-`q` prefix
is nonterminal by (5).  If a low prefix is `xq`, terminality would require
all three other initial tops to be `y` by (7).  In particular, those three
prefixes would expose at least three `y` items, so

\[
 F_y(P)\ge3.                                     \tag{8}
\]

The only production edges with a cap-two low source are edge 184, with
`(X,Y)=(1,2)`, and edges 242, 244, and 248, with `(X,Y)=(1,1)`.  Thus every
possible complement color has exposure at most two, contradicting (8).
Every cap-two low is therefore nonterminal; a cap-one low has prefix `q` and
was already covered by (5).  \(\square\)

There is also a weaker argument which does not use the production exposure
table.  If two words `x_1q,x_2q` both gave terminal early moves, (7) for the
first would force `x_2=y_1`, hence `y_2=x_1`.  A third column's initial top
would then be required to equal both distinct colors `y_1` and `y_2`.  Thus
two low moves of this form can never both be terminal, even in a larger
abstract macro family.

The production-specific conclusion is stronger: neither one is terminal.
The proof uses only the parent debts, the two low caps, their live `f`
cards, and `F_f(P)=0`.  It is independent of the high card endpoint and of
every deeper residual word.  Therefore it covers all 44 macros and all
14,784 production local-NO fixed futures at once.

## 5. What the reported local traps do

The local-NO rows themselves reduce to three forward traps when play is
started at `P`.

1. **Immediate `3+1 D2` (13,398 futures).**  On edges 184, 242, 244, and
   248, either legal low move immediately lands in a `3+1` `D2` terminal.
2. **Forced-two `2+2 D2` (462 futures).**  On edges 116 and 117, taking one
   low move leaves the other low source uniquely legal; taking it lands in a
   `2+2` `D2` terminal.
3. **Forced `E=2 Tq` relay (924 futures).**  On edge 236, the two low moves
   are forced first.  In every reported local-NO word, both resulting `f_2`
   columns have a singleton `q` as their next run.  Up to swapping the two
   low columns, the forced relay is

   \[
   q_1\to f_2,
   \quad q_1\to f_2,
   \quad f_2\to q_3,
   \quad q_2\xrightarrow{\rm final}f^5,
   \quad f_2\to q_3.                            \tag{9}
   \]

   It ends at

   \[
   z=1,
   \qquad d=(-2,7,1,1),
   \qquad\text{tops }q_3,q_3,q_3.               \tag{10}
   \]

   This is exactly the `E=2` `Tq` saturation corner: `F_q=7`.  Equation (3)
   also gives `F_f=7`.

Theorem 1 does not solve any of these states after entering them.  It changes
the order of the zero-debt past so that one low card is taken before the
all-`q` parent is assembled.  The resulting state is known only to be
nonterminal.

## 6. Independent finite audit

`tests/check_c4_h7_sparse_all_q_bypass.py` reads the certified production
`report.json` and `local-no-ledger.jsonl`.  Without expanding any additional
future, it

1. verifies all 14,784 ledger rows and their seven-edge counts;
2. collapses them to the exact 44 parent/card macros;
3. checks (1)--(3), the three-legal-source split, the low-cap bound (2), and
   the saturation census;
4. enumerates the small exposed-prefix word box compatible with each macro
   and verifies that neither early low move is terminal; and
5. verifies the singleton `q` relay condition on all 924 edge-236 rows.

The prefix audit contains at most `3^(sum caps - 4)` assignments per parent
macro and is not a Water Sort state search.  It does not read or enumerate
any zero-debt suffix completion beyond the rows already present in the
production ledger.
