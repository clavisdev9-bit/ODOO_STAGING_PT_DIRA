# HR-Attendance Middleware

**Modul Odoo 18** — Middleware profesional penghubung mesin absensi biometrik dengan sistem HR Odoo 18.

---

## Daftar Isi

1. [Gambaran Umum](#gambaran-umum)
2. [Fitur](#fitur)
3. [Persyaratan](#persyaratan)
4. [Instalasi](#instalasi)
5. [Konfigurasi](#konfigurasi)
6. [Cara Pakai: Mode Push (HTTP API)](#mode-push-http-api)
7. [Cara Pakai: Mode Pull (ZKTeco)](#mode-pull-zkteco)
8. [REST API Reference](#rest-api-reference)
9. [Struktur Modul](#struktur-modul)
10. [Rekomendasi Arsitektur](#rekomendasi-arsitektur)
11. [Troubleshooting](#troubleshooting)

---

## Gambaran Umum

`HR-Attendance` adalah modul middleware yang bertindak sebagai **jembatan** antara mesin absensi fisik
(fingerprint, RFID, face recognition, ZKTeco) dan modul `hr.attendance` di Odoo 18.

```
[Mesin Absensi]  ──Push──►  [/api/attendance/push]  ──►  [hr.attendance]
                                       │
[Mesin ZKTeco]  ◄──Pull──  [Cron / Manual Sync]    ──►  [hr.attendance]
```

---

## Fitur

| Fitur | Keterangan |
|---|---|
| **Multi-Device** | Kelola banyak mesin absensi sekaligus dari satu dashboard |
| **Push Mode** | Mesin mengirim data via HTTP POST ke endpoint Odoo |
| **Pull Mode** | Odoo mengambil data dari mesin ZKTeco via jaringan TCP |
| **REST API** | Endpoint `/api/attendance/push` dengan autentikasi API Key per device |
| **Raw Log** | Semua data mentah dari mesin tersimpan sebelum diproses |
| **Sync History** | Riwayat lengkap setiap sesi sinkronisasi beserta statistik |
| **Cron Auto-Sync** | Sinkronisasi otomatis terjadwal (Pull mode) |
| **Manual Sync** | Wizard untuk trigger sync manual kapan saja |
| **Timezone per Device** | Setiap mesin bisa dikonfigurasi timezone-nya sendiri |
| **Notifikasi Error** | Kirim notifikasi ke user tertentu jika sync gagal |
| **Deduplikasi** | Cegah duplikat record absensi secara otomatis |

---

## Persyaratan

- Odoo 18 Community / Enterprise
- Python 3.10+
- Module `hr_attendance` (sudah terinstall bawaan Odoo)

**Untuk mode Pull (ZKTeco):**
```bash
pip install pyzk
```

---

## Instalasi

1. Salin folder `hr_attendance_middleware` ke direktori addons Odoo Anda:
   ```
   /path/to/odoo/addons/hr_attendance_middleware/
   ```

2. Restart server Odoo:
   ```bash
   ./odoo-bin --config=odoo.conf -u hr_attendance_middleware
   ```

3. Di Odoo: **Settings → Apps → Update App List** → Cari `HR-Attendance` → Install.

---

## Konfigurasi

Buka: **Attendances → HR-Attendance → Konfigurasi** (atau via Settings → Attendance).

| Parameter | Default | Keterangan |
|---|---|---|
| **Aktifkan REST API** | ✓ | Nyalakan/matikan endpoint Push API |
| **Global API Key** | kosong | Fallback key jika device tidak punya API Key sendiri |
| **Timezone Default** | Asia/Jakarta | Timezone default untuk mesin yang tidak dikonfigurasi |
| **Interval Auto-Sync** | 60 menit | Frekuensi cron Pull Mode |
| **Retensi Log Raw** | 90 hari | Log otomatis dihapus setelah N hari |

---

## Mode Push (HTTP API)

### Langkah 1: Daftarkan Device

1. Buka **Attendances → HR-Attendance → Mesin Absensi → Buat Baru**
2. Isi:
   - **Nama**: `Mesin Lobby Lantai 1`
   - **Kode**: `DEVICE-001` ← ini yang digunakan di header API
   - **Tipe Mesin**: Pilih sesuai hardware
   - **Protokol Sync**: `Push (Mesin → Odoo)`
   - **Timezone**: `Asia/Jakarta`
3. Klik **Aktifkan**
4. Catat **API Key** yang tergenerate otomatis di tab "API Key"

### Langkah 2: Konfigurasi Mesin

Di sisi mesin absensi (atau middleware hardware), atur agar mesin mengirim data ke:

```
URL    : http://[DOMAIN_ODOO]/api/attendance/push
Method : POST
Headers:
  Content-Type : application/json
  X-Device-Code: DEVICE-001
  X-Api-Key    : [api_key yang dicatat di langkah 1]
```

### Langkah 3: Format Payload JSON

```json
{
  "attendances": [
    {
      "uid": "101",
      "timestamp": "2025-01-15 08:03:22"
    },
    {
      "uid": "102",
      "timestamp": "2025-01-15 08:10:45"
    },
    {
      "uid": "101",
      "timestamp": "2025-01-15 17:30:00"
    }
  ]
}
```

> **Catatan:** `uid` harus sama dengan nilai field **Barcode** di profil karyawan Odoo (`hr.employee.barcode`).
> `timestamp` dalam format `YYYY-MM-DD HH:MM:SS` sesuai timezone device.

### Contoh dengan `curl`

```bash
curl -X POST "http://localhost:8069/api/attendance/push" \
  -H "Content-Type: application/json" \
  -H "X-Device-Code: DEVICE-001" \
  -H "X-Api-Key: your_api_key_here" \
  -d '{
    "attendances": [
      {"uid": "101", "timestamp": "2025-01-15 08:00:00"},
      {"uid": "101", "timestamp": "2025-01-15 17:00:00"}
    ]
  }'
```

### Contoh dengan Python

```python
import requests

url = "http://localhost:8069/api/attendance/push"
headers = {
    "Content-Type": "application/json",
    "X-Device-Code": "DEVICE-001",
    "X-Api-Key": "your_api_key_here",
}
payload = {
    "attendances": [
        {"uid": "101", "timestamp": "2025-01-15 08:00:00"},
        {"uid": "102", "timestamp": "2025-01-15 08:05:30"},
        {"uid": "101", "timestamp": "2025-01-15 17:00:00"},
    ]
}

response = requests.post(url, json=payload, headers=headers)
print(response.json())
# {
#   "status": "success",
#   "sync_id": 42,
#   "summary": "Total: 3 | Diproses: 2 | Dilewati: 0 | Error: 0"
# }
```

---

## Mode Pull (ZKTeco)

### Persyaratan Tambahan

```bash
pip install pyzk
```

### Langkah 1: Daftarkan Device

1. Buka **Attendances → HR-Attendance → Mesin Absensi → Buat Baru**
2. Isi:
   - **Protokol Sync**: `Pull (Odoo → Mesin)`
   - **Alamat IP**: `192.168.1.100` (IP mesin ZKTeco di jaringan lokal)
   - **Port**: `4370` (default ZKTeco)
   - **Password**: `0` (kosong = 0)
   - **Timezone**: sesuaikan dengan timezone mesin
3. Klik **Test Koneksi** untuk memverifikasi

### Langkah 2: Test Koneksi

Klik tombol **"Test Koneksi"** dari form device. Jika berhasil, status berubah ke **Aktif**.

### Langkah 3: Sync Manual

Klik **"Sync Sekarang"** → wizard terbuka → pilih rentang tanggal → **Mulai Sync**.

### Langkah 4: Auto-Sync (Cron)

Cron `HR-Attendance: Auto-Sync Mesin` sudah aktif secara default (interval 1 jam).
Untuk mengubah interval: **Settings → Technical → Automation → Scheduled Actions**.

---

## REST API Reference

### POST `/api/attendance/push`

Terima data absensi dari mesin dalam format JSON.

**Headers:**
| Header | Wajib | Keterangan |
|---|---|---|
| `Content-Type` | ✓ | `application/json` |
| `X-Device-Code` | ✓ | Kode device yang terdaftar di Odoo |
| `X-Api-Key` | ✓ | API Key device atau Global API Key |

**Request Body:**
```json
{
  "attendances": [
    {"uid": "string", "timestamp": "YYYY-MM-DD HH:MM:SS"}
  ]
}
```

**Response Berhasil (200):**
```json
{
  "status": "success",
  "sync_id": 42,
  "summary": "Total: 5 | Diproses: 5 | Dilewati: 0 | Error: 0"
}
```

**Response Error:**
```json
{"status": "error", "code": 401, "message": "API key tidak valid."}
```

---

### GET `/api/attendance/status`

Cek status dan statistik device.

**Headers:** `X-Device-Code`, `X-Api-Key`

**Response:**
```json
{
  "status": "ok",
  "device": {
    "name": "Mesin Lobby",
    "code": "DEVICE-001",
    "state": "active",
    "protocol": "push",
    "timezone": "Asia/Jakarta",
    "last_sync": "2025-01-15 08:00:00",
    "last_sync_status": "success",
    "total_records_synced": 1250
  }
}
```

---

### GET `/api/attendance/ping`

Health check tanpa autentikasi.

**Response:**
```json
{
  "status": "ok",
  "service": "HR-Attendance Middleware",
  "version": "18.0.1.0.0"
}
```

---

## Struktur Modul

```
hr_attendance_middleware/
├── __manifest__.py               # Metadata modul
├── __init__.py
├── controllers/
│   └── main.py                   # REST API endpoints (/api/attendance/*)
├── models/
│   ├── attendance_device.py      # Model utama: manajemen mesin
│   ├── attendance_raw_log.py     # Log mentah dari mesin
│   ├── attendance_sync_history.py# Riwayat setiap sesi sync
│   └── res_config_settings.py   # Pengaturan global
├── wizard/
│   ├── sync_attendance_wizard.py # Wizard sync manual
│   └── sync_attendance_wizard_views.xml
├── views/
│   ├── attendance_device_views.xml
│   ├── attendance_raw_log_views.xml
│   ├── attendance_sync_history_views.xml
│   ├── res_config_settings_views.xml
│   └── menus.xml
├── security/
│   ├── security.xml              # Security groups
│   └── ir.model.access.csv      # ACL
├── data/
│   └── cron_data.xml             # Scheduled actions
└── README.md
```

---

## Rekomendasi Arsitektur

### Untuk Jaringan On-Premise (LAN)

```
[ZKTeco] ──TCP:4370──► [Odoo Server] ──Pull via pyzk──► [hr.attendance]
```

- Gunakan **Mode Pull** jika Odoo bisa mengakses IP mesin ZKTeco langsung.
- Set cron interval sesuai kebutuhan (default 60 menit).

### Untuk Mesin di Cabang / Cloud

```
[Mesin Cabang] ──HTTPS POST──► [Odoo Cloud] ──► [hr.attendance]
```

- Gunakan **Mode Push** + REST API.
- Pasang skrip middleware kecil di sisi cabang yang membaca log mesin lalu mengirim ke API.
- Gunakan HTTPS untuk keamanan.

### Multi-Site

```
[Mesin Cabang A: DEVICE-101] ──Push──►
[Mesin Cabang B: DEVICE-201] ──Push──►  [Odoo] → [hr.attendance]
[Mesin Pusat:    DEVICE-001] ──Pull──►
```

Setiap device punya kode dan API Key unik. Timezone bisa berbeda per device.

---

## Troubleshooting

### Error: "Library pyzk belum terinstall"
```bash
pip install pyzk
# atau
pip3 install pyzk
```
Restart Odoo setelah install.

### Error: "Device tidak ditemukan atau tidak aktif"
- Pastikan `X-Device-Code` di header sama persis dengan field **Kode** di form device.
- Pastikan status device adalah **Aktif** (bukan Draft/Error/Nonaktif).

### Error: "API key tidak valid"
- Cek API Key di tab "API Key (Push Mode)" di form device.
- Atau tambahkan **Global API Key** di Settings.

### Karyawan tidak ditemukan
- Pastikan field **Barcode** di profil karyawan Odoo (`Employees → [Karyawan] → Settings → Badge ID / Barcode`) sudah diisi.
- Nilai `uid` di payload harus sama persis dengan nilai Barcode karyawan.

### Koneksi ZKTeco gagal
- Pastikan IP dan Port benar.
- Pastikan firewall mengizinkan koneksi TCP ke port 4370.
- Coba `ping [IP_MESIN]` dari server Odoo.
- Pastikan mesin ZKTeco dalam mode "Server Mode" atau "Push Mode" dimatikan.

### Data absensi duplikat
- Aktifkan opsi **"Abaikan Duplikat"** di tab "Opsi Lanjutan" device.

---

## Lisensi

LGPL-3 — © 2025 Clavis Development
