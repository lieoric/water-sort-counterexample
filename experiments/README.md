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
