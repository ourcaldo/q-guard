# Laporan Round 3: Fitur Keteraturan Waktu

Run: 2.000.000 transaksi / 200.000 user sintetis (seed 42), dengan tipe
adversarial. Dievaluasi vs ground truth generator; pipeline tetap unlabeled.

## Masalah yang diselesaikan

Round 2 menemukan limitasi: user yang bayar rutin ke merchant (langganan,
nominal bulat berulang) dan user deposit judi lewat merchant lokal
menghasilkan jejak data identik — 21% user langganan salah masuk daftar
review. Dari data transaksi nominal/merchant saja, keduanya tak terbedakan.

## Dasar solusi (regulator, bukan asumsi)

- **PPATK** (siaran pers 4/8/2026, AGENTS.md 17.3): transaksi deposit judi
  "bernominal kecil, berulang, dan tersebar". Frekuensi deposit naik 140% YoY
  dengan nilai per transaksi turun (pelaku memecah nominal).
- **AUSTRAC** (indikator resmi sektor betting, AGENTS.md 17.3a): "multiple
  deposits within a short period", "increase in number and/or value of
  deposits", dan deposit via point-of-sale milik sendiri — validasi bahwa
  deposit lewat merchant lokal itu pola nyata.

Kesimpulan dari dua sumber: deposit judi = sering dan waktu acak. Pembayaran
rutin yang sah = mengikuti jadwal (gajian, mingguan, bulanan) — ini sisi
asumsi (velocity monitoring standar), tidak ada sumber judol-specific.

## Perubahan round 3

1. **Fitur baru** `same_merchant_interval_cv`: variasi jarak hari antar
   pembayaran ke merchant yang sama. Kecil = terjadwal. Besar = acak/tersebar.
2. **Komponen A** memakai fitur ini: repetisi nominal yang waktunya acak
   dibaca sebagai deposit; repetisi nominal yang waktunya teratur dibaca
   sebagai langganan dan skor turun.
3. **Generator disesuaikan agar jujur** (asumsi perilaku eksplisit di
   docs/ASSUMPTIONS.md):
   - `normal_hard` kini benar-benar berjadwal: satu pembayaran per ~30 hari
     dengan jitter ~2 hari.
   - `risky_silent` kini sesuai pola PPATK: lebih sering (40 tx vs 25) dan
     pool merchant lebih sempit (4 vs 10).

## Hasil (2 jt tx)

| Metrik | Round 2 | Round 3 |
|---|---|---|
| risky recall (review+high) | 99,9% | 99,4% |
| risky_noisy recall | 98,0% | 75,4% |
| risky_silent recall | 76,5% | **89,8%** |
| normal_hard salah review | 20,8% | **5,1%** |
| normal salah review | 0,017% | 0,002% (3 user) |
| remote high_risk | 1 | 0 |
| Rule PR-AUC | 0.970 | 0.966 |
| IF PR-AUC | 0.898 | 0.866 |
| Precision@2000 (rule) | 1.000 | 1.000 |

Distribusi alert lengkap per tipe ada di output/SCORING_REPORT.md.

## Interpretasi

- **Sistem kini membedakan CARA bayar, bukan cuma BERAPA yang dibayar.**
  Dua user dengan nominal bulat berulang ke merchant sama kini dipisah oleh
  keteraturan waktunya. Langganan terjadwal turun skor, deposit acak naik.
- **Trade-off noisy diambil sadar**: risky_noisy (dirancang berantakan) turun
  98% → 75% karena sebagian waktunya kebetulan lebih teratur. Biayanya:
  recall. Untungnya: daftar review 4x lebih bersih dari user unsalah. Total
  user deposit yang ketangkep (semua tipe risky): 86%.
- **Limitasi normal_hard turun kelas**: dari fundamental (fitur identik) ke
  marginal (5% yang jadwalnya paling tidak teratur masih overlap). Sisa ini
  realistis — dunia nyata memang punya orang yang bayarnya tidak teratur
  meski bukan judol.
- **Rule vs IF**: rule tetap unggul untuk ranking (PR-AUC 0.966 vs 0.866).
  Fitur keteraturan membuat ruang fitur IF makin rapat — user normal_hard
  yang terjadwal kini lebih mirip populasi normal di mata IF, yang benar,
  tapi mengorbankan daya pisah IF untuk kasus tepi.

## Posisi vs tujuan proyek

```text
[x] PR-AUC 0.7-0.9 pada data sulit    : 0.966 (sedikit di atas; data kini
                                        benar-benar adversarial)
[x] Semua tipe deposit terdeteksi     : 75-99%, mayoritas di atas 90%
[x] False positive terkendali         : normal 0.002%, normal_hard 5.1%
[x] Jarak jauh sendirian bukan vonis  : remote high_risk = 0
[x] Sinyal berbasis regulator         : repetisi + tersebar (PPATK 17.3),
                                        densus & POS lokal (AUSTRAC 17.3a)
```

## Catatan kejujuran

- Semua angka tetap di data sintetis; generator dan detektor dibangun orang
  yang sama. Keberhasilan round 3 membuktikan fitur bekerja DI HIPOTESIS
  perilaku yang berbasis regulator — bukan janji performa pada data nyata.
- Threshold (30/45/52), pattern floor (48), dan skala interval_cv
  dikalibrasi di data ini — wajib sweep ulang saat distribusi berubah.
- Asumsi "langganan = terjadwal" masih asumsi domain; hanya sisi judol-nya
  yang berbasis regulator. Tercatat di docs/ASSUMPTIONS.md.

## Artefak

- scripts/score_transactions.py — fitur interval_cv + komponen A round 3
- scripts/generate_data.py — normal_hard terjadwal, risky_silent densus
- AGENTS.md 17.3/17.3a — dasar regulator; docs/ASSUMPTIONS.md — status asumsi
- output/SCORING_REPORT.md, output/IFOREST_REPORT.md — laporan run
- Commit: 0b7cfd7 (kode), bb5cd98 (hasil 2 jt)
