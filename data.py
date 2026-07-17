"""
Data layer SIMONA — versi terintegrasi dengan data real:
"Kriteria Penilaian Maturity Level Gudang Distribusi Tahun 2026" (PLN UID Banten).

Semua data disimpan di st.session_state (in-memory, mode prototipe — belum
tersambung Supabase). Formula perhitungan skor mengikuti dokumen resmi:

    Nilai Indikator = (Level / 5) x (Bobot Aspek / Jumlah Indikator dalam Aspek)
    Nilai Total Unit = Σ Nilai Indikator          (maksimum 100)
    Maturity Level (Matlev) = Nilai Total / 20     (skala 1 - 5)

Bobot ditetapkan di level ASPEK (bukan per indikator), sesuai dokumen asli.
Bobot di-snapshot per periode supaya periode yang sudah LOCKED tidak berubah
kalau UID mengubah bobot di periode berjalan.
"""

import streamlit as st
import uuid
import datetime
import json
import base64
import pandas as pd


def _new_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# DEFINISI ASPEK & INDIKATOR (sesuai dokumen "Kriteria Penilaian Maturity
# Level Gudang Distribusi Tahun 2026")
# ---------------------------------------------------------------------------
# Format: (nama_aspek, bobot_aspek, [(nama_indikator, {level: deskripsi_singkat}), ...])

