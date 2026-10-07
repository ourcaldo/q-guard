# AGENTS.md

## Project: Q-Guard (QRIS Gamblin user Anomaly Risk Detector)

> Dokumen rancangan awal. Sistem ini bertujuan menghasilkan **risk score dan alert untuk investigasi**, bukan memutuskan secara otomatis bahwa pengguna atau merchant pasti melakukan judi online.

## 1. Tujuan Project

Membangun prototipe sistem yang mendeteksi apakah perilaku seorang pengguna e-wallet saat membayar merchant QRIS memiliki pola yang tidak wajar dan berisiko terkait deposit judi online.

Fokus utama project adalah **sisi pengguna/pembayar**, bukan klasifikasi merchant secara terpisah.

Output utama:

```text
user_id → transaction risk score → user risk score → alert level
```

## 2. Prinsip Utama

- Setiap transaksi dinilai terlebih dahulu.
- Skor transaksi dikumpulkan berdasarkan `user_id`.
- Skor risiko akun dihitung dari transaksi-transaksi pengguna.
- Merchant dipakai sebagai konteks transaksi, bukan sebagai objek utama deteksi.
- Lokasi merchant dan lokasi pembayar dapat menjadi sinyal tambahan.
- Satu transaksi dapat memicu alert jika risikonya sangat tinggi.
- Risiko akun sebaiknya ditentukan dari skor, bukan hanya jumlah transaksi tertentu.
- Hasil sistem adalah indikasi risiko atau kebutuhan review, bukan vonis hukum.
- Waktu transaksi tidak digunakan sebagai sinyal utama karena judi online dapat dilakukan kapan saja.

## 3. Batasan

Project ini tidak boleh:

- Menyatakan pengguna pasti melakukan judi online hanya dari satu transaksi.
- Menganggap pembayaran lintas kota sebagai bukti judi online.
- Menggunakan nominal kecil, lokasi jauh, atau jumlah transaksi sebagai bukti tunggal.
- Mengabaikan transaksi normal seperti belanja online, donasi, tiket, layanan digital, atau pembayaran kepada keluarga.
- Menggunakan data lokasi tanpa dasar pemrosesan dan perlindungan privasi yang sesuai.

## 4. Unit Analisis

### 4.1 Transaksi

Satu baris data mewakili satu pembayaran QRIS.

Contoh kolom minimum:

```text
transaction_id
timestamp
user_id
merchant_id
amount
merchant_latitude
merchant_longitude
payer_latitude
payer_longitude
merchant_category
status
```

### 4.1.1 Skema data sintesis

Data dibangkitkan secara sintetis karena data transaksi judi online berlabel tidak tersedia publik (lihat 14).

Ukuran:

- Dev pipeline: 100 ribu transaksi, 10 ribu user.
- Simulasi realistis: 1-2 juta transaksi, 100-200 ribu user.
- Generator harus parametrik (`--n-users --n-tx --seed`) sehingga skala hanya mengganti angka.

Tipe user (distribusi user, bukan transaksi):

```text
~85%  normal        lokal, nominal variatif, kategori wajar
~7%   heavy_user    power user QRIS normal, frequent tapi pola sehat
~5%   remote_user   sering bayar lintas kota (kerja/keluarga, uji false positive)
~2%   risky_user    nominal berulang sama, jarak jauh, lonjakan frekuensi,
                    merchant topup/game, remote_payment_ratio tinggi
~1%   mixed         normal + sesekali pola risky (edge case)
```

Label `risky` hanya diketahui generator sebagai ground truth untuk evaluasi. Pipeline tetap memperlakukan semua data sebagai unlabeled (tahap 1 anomaly/rule-based).

Kolom mengikuti struktur receipt QRIS asli (EMVCo merchant-presented QR + overlay Bank Indonesia):

