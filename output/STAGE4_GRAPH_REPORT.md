# Laporan Tahap 4: Graph Features (Konteks Merchant Antar-User)

Run: 2.000.000 transaksi / 200.000 user (seed 42), 10 tipe user (5 adversarial).
Dievaluasi vs ground truth generator; pipeline tetap unlabeled.

## Ide

AGENTS.md 6.3 (komponen M) tadinya dinolkan karena "belum ada merchant risk
score yang valid". Tahap 4 menghidupkannya dari data transaksi sendiri,
tanpa sumber eksternal dan tanpa membaca label generator:

- Merchant yang menerima pembayaran dari BANYAK user yang semuanya
  berperilaku deposit → merchant mencurigakan (proxy merchant risk score).
- Warung yang cuma dilayani 1-2 user → tidak ada bukti lintas-user → diam.

Ini "graph features sederhana" sesuai AGENTS.md 10.3 dan sejalan dengan
pendekatan hybrid graph pada working paper BI WP/14/2025 (17.3): user dan
merchant sebagai node, transaksi sebagai edge, tanpa GNN.

## Desain (hasil 3 iterasi)

Dua iterasi pertama gagal dan pengajarannya penting:

```text
Iterasi 1: M bobot 0.10 di pattern, dicuri dari A  -> risky_silent ambruk
           (89% -> 54%): A adalah tumpuan silent
Iterasi 2: M dicuri proporsional dari F/R/L/C      -> risky_noisy ambruk
           (76% -> 59%): noisy berdiri di kombinasi itu
```

Pelajaran: setiap tipe user bertumpu di komponen berbeda; memotong bobot
komponen mana pun pasti mengorbankan seseorang.

**Iterasi 3 (final) — M sebagai bonus bukti, bukan komponen berbobot:**

- Bobot pattern tetap persis seperti round 3 (tidak ada yang terpotong).
- User dengan pattern >= 35 (zona review) yang merchant-nya "menyala"
  mendapat dorongan hingga +10 poin, proporsional comp_M.
- User tidak bisa masuk review murni karena merchant — pattern user sendiri
  harus sudah meninggi dulu (AGENTS.md 3: bukti tunggal bukan vonis).

**Proteksi anti-kebocoran:**

- Propagasi hanya memakai comp_A (perilaku nominal terukur), bukan user_type
  generator — nol label leakage.
- `MIN_MERCHANT_PAYERS = 2`: merchant yang dibayar satu user tidak memberi
  bukti lintas-user (warung keluarga tetap aman).
- Dua iterasi neighbor-averaging, frekuensi transaksi sebagai bobot edge.

## Hasil (2 jt tx)

| Tipe | Tanpa graph (R4) | Dengan graph | comp_M mean |
|---|---|---|---|
| risky | 99,4% | 100% | 27,8 |
| risky_routine | 97,6% | 98,7% | 27,7 |
| risky_noisy | 75,9% | **83,6%** | 27,6 |
| risky_silent | 88,4% | 89,4% | **2,6** |
| normal_hard | 5,0% | 5,4% | 2,7 |
| normal_hard_random | 2,5% | 2,9% | 2,2 |
| normal | 0,001% | 0,002% | 2,3 |
| remote | 0,06% | 0,06% | 1,2 |

Merchant paling menyala di data: 835 payer (merchant fronting deposit
besar). Merchant langganan keluarga: 1-2 payer, skor rendah.

## Interpretasi

1. **Bonus kena sasaran**: pemisahan comp_M antara user deposit (27-28) dan
   semua tipe innocent (1-3) bersih total. Noisy naik 8 poin persis karena
   merchant-nya shared dengan depositor lain — bukti lintas-user nyata.
2. **comp_M silent = 2,6 dan itu benar, bukan kegagalan**: silent depositor
   di generator ini memakai pool 4 merchant miliknya sendiri — tidak shared,
   tidak ada bukti lintas-user, M wajar diam. Recall silent tetap 89% karena
   sinyal A miliknya sendiri. Sistem tidak menciptakan bukti yang tidak ada.
3. **Implikasi untuk real case**: merchant fronting nyata melayani banyak
   depositor sekaligus — pada data nyata comp_M user silent kemungkinan
   ikut menyala seperti noisy. Asumsi generator "silent itu sendirian"
   dicatat di docs/ASSUMPTIONS.md dan merupakan kandidat adversarial round 5
   (silent yang shared merchant).
4. **Antrean review tetap bersih**: FP normal naik 1 user (3 dari 151.963),
   normal_hard naik 0,4 poin, remote tidak tersentuh.

## Posisi roadmap

```text
[x] Tahap 1: rule-based scoring (L/A/B/F/R/C)     - round 1-4
[x] Tahap 2: Isolation Forest anomaly detection   - PR-AUC 0.838 (rule) / 0.686 (IF)
[x] Tahap 4: graph features sederhana (komponen M) - laporan ini
[ ] Tahap 3: supervised (RF/XGBoost)               - tertunda sampai ada label
    dari human review (AGENTS.md 10.2: label sintetis bukan kebenaran)
[ ] Graph ML (GNN)                                 - hanya jika data hubungan
    antar-entitas jadi fokus (AGENTS.md 10.3)
```

## Artefak

- scripts/graph_features.py — propagasi bipartite + bonus design
- output/GRAPH_REPORT.md — laporan run otomatis
- output/merchant_scores.parquet — skor graph per merchant (835-payer
  merchant paling atas), siap dipakai dashboard review
- Commit: 01552f8/77... (kode), e5db626 (hasil 2 jt)