ASPECT_DEFS = [
    ("Sumber Daya Manusia", 10, [
        ("Sumber Daya Manusia", {
            1: "1 orang pegawai di gudang UP3",
            2: "Lebih dari 1 orang pegawai di gudang UP3",
            3: "1 pegawai + 1 tenaga supporting di gudang UP3",
            4: "1 pegawai + 1 tenaga supporting (jobdesk utama kelola gudang)",
            5: "1 pegawai + 1 supporting (jobdesk utama) + 1 pegawai per ULP kelola gudang ULP",
        }),
        ("Manajemen Material", {
            1: "1 pegawai logistik punya sertifikat pelatihan K3",
            2: ">1 pegawai logistik punya sertifikat pelatihan material management",
            3: "1 pegawai logistik + 1 level manajemen (min. Spv Atas) bersertifikat",
            4: ">1 pegawai logistik + >1 level manajemen bersertifikat",
            5: ">1 pegawai logistik + >1 manajemen + 1 pegawai/ULP bersertifikat",
        }),
        ("Pengoperasian Alat Berat", {
            1: "1 pegawai logistik punya sertifikat keahlian alat berat",
            2: ">1 pegawai logistik punya sertifikat keahlian",
            3: "1 pegawai + 1 tenaga supporting logistik bersertifikat keahlian",
            4: ">1 pegawai + 1 tenaga supporting bersertifikat keahlian",
            5: ">1 pegawai + >1 tenaga supporting bersertifikat keahlian",
        }),
        ("Implementasi K3 (Keselamatan dan Kesehatan Kerja)", {
            1: "1 pegawai logistik punya sertifikat pelatihan K3",
            2: ">1 pegawai logistik punya sertifikat pelatihan K3",
            3: "1 pegawai logistik + 1 level manajemen (min. Spv Atas) bersertifikat K3",
            4: ">1 pegawai logistik + >1 level manajemen bersertifikat K3",
            5: ">1 pegawai + >1 manajemen + 1 tenaga supporting bersertifikat K3",
        }),
        ("Petugas Keamanan", {
            1: "1 orang petugas keamanan",
            2: "1 petugas keamanan tiap shift (<3 shift/hari)",
            3: ">1 petugas keamanan tiap shift (<3 shift/hari)",
            4: "1 petugas keamanan tiap shift (3 shift/hari)",
            5: ">1 petugas keamanan tiap shift (3 shift/hari)",
        }),
    ]),
    ("Anggaran dan Pengelolaan Keuangan", 10, [
        ("Anggaran Pengelolaan Gudang", {
            1: "Sudah ada usulan anggaran dari UP3 ke UID",
            2: "Sudah ada usulan anggaran dari UID ke Kantor Pusat",
            3: "Ada realisasi pemanfaatan anggaran walau tidak dari anggaran khusus gudang",
            4: "Ada anggaran khusus gudang, belum ada realisasi pemanfaatan",
            5: "Ada anggaran khusus gudang dan sudah ada realisasi pemanfaatan",
        }),
        ("Realisasi Pemanfaatan Anggaran Pengelolaan Gudang", {
            1: "Progres pekerjaan <60% dari total nilai kontrak",
            2: "Progres pekerjaan <70% dari total nilai kontrak",
            3: "Progres pekerjaan <80% dari total nilai kontrak",
            4: "Progres pekerjaan <95% dari total nilai kontrak",
            5: "Progres pekerjaan ≥95% dari total nilai kontrak",
        }),
    ]),
    ("Tata Kelola", 30, [
        ("Proses Bisnis Tata Kelola Gudang", {
            1: "Memiliki sebagian SOP/BPM tata kelola gudang",
            2: "Memiliki SOP/BPM lengkap tata kelola gudang",
            3: "Melaksanakan sebagian proses bisnis sesuai SOP/BPM",
            4: "Melaksanakan seluruh proses bisnis, masih ada selisih stok fisik vs SAP",
            5: "Melaksanakan seluruh proses bisnis, tidak ada selisih stok fisik vs SAP",
        }),
        ("Penyusunan Material di Rak", {
            1: "Seluruh material disusun tidak beraturan",
            2: "Sebagian material disusun beraturan",
            3: "Seluruh material disusun teratur, belum sesuai kategori jenis layanan",
            4: "Material sesuai kategori jenis layanan, layanan prabayar 1 fasa belum dekat pintu keluar",
            5: "Material sesuai kategori jenis layanan, prabayar 1 fasa dekat pintu keluar/export area",
        }),
        ("Tata Letak Penyimpanan Material Baru", {
            1: "Ada area penyimpanan material baru, belum disusun",
            2: "Material baru disusun, belum sesuai kelompok material",
            3: "Sebagian material baru sesuai kelompok, belum berurutan sesuai layanan",
            4: "Seluruh material baru sesuai kelompok, belum berurutan sesuai layanan",
            5: "Seluruh material baru sesuai kelompok dan berurutan sesuai jenis layanan",
        }),
        ("Tata Letak Penyimpanan Material Retur", {
            1: "Ada area penyimpanan material retur, belum disusun",
            2: "Material retur disusun, belum sesuai kelompok material",
            3: "Sebagian material retur sesuai kelompok, belum sesuai kategori MRWI",
            4: "Seluruh material retur sesuai kelompok, belum sesuai kategori MRWI",
            5: "Seluruh material retur sesuai kelompok dan kategori MRWI (standby/garansi/perbaikan/usul hapus)",
        }),
        ("Identifikasi Material", {
            1: "Belum ada identitas material",
            2: "Sudah ada identitas material",
            3: "Identitas material disertai barcode",
            4: "Identitas + barcode terintegrasi ke MIMS & SAP",
            5: "Identitas + barcode terintegrasi MIMS & SAP + histori asal-usul material",
        }),
        ("Implementasi 5S di Gudang", {
            1: "Melakukan pemilahan (Seiri)",
            2: "Pemilahan (Seiri) + penataan (Seiton)",
            3: "Pemilahan, penataan, + pembersihan (Seiso)",
            4: "Seiri, Seiton, Seiso konsisten (Seiketsu)",
            5: "Seiri-Seiton-Seiso konsisten + membudaya (Shitsuke) + visual manajemen 5S",
        }),
    ]),
    ("Infrastruktur", 10, [
        ("Rak Penyimpanan", {
            1: "Sudah ada rak penyimpanan di gudang UP3",
            2: "Rak ada, warna sesuai aturan",
            3: "Rak ada, warna & dimensi sesuai aturan",
            4: "Rak sesuai aturan + identitas rak + tata letak rapi + ada rak di tiap gudang ULP",
            5: "Rak sesuai aturan lengkap di gudang UP3 & tiap gudang ULP",
        }),
        ("Lantai Gudang Tertutup", {
            1: "Lantai masih berupa tanah",
            2: "Lantai plester/teraso/keramik/sejenisnya",
            3: "Lantai beton kelas 1",
            4: "Lantai beton kelas 2",
            5: "Lantai beton kelas 2 dilengkapi besi wiremesh",
        }),
        ("Lantai Gudang Terbuka", {
            1: "Lantai masih berupa tanah",
            2: "Lantai plester/teraso/keramik/sejenisnya",
            3: "Lantai beton kelas 1",
            4: "Lantai beton kelas 2",
            5: "Lantai beton kelas 2 dilengkapi besi wiremesh",
        }),
        ("Atap Gudang", {
            1: "Atap bocor dan/atau belum ada ventilasi",
            2: "Atap tidak bocor, belum ada ventilasi",
            3: "Atap tidak bocor, ada ventilasi di atap/dinding",
            4: "Atap tidak bocor, ventilasi berupa turbin ventilator",
            5: "Atap tidak bocor, turbin ventilator lebih dari satu",
        }),
        ("Warna Demarkasi Area Gudang", {
            1: "Tidak ada pewarnaan batas area",
            2: "Pewarnaan sebagian area, warna tidak sesuai standar",
            3: "Pewarnaan seluruh area, warna tidak sesuai standar",
            4: "Pewarnaan seluruh area sesuai standar, lebar tidak sesuai",
            5: "Pewarnaan seluruh area sesuai standar & lebar sesuai standar (10 cm)",
        }),
        ("Ruang Administrasi, Kamar Mandi, Toilet, dan Peralatan P3K", {
            1: "Tersedia, namun tidak dipelihara",
            2: "Tersedia, tidak terpelihara rutin",
            3: "Tersedia, belum ada jadwal & realisasi pemeliharaan rutin",
            4: "Tersedia, belum dilengkapi jadwal & realisasi pemeliharaan rutin",
            5: "Tersedia lengkap dengan jadwal & realisasi pemeliharaan rutin",
        }),
    ]),
    ("Peralatan Penunjang Operasional", 10, [
        ("Peralatan Handling Material Gudang", {
            1: "Tangga beroda + pengunci, hand pallet, troli, forklift tersedia",
            2: "Tersedia, namun tidak terpelihara",
            3: "Tersedia, tidak terpelihara secara rutin",
            4: "Tersedia, belum ada jadwal & realisasi pemeliharaan rutin",
            5: "Tersedia lengkap dengan jadwal & realisasi pemeliharaan rutin",
        }),
        ("Alat Pelindung Diri (APD)", {
            1: "1 set APD, tidak dalam lemari khusus",
            2: "1 set APD dalam lemari khusus",
            3: "2 set APD untuk petugas & tenaga supporting dalam lemari khusus",
            4: "3 set APD untuk petugas & tenaga supporting dalam lemari khusus",
            5: ">3 set APD untuk petugas, supporting & tamu dalam lemari khusus",
        }),
        ("Sistem Pengawasan CCTV", {
            1: "Minimal 1 CCTV beroperasi untuk seluruh area gudang terbuka",
            2: "Minimal 1 CCTV beroperasi baik gudang tertutup & terbuka",
            3: "Minimal 2 CCTV beroperasi baik gudang tertutup & terbuka",
            4: "Seluruh area termonitor CCTV, hanya bisa dimonitor lokal",
            5: "Seluruh area termonitor CCTV, bisa dimonitor lokal & remote",
        }),
        ("Alat Pemadam Kebakaran (APAR) dan Sistem Hydrant", {
            1: "Tersedia APAR",
            2: "APAR berfungsi baik & tidak expired, belum ada jadwal pemeliharaan",
            3: "APAR berfungsi baik, tidak expired, ada jadwal pemeliharaan",
            4: "APAR & Hydrant berfungsi baik & tidak expired, belum ada jadwal pemeliharaan",
            5: "APAR & Hydrant berfungsi baik, tidak expired, ada jadwal & realisasi pemeliharaan",
        }),
        ("Identitas Gudang", {
            1: "Identitas gudang tidak sesuai standar",
            2: "Identitas sesuai standar, kondisi rusak",
            3: "Identitas sesuai standar, kondisi kotor",
            4: "Identitas sesuai standar, bersih, namun terhalang benda",
            5: "Identitas sesuai standar, bersih, tidak terhalang apapun",
        }),
        ("Peralatan Administratif Gudang", {
            1: "Ada alat tulis kantor",
            2: "Alat tulis kantor + komputer/laptop + printer",
            3: "+ rak dokumen",
            4: "+ alat scan barcode",
            5: "+ tersedia material cadangan",
        }),
    ]),
    ("Kinerja", 30, [
        ("Days of Inventory (DOI)", {
            1: "Realisasi pencapaian <95% target periode berjalan",
            2: "Realisasi pencapaian 95%–<100% target",
            3: "Realisasi pencapaian 100%–<105% target",
            4: "Realisasi pencapaian 105%–<110% target",
            5: "Realisasi pencapaian ≥110% target periode berjalan",
        }),
        ("Penghapusan ATTB", {
            1: "Realisasi usulan penghapusan ATTB <70% dari material retur usul hapus",
            2: "Realisasi 70%–<80%",
            3: "Realisasi 80%–<90%",
            4: "Realisasi 90%–<100%",
            5: "Realisasi 100% dari material retur kategori usul hapus",
        }),
        ("Optimalisasi Material Saving MRWI", {
            1: "Penggunaan kembali material saving <50%",
            2: "50%–<60%",
            3: "60%–<70%",
            4: "70%–<80%",
            5: "≥80% penggunaan kembali material saving",
        }),
        ("Optimalisasi Material Slow Moving", {
            1: "Ada material tidak bergerak >4 tahun",
            2: "Ada material tidak bergerak 3–4 tahun",
            3: "Ada material tidak bergerak 2–3 tahun",
            4: "Ada material tidak bergerak 1–2 tahun",
            5: "Ada material tidak bergerak <1 tahun",
        }),
    ]),
]

