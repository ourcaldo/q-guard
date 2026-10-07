# Laporan Isolation Forest (Tahap 2)

Unsupervised anomaly score vs rule score vs ground truth generator.

## Anomaly score per tipe user

| tipe | n | mean | p50 | p95 | flag(-1) |
|---|---|---|---|---|---|
| heavy | 13892 | -0.139 | -0.14 | -0.092 | 0 |
| mixed | 1996 | -0.159 | -0.158 | -0.05 | 22 |
| normal | 158006 | -0.271 | -0.282 | -0.193 | 4 |
| normal_hard | 3993 | -0.118 | -0.115 | -0.038 | 12 |
| remote | 10030 | -0.119 | -0.122 | -0.025 | 114 |
| risky | 3973 | 0.028 | 0.029 | 0.074 | 3301 |
| risky_noisy | 6088 | -0.051 | -0.052 | 0.011 | 547 |
| risky_silent | 2022 | -0.102 | -0.099 | -0.052 | 0 |

## Precision@K: Isolation Forest vs Rule-based

| K | iforest | rule |
|---|---|---|
| 100 | 1.000 | 1.000 |
| 500 | 1.000 | 0.980 |
| 1000 | 0.991 | 0.902 |
| 2000 | 0.963 | 0.739 |
| 4000 | 0.831 | 0.646 |

## PR-AUC (ground truth = risky)

Isolation Forest: 0.9152
Rule-based:       0.7036

## Agreement top-4000

overlap: 3062 / 4000
