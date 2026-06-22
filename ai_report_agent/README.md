# AI Report Agent — Odoo 18

Modul Odoo 18 yang mengubah permintaan laporan dalam bahasa alami (Indonesia/Inggris) menjadi laporan PDF dan Excel secara otomatis, didukung oleh AI (Anthropic Claude, OpenAI, Ollama, atau endpoint HTTP kustom).

---

## Daftar Isi

1. [Gambaran Umum](#gambaran-umum)
2. [Cara Kerja](#cara-kerja)
3. [Persyaratan Sistem](#persyaratan-sistem)
4. [Instalasi](#instalasi)
5. [Konfigurasi](#konfigurasi)
6. [Cara Penggunaan](#cara-penggunaan)
7. [Endpoint API](#endpoint-api)
8. [Integrasi MCP](#integrasi-mcp)
9. [Struktur Modul](#struktur-modul)
10. [Keamanan](#keamanan)
11. [Pertanyaan Umum (FAQ)](#pertanyaan-umum)
12. [Pemecahan Masalah](#pemecahan-masalah)

---

## Gambaran Umum

**AI Report Agent** adalah lapisan cerdas di dalam Odoo yang:

- Menerima permintaan laporan dalam bahasa natural (Bahasa Indonesia atau Inggris)
- Menerjemahkan permintaan menjadi spesifikasi JSON terstruktur menggunakan AI
- Memvalidasi dan memperluas spesifikasi tersebut secara deterministik (tanpa AI)
- Mengambil data dari ORM Odoo
- Menghasilkan file **PDF** dan/atau **Excel (.xlsx)**
- Menyimpan setiap permintaan ke dalam riwayat yang dapat ditelusuri

> **Prinsip utama:** AI hanya bertugas memahami maksud pengguna. Semua logika tanggal, pemetaan model, dan kueri database dilakukan oleh kode Python deterministik — bukan oleh AI.

---

## Cara Kerja

```
Pengguna menulis permintaan
         |
         v
  [1] AI Interpreter
      Memanggil LLM → menghasilkan JSON intent
         |
         v
  [2] Rule Engine
      Memvalidasi & memperluas intent (deterministik)
         |
         v
  [3] Date Parser
      Mengubah kunci tanggal → objek date Python
         |
         v
  [4] Report Builder
      Kueri ORM Odoo → ReportResult
         |
         v
  [5] File Generator
      Excel (openpyxl) dan/atau PDF (QWeb / ReportLab)
         |
         v
  Attachment disimpan di ir.attachment
  Riwayat disimpan di ai.report.history
  Tautan unduhan dikembalikan ke pengguna
```

### Jenis Laporan yang Didukung

| Intent | Model Odoo | Konten Laporan |
|--------|------------|----------------|
| `sales` | `sale.order` | Total pendapatan, jumlah order, produk terlaris |
| `invoice` | `account.move` | Belum dibayar, jatuh tempo, sudah dibayar |
| `inventory` | `stock.quant` | Stok menipis, jumlah stok per lokasi |
| `purchase` | `purchase.order` | Total pembelian, jumlah PO, pemasok |
| `summary` | Gabungan semua | Dashboard KPI bisnis |

---

## Persyaratan Sistem

### Odoo
- Odoo 18 Community atau Enterprise
- Modul yang diaktifkan: `base`, `mail`, `account`, `sale`, `stock`, `purchase`

### Python
```
anthropic>=0.20.0      # Untuk provider Anthropic Claude
openai>=1.0.0          # Untuk provider OpenAI
openpyxl>=3.1.0        # Untuk generator Excel
python-dateutil>=2.8   # Untuk parser tanggal
reportlab>=4.0         # Opsional, fallback PDF jika QWeb gagal
```

Instalasi dependensi:
```bash
pip install anthropic openai openpyxl python-dateutil reportlab
```

---

## Instalasi

### Langkah 1 — Salin modul ke addons path

```bash
cp -r ai_report_agent /path/ke/odoo/addons/
```

Atau tambahkan folder induk ke `addons_path` di `odoo.conf`:
```ini
addons_path = /path/ke/folder/induk,...
```

### Langkah 2 — Perbarui daftar aplikasi

Di Odoo:
1. Masuk sebagai Administrator
2. Buka **Pengaturan → Teknis → Perbarui Daftar Modul**
3. Cari `AI Report Agent`
4. Klik **Instal**

Atau via CLI:
```bash
python odoo-bin -d nama_database -u ai_report_agent --stop-after-init
```

### Langkah 3 — Instal dependensi Python

```bash
pip install anthropic openai openpyxl python-dateutil
```

---

## Konfigurasi

Setelah instalasi, buka menu **AI Reports → Konfigurasi**.

### Pengaturan Provider LLM

| Field | Keterangan |
|-------|------------|
| **Provider** | Pilih: Anthropic Claude, OpenAI, Ollama Local, atau Custom HTTP |
| **Nama Model** | Contoh: `claude-sonnet-4-20250514`, `gpt-4o`, `llama3` |
| **API Key** | Disimpan terenkripsi, tidak pernah terekspos di RPC |
| **API Endpoint** | Wajib untuk Ollama atau Custom HTTP |
| **Temperature** | 0.0 (deterministik) hingga 1.0 (kreatif) — rekomendasi: 0.1 |
| **Max Tokens** | Batas token respons AI — rekomendasi: 1000 |

### Pengaturan Laporan

| Field | Default | Keterangan |
|-------|---------|------------|
| **Max Rows** | 1000 | Batas baris data per laporan |
| **Async Threshold** | 5000 | Data lebih dari nilai ini diproses lewat antrian async |
| **Enable AI Insights** | Ya | Tambahkan ringkasan AI pada hasil laporan |
| **Fallback ke Rule Engine** | Ya | Gunakan rule engine jika confidence AI < 0.5 |

### System Prompt

Prompt sistem dapat diedit langsung dari form konfigurasi. Ini adalah instruksi yang dikirimkan ke LLM setiap kali ada permintaan laporan.

### Uji Koneksi

Klik tombol **Uji Koneksi** untuk memverifikasi bahwa provider LLM dapat dihubungi dengan konfigurasi yang aktif.

---

## Cara Penggunaan

### 1. Melalui Menu AI Reports

Buka **AI Reports → Generate Report**, lalu:
- Masukkan permintaan laporan dalam Bahasa Indonesia atau Inggris
- Centang format output yang diinginkan (PDF, Excel, atau keduanya)
- Klik **Generate Report**
- Wizard akan menampilkan interpretasi AI sebelum file dibuat
- Unduh file dari halaman yang sama

### 2. Melalui Tombol AI Report di Discuss

Di halaman **Discuss** (obrolan tim), klik tombol **AI Report** di toolbar atas. Panel akan muncul dengan:
- Kotak teks untuk menulis permintaan
- Tombol prompt cepat (lihat di bawah)
- Opsi format PDF dan/atau Excel
- Tautan unduhan setelah laporan selesai

### 3. Contoh Permintaan yang Didukung

**Bahasa Indonesia:**
```
Laporan penjualan bulan ini
Faktur belum dibayar bulan ini
Stok menipis di semua gudang
Ringkasan bisnis bulan lalu
Faktur jatuh tempo
Purchase order minggu ini
10 produk terlaris kuartal ini
Laporan pembelian tahun ini
Faktur yang sudah dibayar bulan Maret
```

**Bahasa Inggris:**
```
Unpaid invoices this month
Sales summary last quarter
Low stock alerts
Top 10 best-selling products Q3
Business dashboard last month
Overdue invoices
Purchase orders this week
```

### Tombol Prompt Cepat

Panel Discuss menyediakan 6 tombol prompt cepat:

| Tombol | Maksud |
|--------|--------|
| Unpaid invoices this month | Faktur belum dibayar bulan ini |
| Top 10 best-selling products this quarter | 10 produk terlaris kuartal ini |
| Low stock alerts | Peringatan stok menipis |
| Business summary last month | Ringkasan bisnis bulan lalu |
| Overdue invoices | Faktur jatuh tempo |
| Purchase orders this week | Purchase order minggu ini |

### 4. Melihat Riwayat Laporan

Buka **AI Reports → Riwayat Laporan** untuk melihat semua permintaan yang pernah dibuat, lengkap dengan:
- Teks permintaan asli
- JSON intent yang dihasilkan AI
- Confidence score AI
- Status pemrosesan
- Tautan unduhan file
- Insight AI (jika diaktifkan)

Dari halaman riwayat, Anda dapat:
- **Regenerate**: Buat ulang laporan dengan permintaan yang sama
- **Download PDF / Excel**: Unduh ulang file yang sudah dibuat
- Filter berdasarkan: tanggal, jenis laporan, status, pengguna

---

## Endpoint API

### `POST /ai/report`

Endpoint utama untuk membuat laporan via API.

**Request:**
```json
{
  "message": "laporan penjualan bulan ini",
  "session_id": "opsional-string-sesi",
  "output_formats": ["pdf", "xlsx"]
}
```

**Response (sukses):**
```json
{
  "status": "ok",
  "intent": {
    "intent": "sales",
    "model": "sale.order",
    "date_range": "this_month",
    "filters": {},
    "report_type": "table",
    "output_formats": ["pdf", "xlsx"],
    "confidence": 0.95
  },
  "download_url": "/web/content/42?download=true",
  "download_urls": {
    "pdf": "/web/content/42?download=true",
    "xlsx": "/web/content/43?download=true"
  },
  "insight": "Terdapat 47 order penjualan dengan total pendapatan Rp 234.500.000",
  "history_id": 15,
  "needs_clarification": false,
  "clarification_question": null,
  "record_count": 47,
  "date_from": "2026-05-01",
  "date_to": "2026-05-31"
}
```

**Response (antrian async — data besar):**
```json
{
  "status": "queued",
  "message": "Laporan dimasukkan ke antrian karena dataset besar.",
  "history_id": 16
}
```

**Response (error):**
```json
{
  "status": "error",
  "error": "Pesan error yang menjelaskan masalah",
  "history_id": 17
}
```

**Batas Rate:** Maksimal 10 permintaan per menit per pengguna.

---

## Integrasi MCP

Modul ini mengekspos Odoo sebagai **MCP Server** agar agen AI eksternal dapat memanggil data dan laporan Odoo secara terstandar.

### `GET /mcp/tools`

Mengembalikan skema semua tool yang tersedia.

**Contoh respons:**
```json
{
  "server_info": {
    "name": "odoo-ai-report-agent",
    "version": "1.0.0"
  },
  "tools": [
    {
      "name": "search_records",
      "description": "Cari record di model Odoo mana saja"
    },
    {
      "name": "get_report",
      "description": "Jalankan pipeline AI Report Agent"
    },
    {
      "name": "list_models",
      "description": "Daftar model Odoo yang bisa diakses"
    },
    {
      "name": "get_kpi",
      "description": "Ambil nilai KPI yang telah ditentukan"
    }
  ]
}
```

### `POST /mcp/call`

Panggil salah satu tool di atas.

**Contoh — Ambil laporan:**
```json
{
  "tool_name": "get_report",
  "arguments": {
    "message": "faktur belum dibayar bulan ini",
    "output_format": ["pdf"]
  }
}
```

**Contoh — Cari record:**
```json
{
  "tool_name": "search_records",
  "arguments": {
    "model": "sale.order",
    "domain": [["state", "=", "sale"]],
    "fields": ["name", "partner_id", "amount_total"],
    "limit": 50
  }
}
```

**Contoh — Ambil KPI:**
```json
{
  "tool_name": "get_kpi",
  "arguments": {
    "kpi": "unpaid_invoices",
    "date_range": "this_month"
  }
}
```

Model yang dapat diakses via MCP: `sale.order`, `account.move`, `stock.quant`, `purchase.order`, `hr.expense`, `res.partner`, `product.product`, `product.template`.

---

## Struktur Modul

```
ai_report_agent/
├── __manifest__.py              # Metadata modul Odoo 18
├── __init__.py
│
├── controllers/
│   └── main.py                  # Endpoint HTTP: /ai/report, /mcp/tools, /mcp/call
│
├── services/
│   ├── ai_interpreter.py        # Layer AI: panggil LLM → parse JSON intent
│   ├── date_parser.py           # Parser tanggal deterministik (tanpa AI)
│   ├── rule_engine.py           # Validasi & ekspansi intent (tanpa AI)
│   ├── report_builder.py        # Kueri ORM → ReportResult
│   ├── excel_generator.py       # Generator Excel (openpyxl)
│   ├── pdf_generator.py         # Generator PDF (QWeb / ReportLab)
│   └── mcp_bridge.py            # Bridge MCP untuk agen AI eksternal
│
├── models/
│   ├── ai_report_config.py      # Model konfigurasi LLM
│   ├── ai_report_history.py     # Model riwayat permintaan laporan
│   └── ai_report_queue.py       # Model antrian async + cron
│
├── wizard/
│   └── report_preview_wizard.py # Wizard preview sebelum generate
│
├── views/
│   ├── ai_report_config_view.xml
│   ├── ai_report_history_view.xml
│   ├── ai_report_queue_view.xml
│   ├── report_preview_wizard_view.xml
│   └── menu_views.xml
│
├── templates/
│   └── report_templates.xml     # Template QWeb untuk setiap jenis laporan
│
├── security/
│   └── ir.model.access.csv      # Hak akses per model per grup
│
├── static/src/
│   ├── js/
│   │   └── ai_report_button.js  # Komponen OWL 2.0 untuk panel Discuss
│   └── xml/
│       └── ai_report_components.xml  # Template OWL
│
└── data/
    ├── default_config.xml       # Konfigurasi default saat instalasi
    └── cron_data.xml            # Jadwal cron untuk memproses antrian
```

---

## Keamanan

### Kontrol Akses

| Model | Administrator | Pengguna Biasa |
|-------|:---:|:---:|
| `ai.report.config` | Baca, Tulis, Buat, Hapus | Baca |
| `ai.report.history` | Penuh | Baca, Tulis, Buat |
| `ai.report.queue` | Penuh | Baca, Tulis |
| `report.preview.wizard` | Penuh | Penuh |

### Perlindungan Data

- **API Key** disimpan di `ir.config_parameter` terenkripsi, tidak pernah dikembalikan lewat RPC
- **Multi-company**: semua kueri ORM otomatis dibatasi ke perusahaan pengguna aktif
- **Rate Limiting**: maksimal 10 permintaan per menit per pengguna di endpoint `/ai/report`
- **Sanitasi Input**: Rule Engine memeriksa dan membuang karakter yang berpotensi injeksi sebelum menyentuh ORM
- **Model Allowlist**: endpoint MCP hanya mengizinkan akses ke model yang telah disetujui

### Antrian Async

Permintaan dengan estimasi data lebih dari `async_threshold` (default: 5.000 baris) secara otomatis dimasukkan ke antrian dan diproses oleh `ir.cron` setiap 5 menit. Pengguna menerima notifikasi di Chatter ketika laporan selesai.

---

## Pertanyaan Umum

**Q: Apakah saya harus menggunakan Anthropic Claude?**

Tidak. Anda bisa menggunakan OpenAI GPT, Ollama (model lokal seperti LLaMA, Mistral), atau endpoint HTTP kustom apa pun. Semua provider dikonfigurasi dari menu **AI Reports → Konfigurasi**.

---

**Q: Apakah data perusahaan dikirim ke server AI?**

Hanya teks permintaan pengguna yang dikirim ke LLM — bukan data transaksi. Data aktual (order, faktur, stok) diambil langsung dari database Odoo setelah AI menghasilkan intent JSON.

---

**Q: Apa yang terjadi jika AI tidak memahami permintaan?**

Jika confidence AI di bawah 0.5 dan **Fallback ke Rule Engine** diaktifkan (default: Ya), modul secara otomatis menggunakan laporan ringkasan untuk bulan ini sebagai default yang aman. Pengguna akan melihat pesan klarifikasi.

---

**Q: Berapa batas ukuran laporan?**

- **Sinkron**: hingga `max_rows` baris (default: 1.000)
- **Async**: data di atas `async_threshold` (default: 5.000) diproses di latar belakang

Kedua nilai ini dapat diubah di halaman konfigurasi.

---

**Q: Apakah laporan mendukung multi-perusahaan?**

Ya. Setiap kueri secara otomatis dibatasi ke `company_id` dari pengguna yang sedang login.

---

**Q: Bagaimana cara menambah jenis laporan baru?**

1. Tambahkan handler di `services/report_builder.py` (method `_build_namatipe`)
2. Tambahkan pemetaan di `services/rule_engine.py` (`INTENT_MODEL_MAP`)
3. Tambahkan template QWeb di `templates/report_templates.xml`
4. Daftarkan template di `services/pdf_generator.py` (`TEMPLATE_MAP`)

---

## Pemecahan Masalah

### Error: "No active AI Report configuration found"

**Penyebab:** Belum ada konfigurasi aktif.

**Solusi:** Buka **AI Reports → Konfigurasi**, buat konfigurasi baru, dan pastikan field **Active** dicentang.

---

### Error: "Anthropic API key is not configured"

**Penyebab:** API key belum diisi.

**Solusi:** Buka konfigurasi, isi field **API Key**, simpan, lalu klik **Uji Koneksi**.

---

### Error: "openpyxl is required"

**Penyebab:** Library Python belum terinstal.

**Solusi:**
```bash
pip install openpyxl
```

---

### Laporan dikembalikan sebagai "queued" terus-menerus

**Penyebab:** Cron job tidak berjalan.

**Solusi:**
1. Buka **Pengaturan → Teknis → Tindakan Terjadwal**
2. Cari **AI Report: Process Queue**
3. Pastikan statusnya **Aktif**
4. Klik **Jalankan Sekarang** untuk eksekusi manual

---

### PDF tidak bisa dibuka / rusak

**Penyebab:** QWeb gagal merender dan ReportLab tidak terinstal.

**Solusi:**
```bash
pip install reportlab
```

Atau periksa log Odoo untuk error QWeb yang lebih spesifik.

---

### Confidence AI selalu rendah

**Penyebab:** System prompt tidak sesuai dengan model LLM yang digunakan.

**Solusi:** Buka konfigurasi → tab **System Prompt**, sesuaikan instruksi agar lebih eksplisit untuk model yang digunakan. Turunkan nilai **Temperature** ke 0.0 untuk hasil yang lebih konsisten.

---

## Lisensi

LGPL-3 — Lihat file `LICENSE` untuk detail lengkap.

---

## Pengembang

Dikembangkan oleh **Clavis Development**

Versi: `18.0.1.0.0`