# ---------------------------------------------------------------------------
# DEFINISI ASPEK & INDIKATOR KHUSUS ULP (skala Level 1-3, bukan 1-5)
# Sesuai dokumen "Kriteria Penilaian Maturity Level Gudang ULP UID Banten 2026"
# ---------------------------------------------------------------------------

ULP_ASPECT_DEFS = [
    ("Sumber Daya Manusia", 20, [
        ("Sumber Daya Manusia", {
            1: "0 orang pegawai mengelola material di gudang ULP",
            2: "1 orang pegawai mengelola material di gudang ULP",
            3: "Lebih dari 1 orang pegawai mengelola material di gudang ULP",
        }),
        ("Manajemen Material", {
            1: "0 orang pegawai bersertifikat pelatihan material management (SAP/AGO)",
            2: "1 orang pegawai bersertifikat pelatihan material management",
            3: "Lebih dari 1 orang pegawai bersertifikat pelatihan material management",
        }),
        ("Implementasi K3 (Keselamatan dan Kesehatan Kerja)", {
            1: "0 orang pegawai bersertifikat pelatihan K3",
            2: "1 orang pegawai bersertifikat pelatihan K3",
            3: "Lebih dari 1 orang pegawai bersertifikat pelatihan K3",
        }),
        ("Petugas Keamanan", {
            1: "0 petugas keamanan melakukan kontrol gudang ULP",
            2: "Petugas keamanan kontrol gudang ULP 1 kali/hari",
            3: "Petugas keamanan kontrol gudang ULP lebih dari 1 kali/hari",
        }),
    ]),
    ("Tata Kelola", 30, [
        ("Proses Bisnis Tata Kelola Gudang", {
            1: "Belum memiliki SOP/BPM tata kelola gudang ULP",
            2: "Memiliki sebagian SOP/BPM tata kelola gudang ULP",
            3: "Memiliki SOP/BPM lengkap tata kelola gudang ULP",
        }),
        ("Penyusunan Material", {
            1: "Material disusun secara tidak beraturan",
            2: "Sebagian material disusun secara beraturan",
            3: "Seluruh material disusun secara beraturan",
        }),
        ("Tata Letak Penyimpanan Material Baru", {
            1: "Belum ada area penyimpanan material baru & belum disusun",
            2: "Ada area penyimpanan material baru, belum disusun",
            3: "Ada area penyimpanan material baru & sudah disusun",
        }),
        ("Tata Letak Penyimpanan Material Retur", {
            1: "Belum ada area penyimpanan material retur & belum disusun",
            2: "Ada area penyimpanan material retur, belum disusun",
            3: "Ada area penyimpanan material retur & sudah disusun",
        }),
        ("Identifikasi Material", {
            1: "Belum ada identitas & pencatatan material",
            2: "Sebagian sudah ada identitas & pencatatan material",
            3: "Keseluruhan sudah ada identitas & pencatatan material",
        }),
        ("Implementasi 5S di Gudang", {
            1: "Belum melakukan 5S di Gudang ULP",
            2: "Sebagian melakukan 5S di Gudang ULP",
            3: "Melakukan 5S (Seiri, Seiton, Seiso, Seiketsu, Shitsuke) di Gudang ULP",
        }),
    ]),
    ("Infrastruktur", 10, [
        ("Rak Penyimpanan", {
            1: "Belum ada rak penyimpanan di gudang ULP",
            2: "Ada rak di gudang ULP, belum standar/belum penuhi kapasitas",
            3: "Ada rak di gudang ULP sesuai standar & memenuhi kapasitas",
        }),
        ("Lantai Gudang Tertutup", {
            1: "Lantai masih berupa tanah",
            2: "Lantai menggunakan coran/plesteran",
            3: "Lantai menggunakan cor beton",
        }),
        ("Lantai Gudang Terbuka", {
            1: "Lantai masih berupa tanah",
            2: "Lantai menggunakan coran/plesteran",
            3: "Lantai menggunakan cor beton",
        }),
        ("Warna Demarkasi Area Gudang", {
            1: "Tidak ada pewarnaan batas area",
            2: "Pewarnaan sebagian area, warna tidak sesuai standar",
            3: "Pewarnaan seluruh area sesuai standar",
        }),
        ("Ruang Administrasi, dan Peralatan P3K", {
            1: "Tersedia, namun tidak dipelihara",
            2: "Tersedia, belum dilakukan pengecekan",
            3: "Tersedia dan dilakukan pengecekan berkala",
        }),
    ]),
    ("Peralatan Penunjang Operasional", 20, [
        ("Alat Pelindung Diri (APD)", {
            1: "Tidak tersedia APD (helm, rompi, sepatu safety)",
            2: "Tersedia 1 set APD untuk petugas gudang",
            3: "Tersedia lebih dari 1 set APD untuk petugas gudang",
        }),
        ("Sarana & Alat Kerja", {
            1: "Tidak tersedia hand pallet & alat ukur",
            2: "Tersedia, kondisi tidak lengkap/tidak layak",
            3: "Tersedia, kondisi lengkap & layak",
        }),
        ("Sistem Pengawasan CCTV", {
            1: "Belum ada CCTV yang beroperasi",
            2: "Ada CCTV beroperasi, belum ada sistem monitoring",
            3: "Ada CCTV beroperasi dan ada sistem monitoring",
        }),
        ("Alat Pemadam Kebakaran (APAR) dan Sistem Hydrant", {
            1: "Belum tersedia APAR",
            2: "Tersedia APAR, tidak berfungsi/expired/tidak dipelihara",
            3: "Tersedia APAR, berfungsi dan dipelihara berkala",
        }),
        ("Identitas Gudang & Lay Out", {
            1: "Belum ada papan nama & lay out",
            2: "Sebagian ada papan nama/lay out",
            3: "Ada identitas gudang (totem/papan nama) sesuai standar",
        }),
        ("Peralatan Administratif Gudang", {
            1: "Belum ada peralatan administratif",
            2: "Sebagian ada peralatan administratif",
            3: "Peralatan administratif lengkap tersedia",
        }),
    ]),
    ("Kinerja", 20, [
        ("Perputaran Material (ITO)", {
            1: "Perputaran 1 s.d 2 kali",
            2: "Perputaran 3 s.d 4 kali",
            3: "Perputaran ≥5 kali",
        }),
        ("Data Pendukung Penghapusan ATTB", {
            1: "<50% dari material retur kategori usul hapus",
            2: "<75% dari material retur kategori usul hapus",
            3: "≥75% dari material retur kategori usul hapus",
        }),
        ("Inventory Persediaan Material", {
            1: "Kesesuaian jumlah fisik <75%",
            2: "Kesesuaian jumlah fisik ≥75% dan <95%",
            3: "Kesesuaian jumlah fisik ≥95%",
        }),
        ("Optimalisasi Material Slow Moving", {
            1: "Ada material tidak bergerak >1 tahun",
            2: "Ada material tidak bergerak 6-12 bulan",
            3: "Ada material tidak bergerak 1-5 bulan",
        }),
    ]),
]

