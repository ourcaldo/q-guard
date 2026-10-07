# Laporan Scoring Tahap 1

Skor rule-based vs ground truth generator (evaluasi saja).

## Mean FinalUserRisk per tipe user

| tipe | n | mean final | mean T-user | pattern |
|---|---|---|---|---|
| heavy | 13920 | 19.9 | 11.1 | 33.1 |
| mixed | 2022 | 27.3 | 24.4 | 31.8 |
| normal | 169956 | 14.6 | 9.6 | 22.2 |
| remote | 10109 | 31.2 | 26.7 | 37.8 |
| risky | 3993 | 52.2 | 45.8 | 61.7 |

## Distribusi alert level per tipe

| tipe | normal | monitor | needs_review | high_risk | total |
|---|---|---|---|---|---|
| heavy | 13920 | 0 | 0 | 0 | 13920 |
| mixed | 1928 | 94 | 0 | 0 | 2022 |
| normal | 169956 | 0 | 0 | 0 | 169956 |
| remote | 9575 | 534 | 0 | 0 | 10109 |
| risky | 335 | 3439 | 219 | 0 | 3993 |

## Precision@2000 (top-2000 skor tertinggi)

proporsi risky+mixed: 1.000

## False positive check

remote_user di high_risk: 0 / 10109 (harusnya mendekati 0 - jarak jauh sendirian bukti tidak cukup, AGENTS.md 3/16)