```text
transaction_id          ID Transaksi, contoh: 2026081211121800100166066994149495
rrn                     Retrieval Reference Number, 12 digit, contoh: 020307647306
merchant_pan            Merchant PAN, 19 digit prefix 9360, contoh: 9360091800213336102
cpan                    Customer PAN, identitas instrumen bayar pembayar, prefix 9360
terminal_id             ID Terminal merchant, contoh: A01
order_id                ID order merchant, format bebas/UUID, contoh: f280099ba-0b68-4fee-81aa-58cb15e31835
timestamp               datetime
user_id                string
merchant_id            string
amount                  Rupiah, QRIS umumnya Rp1.000 - Rp2.500.000, max Rp10.000.000 per BI
merchant_mcc            Merchant Category Code 4-digit (tag 52 QR, ISO 18245), mis. 5812 restoran
merchant_name           string
merchant_city           kota (tag 59 QR)
merchant_postal_code    kode pos (tag 61 QR)
merchant_country        ID (tag 60 QR)
merchant_latitude       float (jitter dari pusat kota)
merchant_longitude      float
payer_city              kota domisili/asal pembayar
payer_latitude          float
payer_longitude         float
issuer_name             penerbit aplikasi pembayar
acquirer_name           penyedia jasa pembayaran merchant
status                  enum success/failed/pending
```

Sumber data lokasi (dua sumber publik, di-join sekali saat setup, hasilnya di-commit sebagai `data/locations_id.csv`; generator selanjutnya offline dan deterministic):

```text
Koordinat + populasi : GeoNames dump Indonesia (download.geonames.org/export/dump/ID.zip, CC BY 4.0)
Kota/Prov/Kode pos   : repo Kemendagri "Wilayah-Indonesia-Beserta-Kode-Pos" (turunan data resmi, tanpa koordinat)
Join key             : (kota/kabupaten, provinsi) memakai nama resmi lengkap dengan kualifikasi
```

Aturan join:

- `KAB. X` dan `KOTA X`/`X` adalah dua entitas administratif yang berbeda dan tidak boleh digabung. Contoh: Kab. Bogor dan Kota Bogor adalah district berbeda dengan koordinat dan pool kode pos berbeda. Menghapus kualifikasi `Kab.`/`Kota` saat normalisasi dilarang karena menyebabkan koordinat satu entitas menempel pada pool kode pos entitas lain.
- Normalisasi yang diperbolehkan: case-fold, trim whitespace, ekspansi singkatan (`Kab.` menjadi `Kabupaten`) secara konsisten di kedua sisi.
- Setup script wajib melaporkan baris yang gagal match; tidak boleh ada kota yang dipakai generator tanpa koordinat valid.

Keterangan:

- Nama kota adalah basis generasi lokasi; koordinat adalah jitter di sekitar pusat kota, bukan titik acak. `distance_km` dihitung dari koordinat (haversine).
- Kolom kota dipertahankan untuk sanity check: jarak antar kota harus konsisten dengan pasangan kota.
- Batas BI: maksimal Rp10 juta per transaksi QRIS.
- RRN adalah identitas transaksi lintas pihak (settlement, rekonsiliasi, dispute, audit). Merchant PAN/CPAN adalah identitas merchant/instrumen bayar, bukan fitur risiko, dan tidak boleh dipakai model sebagai sinyal.

Kategori merchant (MCC):

- Data mentah menyimpan `merchant_mcc` 4-digit sesuai tag 52 QR, karena itu field yang benar-benar ada di setiap transaksi QRIS. QRIS disusun BI di atas standar EMVCo Merchant-Presented Mode (PADG No. 21/16/PADG/2019); MCC didefinisikan ISO 18245 dan wajib ada di payload QRIS (contoh payload PJSP Indonesia: `5204 5812`).
- Fitur model memakai `merchant_category` enum turunan (cardinality rendah) hasil mapping statis MCC ke enum, mis. 5812 food_beverage, 5411 retail_grocery, 5732 game_topup, 8398 donation, 7922 ticket, 7372 digital_service. MCC mentah terlalu granular/sparse untuk fitur langsung.
- Mapping MCC ke enum adalah kode (konstanta generator), bukan data: subset ~20-30 MCC yang dipakai, sisanya ke `other`. Bisa diperluas tanpa regenerate data.
- NMID (National Merchant ID, format `ID2019002291555`), Terminal ID, nama merchant, dan nama acquirer tampil pada stiker QRIS resmi sesuai dokumen sosialisasi BI.