# ---------------------------------------------------------------------------
# DATA REAL JUNI 2026 — UID Banten (7 unit), diambil dari dokumen resmi
# Urutan level per unit mengikuti urutan indikator di ASPECT_DEFS di atas.
# Urutan unit: Serpong, Cikokol, Teluk Naga, Cikupa, Banten Utara, Banten Selatan, UP2D
# ---------------------------------------------------------------------------

REAL_UNITS_JUNI = ["Serpong", "Cikokol", "Teluk Naga", "Cikupa", "Banten Utara", "Banten Selatan", "UP2D"]

REAL_LEVELS_JUNI = [
    # SDM
    [5, 5, 5, 5, 3, 5, 5],   # Sumber Daya Manusia
    [5, 5, 5, 5, 4, 4, 5],   # Manajemen Material
    [5, 5, 5, 5, 3, 5, 5],   # Pengoperasian Alat Berat
    [5, 5, 5, 5, 5, 5, 5],   # Implementasi K3
    [5, 5, 5, 5, 5, 5, 5],   # Petugas Keamanan
    # Anggaran
    [5, 5, 5, 5, 5, 5, 5],   # Anggaran Pengelolaan Gudang
    [5, 5, 5, 5, 5, 5, 5],   # Realisasi Pemanfaatan Anggaran
    # Tata Kelola
    [5, 5, 5, 5, 5, 5, 5],   # Proses Bisnis
    [5, 5, 5, 5, 5, 5, 5],   # Penyusunan Material di Rak
    [5, 5, 5, 5, 5, 5, 5],   # Tata Letak Material Baru
    [5, 5, 5, 5, 5, 5, 5],   # Tata Letak Material Retur
    [5, 5, 5, 5, 5, 5, 5],   # Identifikasi Material
    [5, 5, 5, 5, 5, 5, 5],   # Implementasi 5S
    # Infrastruktur
    [5, 5, 5, 5, 5, 5, 5],   # Rak Penyimpanan
    [5, 5, 5, 5, 4, 5, 5],   # Lantai Gudang Tertutup
    [5, 5, 5, 5, 5, 5, 5],   # Lantai Gudang Terbuka
    [5, 5, 4, 5, 5, 5, 5],   # Atap Gudang
    [5, 5, 5, 5, 5, 5, 5],   # Warna Demarkasi
    [5, 5, 5, 5, 5, 5, 5],   # Ruang Administrasi dst
    # Peralatan Operasional
    [5, 5, 5, 5, 5, 5, 5],   # Handling Material
    [5, 5, 5, 5, 5, 5, 5],   # APD
    [5, 5, 5, 5, 5, 5, 5],   # CCTV
    [5, 5, 5, 5, 5, 5, 5],   # APAR & Hydrant
    [5, 5, 5, 5, 5, 5, 5],   # Identitas Gudang
    [5, 5, 5, 5, 5, 5, 5],   # Peralatan Administratif
    # Kinerja
    [5, 1, 1, 1, 5, 1, 1],   # DOI
    [5, 5, 5, 2, 2, 5, 5],   # Penghapusan ATTB
    [5, 4, 5, 5, 3, 5, 2],   # Optimalisasi Saving MRWI
    [4, 5, 5, 1, 4, 1, 5],   # Optimalisasi Slow Moving
]


# ---------------------------------------------------------------------------
# SEED
# ---------------------------------------------------------------------------

