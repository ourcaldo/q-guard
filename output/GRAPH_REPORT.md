# Laporan Graph Features (Tahap 4)

Skor M dihitung dari perilaku antar-user per merchant, tanpa
membaca label generator. Evaluasi vs ground truth:

## comp_M & alert per tipe

| tipe | n | comp_M mean | review+high |
|---|---|---|---|
| heavy | 14086 | 2.3 | 0 (0%) |
| mixed | 1963 | 4.0 | 52 (3%) |
| normal | 148040 | 2.3 | 3 (0%) |
| normal_collective | 2022 | 2.3 | 1 (0%) |
| normal_hard | 4021 | 3.0 | 190 (5%) |
| normal_hard_random | 4018 | 2.5 | 112 (3%) |
| remote | 9772 | 1.3 | 1 (0%) |
| risky | 4074 | 28.9 | 4070 (100%) |
| risky_noisy | 5941 | 28.7 | 4845 (82%) |
| risky_routine | 1984 | 28.6 | 1958 (99%) |
| risky_silent | 2054 | 2.5 | 1788 (87%) |
| risky_silent_shared | 2025 | 3.1 | 1878 (93%) |

## Top-20 merchant by graph score (anonim)

| merchant | graph_score | payers |
|---|---|---|
| M026200016 | 45.9 | 2 |
| M015600003 | 41.5 | 1124 |
| M020600000 | 41.4 | 1250 |
| M020600010 | 41.3 | 901 |
| M015600002 | 41.2 | 1169 |
| M038100010 | 40.9 | 2 |
| M004700006 | 40.9 | 997 |
| M015600005 | 40.9 | 1121 |
| M004700000 | 40.7 | 1166 |
| M020600002 | 40.7 | 1143 |
| M004700002 | 40.7 | 1045 |
| M015600001 | 40.6 | 1177 |
| M042000015 | 40.5 | 2 |
| M020600020 | 40.4 | 793 |
| M004700004 | 40.4 | 1040 |
| M015600010 | 40.1 | 936 |
| M004700010 | 40.1 | 921 |
| M004700007 | 40.0 | 981 |
| M015600000 | 39.9 | 1240 |
| M015600007 | 39.9 | 949 |