### 4.2 User

User adalah unit utama untuk penilaian akun. Sistem menggabungkan transaksi-transaksi milik user dalam periode observasi, misalnya 30 hari atau beberapa transaksi terbaru.

### 4.3 Merchant

Merchant bukan target utama. Informasi merchant digunakan untuk:

- Menghitung jarak dengan lokasi pembayar.
- Mengetahui kategori dan lokasi bisnis.
- Menjadi konteks pola pembayaran.
- Menyediakan merchant risk score jika tersedia dari sistem terpisah.

## 5. Arsitektur Sistem

```text
Data transaksi QRIS
        ↓
Validasi dan anonymization
        ↓
Feature engineering per transaksi
        ↓
Transaction risk score
        ↓
Agregasi berdasarkan user_id
        ↓
User behavior features
        ↓
User risk score
        ↓
Rule/anomaly model/classification model
        ↓
Alert dan human review
```

## 6. Sinyal Risiko

### 6.1 Location mismatch: L

Mengukur perbedaan lokasi user dan merchant.

Contoh:

```text
Merchant: Jakarta
User: Surabaya
```

Lokasi jauh tidak otomatis mencurigakan. Sinyal menjadi lebih berguna jika terjadi berulang dan tidak sesuai profil pembayaran user.

Fitur yang dapat digunakan:

- `distance_km`
- `same_city`
- `same_province`
- `remote_payment_ratio`
- `average_distance`
- `median_distance`

Untuk user:

```text
L_user = jumlah transaksi jauh / total transaksi user
```

### 6.2 Amount pattern: A

Mengukur kejanggalan nominal.

Contoh fitur:

- Rata-rata nominal.
- Median nominal.
- Variasi nominal.
- Proporsi nominal yang sama atau hampir sama.
- Total nominal dalam periode observasi.
- Jumlah transaksi bernilai kecil.

Jangan menganggap transaksi kecil sebagai transaksi judi secara otomatis.

### 6.3 Merchant context: M

Merchant hanya menjadi konteks tambahan.

Contoh:

- Merchant telah mendapat risk score dari sistem lain.
- Merchant memiliki pola penerimaan yang tidak sesuai profil bisnis.
- User membayar merchant yang sebelumnya masuk daftar review.

Jika belum memiliki merchant risk score yang valid, komponen ini dapat dihapus dari model awal.

### 6.4 Transaction behavior: B

Mengukur apakah transaksi berbeda dari perilaku normal user.

Contoh fitur:

- Perubahan jumlah transaksi.
- Perubahan total nominal.
- Perubahan rata-rata nominal.
- Perubahan pola pembayaran.
- Lonjakan penggunaan QRIS dibanding baseline user.

Waktu tidak digunakan sebagai fitur utama.

### 6.5 Frequency: F

Mengukur frekuensi pembayaran user.

Contoh:

- Jumlah transaksi dalam periode tertentu.
- Jumlah transaksi dibanding baseline user.
- Pengulangan pembayaran dengan pola serupa.

Frekuensi tidak boleh menjadi aturan tunggal seperti “setelah lima transaksi pasti judol”.

### 6.6 Repetition: R

Mengukur pengulangan pola.

Contoh:

- Nominal yang sama berulang kali.
- Jarak yang sama atau pola lokasi yang serupa.
- Pola transaksi serupa ke beberapa merchant.

### 6.7 Behavior change: C

Mengukur perubahan perilaku user dibanding riwayat normalnya.

Contoh:

- Sebelumnya jarang menggunakan QRIS, kemudian meningkat tajam.
- Sebelumnya pola transaksi domestik/lokal, kemudian berubah menjadi pembayaran jarak jauh.
- Kategori atau konteks transaksi berubah secara drastis.