def _seed():
    uid_id = _new_id()
    unit_ids = {name: _new_id() for name in REAL_UNITS_JUNI}

    units = [{"id": uid_id, "name": "PLN UID Banten", "type": "UID", "parent_id": None}]
    for name in REAL_UNITS_JUNI:
        units.append({"id": unit_ids[name], "name": name, "type": "UP3", "parent_id": uid_id})

    # ULP tambahan — dikelompokkan secara geografis di bawah UP3 induknya
    ulp_map = {
        "Banten Selatan": ["ULP Labuan", "ULP Malingping", "ULP Pandeglang", "ULP Rangkasbitung"],
        "Banten Utara": ["ULP Anyer", "ULP Cikande", "ULP Cilegon", "ULP Prima Krakatau", "ULP Serang"],
    }
    for up3_name, ulp_names in ulp_map.items():
        parent_id = unit_ids[up3_name]
        for ulp_name in ulp_names:
            units.append({"id": _new_id(), "name": ulp_name, "type": "ULP", "parent_id": parent_id})

    # periode
    period_juni_id = _new_id()
    period_juli_id = _new_id()
    periods = [
        {
            "id": period_juni_id, "month": 6, "year": 2026, "status": "LOCKED",
            "submission_deadline": datetime.date(2026, 6, 25),
            "review_deadline": datetime.date(2026, 6, 30),
        },
        {
            "id": period_juli_id, "month": 7, "year": 2026, "status": "OPEN",
            "submission_deadline": datetime.date(2026, 7, 25),
            "review_deadline": datetime.date(2026, 7, 31),
        },
    ]

    # aspek & indikator & level — dua set: UP3 (skala level 1-5) dan ULP (skala level 1-3)
    aspects = []
    indicators = []
    indicator_order = []       # urutan flat UP3 saja, sejajar dengan REAL_LEVELS_JUNI
    aspect_bobot_map = {}      # aspect_id -> bobot
    aspect_count_map = {}      # aspect_id -> jumlah indikator dalam aspek itu

    def _build_aspect_set(defs, unit_type, max_score):
        for aspect_name, bobot, ind_list in defs:
            aspect_id = _new_id()
            aspects.append({"id": aspect_id, "name": aspect_name, "unit_type": unit_type})
            aspect_bobot_map[aspect_id] = bobot
            aspect_count_map[aspect_id] = len(ind_list)
            for ind_name, level_map in ind_list:
                ind_id = _new_id()
                levels = [{"level": lv, "level_label": desc, "score": lv} for lv, desc in level_map.items()]
                indicators.append({
                    "id": ind_id, "aspect_id": aspect_id, "name": ind_name,
                    "maximum_score": max_score, "levels": levels,
                })
                if unit_type == "UP3":
                    indicator_order.append(ind_id)

    _build_aspect_set(ASPECT_DEFS, "UP3", 5)
    _build_aspect_set(ULP_ASPECT_DEFS, "ULP", 3)

    # bobot aspek per periode (snapshot) — berlaku sama untuk Juni & Juli, untuk kedua set
    weights = {}
    for aspect_id, bobot in aspect_bobot_map.items():
        weights[(period_juni_id, aspect_id)] = bobot
        weights[(period_juli_id, aspect_id)] = bobot

    # peta indicator_id -> aspect_id supaya bisa hitung nilai saat seeding
    ind_to_aspect = {ind["id"]: ind["aspect_id"] for ind in indicators}

    # isi assessment Juni 2026 dengan data real UP3 (status APPROVED semua) — ULP belum ada data historis
    assessments = {}
    for col_idx, unit_name in enumerate(REAL_UNITS_JUNI):
        u_id = unit_ids[unit_name]
        for row_idx, ind_id in enumerate(indicator_order):
            level = REAL_LEVELS_JUNI[row_idx][col_idx]
            aspect_id = ind_to_aspect[ind_id]
            bobot = aspect_bobot_map[aspect_id]
            jml = aspect_count_map[aspect_id]
            nilai = round((level / 5) * (bobot / jml), 4) if jml else None
            assessments[(u_id, period_juni_id, ind_id)] = {
                "level": level, "score": nilai, "notes": "", "status": "APPROVED",
                "filled_by": f"Admin {unit_name}", "evidences": [],
                "submitted_by": f"Admin {unit_name}",
                "submitted_at": datetime.datetime(2026, 6, 28),
                "approved_by": "Admin UID Banten",
                "approved_at": datetime.datetime(2026, 6, 30),
            }

    # ---- kredensial login (username/password) ----
    def _slug(name: str) -> str:
        return name.lower().replace(" ", "").replace(".", "")

    credentials = {}
    credentials["uid banten"] = {
        "password": "uidbanten123", "unit_id": uid_id,
        "fullname": "Admin UID Banten",
    }
    for u in units:
        if u["type"] in ("UP3", "ULP"):
            username = u["name"].lower()
            credentials[username] = {
                "password": f"{_slug(u['name'])}123",
                "unit_id": u["id"],
                "fullname": f"Admin {u['name']}",
            }

    db = {
        "units": units,
        "periods": periods,
        "aspects": aspects,
        "indicators": indicators,
        "weights": weights,          # key: (period_id, aspect_id) -> bobot aspek
        "assessments": assessments,  # key: (unit_id, period_id, indicator_id) -> dict
        "reviews": [],
        "notifications": [],
        "credentials": credentials,  # key: username (lowercase) -> {password, unit_id, fullname}
    }
    return db


def authenticate(username: str, password: str):
    """Cek username/password, kembalikan dict user info kalau cocok, None kalau tidak."""
    creds = _db().get("credentials", {})
    entry = creds.get((username or "").strip().lower())
    if not entry or entry["password"] != password:
        return None
    unit = get_unit_by_id(entry["unit_id"])
    if not unit:
        return None
    return {
        "role": unit["type"],
        "unit_id": unit["id"],
        "unit_name": unit["name"],
        "fullname": entry["fullname"],
    }


def get_all_credentials_list():
    """Untuk ditampilkan di halaman login sebagai referensi (mode prototipe)."""
    creds = _db().get("credentials", {})
    rows = []
    for username, entry in creds.items():
        unit = get_unit_by_id(entry["unit_id"])
        rows.append({
            "username": username, "password": entry["password"],
            "role": unit["type"] if unit else "-", "unit_name": unit["name"] if unit else "-",
        })
    role_order = {"UID": 0, "UP3": 1, "ULP": 2}
    rows.sort(key=lambda r: (role_order.get(r["role"], 9), r["unit_name"]))
    return rows


# ---------------------------------------------------------------------------
# PERSISTENSI SUPABASE (opsional) — kalau secrets Supabase tersedia di
# .streamlit/secrets.toml, seluruh state di-load dari & disimpan ke Supabase
# supaya bertahan lintas restart server. Kalau secrets belum di-setup,
# otomatis fallback ke in-memory saja (perilaku sebelumnya) tanpa error.
# ---------------------------------------------------------------------------

_SUPABASE_TABLE = "simona_state"
_SUPABASE_ROW_ID = 1


def _get_supabase_client():
    try:
        from supabase import create_client
    except ImportError:
        return None
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_ANON_KEY"]
    except Exception:
        return None
    if not url or not key:
        return None
    try:
        return create_client(url, key)
    except Exception:
        return None


def _load_from_supabase():
    client = _get_supabase_client()
    if not client:
        return None
    try:
        res = client.table(_SUPABASE_TABLE).select("data").eq("id", _SUPABASE_ROW_ID).execute()
        if res.data and len(res.data) > 0 and res.data[0].get("data"):
            raw = res.data[0]["data"]
            if isinstance(raw, str):
                raw = json.loads(raw)
            decoded = _decode_nested(raw)
            return {
                "units": decoded["units"],
                "periods": decoded["periods"],
                "aspects": decoded["aspects"],
                "indicators": decoded["indicators"],
                "weights": {tuple(k): v for k, v in decoded["weights"]},
                "assessments": {tuple(k): v for k, v in decoded["assessments"]},
                "reviews": decoded["reviews"],
                "notifications": decoded["notifications"],
                "credentials": decoded["credentials"],
            }
    except Exception as e:
        print(f"[SIMONA] Gagal load dari Supabase, fallback ke seed baru: {e}")
    return None


