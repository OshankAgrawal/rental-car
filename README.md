# Rental Car Video Inspection MVP

This project records pickup and return videos, runs YOLO damage detection, and generates a final rental and damage-charge report.

## Tables

- `rentals`: one row per Rental ID, vehicle registration, customer details and final charges.
- `inspections`: one pickup and one return inspection maximum per rental.
- `videos`: one video maximum per inspection.
- `detections`: YOLO detections, frame references, bounding boxes, segmentation polygons and employee-entered damage charges.
- `reports`: one pickup report, one return report and one final comparison report maximum per rental.

Rental duration is **not stored**. It is calculated from the pickup and return `inspection_time` values.

## 1. Create the PostgreSQL database

In pgAdmin, connect to your PostgreSQL server, open the Query Tool while connected to the default `postgres` database, and run:

```sql
CREATE DATABASE rental_car_db;
```

If you already created `rental_car_db`, do not run this again.

## 2. Set up the Python environment (Windows PowerShell)

From this project folder:

```powershell
python -m venv rentalCarenv
.\rentalCarenv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks activation, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\rentalCarenv\Scripts\Activate.ps1
```

## 3. Configure the database connection

Copy `.env.example` to `.env`, then edit `.env` and replace `YOUR_PASSWORD` with your PostgreSQL password.

Do not share or commit your `.env` file.

## 4. Start the API

```powershell
python -m uvicorn main:app --reload
```

Open these addresses in your browser:

- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/health/db`
- `http://127.0.0.1:8000/docs`

The home page links to pickup and return inspections. Completing the return review automatically opens `/reports/{rental_id}` with the final comparison report and inspection frames.

## Inspection workflow

- Open `/pickup` to enter rental and customer details, upload the pickup video, and save its damage frames and detection JSON.
- Open `/return` and enter the Rental ID before uploading the return video.
- Upload progress reports actual transferred bytes; analysis progress tracks sampled video frames, and return review progress tracks damage items charged.
- New or potentially worsened damage is grouped across nearby video frames. The return page displays the related frames one damage item at a time and asks the employee for a charge for each item.
- If no new or worsened damage is found, the final report is generated without asking for damage charges.
- Pickup analysis reports are shown on the pickup page; the return inspection report is shown on the return page after review. The home page also provides report lookup by Rental ID and report type.
- Rental charges are calculated at INR 50 per started hour. The final JSON comparison report is saved under `reports/`; detected frames and inference JSON are saved under `detected_frames/` and `detection_json/`.

The HTTP route handlers live in `routers/`; video and comparison/report logic live in `services/`. `main.py` creates the app, mounts static files and includes the routers.

Run the focused service tests with:

```powershell
python -m unittest test_inspection_service -v
```
