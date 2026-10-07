# Laporan Scoring Tahap 1

Skor rule-based vs ground truth generator (evaluasi saja).

## Mean FinalUserRisk per tipe user

| tipe | n | mean final | mean T-user | pattern |
|---|---|---|---|---|
| heavy | 13892 | 19.5 | 11.1 | 32.3 |
| mixed | 1996 | 26.6 | 23.7 | 31.0 |
| normal | 158006 | 14.7 | 9.4 | 22.5 |
| normal_hard | 3993 | 26.9 | 24.4 | 30.6 |
| remote | 10030 | 31.0 | 26.7 | 37.6 |
| risky | 3973 | 51.8 | 45.8 | 60.7 |
| risky_noisy | 6088 | 47.0 | 42.0 | 54.4 |
| risky_silent | 2022 | 22.3 | 19.3 | 26.7 |

## Distribusi alert level per tipe

| tipe | normal | monitor | needs_review | high_risk | total |
|---|---|---|---|---|---|
| heavy | 13892 | 0 | 0 | 0 | 13892 |
| mixed | 1291 | 686 | 17 | 2 | 1996 |
| normal | 158006 | 0 | 0 | 0 | 158006 |
| normal_hard | 2881 | 1108 | 4 | 0 | 3993 |
| remote | 4016 | 5919 | 95 | 0 | 10030 |
| risky | 232 | 106 | 1174 | 2461 | 3973 |
| risky_noisy | 541 | 582 | 3670 | 1295 | 6088 |
| risky_silent | 2022 | 0 | 0 | 0 | 2022 |

## Precision@2000 (top-2000 skor tertinggi)

proporsi risky+mixed: 0.739

## False positive check

remote_user di high_risk: 0 / 10030 (harusnya mendekati 0 - jarak jauh sendirian bukti tidak cukup, AGENTS.md 3/16)
