# Laporan Graph Features (Tahap 4)

Skor M dihitung dari perilaku antar-user per merchant, tanpa
membaca label generator. Evaluasi vs ground truth:

## comp_M & alert per tipe

| tipe | n | comp_M mean | review+high |
|---|---|---|---|
| heavy | 14053 | 2.2 | 0 (0%) |
| mixed | 2039 | 3.5 | 49 (2%) |
| normal | 151963 | 2.3 | 3 (0%) |
| normal_hard | 4038 | 2.7 | 219 (5%) |
| normal_hard_random | 4047 | 2.2 | 116 (3%) |
| remote | 9956 | 1.2 | 6 (0%) |
| risky | 3917 | 27.8 | 3915 (100%) |
| risky_noisy | 5969 | 27.6 | 4990 (84%) |
| risky_routine | 1968 | 27.7 | 1944 (99%) |
| risky_silent | 2050 | 2.6 | 1833 (89%) |

## Top-20 merchant by graph score (anonim)

| merchant | graph_score | payers |
|---|---|---|
| M004700002 | 40.6 | 1147 |
| M004700007 | 40.2 | 987 |
| M020600003 | 39.9 | 1182 |
| M004700000 | 39.8 | 1218 |
| M004700004 | 39.8 | 1077 |
| M004700018 | 39.8 | 755 |
| M004700006 | 39.7 | 1036 |
| M020600005 | 39.6 | 1049 |
| M004700001 | 39.6 | 1185 |
| M004700005 | 39.5 | 1003 |
| M046100001 | 39.4 | 1234 |
| M046100002 | 39.3 | 1185 |
| M046100006 | 39.2 | 1065 |
| M004700014 | 39.2 | 816 |
| M004700008 | 39.2 | 1003 |
| M004700009 | 39.2 | 904 |
| M015600002 | 39.1 | 1101 |
| M004700029 | 39.0 | 585 |
| M004700011 | 39.0 | 881 |
| M004700012 | 39.0 | 835 |
