# Laporan Scoring Tahap 1

Skor rule-based vs ground truth generator (evaluasi saja).

## Mean FinalUserRisk per tipe user

| tipe | n | mean final | mean T-user | pattern |
|---|---|---|---|---|
| heavy | 13892 | 14.9 | 9.2 | 23.5 |
| mixed | 1996 | 23.1 | 21.0 | 25.7 |
| normal | 158006 | 10.9 | 7.6 | 15.8 |
| normal_hard | 3993 | 27.5 | 21.3 | 35.0 |
| remote | 10030 | 24.8 | 24.8 | 24.8 |
| risky | 3973 | 70.7 | 46.2 | 70.7 |
| risky_noisy | 6088 | 50.4 | 40.2 | 51.7 |
| risky_silent | 2022 | 52.3 | 18.9 | 53.9 |

## Distribusi alert level per tipe

| tipe | normal | monitor | needs_review | high_risk | total |
|---|---|---|---|---|---|
| heavy | 13892 | 0 | 0 | 0 | 13892 |
| mixed | 1608 | 356 | 21 | 11 | 1996 |
| normal | 158003 | 0 | 2 | 1 | 158006 |
| normal_hard | 2808 | 982 | 130 | 73 | 3993 |
| remote | 8532 | 1496 | 2 | 0 | 10030 |
| risky | 2 | 8 | 28 | 3935 | 3973 |
| risky_noisy | 423 | 1078 | 1385 | 3202 | 6088 |
| risky_silent | 188 | 15 | 316 | 1503 | 2022 |

## Precision@2000 (top-2000 skor tertinggi)

proporsi risky+mixed: 1.000

## False positive check

remote_user di high_risk: 0 / 10030 (harusnya mendekati 0 - jarak jauh sendirian bukti tidak cukup, AGENTS.md 3/16)