## 7. Skor Satu Transaksi

Untuk transaksi ke-i]:

```text
T_i = 0.30 L_i + 0.25 A_i + 0.20 M_i + 0.25 B_i
```

Semua komponen berada pada skala 0–100.

Keterangan:

- `L_i`: skor perbedaan lokasi.
- `A_i`: skor kejanggalan nominal.
- `M_i`: skor konteks merchant, jika tersedia.
- `B_i`: skor kejanggalan perilaku transaksi.

Contoh:

```text
L = 80
A = 60
M = 50
B = 70
```

```text
T_i = (0.30 × 80) + (0.25 × 60) + (0.20 × 50) + (0.25 × 70)
T_i = 66.5
```

Skor 66,5 berarti transaksi perlu diperhatikan, bukan bukti bahwa transaksi tersebut pasti judi online.

## 8. Skor Risiko User

### 8.1 Weighted average

Gunakan skor transaksi user yang terbaru dalam periode observasi.

```text
UserRisk = Σ(d_i × T_i) / Σd_i
```

Keterangan:

- `T_i`: skor transaksi.
- `d_i`: bobot kebaruan transaksi.
- Transaksi terbaru dapat diberi bobot lebih besar.

Contoh bobot:

```text
Transaksi lama       d = 1
Transaksi berikutnya d = 2
Transaksi berikutnya d = 3
Transaksi terbaru    d = 4
```

### 8.2 Pattern score

```text
PatternScore = 0.30 F + 0.25 R + 0.25 L + 0.20 C
```

Keterangan:

- `F`: frekuensi.
- `R`: pengulangan pola.
- `L`: proporsi pembayaran jarak jauh.
- `C`: perubahan perilaku user.

### 8.3 Final user risk

```text
FinalUserRisk = 0.60 × UserRisk + 0.40 × PatternScore
```

Bobot ini adalah titik awal dan harus dikalibrasi dengan data validasi.

## 9. Level Alert

Contoh threshold awal:

```text
0–39    Normal
40–59   Monitor
60–79   Perlu review
80–100  Prioritas tinggi
```

Threshold tidak boleh dianggap final. Threshold harus diuji dengan data dan biaya false positive/false negative.

### 9.1 Alert transaksi

```text
Jika T_i ≥ 90:
    buat alert transaksi segera
```

### 9.2 Alert akun

```text
Jika FinalUserRisk ≥ 60:
    masukkan user ke review
```

Status sebaiknya menggunakan istilah:

- `normal`
- `monitor`
- `needs_review`
- `high_risk`

Hindari label `confirmed_gambling` kecuali terdapat verifikasi eksternal yang memadai.

## 10. Pilihan Machine Learning

### 10.1 Tahap pertama: anomaly detection

Gunakan jika belum mempunyai label transaksi judi online yang terpercaya.

Rekomendasi:

- Isolation Forest.
- Local Outlier Factor.
- One-Class SVM sebagai pembanding.

Outputnya adalah `anomaly_score`, bukan probabilitas judi online.

Isolation Forest sesuai untuk baseline karena data positif biasanya terbatas dan label dapat terlambat atau tidak lengkap.

### 10.2 Tahap kedua: classification

Gunakan setelah tersedia label dari human review atau sumber terverifikasi.

Rekomendasi:

- Logistic Regression sebagai baseline.
- Random Forest.
- XGBoost atau LightGBM.

Contoh label:

```text
0 = normal
1 = perlu ditinjau
2 = indikasi kuat
```

Jangan menggunakan label sintetis sebagai kebenaran final. Data sintetis hanya cocok untuk menguji pipeline.

### 10.3 Tahap ketiga: graph analysis atau graph ML

Graph ML belum diperlukan pada versi awal.

Jika nanti digunakan, node dapat berupa:

- User.
- Merchant.
- Rekening atau e-wallet, jika tersedia dan sah digunakan.