def _save_to_supabase(db: dict):
    client = _get_supabase_client()
    if not client:
        return
    try:
        export_obj = {
            "units": db["units"],
            "periods": db["periods"],
            "aspects": db["aspects"],
            "indicators": db["indicators"],
            "weights": [[list(k), v] for k, v in db["weights"].items()],
            "assessments": [[list(k), v] for k, v in db["assessments"].items()],
            "reviews": db["reviews"],
            "notifications": db["notifications"],
            "credentials": db["credentials"],
        }
        payload_str = json.dumps(export_obj, default=_json_default, ensure_ascii=False)
        payload = json.loads(payload_str)  # balik jadi dict/list murni biar bisa dikirim sebagai jsonb
        client.table(_SUPABASE_TABLE).upsert({
            "id": _SUPABASE_ROW_ID, "data": payload,
            "updated_at": datetime.datetime.now().isoformat(),
        }).execute()
    except Exception as e:
        print(f"[SIMONA] Gagal simpan ke Supabase: {e}")


def _persist():
    """Panggil setelah operasi tulis supaya perubahan tersimpan permanen di
    Supabase (kalau sudah terkonfigurasi). Aman dipanggil walau Supabase
    belum di-setup — akan diam-diam tidak melakukan apa-apa."""
    _save_to_supabase(_db())


@st.cache_resource(show_spinner=False)
def _get_shared_db():
    """
    Dict database yang di-cache dengan st.cache_resource, sehingga OBJEK YANG
    SAMA dipakai bersama oleh SEMUA sesi/user yang mengakses app ini pada
    instance server yang sama — bukan per-browser seperti st.session_state.

    Kalau Supabase sudah dikonfigurasi (lihat _get_supabase_client), state
    di-load dari sana saat pertama kali dibutuhkan, dan setiap perubahan
    (lewat _persist()) langsung disimpan balik ke Supabase — sehingga data
    tetap ada meski server sempat restart/tidur. Kalau Supabase belum
    dikonfigurasi, otomatis pakai data seed awal yang hanya hidup di memori
    (hilang kalau server restart, sama seperti sebelumnya).
    """
    from_supabase = _load_from_supabase()
    if from_supabase is not None:
        return from_supabase
    db = _seed()
    _save_to_supabase(db)
    return db


def _db() -> dict:
    return _get_shared_db()


def init_demo_data():
    _get_shared_db()


def reset_demo_data():
    """Paksa reseed data awal (Juni 2026 real + Juli 2026 kosong), dan timpa
    Supabase kalau sudah dikonfigurasi — beda dari _get_shared_db() biasa
    yang akan coba load data lama dari Supabase dulu."""
    _get_shared_db.clear()
    fresh_db = _seed()
    _save_to_supabase(fresh_db)
    _get_shared_db()  # isi ulang cache dengan data fresh yang baru saja disimpan


# ---------------------------------------------------------------------------
# BACKUP & RESTORE — pengaman kalau server sempat restart/tidur.
# Karena data disimpan di cache_resource (memory server), data akan hilang
# kalau proses server-nya benar-benar restart (misal app tidur lama di
# Streamlit Cloud versi gratis, atau redeploy). Export berkala ke file JSON
# supaya bisa dipulihkan kalau itu terjadi.
# ---------------------------------------------------------------------------

def _json_default(o):
    if isinstance(o, datetime.datetime):
        return {"__type__": "datetime", "value": o.isoformat()}
    if isinstance(o, datetime.date):
        return {"__type__": "date", "value": o.isoformat()}
    if isinstance(o, bytes):
        return {"__type__": "bytes", "value": base64.b64encode(o).decode()}
    raise TypeError(f"Tipe tidak didukung untuk backup: {type(o)}")


