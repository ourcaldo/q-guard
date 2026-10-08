# Laporan Isolation Forest (Tahap 2)

Unsupervised anomaly score vs rule score vs ground truth generator.

## Anomaly score per tipe user

| tipe | n | mean | p50 | p95 | flag(-1) |
|---|---|---|---|---|---|
| heavy | 13892 | -0.134 | -0.133 | -0.073 | 0 |
| mixed | 1996 | -0.157 | -0.157 | -0.046 | 17 |
| normal | 158006 | -0.272 | -0.285 | -0.181 | 13 |
| normal_hard | 3993 | -0.097 | -0.088 | -0.024 | 34 |
| remote | 10030 | -0.129 | -0.131 | -0.041 | 33 |
| risky | 3973 | 0.022 | 0.021 | 0.066 | 3066 |
| risky_noisy | 6088 | -0.039 | -0.04 | 0.013 | 608 |
| risky_silent | 2022 | -0.031 | -0.029 | 0.007 | 229 |

## Precision@K: Isolation Forest vs Rule-based

| K | iforest | rule |
|---|---|---|
| 100 | 1.000 | 1.000 |
| 500 | 0.992 | 1.000 |
| 1000 | 0.972 | 1.000 |
| 2000 | 0.930 | 1.000 |
| 4000 | 0.771 | 0.900 |

## PR-AUC (ground truth = risky)

Isolation Forest: 0.8655
Rule-based:       0.9661

## Agreement top-4000

overlap: 3019 / 4000
