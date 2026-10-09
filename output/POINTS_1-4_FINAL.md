# Laporan Final: Points 1-4 (Validasi Lanjutan)

Seri ujian setelah tahap deteksi dinyatakan selesai (output/ROUND4_REPORT.md).
Semua run di 2 jt transaksi / 200 ribu user, dievaluasi vs ground truth
generator, pipeline tetap unlabeled.

## Point 1 — Round 5: warung fronting bersama (commit 88fa108)

Dua tipe baru menyerang asumsi tahap graph (merchant yang ramai pembayar
deposit = mencurigakan):

- `risky_silent_shared` (1%): penjudi yang nebeng warung fronting yang sama
  dengan banyak penjudi lain — pola realistis (PPATK: penyalahgunaan
  merchant; AUSTRAC: deposit via POS lokal).
- `normal_collective` (1%): warga tak bersalah yang bayar iuran rutin ke satu
  warung yang sama, ramai — uji false positive paling realistis sejauh ini.

Hasil:

```text
risky_silent_shared : 93% ketangkep (1.878/2.025)
normal_collective   : 0,05% salah (1/2.022)
semua tipe lain     : tidak ada regresi (risky 100%, silent 87%, FP normal 3 user)
```

Bug generator ketemu dan diperbaiki: merchant fronting awalnya di-sample dari
registry umum sehingga tercampur pembayar biasa dan sinyal graph mati —
dibuat registry fronting terpisah (dedicated). Pelajaran: sinyal lintas-user
hanya hidup jika pembaginya memang murni.

## Point 2 — Time split: apakah angka kita jujur antar waktu (commit 2b57b04)

Ambang batas dikalibrasi di Apr–Jun, dipakai mentah di Jul–Sep (AGENTS.md 13;
selama ini semua evaluasi in-sample di window penuh).

Hasil:

```text
risky   : fit 84,4% -> test 89,9%  (stabil, malah naik)
normal  : FP 0,001% -> 0,002%      (tetap nol praktis)
innocent: semua ~0% di kedua window
```

Ambang batas TAHAN transfer waktu — angka laporan bukan keberuntungan in-sample.

Temuan jujur: tipe deposit tipis (noisy/silent/routine/shared) cuma 5-14% di
window 3 bulan, karena sinyal repetisi butuh ~20+ transaksi berpola sebelum
matang. Ini bukan kegagalan tapi sifat sinyal: bukti terakumulasi. Penjudi
berat kebaca di window pendek; penjudi tipis butuh observasi lebih panjang.

## Point 3 — Supervised rehearsal: mekanik siap colok (commit 68fef7c)

Bukan klaim performa (label = placeholder generator, per AGENTS.md 10.2
label sintetis bukan kebenaran). Yang dibuktikan: jalur training end-to-end
siap dipakai begitu label human review ada.

```text
RandomForest      : PR-AUC 0.997 (test window), precision@K 1.000
HistGradientBoost : PR-AUC 0.997
Baseline rule     : PR-AUC 0.929 (window test yang sama)
Split waktu       : terjaga (train Apr-Jun, test Jul-Sep)
Kalibrasi isotonic: jalan
```

Angka supervised tinggi itu efek belajar dari pembuat soal — dicatat sebagai
catatan keabsahan di laporan. Untuk data nyata: ganti kolom user_type dengan
keputusan reviewer, kode lain tetap.

## Point 4 — Simulasi operasional (commit b0f7e01)

Jawaban pertanyaan praktis kalau sistem jalan beneran pada populasi 200 ribu
user QRIS:

```text
Beban antrean review : 14.964 user / 6 bulan (7,5%) = ~2.494/bulan
Kapasitas reviewer   : 5,2 FTE (asumsi: 20 menit/user, 160 jam/bulan)
Latensi deteksi      : median 33 hari dari transaksi deposit pertama
                       (p25: 25, p75: 86) — penjudi berat masuk review di
                       bulan pertama
Tertangkap rolling   : 62,3% deposit user dalam 30-hari window berjalan
```

Asumsi operasional tunggal: 20 menit per review — parameter tim, ditandai
bukan klaim (docs/ASSUMPTIONS.md). Sisanya dari data.

## Vonis gabungan

```text
[x] Point 1: asumsi graph diserang dua arah, tahan, tanpa regresi
[x] Point 2: threshold terbukti transfer antar waktu (evaluasi jujur)
[x] Point 3: jalur supervised siap untuk label nyata
[x] Point 4: beban operasional terukur (5,2 FTE, latensi ~1 bulan)
```

Proyek kini punya: deteksi teruji (rule + IF + graph) pada data adversarial
6 round, evaluasi time-split yang jujur, jalur supervised siap colok, dan
angka operasional untuk keputusan deploy. Batas yang tersisa dan tercatat:
label nyata belum ada (tidak akan ada dalam proyek ini), sinyal deposit tipis
butuh observasi panjang, dan seluruh hasil tetap berlaku pada hipotesis
perilaku yang berbasis regulator.