def _decode_nested(obj):
    if isinstance(obj, dict):
        if set(obj.keys()) == {"__type__", "value"}:
            t = obj["__type__"]
            if t == "datetime":
                return datetime.datetime.fromisoformat(obj["value"])
            if t == "date":
                return datetime.date.fromisoformat(obj["value"])
            if t == "bytes":
                return base64.b64decode(obj["value"])
        return {k: _decode_nested(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_decode_nested(v) for v in obj]
    return obj


def export_data_json() -> str:
    """Serialize seluruh database (mode prototipe, in-memory) jadi teks JSON."""
    db = _db()
    export_obj = {
        "units": db["units"],
        "periods": db["periods"],
        "aspects": db["aspects"],
        "indicators": db["indicators"],
        "weights": [[list(k), v] for k, v in db["weights"].items()],
        "assessments": [[list(k), v] for k, v in db["assessments"].items()],
        "reviews": db["reviews"],
        "notifications": db["notifications"],
        "credentials": db["credentials"],
        "exported_at": datetime.datetime.now().isoformat(),
    }
    return json.dumps(export_obj, default=_json_default, ensure_ascii=False, indent=2)


def import_data_json(json_str: str):
    """Timpa seluruh database dengan isi file backup JSON. Berlaku untuk semua
    user yang sedang pakai app ini (karena datanya shared/cache_resource)."""
    raw = json.loads(json_str)
    raw = _decode_nested(raw)
    db = _db()
    db.clear()
    db["units"] = raw["units"]
    db["periods"] = raw["periods"]
    db["aspects"] = raw["aspects"]
    db["indicators"] = raw["indicators"]
    db["weights"] = {tuple(k): v for k, v in raw["weights"]}
    db["assessments"] = {tuple(k): v for k, v in raw["assessments"]}
    db["reviews"] = raw["reviews"]
    db["notifications"] = raw["notifications"]
    db["credentials"] = raw["credentials"]
    _persist()


# ---------------------------------------------------------------------------
# UNITS & PERIODS
# ---------------------------------------------------------------------------

def get_units(unit_type: str | None = None) -> pd.DataFrame:
    df = pd.DataFrame(_db()["units"])
    if unit_type:
        df = df[df["type"] == unit_type]
    return df


def get_unit_by_id(unit_id: str) -> dict | None:
    for u in _db()["units"]:
        if u["id"] == unit_id:
            return u
    return None


def get_child_units(parent_id: str) -> pd.DataFrame:
    df = pd.DataFrame(_db()["units"])
    if df.empty:
        return df
    return df[df["parent_id"] == parent_id]


def get_periods() -> pd.DataFrame:
    return pd.DataFrame(_db()["periods"])


def add_period(month, year, submission_deadline, review_deadline):
    new_id = _new_id()
    _db()["periods"].append({
        "id": new_id, "month": month, "year": year, "status": "OPEN",
        "submission_deadline": submission_deadline, "review_deadline": review_deadline,
    })
    # otomatis salin bobot aspek dari periode terakhir supaya tidak mulai dari nol
    existing_periods = [p for p in _db()["periods"] if p["id"] != new_id]
    if existing_periods:
        latest = existing_periods[-1]
        for a in _db()["aspects"]:
            w = _db()["weights"].get((latest["id"], a["id"]))
            if w is not None:
                _db()["weights"][(new_id, a["id"])] = w
    _persist()
    return new_id


def lock_period(period_id: str):
    for p in _db()["periods"]:
        if p["id"] == period_id:
            p["status"] = "LOCKED"
    _persist()


def add_unit(name, unit_type, parent_id):
    _db()["units"].append({
        "id": _new_id(), "name": name, "type": unit_type, "parent_id": parent_id,
    })
    _persist()


# ---------------------------------------------------------------------------
# ASPECTS / INDICATORS / WEIGHTS (bobot di level ASPEK, snapshot per periode)
# ---------------------------------------------------------------------------

def get_aspects(unit_type: str | None = None) -> pd.DataFrame:
    df = pd.DataFrame(_db()["aspects"])
    if unit_type and not df.empty:
        df = df[df["unit_type"] == unit_type]
    return df


def add_aspect(name, unit_type="UP3"):
    _db()["aspects"].append({"id": _new_id(), "name": name, "unit_type": unit_type})
    _persist()


def get_indicators(aspect_id: str | None = None) -> list[dict]:
    inds = _db()["indicators"]
    if aspect_id:
        inds = [i for i in inds if i["aspect_id"] == aspect_id]
    return inds


def get_indicators_for_unit_type(unit_type: str) -> list[dict]:
    """Semua indikator (lintas aspek) yang berlaku untuk tipe unit tertentu (UP3/ULP)."""
    aspect_ids = {a["id"] for a in _db()["aspects"] if a["unit_type"] == unit_type}
    return [i for i in _db()["indicators"] if i["aspect_id"] in aspect_ids]


def add_indicator(aspect_id, name, maximum_score=5):
    _db()["indicators"].append({
        "id": _new_id(), "aspect_id": aspect_id, "name": name,
        "maximum_score": maximum_score, "levels": [],
    })
    _persist()


def add_level(indicator_id, level, label, score=None):
    for ind in _db()["indicators"]:
        if ind["id"] == indicator_id:
            ind["levels"] = [lv for lv in ind["levels"] if lv["level"] != level]
            ind["levels"].append({"level": level, "level_label": label, "score": score if score is not None else level})
            ind["levels"].sort(key=lambda x: x["level"])
    _persist()


def get_aspect_weight(period_id, aspect_id) -> float:
    return _db()["weights"].get((period_id, aspect_id), 0.0)


def set_aspect_weight(period_id, aspect_id, bobot):
    period = next((p for p in _db()["periods"] if p["id"] == period_id), None)
    if period and period["status"] == "LOCKED":
        raise ValueError("Periode sudah LOCKED, bobot aspek tidak bisa diubah.")
    _db()["weights"][(period_id, aspect_id)] = bobot
    _persist()


# ---------------------------------------------------------------------------
# ASSESSMENTS
# ---------------------------------------------------------------------------

def _akey(unit_id, period_id, indicator_id):
    return (unit_id, period_id, indicator_id)


def get_assessment(unit_id, period_id, indicator_id) -> dict | None:
    return _db()["assessments"].get(_akey(unit_id, period_id, indicator_id))


def get_assessments_for_unit(unit_id, period_id) -> list[dict]:
    out = []
    for (u, p, i), val in _db()["assessments"].items():
        if u == unit_id and p == period_id:
            out.append({**val, "unit_id": u, "period_id": p, "indicator_id": i})
    return out


def get_assessments_for_units(unit_ids, period_id) -> list[dict]:
    out = []
    for (u, p, i), val in _db()["assessments"].items():
        if u in unit_ids and p == period_id:
            out.append({**val, "unit_id": u, "period_id": p, "indicator_id": i})
    return out


def _count_indicators_in_aspect(aspect_id) -> int:
    return len([i for i in _db()["indicators"] if i["aspect_id"] == aspect_id])


def _indicator_nilai(period_id, indicator_id, level) -> float | None:
    """Nilai kontribusi indikator ke total 100, sesuai formula resmi:
    (Level / MaxLevel) x (Bobot Aspek / Jumlah Indikator dalam Aspek).
    MaxLevel otomatis mengikuti skala indikator (5 untuk UP3, 3 untuk ULP)."""
    if level is None:
        return None
    ind = next((i for i in _db()["indicators"] if i["id"] == indicator_id), None)
    if not ind:
        return None
    bobot_aspek = get_aspect_weight(period_id, ind["aspect_id"])
    jumlah_indikator = _count_indicators_in_aspect(ind["aspect_id"])
    max_level = max((lv["level"] for lv in ind["levels"]), default=5)
    if jumlah_indikator == 0:
        return None
    return round((level / max_level) * (bobot_aspek / jumlah_indikator), 4)


def save_draft(unit_id, period_id, indicator_id, level, notes, filled_by):
    key = _akey(unit_id, period_id, indicator_id)
    existing = _db()["assessments"].get(key, {})
    nilai = _indicator_nilai(period_id, indicator_id, level)

    _db()["assessments"][key] = {
        **existing,
        "level": level, "score": nilai, "notes": notes,
        "status": existing.get("status", "DRAFT")
        if existing.get("status") in ("DRAFT", "REVISION") else "DRAFT",
        "filled_by": filled_by,
        "evidences": existing.get("evidences", []),
        "updated_at": datetime.datetime.now(),
    }
    _persist()


def submit_unit_assessments(unit_id, period_id, submitted_by):
    count = 0
    for key, val in _db()["assessments"].items():
        u, p, _ = key
        if u == unit_id and p == period_id and val["status"] in ("DRAFT", "REVISION"):
            val["status"] = "SUBMITTED"
            val["submitted_by"] = submitted_by
            val["submitted_at"] = datetime.datetime.now()
            count += 1
    if count:
        add_notification(
            target_role="UID",
            title="Assessment baru menunggu review",
            message=f"{get_unit_by_id(unit_id)['name']} mengirim {count} indikator untuk periode ini.",
            n_type="SUBMISSION_RECEIVED",
        )
    _persist()
    return count


def approve_assessment(unit_id, period_id, indicator_id, reviewer, comments):
    key = _akey(unit_id, period_id, indicator_id)
    val = _db()["assessments"].get(key)
    if val:
        val["status"] = "APPROVED"
        val["approved_by"] = reviewer
        val["approved_at"] = datetime.datetime.now()
    _db()["reviews"].append({
        "unit_id": unit_id, "period_id": period_id, "indicator_id": indicator_id,
        "decision": "APPROVE", "comments": comments, "reviewer": reviewer,
        "time": datetime.datetime.now(),
    })
    add_notification(
        target_unit_id=unit_id,
        title="Assessment disetujui",
        message=f"Indikator disetujui oleh {reviewer}.",
        n_type="APPROVAL",
    )
    _persist()


def request_revision(unit_id, period_id, indicator_id, reviewer, comments):
    key = _akey(unit_id, period_id, indicator_id)
    val = _db()["assessments"].get(key)
    if val:
        val["status"] = "REVISION"
        val["revision_count"] = val.get("revision_count", 0) + 1
    _db()["reviews"].append({
        "unit_id": unit_id, "period_id": period_id, "indicator_id": indicator_id,
        "decision": "REQUEST_REVISION", "comments": comments, "reviewer": reviewer,
        "time": datetime.datetime.now(),
    })
    add_notification(
        target_unit_id=unit_id,
        title="Assessment dikembalikan untuk revisi",
        message=comments,
        n_type="REVISION_REQUEST",
    )
    _persist()


def get_reviews_for(unit_id, period_id, indicator_id) -> list[dict]:
    return [
        r for r in _db()["reviews"]
        if r["unit_id"] == unit_id and r["period_id"] == period_id and r["indicator_id"] == indicator_id
    ]


# ---------------------------------------------------------------------------
# EVIDENCE
# ---------------------------------------------------------------------------

def add_evidence(unit_id, period_id, indicator_id, filename, uploaded_by, file_bytes=None, mime_type=None):
    key = _akey(unit_id, period_id, indicator_id)
    val = _db()["assessments"].setdefault(key, {
        "level": None, "score": None, "notes": "", "status": "DRAFT",
        "filled_by": uploaded_by, "evidences": [],
    })
    val.setdefault("evidences", []).append({
        "filename": filename, "uploaded_by": uploaded_by,
        "uploaded_at": datetime.datetime.now(),
        "file_bytes": file_bytes,
        "mime_type": mime_type,
    })
    _persist()


# ---------------------------------------------------------------------------
# SCORING — sesuai formula resmi dokumen
# ---------------------------------------------------------------------------

def compute_unit_total_score(unit_id, period_id) -> dict:
    unit = get_unit_by_id(unit_id)
    unit_type = unit["type"] if unit else "UP3"
    assessments = get_assessments_for_unit(unit_id, period_id)
    total_nilai = 0.0
    counts = {"DRAFT": 0, "SUBMITTED": 0, "REVISION": 0, "APPROVED": 0}
    total_indicators = len(get_indicators_for_unit_type(unit_type))

    for a in assessments:
        if a.get("score") is not None:
            total_nilai += a["score"]
        status = a.get("status", "DRAFT")
        counts[status] = counts.get(status, 0) + 1

    total_nilai = round(total_nilai, 2)
    matlev = round(total_nilai / 20, 2) if total_nilai else 0.0
    completion = round(100 * counts["APPROVED"] / total_indicators, 1) if total_indicators else 0

    return {
        "unit_id": unit_id, "period_id": period_id,
        "total_score": total_nilai, "matlev": matlev,
        "completion_percentage": completion, "total_indicators": total_indicators,
        **{f"{k.lower()}_indicators": v for k, v in counts.items()},
    }


def compute_aspect_scores(unit_id, period_id) -> pd.DataFrame:
    unit = get_unit_by_id(unit_id)
    unit_type = unit["type"] if unit else "UP3"
    rows = []
    for aspect in _db()["aspects"]:
        if aspect["unit_type"] != unit_type:
            continue
        inds = get_indicators(aspect["id"])
        bobot_aspek = get_aspect_weight(period_id, aspect["id"])
        nilai_total = 0.0
        levels_filled = []
        aspect_max_level = max(
            (lv["level"] for ind in inds for lv in ind["levels"]), default=5
        )
        for ind in inds:
            a = get_assessment(unit_id, period_id, ind["id"])
            if a and a.get("score") is not None:
                nilai_total += a["score"]
            if a and a.get("level") is not None:
                levels_filled.append(a["level"])
        avg_level = round(sum(levels_filled) / len(levels_filled), 2) if levels_filled else 0
        pct_achieved = round(100 * avg_level / aspect_max_level, 1) if aspect_max_level else 0
        rows.append({
            "aspect_name": aspect["name"],
            "aspect_score": round(nilai_total, 2),   # kontribusi ke total 100
            "bobot_aspek": bobot_aspek,
            "avg_level": avg_level,                   # rata-rata level di aspek ini (skala sesuai tipe unit)
            "max_level": aspect_max_level,
            "pct_achieved": pct_achieved,              # avg_level dinormalisasi 0-100%, agar UP3 & ULP sebanding
        })
    return pd.DataFrame(rows)


def compute_evidence_completion(unit_id, period_id) -> float:
    unit = get_unit_by_id(unit_id)
    unit_type = unit["type"] if unit else "UP3"
    assessments = get_assessments_for_unit(unit_id, period_id)
    total = len(get_indicators_for_unit_type(unit_type))
    with_evidence = sum(1 for a in assessments if a.get("evidences"))
    return round(100 * with_evidence / total, 1) if total else 0.0


# ---------------------------------------------------------------------------
# NOTIFICATIONS
# ---------------------------------------------------------------------------

def add_notification(title, message, n_type, target_unit_id=None, target_role=None):
    _db()["notifications"].append({
        "id": _new_id(), "title": title, "message": message, "type": n_type,
        "target_unit_id": target_unit_id, "target_role": target_role,
        "is_read": False, "created_at": datetime.datetime.now(),
    })


def get_notifications_for(role, unit_id) -> list[dict]:
    out = []
    for n in _db()["notifications"]:
        if n.get("target_role") == role or n.get("target_unit_id") == unit_id:
            out.append(n)
    return sorted(out, key=lambda x: x["created_at"], reverse=True)
