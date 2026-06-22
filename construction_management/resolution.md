# Bug Resolution Log — construction_management

---

## [2026-05-12] BUG-001: ValueError: Invalid field 'purchase_deadline' on model 'purchase.order'

### Deskripsi Bug
Ketika user menekan tombol **"Create PO"** pada form `construction.material.req` (MPR) dengan status `approved`, terjadi error server:

```
ValueError: Invalid field 'purchase_deadline' on model 'purchase.order'
```

Error muncul di UI sebagai `RPC_ERROR / Odoo Server Error`.

### Lokasi
- **File:** `models/construction_material_req.py`
- **Method:** `_make_purchase_order()` — baris 103 (sebelum fix)
- **Model:** `construction.material.req`
- **Terjadi pada:** localhost:8099 — PT Dira Staging, 2026-05-12 14:06:28 GMT

### Root Cause
Developer menggunakan field `purchase_deadline` saat membuat record `purchase.order`:

```python
# SALAH — field ini tidak ada di Odoo 18
po = self.env['purchase.order'].create({
    ...
    'purchase_deadline': self.date_required,
    ...
})
```

Field `purchase_deadline` **tidak pernah ada** di model `purchase.order` Odoo 18. Field ini kemungkinan disalin/terinspirasi dari dokumentasi atau kode versi lama (Odoo 16 ke bawah), atau merupakan kesalahan penulisan nama field.

Di Odoo 18, field tanggal relevan pada `purchase.order` adalah:
| Field | Label | Tipe | Keterangan |
|---|---|---|---|
| `date_order` | Order Deadline | Datetime | Batas waktu konfirmasi quotation |
| `date_approve` | Confirmation Date | Datetime | Diisi otomatis saat approve |

Tanggal pengiriman yang diinginkan (`date_required`) sudah dengan benar diset pada setiap **order line** melalui field `date_planned` di baris 94 — sehingga field `purchase_deadline` di level header memang tidak diperlukan.

### Kenapa Bisa Terjadi
1. Odoo mengubah/menghapus beberapa field PO antara versi lama dan v18.
2. Tidak ada validasi compile-time untuk nama field string dalam `dict` yang di-pass ke `create()` — error baru muncul saat runtime.
3. Tidak ada test otomatis untuk flow `action_create_po` yang akan mendeteksi ini lebih awal.

### Resolusi
Hapus baris `'purchase_deadline': self.date_required,` dari dict `create()` pada method `_make_purchase_order()`.

**Sebelum:**
```python
po = self.env['purchase.order'].create({
    'partner_id': vendor.id if vendor and vendor.id else self.env.ref('base.res_partner_1').id,
    'date_order': fields.Datetime.now(),
    'purchase_deadline': self.date_required,   # <-- DIHAPUS
    'order_line': po_line_vals,
    ...
})
```

**Sesudah:**
```python
po = self.env['purchase.order'].create({
    'partner_id': vendor.id if vendor and vendor.id else self.env.ref('base.res_partner_1').id,
    'date_order': fields.Datetime.now(),
    'order_line': po_line_vals,
    ...
})
```

Tanggal `date_required` dari MPR tetap digunakan sebagai `date_planned` di setiap order line, yang merupakan tempat yang benar untuk menyimpan tanggal kebutuhan pengiriman per item.

### Pencegahan
- Setiap field yang di-pass ke `create()` atau `write()` harus diverifikasi terhadap definisi model Odoo target.
- Saat upgrade versi Odoo, cari semua pemanggilan `create()`/`write()` yang menyentuh model standar dan validasi nama field-nya.
- Tambahkan test `action_create_po` yang memverifikasi PO berhasil dibuat dari MPR yang sudah approved.

---

## [2026-05-12] BUG-002: Pylance Warning — Potential NoneType access pada `po.id` dan `vendor.id`

### Deskripsi Bug
Dua Pylance static analysis warning (`reportOptionalMemberAccess`) terdeteksi setelah fix BUG-001:

- **Line 65:** `rec.purchase_order_ids = [(4, po.id)]` — `po` bisa `None`
- **Line 101:** `vendor.id if vendor and vendor.id else ...` — ekspresi redundan, `vendor.id` bisa dianggap `None` oleh type checker

### Root Cause

**Warning 1 (line 65):**
`_make_purchase_order()` menginisialisasi `po = None` dan mengisinya dalam loop `for vendor, lines in vendor_lines.items()`. Jika karena suatu sebab loop tidak pernah berjalan, method mengembalikan `None`. Pemanggil di `action_create_po()` langsung akses `po.id` tanpa memeriksa nilainya — ini adalah bug laten yang bisa menyebabkan `AttributeError: 'NoneType' object has no attribute 'id'`.