Edge berupa transaksi pembayaran.

Untuk tahap awal, gunakan graph features sederhana, bukan Graph Neural Network:

- Jumlah merchant yang pernah dibayar user.
- Jumlah user yang membayar merchant.
- Kesamaan merchant antar-user.
- Ukuran komunitas transaksi.

Graph ML baru dipertimbangkan jika data besar dan hubungan lintas entitas memang menjadi fokus.

## 11. Pipeline Implementasi yang Disarankan

### Tahap 1: baseline

1. Siapkan data transaksi anonim.
2. Hitung jarak user–merchant.
3. Buat fitur nominal dan frekuensi.
4. Hitung skor transaksi dengan rule-based scoring.
5. Agregasikan skor berdasarkan `user_id`.
6. Tampilkan user dengan skor tertinggi.

### Tahap 2: anomaly detection

1. Latih Isolation Forest pada fitur perilaku user.
2. Bandingkan anomaly score dengan rule score.
3. Buat dashboard review.
4. Simpan keputusan reviewer.

### Tahap 3: supervised learning

1. Gunakan hasil review sebagai label.
2. Pisahkan data berdasarkan waktu.
3. Latih Random Forest atau XGBoost.
4. Kalibrasikan probabilitas dan threshold.
5. Bandingkan hasil model dengan baseline.

### Tahap 4: graph features

1. Buat graf user–merchant.
2. Hitung fitur jaringan sederhana.
3. Tambahkan fitur tersebut ke model tabular.
4. Uji apakah performa dan interpretabilitas meningkat.

## 12. Contoh Pseudocode

```python
transaction_score = (
    0.30 * location_score +
    0.25 * amount_score +
    0.20 * merchant_score +
    0.25 * behavior_score
)

user_risk = weighted_average(
    recent_transaction_scores,
    newer_transactions_have_higher_weight=True
)

pattern_score = (
    0.30 * frequency_score +
    0.25 * repetition_score +
    0.25 * location_pattern_score +
    0.20 * behavior_change_score
)

final_user_risk = (
    0.60 * user_risk +
    0.40 * pattern_score
)

if transaction_score >= 90:
    alert_transaction()
elif final_user_risk >= 80:
    alert_user(priority="high")
elif final_user_risk >= 60:
    alert_user(priority="review")
```

## 13. Evaluasi Model

Jangan hanya menggunakan accuracy karena transaksi berisiko biasanya merupakan kelas minoritas.

Gunakan:

- Precision.
- Recall.
- F1-score.
- PR-AUC.
- Precision@K.
- Recall@K.
- False positive rate.
- Jumlah alert yang benar-benar berguna.
- Waktu investigasi yang dihemat.

Gunakan pembagian data berdasarkan waktu:

```text
Januari–Juni → training
Juli          → validation
Agustus       → testing
```

Hindari random split saja karena dapat menyebabkan kebocoran pola masa depan ke data training.

## 14. Tantangan Data

Data transaksi judi online berlabel biasanya tidak tersedia secara publik karena alasan privasi, kerahasiaan, dan penegakan hukum.

Alternatif:

- Data sintetis untuk pengujian awal.
- Data anonim dari penyedia pembayaran melalui kerja sama resmi.
- Positive-unlabeled learning.
- Anomaly detection.
- Label dari hasil human review.
- Proxy label dari akun atau rekening yang telah dilaporkan, dengan kehati-hatian.

Proxy label tidak selalu sama dengan kebenaran hukum.

## 15. Privasi dan Tata Kelola

Lokasi user dan data transaksi adalah data sensitif untuk sistem ini. Implementasi nyata perlu memperhatikan:

- Dasar pemrosesan data.
- Tujuan penggunaan yang jelas.
- Minimasi data.
- Anonymization atau pseudonymization.
- Kontrol akses.
- Retensi data.
- Audit log.
- Human review.
- Prosedur keberatan dan koreksi jika diperlukan.

