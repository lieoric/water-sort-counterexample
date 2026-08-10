# A zero-debt bypass for the 210 edge-116 three-source residuals

## Scope and claim boundary

The three-legal-source `D2` checkpoint experiment has 1,106,490 labelled
fixed futures.  A completed production artifact reports 14,784 local `NO`
rows in the full experiment.  They occur on seven bridge edges:

| bridge edge | local `NO` rows |
| ---: | ---: |
| 116 | 210 |
| 117 | 252 |
| 184 | 462 |
| 236 | 924 |
| 242 | 11,088 |
| 244 | 924 |
| 248 | 924 |

This note eliminates exactly the 210 rows on edge 116 after restoring every
balanced zero-debt past compatible with those rows.  It proves more than the
local fixed-future recursion: from the initial state there is an explicit
legal macro to one exhausted column, after which **every** maximal legal
continuation reaches a second exhausted column.

The other 14,574 local `NO` rows are not treated here.  Consequently this is
not an elimination of the full three-source checkpoint family and not a
proof of the full `c=4,h=7,k=2` theorem.

## 1. Border identities

Use colors `q,f,g,h`, height `7`, and let `z` be the number of exhausted
original columns.  A source of color `x` and accumulated cap `s` is legal at
debt vector `d` precisely when

\[
 \left|\operatorname{Pos}(d+s e_x)\right|\le 2+z.       \tag{1}
\]

A live event `x_s -> y_R`, with `R<7`, changes the debt by

\[
 s(e_x-e_y),                                             \tag{2}
\]

whereas an exhausting event whose final run has color `y` changes it by

\[
 s e_x+(7-s)e_y.                                         \tag{3}
\]

Two elementary identities will be used repeatedly.

### Prefix-test identity

Fix a background debt `b` and walk down one original column.  Let `W_r` be
the top-to-bottom prefix through its current run, let `r=|W_r|`, and let the
current source color be `x`.  The contribution of that column to the debt is

\[
 \#(W_r)-r e_x.                                          \tag{4}
\]

Therefore its source test is simply

\[
 b+\#(W_r).                                              \tag{5}
\]

Here `#(W_r)` is the four-coordinate color-count vector of the prefix.  This
follows by telescoping (2) across the runs of `W_r`.  In particular, a word
using only two colors can be walked from a background for which only those
two colors can be positive.

### Remaining-inventory identity

At any border state let `H_i` be the number of color-`i` balls still hidden
strictly below the active sources, and let

\[
 G_i=\sum_{\text{active source of color }i}\text{cap}.
\]

Every color has total inventory seven.  The already exposed prefix has
count `7-H_i`, so `d=F-G` gives

\[
 d_i=7-H_i-G_i.                                         \tag{6}
\]

This remains true after an original column is exhausted.

## 2. The uniform edge-116 core

All 210 local `NO` rows have the same checkpoint data:

\[
 d=(-4,0,1,3),                                          \tag{7}
\]

with the following four sources and fixed futures.

* `A` is the bad source `q_4`, followed by the final word `fff`.
* `C,D` are two sources `q_1`, each followed by `ff` and then an arbitrary
  four-letter word over `{g,h}`.
* `B` is `q_5`, followed by a two-letter word over `{g,h}`.

The 210 futures split by the top-to-bottom word below `B` as follows:

| word below `q_5` | small-tail `g` count | futures |
| --- | ---: | ---: |
| `gh` | 5 | `C(8,5)=56` |
| `gg` | 4 | `C(8,4)=70` |
| `hg` | 5 | `C(8,5)=56` |
| `hh` | 6 | `C(8,6)=28` |

Thus there are `56+70+56+28=210` labelled fixed futures.  The local failure
is the same in every row: at (7), taking both `q_1 -> f_3` events packs the
two small columns into a `D2` terminal, while exhausting `A` first gives a
`Tq` terminal.  This says nothing about a different ordering from the
zero-debt initial state.

## 3. Every compatible zero-debt past

Let the top-to-bottom past prefix of `A` also be denoted `A`; it has length
four and ends in `q`.  Let the corresponding prefix of `B` have length five
and end in `q`.

At (7), the total active `q` cap is

\[
 4+1+1+5=11.
\]

Hence the exposed-prefix inventory is `d+11e_q=(7,0,1,3)`.  The two
length-one prefixes are forced to be the single letter `q`.  Consequently

\[
 \#(A)+\#(B)=5e_q+e_g+3e_h.                     \tag{8}
\]

Conversely, every pair of words satisfying (8), with lengths four and five
and final letter `q`, is a compatible labelled past template.  After fixing
the two final `q` letters, the other seven positions contain
`q^3 g h^3`, so their number is

\[
 \frac{7!}{3!1!3!}=140.                         \tag{9}
\]

The proof below applies to all `210*140=29,400` full balanced layouts.

## 4. Double-`q_1` start and the `g`-free deep prefix