**Warning 2 (line 101):**
`vendor` adalah Odoo recordset (`res.partner`). Saat kosong (empty recordset), `bool(vendor)` bernilai `False` dan `vendor.id` bernilai `False` (bukan integer). Kondisi `vendor and vendor.id` adalah double-check yang membingungkan — `vendor` tidak pernah `None`, hanya bisa empty recordset. Pylance menandai `vendor.id` sebagai potentially `None` karena melihat kondisi `if vendor` sebelumnya.

### Resolusi

**Fix 1 — guard `po` sebelum digunakan:**
```python
# Sebelum
po = rec._make_purchase_order()
rec.purchase_order_ids = [(4, po.id)]

# Sesudah
po = rec._make_purchase_order()
if not po:
    raise UserError(_('No purchase order could be created. Please check the material lines.'))
rec.purchase_order_ids = [(4, po.id)]
```
Menghasilkan pesan error yang jelas bagi user, bukan `AttributeError` mentah.

**Fix 2 — hapus fallback `env.ref()`, validasi vendor eksplisit:**

`self.env.ref('base.res_partner_1').id` di-flag Pylance karena `env.ref()` dianggap berpotensi `None`. Selain itu, fallback ke partner default tidak masuk akal secara bisnis — PO tanpa vendor yang jelas seharusnya ditolak.

```python
# Sebelum
if not vendor_lines:
    vendor_lines[self.env['res.partner']] = list(self.line_ids)  # empty recordset sebagai key
...
'partner_id': vendor.id or self.env.ref('base.res_partner_1').id,

# Sesudah
if not vendor_lines:
    raise UserError(_('No material lines with quantity to order.'))
...
if not vendor.id:
    raise UserError(_('All material lines must have a vendor set before creating a PO.'))
...
'partner_id': vendor.id,
```

User kini mendapat pesan error yang actionable, dan `partner_id` selalu berisi integer valid.

### Pencegahan
- Setiap return value dari method internal yang bisa `None` harus di-guard sebelum di-akses atributnya.
- Hindari `env.ref().id` langsung — simpan ke variabel dan cek dulu, atau lebih baik raise `UserError` jika data wajib tidak ada.
- Fallback ke data default yang tidak relevan secara bisnis (misal `res_partner_1`) menyembunyikan data entry error. Lebih baik validasi eksplisit.

---

## [2026-05-12] BUG-003: Invalid fields: "Contract" pada model `construction.job.costing`

### Deskripsi Bug
Ketika mengakses menu **Job Costing** secara langsung, atau saat ada operasi quick-create pada model `construction.job.costing`, muncul error:

```
Invalid fields: "Contract"
```

Disertai kondisi: tidak ada form input untuk field `Contract` pada halaman form.

### Lokasi
- **File model:** `models/construction_job_costing.py`
- **File view:** `views/construction_job_costing_views.xml`
- **File kontrak:** `models/construction_job_contract.py` — method `action_view_job_costing()`
- **Model:** `construction.job.costing`

### Root Cause (3 lapisan)

**1. `_rec_name = 'contract_id'` — Many2one sebagai record name (penyebab utama)**

Odoo menggunakan `_rec_name` untuk operasi `name_create()`. Ketika ada quick-create (dari widget Many2one lain yang menunjuk ke model ini, atau dari list view), Odoo memanggil:
```python
# Default Odoo name_create
def name_create(self, name):
    return self.create({self._rec_name: name}).name_get()[0]
# menghasilkan: self.create({'contract_id': 'teks input user'})
```
Many2one field `contract_id` tidak bisa menerima string — hanya menerima integer (record ID). Odoo melempar error yang oleh web layer diterjemahkan menjadi **"Invalid fields: Contract"** (menggunakan `string` label field, bukan nama teknis).

**2. Form view: `contract_id` selalu `readonly="1"`**

```xml
<!-- Sebelum fix — readonly di semua kondisi, termasuk saat create -->
<h1><field name="contract_id" readonly="1"/></h1>
```
Ketika user membuka form dalam mode create (via menu → New), field `contract_id` yang `required=True` tidak bisa diisi karena readonly. Record tidak bisa disimpan.

**3. Penulisan ke `related` field dalam `create()`**

