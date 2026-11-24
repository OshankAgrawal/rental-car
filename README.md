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

If `.env` does not exist, copy `.env.example` to `.env`; otherwise add the example's authentication settings to your existing `.env` and keep its PostgreSQL `DATABASE_URL`. Replace every example value: use a unique `APP_USERNAME`, a strong `APP_PASSWORD` (at least 14 characters), and a random `APP_SESSION_SECRET` (at least 32 characters). Use `COOKIE_SECURE=false` only for local HTTP development; use `true` behind HTTPS. Do not share or commit your `.env` file.

## 4. Start the API

```powershell
python download_model.py
python -m uvicorn main:app --reload
```

Open these addresses in your browser:

- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/health/db`
- `http://127.0.0.1:8000/docs`

The home page links to pickup and return inspections. Completing the return review automatically opens `/reports/{rental_id}` with the final comparison report and inspection frames.

Users must sign in before accessing the application. GitHub Pages cannot host the FastAPI backend or connect directly to a private local PostgreSQL database; the backend must run on a reachable server or on the PC with a secure internet access path.

For internet use from a home PC without a domain or router port forwarding, Tailscale Funnel is one option. Install and sign in to Tailscale on the PC, enable MagicDNS/HTTPS and Funnel for the device, then:

1. Set `COOKIE_SECURE=true` in the local `.env` and configure the required login credentials and session secret. Never commit `.env`.
2. Start the app locally: `python -m uvicorn main:app --host 127.0.0.1 --port 8000`.
3. In a second PowerShell window, run `tailscale funnel 8000`. Share the resulting HTTPS URL with the friend; share the app login separately and privately.

The PC and both commands must remain running. Funnel makes the URL publicly reachable, so keep app login enabled. Keep PostgreSQL bound to localhost and never expose its port. GitHub Pages cannot host the FastAPI backend. See the [Tailscale Funnel documentation](https://tailscale.com/docs/features/tailscale-funnel) for account and device requirements.

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
