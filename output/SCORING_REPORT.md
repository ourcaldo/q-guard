# Laporan Scoring Tahap 1

Skor rule-based vs ground truth generator (evaluasi saja).

## Mean FinalUserRisk per tipe user

| tipe | n | mean final | mean T-user | pattern |
|---|---|---|---|---|
| heavy | 14053 | 14.9 | 9.2 | 23.4 |
| mixed | 2039 | 23.3 | 21.2 | 25.8 |
| normal | 151963 | 10.9 | 7.7 | 15.8 |
| normal_hard | 4038 | 27.5 | 21.4 | 34.9 |
| normal_hard_random | 4047 | 21.5 | 13.4 | 32.4 |
| remote | 9956 | 24.8 | 24.8 | 24.8 |
| risky | 3917 | 70.2 | 45.6 | 70.3 |
| risky_noisy | 5969 | 50.3 | 40.2 | 51.5 |
| risky_routine | 1968 | 65.6 | 44.1 | 65.9 |
| risky_silent | 2050 | 51.7 | 18.7 | 53.6 |

## Distribusi alert level per tipe

| tipe | normal | monitor | needs_review | high_risk | total |
|---|---|---|---|---|---|
| heavy | 14053 | 0 | 0 | 0 | 14053 |
| mixed | 1629 | 367 | 24 | 19 | 2039 |
| normal | 151961 | 0 | 2 | 0 | 151963 |
| normal_hard | 2817 | 1018 | 126 | 77 | 4038 |
| normal_hard_random | 3936 | 8 | 98 | 5 | 4047 |
| remote | 8477 | 1473 | 6 | 0 | 9956 |
| risky | 7 | 5 | 32 | 3873 | 3917 |
| risky_noisy | 401 | 1035 | 1468 | 3065 | 5969 |
| risky_routine | 21 | 25 | 49 | 1873 | 1968 |
| risky_silent | 203 | 34 | 346 | 1467 | 2050 |

## Precision@2000 (top-2000 skor tertinggi)

proporsi risky+mixed: 0.876

## False positive check

remote_user di high_risk: 0 / 9956 (harusnya mendekati 0 - jarak jauh sendirian bukti tidak cukup, AGENTS.md 3/16)
