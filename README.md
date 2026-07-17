# SIMONA — UID Banten (Maturity Level Gudang Distribusi)

Versi ini pakai **data & formula resmi** dari dokumen "Kriteria Penilaian
Maturity Level Gudang Distribusi Tahun 2026" — bukan lagi data contoh generik.

## Yang Sudah Sesuai Dokumen Asli

- **6 Aspek** dengan bobot resmi: Sumber Daya Manusia (10), Anggaran dan
  Pengelolaan Keuangan (10), Tata Kelola (30), Infrastruktur (10),
  Peralatan Penunjang Operasional (10), Kinerja (30)
- **29 indikator** dengan rubrik kriteria Level 1-5 asli dari dokumen
- **Formula resmi**:
  ```
  Nilai Indikator = (Level / 5) x (Bobot Aspek / Jumlah Indikator dalam Aspek)
  Nilai Total     = Σ Nilai Indikator            (maksimum 100)
  Maturity Level  = Nilai Total / 20              (skala 1 - 5)
  ```
  Sudah diverifikasi cocok 100% dengan contoh perhitungan di dokumen
  (misal: semua level 5 → total 100 → Matlev 5).
- **Unit**: PLN UID Banten + 7 unit gudang (Serpong, Cikokol, Teluk Naga,
  Cikupa, Banten Utara, Banten Selatan, UP2D)
- **Data Juni 2026 sudah diisi dengan data real** dari dokumen (status
  APPROVED, periode LOCKED) — jadi begitu dibuka, dashboard sudah menampilkan
  hasil real: Serpong 98,50 (Matlev 4,92), Cikokol 92,50, dst.
- **Periode Juli 2026 dibuka (OPEN)** untuk simulasi isi assessment baru.

## SETUP SUPABASE (WAJIB dibaca — supaya data tidak hilang)

Tanpa Supabase, app ini tetap bisa jalan (fallback ke memory server), TAPI
data akan hilang setiap server restart/tidur. Ikuti langkah ini sekali saja
supaya data permanen dan tersimpan bersama untuk semua user:

### Langkah 1 — Buat akun & project Supabase (5 menit)

