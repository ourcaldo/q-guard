# Laporan Supervised (Rehearsal) - Point 3

Latihan mekanik pipeline supervised. Label = generator
(placeholder), BUKAN kebenaran - lihat catatan di file ini.

## random_forest

PR-AUC (test window): 0.9972
Precision@K (test): 100=1.000, 500=1.000, 1000=1.000, 2000=1.000
Recall@n(risky): 0.980

## grad_boost

PR-AUC (test window): 0.9975
Precision@K (test): 100=1.000, 500=0.998, 1000=0.999, 2000=0.999
Recall@n(risky): 0.982

## Baseline (rule) di test window yang sama

PR-AUC: 0.9290

## Catatan keabsahan

1. Label berasal dari generator, dipakai sebagai placeholder
   untuk menguji MEKANIK pipeline, bukan performa model.
   (AGENTS.md 10.2: label sintetis bukan kebenaran final).
2. Split waktu dijaga: train Apr-Jun, test Jul-Sep - tidak
   ada kebocoran masa depan (AGENTS.md 13).
3. Saat label human review tersedia, ganti kolom user_type
   dengan keputusan reviewer; seluruh kode tetap sama.