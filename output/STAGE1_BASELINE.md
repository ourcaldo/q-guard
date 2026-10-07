# Tahap 1: Baseline Rule-Based — Laporan Akhir

Run: 2.000.000 transaksi / 200.000 user sintetis, seed 42, window Apr–Sep 2026.
Semua angka di bawah dievaluasi vs ground truth generator (tipe user). Pipeline
tetap memperlakukan data sebagai unlabeled — ground truth hanya untuk mengukur.

## Hasil utama

| Metrik | Nilai |
|---|---|
| Risky recall (needs_review + high_risk) | 91,2% (3.649 / 3.993) |
| Risky di high_risk | 67,3% (2.687) |
| Normal FP ( salah flag ≥ needs_review) | 0 / 169.956 (0%) |
| Remote FP di high_risk | 2 / 10.109 (0,02%) |
| Precision@2000 (top skor) | 1,000 (semuanya risky/mixed) |
| Separasi mean skor risky vs normal | 52,2 vs 14,6 |

## Threshold alert (terkalibrasi)

Awal AGENTS.md §9: 40/60/80. Skala skor aktual komponen menghasilkan risky
p50=53,5 / p95=60,1 dan normal p95=19,4, sehingga threshold asli terlalu
tinggi. Kalibrasi data-driven (sweep di VM, 2026-10-07):

```text
monitor       >= 30
needs_review  >= 45   (risky recall 0.914, normal FP 0.000, remote FP 0.007)
high_risk     >= 52   (risky recall 0.673, remote FP 0.002)
```

Kode: scripts/score_transactions.py (ALERT_THRESHOLDS, catatan kalibrasi inline).
Recalibrate saat komponen berubah atau data nyata tersedia.

## Interpretasi sesuai prinsip AGENTS.md

- Ranking bekerja sempurna untuk tujuan investigasi: reviewer yang membuka
  top-N selalu melihat kandidat relevan (precision@2000 = 1.0).
- Jarak jauh sendirian tidak men-vonis: remote user 94% tidak melewati
  monitor; yang high_risk hanya 2 dari 10.109 — kombinasi sinyal lain yang
  menaikkan mereka.
- Sinyal yang mengangkat risky user: remote_ratio (L), proporsi nominal
  bulat besar + repetisi nominal (A/R), konsentrasi merchant (R), dan
  lonjakan frekuensi (C). Kategori merchant tidak berperan, sesuai desain.
- Limitasi dikenal: steady-shape risky user (densus sejak awal, tanpa
  lonjakan) tidak terbantu komponen C dan sebagian lolos di monitor level.
  Ini ditangani tahap 2 (anomaly detection) yang tidak bergantung baseline
  waktu.

## Artefak

- scripts/score_transactions.py — scoring + kalibrasi threshold
- output/SCORING_REPORT.md — laporan run (per-output tabel lengkap)
- output/user_scores.parquet — skor per user + alert_level
- output/tx_scores.parquet — skor per transaksi

## Next: Tahap 2 — Isolation Forest (AGENTS.md §11.2)

1. Latih Isolation Forest pada fitur perilaku user (unlabeled).
2. Bandingkan anomaly_score dengan rule score: agreement/kedua ranking.
3. Evaluasi gabungan vs ground truth: PR-AUC, precision@K, recall@K.
4. Bandingkan dengan baseline rule-based ini.