1. Buka **[supabase.com](https://supabase.com)** → klik **Start your project** → daftar/login (bisa pakai akun Google)
2. Klik **New Project**
3. Isi:
   - **Name**: bebas, misal `simona-uid-banten`
   - **Database Password**: buat password kuat, **simpan/catat**, akan dipakai lagi
   - **Region**: pilih yang terdekat, misal `Southeast Asia (Singapore)`
4. Klik **Create new project**, tunggu ±2 menit sampai project selesai dibuat

### Langkah 2 — Jalankan SQL setup (1 menit)

1. Di sidebar kiri dashboard Supabase, klik **SQL Editor**
2. Klik **New query**
3. Buka file **`supabase_setup.sql`** yang ada di folder ini, copy semua isinya
4. Paste ke SQL Editor, klik **Run** (atau Ctrl+Enter)
5. Harus muncul "Success. No rows returned" — berarti tabel berhasil dibuat

### Langkah 3 — Ambil URL & API Key (1 menit)

1. Di sidebar kiri, klik **Project Settings** (ikon gerigi) → **API**
2. Copy dua nilai ini:
   - **Project URL** (contoh: `https://xxxxxxxxxxxx.supabase.co`)
   - **anon public** key (di bagian "Project API keys", yang **bukan** `service_role`)

### Langkah 4a — Kalau jalanin LOKAL di komputer

1. Di folder project ini, copy `.streamlit/secrets.toml.example` jadi `.streamlit/secrets.toml`
2. Buka file itu, isi `SUPABASE_URL` dan `SUPABASE_ANON_KEY` dengan nilai dari Langkah 3
3. Jalankan seperti biasa: `streamlit run app.py`

### Langkah 4b — Kalau sudah di-deploy di Streamlit Community Cloud

1. Buka **[share.streamlit.io](https://share.streamlit.io)**, masuk ke app kamu
2. Klik titik tiga (⋮) di app kamu → **Settings** → tab **Secrets**
3. Paste ini (ganti dengan nilai kamu dari Langkah 3):
   ```
   SUPABASE_URL = "https://xxxxxxxxxxxx.supabase.co"
   SUPABASE_ANON_KEY = "isi-anon-key-kamu-di-sini"
   ```
4. Klik **Save** — app akan otomatis restart dan langsung pakai Supabase

### Cara mastiin udah kesambung

Buka app-nya, login, isi 1 assessment apa saja. Buka lagi dashboard Supabase
→ **Table Editor** → tabel `simona_state` → harus ada 1 baris dengan kolom
`data` berisi JSON besar. Kalau ada, berarti sudah tersambung dengan benar.

Setelah ini, data **tidak akan hilang lagi** meski server restart — karena
setiap ada perubahan (assessment disimpan, di-approve, dst), otomatis
tersimpan ke Supabase, dan setiap app hidup ulang, otomatis di-load balik
dari sana.

---

## Cara Jalankan

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Cara Coba

1. Masuk sebagai **UID** (PLN UID Banten) → buka **Dashboard** → pilih
   periode **06/2026 (LOCKED)** → lihat ranking 7 unit dengan skor real,
   radar chart per aspek, dan tabel monitoring lengkap.
2. Klik expander **"Contoh perhitungan"** di bagian bawah Dashboard untuk
   lihat rincian kontribusi nilai per aspek suatu unit — cocokkan dengan
   tabel di dokumen aslinya.
3. Ganti Role → masuk sebagai **UP3** (misal Serpong) → buka **Dashboard**
   → lihat skor & rata-rata level per aspek unit itu sendiri untuk periode
   Juni.
4. Ganti periode ke **07/2026 (OPEN)** → buka **Assessment** → coba isi
   level pakai slider, baca kriteria di bawahnya, simpan draft, upload
   evidence, submit.
5. Ganti Role ke **UID** → buka **Review** → approve atau kembalikan untuk
   revisi assessment Juli yang baru di-submit tadi.
6. Coba juga **Master Data** (khusus UID) → tab **Bobot Aspek** → lihat
   bobot resmi (10/10/30/10/10/30), coba ubah, lihat efeknya ke skor.

## Perbedaan dari Versi Demo Generik Sebelumnya

| | Demo generik sebelumnya | Versi UID Banten ini |
|---|---|---|
| Bobot | per indikator, manual isi rata | per **aspek**, sesuai dokumen resmi |
| Level | skor 40-100 per level (buatan) | Level 1-5 langsung sesuai dokumen |
| Formula skor | rata-rata tertimbang biasa | formula resmi PLN (nilai/20 = Matlev) |
| Data | kosong / contoh acak | **Juni 2026 diisi data real** dari dokumen |
| Unit | 1 UID + 2 UP3 + 4 ULP fiktif | UID Banten + 7 unit gudang real |

## Struktur File

```
simona_uid_banten/
├── app.py                  # entry point tunggal — navigasi role-aware (st.navigation)
├── data.py                 # seluruh data & formula perhitungan
├── ui.py                   # topbar, hero, styling bersama
├── assets/
│   ├── logo_pln.png
│   └── logo_danantara.png
└── views/
    ├── home.py              # beranda: hero+login (belum masuk) / ringkasan (sudah masuk)
    ├── dashboard.py
    ├── assessment.py        # hanya muncul di sidebar untuk role UP3/ULP
    ├── review.py             # hanya muncul di sidebar untuk role UID
    ├── master_data.py       # hanya muncul di sidebar untuk role UID
    └── notifikasi.py
```

Navigasi sidebar sekarang otomatis menyembunyikan halaman yang tidak relevan
dengan role yang sedang login (misalnya UID tidak akan melihat menu
"Assessment" sama sekali, bukan cuma diblokir saat diklik).

## Catatan Desain

- Ikon navigasi memakai Material Symbols bawaan Streamlit (`:material/...:`),
  bukan emoji — supaya terlihat konsisten dengan produk enterprise.
- Hero section di halaman Beranda memakai gradient biru + logo, bukan foto asli
  dari materi presentasi (karena file foto tersebut belum tersedia sebagai
  aset gambar terpisah). Kalau ingin memakai foto asli dari slide presentasi,
  export slide tersebut sebagai PNG/JPG dan kirimkan filenya — bisa dipasang
  sebagai background hero.