Di `action_view_job_costing()`:
```python
costing = self.env['construction.job.costing'].create({
    'contract_id': self.id,
    'analytic_account_id': self.analytic_account_id.id,  # ← SALAH
})
```
`analytic_account_id` adalah `related='contract_id.analytic_account_id'` — di Odoo 18, `related` fields bersifat readonly by default. Menulis nilai ke dalamnya via `create()` menyebabkan error "Invalid fields: Analytic Account". Nilai ini tidak perlu di-pass karena otomatis terisi saat `contract_id` di-set.

### Kenapa Bisa Terjadi
1. Developer memakai Many2one sebagai `_rec_name` untuk menggunakan display name contract — valid untuk `name_get`, tapi tidak untuk `name_create`.
2. Form didesain hanya sebagai "view only" (buka dari smart button kontrak), namun tidak ada proteksi yang mencegah user membuka mode create dari menu.
3. `related` field di-pass ke `create()` seperti field biasa — tidak ada validasi statik yang mendeteksi ini.

### Resolusi

**Fix 1 — Ganti `_rec_name`, tambah computed `name`, override `name_create`:**
```python
# Hapus: _rec_name = 'contract_id'

name = fields.Char(
    string='Reference', compute='_compute_name', store=True,
)

@api.depends('contract_id', 'contract_id.project_name')
def _compute_name(self):
    for rec in self:
        rec.name = rec.contract_id.project_name or rec.contract_id.name or '/'

@api.model
def name_create(self, name):
    raise UserError(_('Job Costing records can only be created from a Job Contract.'))
```

**Fix 2 — `contract_id` editable hanya saat create:**
```xml
<!-- Sebelum -->
<h1><field name="contract_id" readonly="1"/></h1>

<!-- Sesudah: readonly="id" → False (editable) saat record baru, True saat sudah tersimpan -->
<h1><field name="contract_id" readonly="id"/></h1>
```

**Fix 3 — Tambah `create="false"` pada list view:**
```xml
<list string="Job Costing" create="false">
```
Mencegah user membuat record dari menu Job Costing secara langsung.

**Fix 4 — Hapus `analytic_account_id` dari `create()` di `action_view_job_costing`:**
```python
# Sebelum
costing = self.env['construction.job.costing'].create({
    'contract_id': self.id,
    'analytic_account_id': self.analytic_account_id.id,  # dihapus
})

# Sesudah
costing = self.env['construction.job.costing'].create({
    'contract_id': self.id,
})
```

### Pencegahan
- Jangan gunakan Many2one sebagai `_rec_name` tanpa meng-override `name_create` dan `name_search`.
- `related` fields (terutama yang `store=True`) tidak boleh di-pass ke `create()`/`write()` — nilainya diisi otomatis oleh ORM.
- Model yang hanya boleh dibuat melalui satu entry point harus menggunakan `create="false"` di list view dan override `name_create` dengan `UserError`.

---

## [2026-05-13] CR-001: Migrasi `construction.budget` → `budget.analytic` (account_budget)

### Deskripsi
Model custom `construction.budget` diganti dengan model standar Odoo `budget.analytic` dari modul `account_budget`. Error yang muncul sebelum migrasi selesai:

```
KeyError: 'construction.budget'
404: Not Found
```

### Root Cause (4 tempat yang perlu difix)

**1. `_create_budget()` di `construction_job_contract.py`**
Memanggil `create({'analytic_account_id': ...})` padahal `budget.analytic` tidak punya field `analytic_account_id`. Field required `date_from` dan `date_to` juga tidak di-pass.

**2. `_compute_budget()` di `construction_job_costing.py`**
Mengakses `budget.line_ids`, `line.cost_type`, dan `line.amount_planned` — semua field yang hanya ada di model lama `construction.budget.line`. Di `budget.analytic`, relasi ke lines adalah `budget_line_ids` dengan field `budget_amount`.

**3. `construction_budget_views.xml`**
View masih memakai field-field yang tidak ada di `budget.analytic`:
- `analytic_account_id` — tidak ada di `budget.analytic`
- `total_planned` — tidak ada
- `line_ids` → harusnya `budget_line_ids`
- `cost_type`, `amount_planned`, `amount_committed`, `amount_actual`, `variance`, `progress_pct` — field dari model lama

**4. `ir.model.access.csv`**
Entry lama untuk `construction.budget` dan `construction.budget.line` perlu dihapus (sudah dilakukan sebelumnya).

### Resolusi

| File | Perubahan |
|---|---|
| `models/construction_job_contract.py` | `_create_budget()`: hapus `analytic_account_id`, tambah `date_from`, `date_to`, `budget_type`, `company_id` |
| `models/construction_job_costing.py` | `_compute_budget()`: ganti `line_ids.cost_type/amount_planned` → `budget_line_ids.budget_amount` |
| `views/construction_budget_views.xml` | Hapus form custom berisi field non-existent, ganti dengan inherit form standar `account_budget`; list & search view diupdate ke field yang valid |
| `__manifest__.py` | `account_budget` sudah ada di depends ✓ |

