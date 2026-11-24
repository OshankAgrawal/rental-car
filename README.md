# Rental Car Video Inspection

A FastAPI application for recording vehicle condition at pickup and return. It analyzes uploaded videos with a YOLO damage-detection model, saves frames containing detected damage, and creates inspection and comparison reports.

> **Project status:** MVP for local development. Model detections should be reviewed by an employee and are not a substitute for a physical inspection.

## Features

- Record pickup details and analyze a vehicle video.
- Record a return video and compare its detected damage with the pickup inspection.
- Review frames for newly detected or potentially worsened damage and enter a separate charge for each item.
- Calculate rental charges at **INR 50 per started hour** using the server-recorded pickup and return times.
- View pickup, return, and final comparison reports in the application or through the report API.
- Track upload, video-analysis, and damage-review progress.

## Technology

- Python, FastAPI, and Uvicorn
- PostgreSQL with SQLAlchemy
- Ultralytics YOLO and OpenCV
- HTML, CSS, and JavaScript

## Requirements

- Windows with Python 3.10 or later
- PostgreSQL
- Internet access for the initial download of the model weights

## Setup

### 1. Create a PostgreSQL database

Create a database named `rental_car_db` in pgAdmin or with `psql`:

```sql
CREATE DATABASE rental_car_db;
```

### 2. Create and activate a virtual environment

Run these commands from the project directory in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell prevents environment activation, allow it for the current session and retry:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### 3. Configure the database connection

Create a local `.env` file from the example:

```powershell
Copy-Item .env.example .env
```

Set `DATABASE_URL` in `.env` to match your PostgreSQL username, password, host, port, and database. For example:

```dotenv
DATABASE_URL=postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/rental_car_db
```

Replace `YOUR_PASSWORD` with your local PostgreSQL password. Do not commit or share `.env`; it contains credentials.

### 4. Download the detection model

```powershell
python download_model.py
```

The script downloads `damage_segmentation.pt` into `models/`. The weights are intentionally excluded from Git. The app requires the model file to start.

### 5. Start the application

```powershell
python -m uvicorn main:app --reload
```

Open the application at [http://127.0.0.1:8000](http://127.0.0.1:8000). The API documentation is available at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs), and the database health check is at [http://127.0.0.1:8000/health/db](http://127.0.0.1:8000/health/db).

On startup, the application creates its database tables and applies a small set of additive column updates. Rental duration is calculated from the pickup and return inspection timestamps; it is not stored separately.

## Using the application

1. On the home page, open **Pickup Inspection**.
2. Enter the rental ID, vehicle registration, and customer details; upload a supported video.
3. Review the pickup analysis and its detected frames.
4. Open **Return Inspection**, enter the same rental ID, and upload the return video.
5. If new or potentially worsened damage is detected, review each damage item and enter its charge. No damage charge is requested when there are no chargeable items.
6. Review the return report or open the final comparison report. The home page also provides report lookup by rental ID and report type.

Progress reflects the actual upload, sampled-frame analysis, or damage-review stage. Supported video formats are `.mp4`, `.mov`, `.avi`, `.mkv`, and `.webm`.

## Routes

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/` | Home page and report lookup |
| `GET` | `/pickup` | Pickup inspection page |
| `GET` | `/return` | Return inspection page |
| `POST` | `/api/pickup-inspections` | Create and analyze a pickup inspection |
| `POST` | `/api/return-inspections` | Create and analyze a return inspection |
| `GET` | `/api/inspections/{rental_id}/progress` | Get current inspection progress |
| `POST` | `/api/return-inspections/{inspection_id}/charges` | Submit employee-entered damage charges |
| `GET` | `/reports/{rental_id}?report_type=...` | View a report |
| `GET` | `/api/reports/{rental_id}?report_type=...` | Retrieve report data as JSON |
| `GET` | `/health/db` | Check database connectivity |

Supported `report_type` values are `pickup_inspection`, `return_inspection`, and `final_comparison`. Interactive API documentation is available at `/docs`.

## Reports and local files

The final comparison report includes rental details, pickup and return timestamps, rental duration and charges, damage comparison, inspection frames, and the final damage summary. Rental charges are rounded up to the next started hour at INR 50 per hour; employee-entered damage charges are added to the total.

Uploaded videos, detected frames, inference JSON, and generated reports are stored locally in:

- `uploaded_videos/`
- `detected_frames/`
- `detection_json/`
- `reports/`

Rental and inspection records, detections, and report references are also stored in PostgreSQL. These folders may contain customer information and inspection media; protect and back them up appropriately. Generated files and model weights are excluded from Git.

## Project structure

```text
.
|-- main.py                 # FastAPI app, static files, router registration, DB setup
|-- database.py             # SQLAlchemy engine and session configuration
|-- models.py               # Database models
|-- routers/                # Page, inspection, and report routes
|-- services/               # Video analysis, inspection, report, and progress logic
|-- templates/              # HTML pages
|-- style/                  # CSS and JavaScript assets
|-- models/                 # Locally downloaded model weights
`-- test_inspection_service.py
```

## Tests

Run the focused inspection-service tests from the project directory:

```powershell
python -m unittest test_inspection_service -v
```

## Security

This MVP does not include application authentication. Run it only in a trusted local development environment; do not expose it to the public internet as-is. Keep `.env`, customer details, uploaded videos, generated frames, and reports private.
