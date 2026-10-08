# Laporan Round 2: Penguatan Sinyal Repetisi & Data Adversarial

Run: 2.000.000 transaksi / 200.000 user sintetis (seed 42), dengan tipe
adversarial. Dievaluasi vs ground truth generator; pipeline tetap unlabeled.

## Konteks: kenapa ada round 2

Round 1 (data terlalu mudah) menghasilkan PR-AUC 0.995 — terlalu bagus untuk
dipercaya. Hardening round 1 menambah 3 tipe adversarial, PR-AUC IF jatuh ke
0.915 dan rule ke 0.704, serta menemukan gap: `risky_silent` (deposit lokal,
nominal bulat berulang) tidak terdeteksi sama sekali (0%). Round 2 menutup gap
tersebut dengan memperkuat sinyal repetisi nominal.

## Perubahan round 2

1. Komponen A (nominal) kini berbasis `repeat_amount_ratio` — proporsi transaksi
   yang nominal persisnya muncul lebih dari sekali — dengan bobot 0.45,
   menggantikan dominasi roundness semata.
2. Skor transaksi A_i memakai `amt_occurrences`: berapa kali nominal persis
   itu muncul dalam riwayat user itu sendiri.
3. Isolation Forest memakai 2 fitur baru: `repeat_round_ratio` (nominal bulat
   yang berulang) dan `max_amount_occurrences` (nominal paling sering diulang).
4. Pattern score kini menyertakan komponen A langsung (bobot 0.40).
5. Pattern floor: pattern score >= 48 membawa user ke review tanpa menunggu
   skor transaksi — pola deposit satu-dimensi kini bisa mengangkat sendirian.

## Hasil utama (2 jt tx)

| Tipe | Round 1 (review+high) | Round 2 | Perubahan |
|---|---|---|---|
| risky | 91% | **99,9%** (3.970/3.973) | naik |
| risky_noisy | 82% | **98,0%** (4.846/6.088) | naik |
| risky_silent | **0%** | **76,5%** (1.546/2.022) | gap tertutup |
| normal | 0% | 0,017% (27/158.006) | tetap bersih |
| remote | 0,1% | 0,1% (13/10.030) | tetap terjaga |
| normal_hard | 21% | 20,8% (830/3.993) | lihat limitasi |
| mixed | 4% | 3,8% (75/1.996) | stabil |

Metrik gabungan:

```text
PR-AUC (ground truth = risky):
  rule-based      0.970   (round 1: 0.704)
  Isolation Forest 0.898  (round 1: 0.915)
Precision@2000 (rule)  : 1.000
Agreement top-4000     : 3.097/4.000 (77%)
remote di high_risk    : 1/10.030 (0,01%)
```

## Interpretasi

- **Gap silent tertutup.** Dari nol menjadi 76,5% — sinyal repetisi nominal
  adalah deteksi yang benar untuk pola deposit tanpa sinyal lokasi/merchant.
- **Rule kini melampaui IF** (0.970 vs 0.898). Penjelasan: fitur repetisi
  adalah sinyal diskrit yang kuat; rule memakainya langsung dengan skala
  yang dikalibrasi, IF harus "menemukan" struktur itu sendiri di ruang fitur
  yang juga dihuni normal_hard yang kini lebih mirip risky. Kombinasi
  keduanya tetap yang terbaik: overlap top-4000 hanya 77% — keduanya
  menangkap populasi yang berbeda di tepi.
- **Ranking investigasi bersih**: seluruh top-2000 skor tertinggi adalah
  user risky/mixed. Antrean reviewer paling atas bebas noise.
- **Prinsip AGENTS.md tetap terjaga**: jarak jauh sendirian tidak men-vonis
  (remote high_risk 0,01%), user normal 99,98% tidak tersentuh.

## Limitasi fundamental (temuan arsitektur, bukan bug)

`normal_hard` yang masuk antrean review (20,8%) **statistiknya identik**
dengan `risky_silent` yang tertangkap:

```text
                   repeat  repeat_round  max_occ  tx/user
nh di review       0.54    0.72           3.2      15
risky_silent       0.59    0.70           3.4      16
```

Transfer rutin keluarga (bulanan, kelipatan 50k, ke merchant yang sama) dan
deposit judi via warung lokal menghasilkan jejak data transaksi yang sama.
Perbedaannya konteks, bukan perilaku pembayaran. Konsekuensinya:

1. Ini limitasi informasi — tidak bisa diselesaikan dengan tuning pada fitur
   saat ini.
2. Kandidat solusi eksternal (butuh data yang tidak ada di schema sekarang):
   durasi & konsistensi pola (deposit cenderung lebih sering dari cicilan
   keluarga), konteks merchant dari hasil review (§6.3 M), atau sinyal dari
   sistem lain (rekening terkait).
3. Sampai itu tersedia, 20,8% FP pada tipe yang *sengaja* dibikin mirip
   adalah biaya recall. Untuk alat investigasi, ini trade-off yang benar:
   reviewer menghabiskan beberapa menit per FP, deposit yang lolos jauh
   lebih mahal.

## Catatan kejujuran

- Semua angka tetap di data sintetis — generator dan detektor dibangun
  oleh orang yang sama. Angka recall/precision bukan janji performa nyata;
  yang terbukti adalah: pipeline utuh, sinyal kebaca di kondisi susah,
  trade-off FP/FN dieksplisitkan.
- Threshold (30/45/52) dan pattern floor (48) dikalibrasi di data ini —
  wajib di-sweep ulang saat distribusi berubah (docs/ASSUMPTIONS.md).

## Artefak

- scripts/score_transactions.py — komponen A baru, pattern floor
- scripts/train_iforest.py — 2 fitur interaksi baru
- output/SCORING_REPORT.md, output/IFOREST_REPORT.md — laporan run
- Commit: 0d44c2d (kode), 27300ed (hasil)
