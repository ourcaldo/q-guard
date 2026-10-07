# Parameter Asumsi Generator

Daftar semua parameter `scripts/generate_data.py` yang TIDAK punya dasar resmi
atau referensi tercatat di AGENTS.md 17. Parameter ini harus di-sweep saat
kalibrasi threshold, dan diganti begitu ada sumber yang lebih baik.

Angka resmi yang dipakai sebagai anchor (bukan asumsi):

```text
Max transaksi QRIS                    Rp10.000.000        (BI)
Rata-rata nilai per transaksi QRIS   ~Rp89-96 ribu       (BI: 579T/6,05M S1-2025; 1,12Q/12,55M S1-2026)
Merchant didominasi UMKM             93-96%              (BI siaran pers)
Kategori merchant (set PJSP)         food/retail/services/other (DANA Bisnis, Xendit)
```

## Asumsi (tidak ada sumber; nilai awal untuk pipeline test saja)

Tipe adversarial (hardening round 1, agar evaluasi tidak terlalu mudah):

| Tipe | Share | Desain |
|---|---|---|
| `risky_noisy` | 3% | pola deposit tapi berantakan: nominal gak selalu bulat (45%), pool merchant 8 |
| `normal_hard` | 2% | innocent tapi mirip judol: transfer kelipatan 50k (50%), 18% tx ke kota jauh (keluarga) |
| `risky_silent` | 1% | anomali SATU dimensi saja: nominal bulat berulang, merchant lokal (jarak netral) |

| Parameter | Nilai awal | Catatan |
|---|---|---|
| `TX_PER_USER` | normal 10, heavy 60, remote 14, risky 45, mixed 12, risky_noisy 45, normal_hard 20, risky_silent 25 per 6 bulan | agregat nasional ~30 tx/user/semester (BI) adalah batas bawah termasuk user dorman; baseline normal di generator masih jauh lebih rendah - perlu dinaikkan saat kalibrasi |
| `CATEGORY_W` | food 40%, retail 35%, services 20%, other 5% | hanya dominasi food/retail yang berdasar (UMKM); persentase karangan |
| `AMOUNT_BY_CATEGORY` | rentang log-uniform per kategori | dikalibrasi agar mean global ~Rp90rb cocok anchor BI; rentang per kategori karangan |
| `POOL_SIZE` | normal 10, heavy 30, remote 14, risky 3, mixed 10 | "pool sempit untuk repetisi" ada di AGENTS.md; angka karangan |
| `MIXED_RISKY_SHARE` | 0.3 | tidak ada data proporsi edge-case user |
| `RISKY_ROUND_SHARE` | 0.85 | kebulatan deposit judi (kelipatan 50k) berdasar domain knowledge; proporsi persis karangan |
| `ROUND_TRANSFER_SHARE` | 0.40 | normal user juga bayar bulat (tagihan/jasa); proporsi karangan |
| `RISKY_DEPOSIT_GRID` | 50k s/d 1jt kelipatan 50k | grid kelipatan 50k berdasar domain knowledge; batas atas karangan |
| Timing shapes risky | steady/spike/burst 1:1:1 | tiga bentuk masuk akal (escalation/binge/chronic) tapi proporsi karangan |
| `risky_cities` | 6 kota populasi terbesar | asumsi merchant deposit nongkrong di kota besar |
| Failed rate | 4% | tidak ada data publik failure rate QRIS |
| `JITTER_KM` | 3 km | presisi lokasi user/merchant sintetis |
| Popularity weighting | 1/(1+0.05i) | bentuk distribusi popularitas merchant |

## Aturan

- Parameter di atas tidak boleh dipakai sebagai justifikasi sinyal; mereka
  hanya menghasilkan data uji pipeline.
- Saat kalibrasi threshold (AGENTS.md 9), parameter berdampak besar
  (`TX_PER_USER`, `RISKY_ROUND_SHARE`, `POOL_SIZE`) di-sweep, bukan dianggap benar.
- Kalau menemukan sumber resmi untuk salah satu parameter, pindahkan ke daftar
  anchor di atas dan catat sumbernya.
