# Laporan Isolation Forest (Tahap 2)

Unsupervised anomaly score vs rule score vs ground truth generator.

## Anomaly score per tipe user

| tipe | n | mean | p50 | p95 | flag(-1) |
|---|---|---|---|---|---|
| heavy | 14053 | -0.127 | -0.127 | -0.064 | 0 |
| mixed | 2039 | -0.156 | -0.159 | -0.045 | 21 |
| normal | 151963 | -0.266 | -0.28 | -0.177 | 11 |
| normal_hard | 4038 | -0.101 | -0.094 | -0.027 | 31 |
| normal_hard_random | 4047 | -0.151 | -0.144 | -0.075 | 0 |
| remote | 9956 | -0.125 | -0.129 | -0.033 | 67 |
| risky | 3917 | 0.012 | 0.011 | 0.058 | 2501 |
| risky_noisy | 5969 | -0.041 | -0.042 | 0.012 | 507 |
| risky_routine | 1968 | -0.005 | -0.009 | 0.038 | 654 |
| risky_silent | 2050 | -0.034 | -0.034 | 0.006 | 208 |

## Precision@K: Isolation Forest vs Rule-based

| K | iforest | rule |
|---|---|---|
| 100 | 0.990 | 1.000 |
| 500 | 0.870 | 1.000 |
| 1000 | 0.825 | 0.982 |
| 2000 | 0.763 | 0.876 |
| 4000 | 0.630 | 0.749 |

## PR-AUC (ground truth = risky)

Isolation Forest: 0.6861
Rule-based:       0.8376

## Agreement top-4000

overlap: 2581 / 4000
