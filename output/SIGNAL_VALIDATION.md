# Validasi Sinyal Data Sintetis

Hasil smoke test: `generate_data.py --n-users 2000 --n-tx 20000 --seed 42`.
Ground truth = tipe user dari generator (evaluation only, pipeline tetap unlabeled).

## Sinyal per tipe user

| Tipe | n tx | >50 km | mean km | same_city | Merchant unik/user | Pola nominal |
|---|---|---|---|---|---|---|
| normal | 11756 | 0.000 | 3.1 | 1.000 | 5.1 | log-uniform |
| heavy | 5825 | 0.000 | 3.1 | 1.000 | pool besar (30) | log-uniform |
| remote | 999 | 0.465 | 443.2 | 0.512 | 2 kota | log-uniform |
| risky | 1224 | **0.918** | **592.0** | **0.029** | **3.0** | **4 nominal tetap berulang** |
| mixed | 196 | 0.301 | 262.0 | 0.699 | campuran | campuran |

## Interpretasi

- **risky** menonjol di semua sinyal yang direncanakan (AGENTS.md 6.1 L, 6.2 A, 6.6 R):
  - Jarak: 92% transaksi >50 km, rata-rata 592 km (merchant di kota besar, payer di home city).
  - Nominal: hanya {25.000, 50.000, 100.000, 200.000} — berulang sama persis, tidak variasi.
  - Repetisi merchant: rata-rata hanya 3 merchant per user, dibayar puluhan kali.
  - Kategori merchant: sebaran identik dengan user normal (food ~30%, retail ~21%,
    transport ~12%, dst). Kategori TIDAK menjadi sinyal - semua tipe user men-draw
    dari registry kota yang sama, tanpa subset merchant khusus risky.
  - Waktu: transaksi terkonsentrasi di paruh kedua window (spike perilaku, 6.7 C).
- **remote** = uji false positive: jarak jauh (~50% transaksi lintas kota) tapi nominal
  variatif dan kategori normal. Sistem yang benar harus TIDAK menaruhnya di high_risk
  hanya karena jarak (AGENTS.md 3, 16).
- **normal/heavy**: same_city 100%, jarak ~3 km (jitter lokal). Baseline sehat.
- **mixed**: ~30% transaksi berpola risky — edge case antara normal dan risky.

## Sanity check umum

- RRN unik 100%, transaction_id unik 100% (0 duplikat dari 20.000 tx).
- Window: 2026-04-01 s/d 2026-09-30 (6 bulan, sesuai time split AGENTS.md 13).
- Distribusi kota merchant mengikuti populasi (Surabaya/Bandung teratas).
- Status: 95.6% success, 4.4% failed.
- MCC distribusi sesuai bobot kategori normal (5812 food teratas).

## Catatan

- Payer location = home city user (AGENTS.md 6.1: L = perbedaan lokasi user vs merchant).
  Bukan lokasi merchant — keputusan ini yang menghidupkan sinyal jarak.
- Merchant count emergent: 2000 user menghasilkan 6496 merchant via registry per kota,
  merchant populer di-share lintas user dengan popularity weighting.