### Perbedaan `construction.budget` vs `budget.analytic`

| Aspek | construction.budget (lama) | budget.analytic (standar) |
|---|---|---|
| Lines relation | `line_ids` | `budget_line_ids` |
| Line amount | `amount_planned` | `budget_amount` |
| Line category | `cost_type` (material/labor/etc) | analytic plan columns (dynamic) |
| Required fields | name, contract_id | name, date_from, date_to |
| Workflow state | tidak ada | draft → confirmed → done |

### Pencegahan
- Sebelum membuat model custom, cek apakah Odoo sudah menyediakan model standar yang bisa di-extend via `_inherit`.
- Saat migrasi ke model standar, baca field definitions model target dulu sebelum menyesuaikan `create()` dan compute methods.

---

## [2026-05-14] BUG-004: `boq_line_id` pada `construction.work.order` masih lookup dari `construction.boq.line`

### Deskripsi Bug
Field `boq_line_id` pada model `construction.work.order` (form Work Order) masih menampilkan dan men-search data dari model `construction.boq.line` menggunakan field `code`, padahal comodel sudah diubah ke `cop.line`.

### Root Cause (2 penyebab)

**1. `_rec_name = 'cop_name'` pada `cop.line`**

Setelah comodel `boq_line_id` diubah dari `construction.boq.line` ke `cop.line`, Odoo menggunakan `_name_search` milik `cop.line` untuk mengisi dropdown. Default `_name_search` Odoo mencari berdasarkan `_rec_name`. Karena `cop.line` mendefinisikan `_rec_name = 'cop_name'`, pencarian dilakukan ke field `cop_name`, bukan `code`. User yang mengetik kode COP tidak mendapat hasil yang diharapkan.

**2. Client-side field definition cache (browser)**

Odoo JS client men-cache hasil `fields_get()` per session. Setelah comodel diubah tanpa menjalankan `-u` (module update), browser masih mengirim request `name_search` ke model lama (`construction.boq.line`) karena cache menyimpan `relation: 'construction.boq.line'`. Module update (`-u construction_management`) memperbarui `ir.model.fields` di DB dan me-bust cache server-side, memaksa browser fetch ulang definisi field saat halaman di-reload.

### Files Changed

| File | Perubahan |
|------|-----------|
| `models/cop_line.py` | `_rec_name`: `'cop_name'` → `'code'`; ditambah `_compute_display_name` |
| `models/construction_work_order.py` | `boq_line_id` comodel: `'construction.boq.line'` → `'cop.line'`; string: `'BOQ Item'` → `'COP Item'` |

### Resolusi

**`models/cop_line.py`:**
```python
# Sebelum
_rec_name = 'cop_name'

# Sesudah
_rec_name = 'code'  # search di dropdown menggunakan field code

def _compute_display_name(self):
    for rec in self:
        rec.display_name = '[%s] %s' % (rec.code, rec.cop_name) if rec.code else rec.cop_name
```
`_rec_name = 'code'` membuat default `_name_search` mencari berdasarkan `code`. `_compute_display_name` memastikan dropdown menampilkan label yang informatif: `[COP-001] Pekerjaan Tata Gedung`.

**DB Migration (sebelum `-u`):**
```sql
UPDATE construction_work_order SET boq_line_id = NULL WHERE boq_line_id IS NOT NULL;
ALTER TABLE construction_work_order DROP CONSTRAINT construction_work_order_boq_line_id_fkey;
```
Diperlukan karena existing integer IDs merujuk ke `construction.boq.line`, bukan `cop.line`.

### Perilaku Setelah Fix
- Dropdown `boq_line_id` pada Work Order menampilkan records dari `cop.line`
- Autocomplete mencari berdasarkan field `code` dari `cop.line`
- Display setiap record: `[code] cop_name` (contoh: `[COP-001] Pekerjaan Tata Gedung`)
- Domain filter tetap `[('contract_id', '=', contract_id)]`

### Pencegahan
- Saat mengganti comodel Many2one, selalu cek `_rec_name` dan `_name_search` pada model target.
- Setelah mengubah comodel, wajib jalankan `-u <module>` dan reload browser (Ctrl+Shift+R).
- Existing FK data ke model lama harus di-NULL-kan sebelum update jika target tabel berubah.

---
