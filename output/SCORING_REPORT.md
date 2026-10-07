# Laporan Scoring Tahap 1

Skor rule-based vs ground truth generator (evaluasi saja).

## Mean FinalUserRisk per tipe user

| tipe | n | mean final | mean T-user | pattern |
|---|---|---|---|---|
| heavy | 13892 | 15.2 | 9.2 | 24.1 |
| mixed | 1996 | 24.2 | 21.0 | 27.6 |
| normal | 158006 | 11.3 | 7.7 | 16.6 |
| normal_hard | 3993 | 32.1 | 21.5 | 39.9 |
| remote | 10030 | 25.2 | 24.9 | 25.6 |
| risky | 3973 | 72.1 | 45.9 | 72.1 |
| risky_noisy | 6088 | 52.0 | 40.0 | 53.3 |
| risky_silent | 2022 | 45.9 | 17.4 | 49.7 |

## Distribusi alert level per tipe

| tipe | normal | monitor | needs_review | high_risk | total |
|---|---|---|---|---|---|
| heavy | 13892 | 0 | 0 | 0 | 13892 |
| mixed | 1526 | 395 | 38 | 37 | 1996 |
| normal | 157978 | 1 | 13 | 14 | 158006 |
| normal_hard | 2244 | 919 | 456 | 374 | 3993 |
| remote | 8362 | 1655 | 12 | 1 | 10030 |
| risky | 1 | 2 | 7 | 3963 | 3973 |
| risky_noisy | 449 | 793 | 1108 | 3738 | 6088 |
| risky_silent | 453 | 23 | 700 | 846 | 2022 |

## Precision@2000 (top-2000 skor tertinggi)

proporsi risky+mixed: 1.000

## False positive check

remote_user di high_risk: 1 / 10030 (harusnya mendekati 0 - jarak jauh sendirian bukti tidak cukup, AGENTS.md 3/16)
