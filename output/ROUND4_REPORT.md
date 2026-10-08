# Laporan Round 4: Ujian Serangan Balik & Hasil Akhir Tahap Deteksi

Run: 2.000.000 transaksi / 200.000 user (seed 42), 10 tipe user (5 adversarial).
Dievaluasi vs ground truth generator; pipeline tetap unlabeled.

## Tujuan round 4

Round 3 menang lewat fitur keteraturan waktu. Round 4 menguji apakah kemenangan
itu nyata atau kebetulan, dengan dua tipe yang menyerang asumsi round 3
langsung dari dua arah berlawanan:

| Tipe | Serangan | Dasar |
|---|---|---|
| `risky_routine` (1%) | Deposit judi yang TERJADUL (ritual mingguan bettor rekreasi) — meruntuhkan asumsi "deposit = tersebar" | Aktivitas betting rekreasi berpola mingguan adalah perilaku yang terdokumentasi; AUSTRAC 17.3a mencatat perubahan frekuensi sebagai indikator |
| `normal_hard_random` (2%) | Pembayaran rutin sah yang waktunya ACAK (beli saat butuh, bukan jadwal gajian) — meruntuhkan asumsi "rutin = terjadwal" | Perilaku belanja normal; normal user di generator memang acak |

Tanpa perubahan kode deteksi sama sekali — murni ujian.

## Hasil (2 jt tx)

| Tipe | Review+high | Catatan |
|---|---|---|
| risky | 99,4% | stabil |
| **risky_routine** | **97,6%** | lolos ujian: ditangkap lewat sinyal gabungan (jarak + repetisi), tidak bergantung satu fitur |
| risky_silent | 88,4% | stabil |
| risky_noisy | 75,9% | batas bawah, trade-off yang disengaja |
| **normal_hard_random** | **2,5% salah review** | lolos ujian: fitur keteraturan tidak sekadar mem-flag "acak" |
| normal_hard | 5,0% | stabil |
| normal | 0,001% (2 user) | praktis nol |
| remote di high_risk | 0 | prinsip AGENTS.md utuh |

Metrik:

```text
PR-AUC rule   : 0.838  (round 3: 0.966) - kini DI DALAM range jujur 0.7-0.9
PR-AUC IF     : 0.686
Precision@2000: 0.876 (rule) - jujur turun karena data makin sulit
```

## Interpretasi

- **Sistem tidak mono-sinyal.** Bettor terjadwal (risky_routine) tetap
  tertangkap 97,6% karena sinyal jarak dan repetisi nominal tetap hidup
  meski asumsi waktu-tersebar dilanggar. Ini bukti desain multi-sinyal
  (AGENTS.md 6) bekerja: tidak ada satu fitur yang menjadi titik kegagalan
  tunggal.
- **Fitur keteraturan terbukti selektif, bukan shortcut.** Pembayaran rutin
  yang acak waktunya (normal_hard_random) salah review hanya 2,5% — fitur
  interval tidak sekadar menghukum "waktu acak", ia membaca kombinasi
  repetisi nominal × pola waktu.
- **PR-AUC akhirnya jujur.** 0.966 di round 3 masih terlalu bagus; dengan
  5 tipe adversarial, 0.838 adalah angka yang bisa dipercaya mewakili
  kemampuan sistem pada data yang secara sengaja memusuhi asumsinya.
- **Isolation Forest kalah konsisten dari rule pada data ini.** Penjelasan:
  populasi adversarial (innocent yang mirip judol) menghuni ruang fitur IF
  juga, sehingga anomali "murni" sulit dipisahkan tanpa kalibrasi eksplisit.
  Rule memakai pengetahuan regulator (repetisi, tersebar) sebagai struktur
  yang IF tidak punya. Keduanya tetap saling melengkapi: overlap top-4000
  hanya 2.581 (65%) — IF menangkap populasi berbeda di tepi.

## Vonis akhir tahap deteksi

Kriteria keberhasilan yang ditetapkan proyek (diskusi 2026-10-08):

```text
[x] PR-AUC 0.7-0.9 pada data sulit           : 0.838
[x] Semua tipe deposit terdeteksi            : 75,9-99,4%
[x] False positive terkendali                : normal 0.001%, innocent-mirip 2,5-5%
[x] Jarak jauh sendirian tidak men-vonis     : remote high_risk = 0
[x] Sinyal berbasis regulator                : PPATK 17.3, AUSTRAC 17.3a
[x] Tahan serangan dua arah                  : asumsi keteraturan diserang
                                              balik, sistem tetap berdiri
```

**Keputusan: iterasi deteksi dihentikan di round 4.** Alasan:

1. Round 3 -> 4 tidak mengubah kode deteksi; sistem stabil di datanya.
2. Sisa kelemahan (noisy 75%) tidak bisa diselesaikan dengan fitur dari data
   transaksi — butuh konteks eksternal (merchant risk score dari review,
   graph antar-entitas), yang merupakan tahap berbeda (AGENTS.md 10.3).
3. Sirkularitas data sintetis sudah di batas maksimal yang bisa dikurangi:
   4 round hardening, setiap asumsi diserang balik.

## Artefak & jejak

- Round 1: tipe adversarial dasar (noisy/hard/silent) - commit 624a30e
- Round 2: sinyal repetisi nominal - commit 0d44c2d, hasil 27300ed
- Round 3: fitur keteraturan waktu (regulator-grounded) - hasil bb5cd98
- Round 4: ujian serangan balik, tanpa perubahan deteksi - hasil e4bbdbb
- Laporan lengkap: output/ROUND1-4 + SCORING_REPORT.md + IFOREST_REPORT.md