Data lokasi sebaiknya diproses dalam bentuk yang minimal, misalnya kota, provinsi, atau grid lokasi, jika koordinat presisi tidak diperlukan.

## 16. Hal yang Tidak Digunakan sebagai Sinyal Utama

- Waktu malam atau dini hari. Aktivitas judi dapat dilakukan kapan saja.
- Satu transaksi lintas kota.
- Nominal kecil saja.
- Jumlah transaksi tertentu saja.
- Jumlah merchant yang dibayar saja.
- Kategori merchant saja.
- Lokasi merchant saja.

Sinyal harus dinilai bersama dan dibandingkan dengan profil perilaku user.

## 17. Referensi dan Rujukan

### 17.1 Penelitian Bank Indonesia

- Renardi Ardiya Bimantoro, Rudy Hardiyanto, Irfan Sampe, Agung Bayu Purwoko, Imam Dwi Kuncoro, Irvan Fadjar R., Devima Christi M., Anugerah Mohamad Setiawan, Moh. Mashudi Arif, Mahanani Margani, dan penulis lainnya. **“Identification of Illegal Transaction Patterns in Payment System Data Using AI/ML: A Case Study on Online Gambling.”** Bank Indonesia Working Paper WP/14/2025.
- Abstrak publik menyebut pendekatan hybrid yang menggabungkan clustering, classification, dan Graph Machine Learning untuk mengidentifikasi pola transaksi ilegal dan jaringan akun.
- Detail implementasi internal seperti fitur lengkap, bobot, threshold, dan dataset tidak seluruhnya tersedia secara publik.

### 17.2 Penelitian QRIS

- Ahmad Rijaluddin Nisbil Kamal dan Valeriana Lukitosari. **“A Segmentation-Aware Isolation Forest Framework for Fraud Investigation Prioritization in QRIS Transactions.”** 2026.
- Penelitian tersebut menggunakan Isolation Forest dan fitur perilaku merchant untuk memprioritaskan investigasi anomali pada transaksi QRIS.
- Metodenya relevan sebagai inspirasi anomaly detection, tetapi tidak boleh dianggap sebagai sistem khusus pendeteksi judi online.

### 17.3 PPATK

- PPATK. **“Judi Online Membajak Piala Dunia 2026, Deposit Tembus Rp1 Triliun.”** 5 Agustus 2026.
- PPATK melaporkan QRIS sebagai kanal penting dalam deposit judi online dan menganalisis rekening, kanal pembayaran, frekuensi, nilai deposit, serta aliran dana.

### 17.4 Referensi teknis

- SAS. **Customer aggregate risk scoring.** Skor transaksi individual dapat diagregasikan menjadi skor risiko pelanggan.
- Visa. **Smarter transaction monitoring for secure payments.** Transaction monitoring dilakukan secara berkelanjutan untuk menemukan perilaku tidak biasa.
- Feedzai. **AML Transaction Monitoring Guide.** Behavioral profiling membandingkan aktivitas customer dengan profil perilaku individual.

### 17.5 Regulasi dan privasi

- Undang-Undang Republik Indonesia Nomor 27 Tahun 2022 tentang Pelindungan Data Pribadi.
- Peraturan OJK Nomor 8 Tahun 2023 tentang penerapan program anti pencucian uang, pencegahan pendanaan terorisme, dan pencegahan pendanaan proliferasi senjata pemusnah massal di sektor jasa keuangan.
- Peraturan Bank Indonesia terkait QRIS dan pengawasan penyelenggara jasa pembayaran.

## 18. Catatan Akhir

Versi pertama yang realistis:

```text
Rule-based transaction scoring
        +
Isolation Forest untuk anomali user
        +
Weighted aggregation per user
        +
Human review
```

Setelah tersedia label yang cukup:

```text
Random Forest atau XGBoost
```

Graph ML ditunda sampai data hubungan user–merchant dan kebutuhan analisis jaringan benar-benar tersedia.

Sistem harus berfungsi sebagai alat bantu investigasi berbasis risiko, bukan mesin vonis otomatis.
