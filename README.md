# 🎓 Aereo — Bulk Certificate Generation Engine

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.x-092E20?style=for-the-badge&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![DRF](https://img.shields.io/badge/DRF-3.14-A30000?style=for-the-badge&logo=django&logoColor=white)](https://www.django-rest-framework.org/)
[![ReportLab](https://img.shields.io/badge/ReportLab-PDF_Engine-FF5733?style=for-the-badge)](https://www.reportlab.com/)
[![Tests](https://img.shields.io/badge/Tests-19%2F19_Passing-brightgreen?style=for-the-badge&logo=pytest&logoColor=white)](https://pytest.org)
[![License](https://img.shields.io/badge/License-MIT-9B59B6?style=for-the-badge)](LICENSE)

**A high-throughput, fault-tolerant backend API for generating authentic vector PDF certificates in bulk — built for the Aereo Backend Assignment.**

[Features](#-key-features) · [Quick Start](#-quick-start-guide) · [API Docs](#-api-documentation--examples) · [Architecture](#-architecture--design-decisions) · [Tests](#-running-automated-tests)

</div>

---

## 📌 What is this?

This is my submission for the **Aereo Backend Engineering Assignment** — a fully functional backend system that accepts bulk certificate generation requests, processes them asynchronously in the background, and exposes clean REST APIs for status polling, certificate download, ZIP bundling, and public QR-code-based verification.

I built this using **Django + Django REST Framework** with **ReportLab** for vector PDF generation. The system is designed to handle hundreds (or thousands) of certificate recipients in a single API call without timing out, without cascading failures, and with full traceability per recipient.

Everything — from the certificate template design to the test suite — was built from scratch.

---

## 🌟 Key Features

### 1. 🚀 High-Throughput Bulk Processing
- Accepts a single `POST` request with **hundreds of recipients** in one shot
- Jobs are dispatched to **daemon background threads** immediately — the API responds in `< 100ms` even for 500+ recipients
- A `?sync=true` query flag is available for synchronous (instant) processing (used in tests and debugging)

### 2. 🛡️ Fault-Tolerant Error Isolation — Zero Cascading Failures
- A single bad record (empty name, bad email, rendering crash) **never aborts the entire batch**
- Each recipient is processed independently inside a `try/except` block
- Jobs resolve to `COMPLETED`, `PARTIALLY_COMPLETED`, or `FAILED` — each recipient gets its own `status` and `error_message`

### 3. 🏅 High-Fidelity Vector Certificate Template
Built entirely with **ReportLab** pure vector primitives:
- Deep navy + metallic gold dual-layer border frame with geometric corner ornaments
- Recipient name rendered in large serif-style gold lettering
- Event name, issuer name, and issuer title — all dynamic
- **QR Code** embedded on every certificate, linking to the live public verification API
- Gold foil rosette seal + digital signature line

### 4. 📥 Multi-Format Input Support
- **JSON API** (`POST /api/jobs/`) — for programmatic bulk job submission
- **Excel `.xlsx` upload** (`POST /api/jobs/upload-file/`) — for uploading real spreadsheets
- **CSV upload** (`POST /api/jobs/upload-file/`) — for raw attendee exports
- Columns automatically recognized: `name`, `recipient_name`, `email`, `recipient_email`, `roll_no`, `roll_number`

### 5. 📦 Multi-Channel Certificate Retrieval
- **Individual PDF** — `GET /api/certificates/<id>/download/`
- **Inline Browser Preview** — Add `?preview=true` to open in browser
- **Batch ZIP Archive** — `GET /api/jobs/<job_id>/download-all/` — downloads every successful certificate in one `.zip`

### 6. 🔐 Tamper-Evident Public Verification
- Every certificate gets a unique **credential code** like `AER-2026-X8K9L2`
- Codes are generated using `uuid4().hex[:8].upper()` — practically unguessable
- Anyone can verify a certificate at `GET /api/verify/<certificate_code>/` — even without logging in

### 7. 🖥️ Interactive Glassmorphic Web Dashboard
- Full UI at `/` — no Postman needed
- Submit jobs, load 100/500 recipient presets, monitor live progress bars
- Preview PDFs inline, download ZIP bundles, and verify certificate codes — all from the browser

---

## 🏗️ Architecture & Design Decisions

### Framework Choice: Django + Django REST Framework

I chose **Django + DRF** over FastAPI or Flask for this project because:
- DRF's `ModelSerializer` + `Serializer` classes give clean input validation and output shaping with almost no boilerplate
- Django's **ORM** handles complex aggregations (progress percentage, status counts) very cleanly
- **Django Admin** gives a free auditing panel — I can inspect every job, every recipient, and every error without writing extra UI
- The browsable API (`/api/jobs/`) is a huge DX win during development

> FastAPI's async would be faster for I/O heavy workloads, but since certificate generation is CPU-bound (PDF rendering), threading is the correct concurrency model here anyway.

---

### Database & Data Model

Using **SQLite** for zero-friction local setup. The schema is fully portable to **PostgreSQL** by changing one line in `settings.py`.

```
CertificateJob (1) ─────────────────── (N) RecipientCertificate
```

```
CertificateJob
├── id                UUID (PK)
├── event_name        string
├── event_date        date
├── issuer_name       string
├── issuer_title      string
├── template_name     string
├── status            PENDING | PROCESSING | COMPLETED | PARTIALLY_COMPLETED | FAILED
├── total_count       int
├── processed_count   int
├── success_count     int
├── failed_count      int
├── created_at        datetime
└── completed_at      datetime (nullable)

RecipientCertificate
├── id                UUID (PK)
├── job               FK -> CertificateJob
├── recipient_name    string
├── recipient_email   string (validated)
├── certificate_code  string (unique, e.g. AER-2026-A3F91C2D)
├── custom_attributes JSON (flexible key-value pairs)
├── status            PENDING | PROCESSING | COMPLETED | FAILED
├── error_message     string (nullable)
├── file              FileField -> media/certificates/
├── file_size_bytes   int
└── created_at        datetime
```

---

### Background Processing Architecture

```
POST /api/jobs/
       |
       v
  [Validate Input] --FAIL--> 400 Bad Request
       |
       v
  [Create CertificateJob + RecipientCertificate rows in DB]
       |
       v
  [Spawn daemon thread]
       |
       v
  202 Accepted (instant)          Background Thread:
  {job_id, status: "PROCESSING"}  For each recipient:
                                    1. validate name/email
                                    2. render vector PDF
                                    3. save to media/
                                    4. mark COMPLETED or FAILED
                                    5. update job counters atomically
```

- `?sync=true` bypasses the thread and runs `process_job_sync()` inline — deterministic, used in all tests.
- The processor is isolated in `certificates/services/processor.py`, making it a 1-line swap to Celery for production.

---

### Certificate PDF Engine (ReportLab)

`certificates/services/generator.py` draws the entire certificate using ReportLab's canvas API:

- **Page size**: A4 Landscape (`841.89 × 595.28` pt)
- **Background**: Dark navy fill (`#0B1D3A`)
- **Borders**: Two concentric gold rectangles + corner diamond ornaments
- **Fonts**: Helvetica family (built-in, no font files needed)
- **QR Code**: Generated via `reportlab.graphics.barcode.qr.QrCodeWidget`, pointing to `/api/verify/<code>/`
- **Seal**: Drawn as a 12-petal golden rosette using `canvas.rotate()` loops

All vector — infinitely scalable, crisp at any print resolution.

---

## 🚀 Quick Start Guide

### Prerequisites
- Python 3.10 or higher
- pip

### 1. Clone the Repository
```bash
git clone https://github.com/tangeti-pranavi-git/Aereo-bulk-certificate-generation.git
cd Aereo-bulk-certificate-generation
```

### 2. (Optional but Recommended) Create a Virtual Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux / macOS
python -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

All dependencies — Django, DRF, ReportLab, Pillow, openpyxl — are pinned in `requirements.txt`.

### 4. Run Database Migrations
```bash
python manage.py migrate
```

This creates the SQLite database with the `CertificateJob` and `RecipientCertificate` tables.

### 5. Start the Development Server
```bash
python manage.py runserver
```

The server starts at **`http://127.0.0.1:8000/`**

| URL | Description |
|-----|-------------|
| `http://127.0.0.1:8000/` | Interactive Web Dashboard |
| `http://127.0.0.1:8000/api/jobs/` | Browsable REST API |
| `http://127.0.0.1:8000/admin/` | Django Admin Panel |

---

## 🧪 Running Automated Tests

The test suite covers **all requirements** from the assignment spec:

| Test File | What It Tests |
|---|---|
| `test_job_creation.py` | Bulk submission, async worker execution, DB record creation |
| `test_validation.py` | Blank event names, empty recipient lists, invalid emails |
| `test_generator.py` | PDF rendering, `%PDF` magic bytes, file size, QR embedding |
| `test_progress_status.py` | Progress percentage polling, recipient-level status breakdown |
| `test_failure_handling.py` | Fault isolation — bad recipients do not crash valid ones |
| `test_downloads.py` | PDF download, ZIP bundle, inline preview, verify endpoint |

### Run with pytest (recommended):
```bash
python -m pytest
```

### Run with Django's native test runner:
```bash
python manage.py test
```

**Result: 19/19 tests passing in ~1.5 seconds**

> All tests use `?sync=true` to bypass background threads — deterministic and CI-friendly.

---

## 📖 API Documentation & Examples

### `POST /api/jobs/` — Submit a Bulk Generation Job

Accepts JSON with event metadata and a list of recipients.

**Query Params:**
- `?sync=true` — Process immediately (blocking). Default is async.

**Request:**
```bash
curl -X POST http://127.0.0.1:8000/api/jobs/ \
  -H "Content-Type: application/json" \
  -d @sample_request.json
```

**Request Body:**
```json
{
  "event_name": "Autonomous Drone Systems Engineering Bootcamp",
  "event_date": "2026-10-15",
  "issuer_name": "Aereo Certification Authority",
  "issuer_title": "Director of Technical Education",
  "recipients": [
    {
      "recipient_name": "Aarav Sharma",
      "recipient_email": "aarav.sharma@example.com",
      "custom_attributes": {
        "grade": "Distinction (98%)",
        "track": "Autonomous Navigation"
      }
    },
    {
      "recipient_name": "Priya Nair",
      "recipient_email": "priya.nair@example.com",
      "custom_attributes": {
        "grade": "Honors (94%)",
        "track": "Remote Sensing"
      }
    },
    {
      "recipient_name": "",
      "recipient_email": "invalid-recipient@example.com"
    }
  ]
}
```

**Response — `202 Accepted`:**
```json
{
  "id": "f11eda9e-8fc7-482b-9618-2c9563ac315c",
  "event_name": "Autonomous Drone Systems Engineering Bootcamp",
  "status": "PROCESSING",
  "progress_percentage": 0,
  "total_count": 3,
  "processed_count": 0,
  "success_count": 0,
  "failed_count": 0
}
```

---

### `POST /api/jobs/upload-file/` — Bulk Upload via Excel or CSV

Upload a `.xlsx` or `.csv` file directly. The system auto-detects name and email columns.

```bash
# Upload Excel spreadsheet
curl -X POST http://127.0.0.1:8000/api/jobs/upload-file/ \
  -F "event_name=Drone Operator Licensing Cohort" \
  -F "event_date=2026-10-15" \
  -F "issuer_name=Aereo Authority" \
  -F "issuer_title=Director" \
  -F "file=@sample_recipients_100.xlsx"

# Upload CSV
curl -X POST http://127.0.0.1:8000/api/jobs/upload-file/ \
  -F "event_name=Drone Operator Licensing Cohort" \
  -F "file=@sample_recipients_100.csv"
```

**Accepted column names in the file:**

| Field | Accepted Column Headers |
|-------|------------------------|
| Name | `name`, `recipient_name`, `student_name` |
| Email | `email`, `recipient_email`, `mail` |
| Roll No | `roll_no`, `roll_number`, `rollno` (stored in `custom_attributes`) |

---

### `GET /api/jobs/<job_id>/` — Poll Job Status

```bash
curl http://127.0.0.1:8000/api/jobs/f11eda9e-8fc7-482b-9618-2c9563ac315c/
```

**Response:**
```json
{
  "id": "f11eda9e-8fc7-482b-9618-2c9563ac315c",
  "status": "PARTIALLY_COMPLETED",
  "progress_percentage": 100,
  "total_count": 3,
  "processed_count": 3,
  "success_count": 2,
  "failed_count": 1,
  "download_all_url": "http://127.0.0.1:8000/api/jobs/f11eda9e-.../download-all/",
  "completed_at": "2026-10-11T10:24:56.128Z",
  "recipients": [
    {
      "recipient_name": "Aarav Sharma",
      "certificate_code": "AER-2026-0FCA9CFF",
      "status": "COMPLETED",
      "download_url": "http://127.0.0.1:8000/api/certificates/e4f8d224.../download/"
    },
    {
      "recipient_name": "Unknown",
      "status": "FAILED",
      "error_message": "recipient_name cannot be blank"
    }
  ]
}
```

---

### `GET /api/certificates/<id>/download/` — Download Individual Certificate

```bash
# Download as file
curl -O -J http://127.0.0.1:8000/api/certificates/<id>/download/

# Open inline in browser
open http://127.0.0.1:8000/api/certificates/<id>/download/?preview=true
```

---

### `GET /api/jobs/<job_id>/download-all/` — Download All as ZIP

```bash
curl -O -J http://127.0.0.1:8000/api/jobs/<job_id>/download-all/
```

Returns a `.zip` file containing all successfully generated certificates. Each file is named `<recipient_name>_<certificate_code>.pdf`.

---

### `GET /api/verify/<certificate_code>/` — Public Verification

```bash
curl http://127.0.0.1:8000/api/verify/AER-2026-0FCA9CFF/
```

**Response:**
```json
{
  "valid": true,
  "certificate_code": "AER-2026-0FCA9CFF",
  "recipient_name": "Aarav Sharma",
  "event_name": "Autonomous Drone Systems Engineering Bootcamp",
  "event_date": "2026-10-15",
  "issuer_name": "Aereo Certification Authority",
  "issued_at": "2026-10-11T10:24:56.092Z",
  "download_url": "http://127.0.0.1:8000/api/certificates/.../download/"
}
```

If the code does not exist:
```json
{ "valid": false, "detail": "Certificate not found." }
```

---

### Generating Bulk Sample Data

```bash
# Generate 100-recipient payload
python generate_mock_data.py --count 100 --out sample_bulk_100.json

# Generate 500-recipient payload
python generate_mock_data.py --count 500 --out sample_bulk_500.json

# Custom 1000-recipient batch
python generate_mock_data.py --count 1000 --out custom_bulk_1000.json

# Submit directly
curl -X POST http://127.0.0.1:8000/api/jobs/ \
  -H "Content-Type: application/json" \
  -d @custom_bulk_1000.json
```

---

## 📁 Project Structure

```
Aereo/
|
|-- core/                          # Django project config
|   |-- settings.py                # Apps, middleware, DRF, CORS, media paths
|   |-- urls.py                    # Root URL routing + static/media serving
|   |-- wsgi.py
|   `-- asgi.py
|
|-- certificates/                  # Core application
|   |-- models.py                  # CertificateJob & RecipientCertificate models
|   |-- serializers.py             # Input validation + output shaping serializers
|   |-- views.py                   # All API views (Job CRUD, download, verify, UI)
|   |-- urls.py                    # API URL patterns
|   |-- admin.py                   # Rich Django admin with progress display
|   |
|   |-- services/
|   |   |-- generator.py           # ReportLab vector PDF engine + QR code
|   |   `-- processor.py           # Resilient background job processor
|   |
|   |-- templates/
|   |   `-- dashboard.html         # Glassmorphic web dashboard (vanilla JS)
|   |
|   |-- static/
|   |   `-- custom.css             # Dashboard styles
|   |
|   `-- tests/
|       |-- test_generator.py      # PDF rendering, magic bytes, QR integrity
|       |-- test_validation.py     # Input validation edge cases
|       |-- test_job_creation.py   # Bulk submission and DB record verification
|       |-- test_progress_status.py# Progress polling and status transitions
|       |-- test_failure_handling.py # Fault isolation and partial success
|       `-- test_downloads.py      # PDF download, ZIP, inline preview, verify
|
|-- media/
|   `-- certificates/              # Generated PDFs stored here (gitignored)
|
|-- sample_request.json            # Minimal example request body
|-- sample_bulk_100.json           # 100-recipient bulk payload for testing
|-- sample_bulk_500.json           # 500-recipient bulk payload for load testing
|-- sample_recipients_100.xlsx     # Excel file with 100 recipients
|-- sample_recipients_100.csv      # CSV version of the same
|-- generate_mock_data.py          # Script to generate bulk JSON test data
|-- requirements.txt               # All Python dependencies
|-- pytest.ini                     # pytest + Django settings configuration
|-- manage.py                      # Django management CLI
`-- README.md                      # You are here
```

---

## ⚙️ Configuration Reference

All configuration lives in `core/settings.py`.

| Setting | Default | Description |
|---------|---------|-------------|
| `DATABASES` | SQLite (`db.sqlite3`) | Swap to PostgreSQL for production |
| `MEDIA_ROOT` | `./media/` | Where generated PDFs are stored |
| `CORS_ALLOW_ALL_ORIGINS` | `True` | Allow all origins (restrict in production) |
| `ALLOWED_HOSTS` | `['*']` | Restrict to your domain in production |
| `REST_FRAMEWORK.PAGE_SIZE` | `20` | Default pagination size for job list |

---

## 💡 Production Scaling Recommendations

### 1. Replace Background Threads with Celery

The existing `process_job_sync()` function in `processor.py` is already isolated and stateless. Adding Celery is literally a 3-line change:

```python
# certificates/services/processor.py
from celery import shared_task

@shared_task
def process_job_task(job_id):
    process_job_sync(job_id)
```

Then replace thread spawning with:
```python
process_job_task.delay(str(job.id))
```

Pair with **Redis** or **RabbitMQ** as the broker.

### 2. Object Storage for Generated PDFs

Swap `FileField` local storage with **Amazon S3** via `django-storages`:
```bash
pip install django-storages[s3] boto3
```

```python
# settings.py
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
```

### 3. PostgreSQL Database

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'aereo_db',
        'USER': 'postgres',
        'PASSWORD': 'your_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

### 4. Email Delivery of Certificates

Extend `RecipientCertificate` with a `sent_at` field and add a post-generation email step using Django's email backend (SMTP / SendGrid / SES).

---

## 🔧 Tech Stack

| Layer | Technology |
|-------|-----------|
| **Web Framework** | Django 5.x |
| **REST API** | Django REST Framework 3.14+ |
| **PDF Generation** | ReportLab 4.x |
| **Image Processing** | Pillow 10.x |
| **Excel Parsing** | openpyxl 3.x |
| **Database** | SQLite (dev) / PostgreSQL (prod) |
| **Cross-Origin** | django-cors-headers |
| **Testing** | pytest + pytest-django + httpx |
| **Background Jobs** | Python threading.Thread (dev) / Celery (prod) |

---

## 👩‍💻 Author

**Tangeti Pranavi**  
Backend Engineering Assignment — Aereo  
GitHub: [@tangeti-pranavi-git](https://github.com/tangeti-pranavi-git)

---

## 📄 License

This project is licensed under the **MIT License**.