From zero debt, take the event `q_1 -> f_3` on `C`, then on `D`.  The two
source tests have respectively one positive coordinate, so both moves are
legal, and the resulting state is

\[
 b=(2,-2,0,0),\qquad z=0,                       \tag{10}
\]

with `C,D` both at source `f_3`.

Equation (8) contains only one `g`, so at least one of the two deep prefixes
`A,B` is `g`-free.  Such a prefix uses only `{q,h}`.  By (5), walking it from
the background (10) has at most the two positive colors `q,h` at every
source test.  It can therefore be advanced legally to its final `q` gate.

## 5. The deep-anchor macro

### Case A: `A` is `g`-free

Write `b_h` for the number of `h` letters in `A`.  At the `q_4` gate the
debt is

\[
 (2-b_h,-2,0,b_h).
\]

The test for `q_4 -> f_7` has at most the two positive colors `q,h`, so the
event is legal.  Its successor is

\[
 (6-b_h,1,0,b_h),\qquad z=1.                    \tag{11}
\]

The two small columns have not moved from `f_3`.

### Case B: `B` is `g`-free

Let `b_h=#_h(B)`.  At its `q_5` gate the debt is

\[
 (2-b_h,-2,0,b_h),                              \tag{12}
\]

and the `q_5` event is legal.

* If the two-letter future is `gg` or `hh`, that event exhausts `B`.
* If it is `hg`, the live event gives
  `(7-b_h,-2,0,b_h-5)`.  Testing the new source `h_6` gives only `q,h`
  positive, so `h_6 -> g_7` exhausts `B` legally.
* The only corner is the future `gh`.  After `q_5 -> g_6`,

  \[
   D=(7-b_h,-2,-5,b_h).                          \tag{13}
  \]

  Here (8) forces

  \[
   \#(A)=b_h e_q+e_g+(3-b_h)e_h.                 \tag{14}
  \]

  Since `A` ends in `q`, necessarily `1<=b_h<=3`.  Walk `A` instead of
  trying to exhaust `B`.  Every source test on this walk equals `D` plus a
  prefix count of `A`.  The unique `g` can raise the `g` coordinate only
  from `-5` to `-4`; hence only `q,h` are positive and every step is legal.
  At the `q_4` gate the state is

  \[
   (3,-2,-4,3).
  \]

  The exhausting event `q_4 -> f_7` is legal and gives the fixed state

  \[
   (7,1,-4,3),\qquad z=1.                        \tag{15}
  \]

In every case the macro reaches exactly one exhausted deep column while
`C,D` are still the two sources `f_3`.  No choice in the four-letter tails
of `C,D` was used.

## 6. The two-anchor no-terminal lemma at `z=1`

Consider any state reached after the macro and before a second exhaustion.
The first exhausting event was legal at threshold two.  Its source test had
at most two positive coordinates, and (3) can introduce at most one further
positive coordinate.  Thus its successor has at most three positive debts.

At `z=1`, a legal live event has successor

\[
 (d+s e_x)-s e_y.                                      \tag{18}
\]

Its positive support is contained in that of its legal source test, so every
later live successor also has at most three positive debts.  Therefore at
every pre-goal state there is a color `j` with `d_j<=0`.

Suppose such a state were terminal.  An illegal source test at threshold
three must make all four coordinates positive.  Any source whose color is
not `j` leaves `d_j` unchanged and is therefore legal.  Hence all three
active sources would have to have the same color `j`; if a second debt were
nonpositive, the same argument would still make every action legal, so `j`
would be the unique nonpositive color.

The remaining deep column never has `f` as a live source.  Therefore both
small columns must already have left `f_3`.  Their tails use only `{g,h}`, so
their common source color is `j in {g,h}` and their caps `c_C,c_D` satisfy

\[
 c_C>=4,\qquad c_D>=4.                            \tag{16}
\]

Let the remaining deep cap be `c_E`.  Applying (6) to the common source
color gives its source-test coordinate as

\[
 d_j+c_E=7-H_j-c_C-c_D\le 7-4-4=-1.              \tag{17}
\]

So the deep source test does not make `j` positive and is legal, a
contradiction.  There is no non-goal terminal at `z=1`.

Every event advances a finite original-column run chain.  It follows that
every maximal legal continuation after the macro must eventually exhaust a
second column.

## 7. Result

**Edge-116 210-row bypass theorem.**  Every balanced zero-debt initial layout
whose checkpoint future is one of the 210 edge-116 local `NO` rows has a
legal path to `z>=2`: take both exposed `q_1 -> f_3` events first, execute the
deep-anchor macro of Section 5, and then take legal events in any order until
the second exhaustion.

The accompanying checker independently enumerates the 210 futures and 140
past templates, replays every macro step, verifies (6) on all explored
states, and checks the constructive no-terminal argument throughout the
reachable `z=1` suffix.  This is a finite audit of the proof, not a larger
checkpoint search.
