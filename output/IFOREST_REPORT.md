# Laporan Isolation Forest (Tahap 2)

Unsupervised anomaly score vs rule score vs ground truth generator.

## Anomaly score per tipe user

| tipe | n | mean | p50 | p95 | flag(-1) |
|---|---|---|---|---|---|
| heavy | 13892 | -0.135 | -0.136 | -0.073 | 0 |
| mixed | 1996 | -0.163 | -0.164 | -0.043 | 22 |
| normal | 158006 | -0.276 | -0.289 | -0.188 | 12 |
| normal_hard | 3993 | -0.100 | -0.092 | -0.024 | 36 |
| remote | 10030 | -0.128 | -0.13 | -0.037 | 57 |
| risky | 3973 | 0.025 | 0.027 | 0.069 | 3172 |
| risky_noisy | 6088 | -0.041 | -0.042 | 0.013 | 693 |
| risky_silent | 2022 | -0.064 | -0.058 | -0.019 | 8 |

## Precision@K: Isolation Forest vs Rule-based

| K | iforest | rule |
|---|---|---|
| 100 | 1.000 | 1.000 |
| 500 | 0.998 | 1.000 |
| 1000 | 0.992 | 1.000 |
| 2000 | 0.956 | 1.000 |
| 4000 | 0.798 | 0.900 |

## PR-AUC (ground truth = risky)

Isolation Forest: 0.8983
Rule-based:       0.9697

## Agreement top-4000

overlap: 3097 / 4000
