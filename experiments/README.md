# Structural experiment seeds

`minimized-15b.txt` is a verified two-empty-column NO instance with only 15
color borders and no singleton runs. It is deliberately separate from the
original hunt corpus: the neighborhood workflow uses the five original seeds,
while the skeleton workflow varies the positive run lengths of this simplified
color-block order.

The matching certificate is generated and checked by CI. The instance was
first produced by the `ce-005 restart 1` job in GitHub Actions run
`31311471973`.

An exact length enumeration of this same 20-run color skeleton gives:

| Height | Exact symmetry classes | YES | NO |
|---:|---:|---:|---:|
| 5 | 1 | 1 | 0 |
| 6 | 59 | 59 | 0 |
| 7 | 1,029 | 1,029 | 0 |
| 8 | 9,648 | 9,645 | 3 |

The three height-8 NO classes are committed as `skeleton-h8-ce-000` through
`skeleton-h8-ce-002`, each with an independent transition-closed certificate.
This is an exact statement about this fixed run-color skeleton, not about all
five-color height-8 instances.

## One-empty-column minimal obstructions

The files `k1-minimal-c2-h4`, `k1-minimal-c3-h3`, and
`k1-minimal-c4-h2` are independently certified NO witnesses at the three
minimal parameter pairs for one empty column. Complete orderly scans give:

| Colors | Height | Exact classes | YES | NO |
|---:|---:|---:|---:|---:|
| 2 | 3 | 7 | 7 | 0 |
| 3 | 2 | 5 | 5 | 0 |
| 2 | 4 | 23 | 22 | 1 |
| 3 | 3 | 55 | 48 | 7 |
| 4 | 2 | 12 | 11 | 1 |

Height and color monotonicity therefore give the complete balanced-model
classification `E(c,h,1)` exactly when `c>=2`, `h>=2`, and `c+h>=6`.

## Exact global minimum height

The files `minimum-h5-ce-000` through `minimum-h5-ce-003` are four
pairwise-inequivalent height-5 NO instances. They were obtained by repeatedly
removing one unit from one run in every column, using every color exactly once,
from independently discovered taller NO instances. Every reduction candidate
was classified by the exact border oracle; the committed binary certificates
were then checked by the independent transition-closure verifier.

| Instance | Marked states | Checked transitions |
|---|---:|---:|
| `minimum-h5-ce-000` | 371 | 1,855 |
| `minimum-h5-ce-001` | 371 | 1,855 |
| `minimum-h5-ce-002` | 255 | 1,275 |
| `minimum-h5-ce-003` | 255 | 1,275 |

The complete height-4 universe scan examined 113,291,534 orderly
representations and classified all 21,383,163 exact symmetry classes as YES.
Together with the height-1 through height-3 scans and the witnesses here, this
proves that the minimum height admitting a NO instance for five colors, five
full columns, and two empty columns is exactly 5. The height-4 result is from
[GitHub Actions run 31315095516](https://github.com/lieoric/water-sort-counterexample/actions/runs/31315095516).

The balanced bottom-layer monotonicity theorem in the main README extends any
one of these witnesses to every height greater than 5. Thus NO instances exist
for every `h >= 5`, while the exhaustive scans prove that none exist below 5.

The complete `(c,h,k)=(4,5,2)` scan classified all 20,434,876 symmetry
classes as YES. Combined with the complete `(5,4,2)` YES scan and the height-5
witnesses here, this proves that `(c,h)=(5,5)` is a minimal two-empty-column
NO-existence parameter pair. The `(4,5,2)` result is from
[GitHub Actions run 31322659737](https://github.com/lieoric/water-sort-counterexample/actions/runs/31322659737).

## Four colors, two empty columns

`c4-k2-h9-no-000` is a balanced height-9 NO instance:

```text
222311112 / 223333002 / 200111002 / 113333000
```

The checked top-border closure contains 41 marked states and 163 examined
transitions. An independent exact physical-state BFS, using forced maximal
bulk pours and locked completed monochrome columns, exhausts 184 states and
also returns NO. The bounded next-run game proves every instance through
height 6 solvable, so the global minimum height is currently in `{7,8,9}`.

For this witness's fixed 16-run/12-border color skeleton, exhaustive positive
run-length enumeration is sharper: all 1,725 canonical height-8 assignments
are YES, while 4 of 8,264 height-9 assignments are NO. All nine canonical
balanced one-layer deletions of the committed witness are YES. These are exact
local-family results, not a proof that every height-8 arrangement is solvable.
