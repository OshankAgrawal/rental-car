from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

import models  # noqa: F401 - register all models before creating tables
from database import Base, engine
from routers.inspections import router as inspections_router
from routers.pages import router as pages_router
from routers.reports import router as reports_router

BASE_DIR = Path(__file__).resolve().parent
for directory_name in ("uploaded_videos", "detected_frames", "detection_json", "reports"):
    (BASE_DIR / directory_name).mkdir(parents=True, exist_ok=True)

Base.metadata.create_all(bind=engine)
with engine.begin() as connection:
    connection.execute(text(
        "ALTER TABLE rentals ADD COLUMN IF NOT EXISTS customer_name VARCHAR(120)"
    ))
    connection.execute(text(
        "ALTER TABLE rentals ADD COLUMN IF NOT EXISTS customer_phone VARCHAR(30)"
    ))
    connection.execute(text(
        "ALTER TABLE rentals ADD COLUMN IF NOT EXISTS damage_charge NUMERIC(12, 2)"
    ))
    connection.execute(text(
        "ALTER TABLE rentals ADD COLUMN IF NOT EXISTS total_charge NUMERIC(12, 2)"
    ))
    connection.execute(text(
        "ALTER TABLE detections ADD COLUMN IF NOT EXISTS damage_charge NUMERIC(12, 2)"
    ))

app = FastAPI(
    title="Rental Car Video Inspection API",
    version="0.1.0",
    description="Video-based pickup and return vehicle damage inspection.",
)

app.mount("/style", StaticFiles(directory=BASE_DIR / "style"), name="style")
app.mount(
    "/detected_frames",
    StaticFiles(directory=BASE_DIR / "detected_frames"),
    name="detected_frames",
)
app.include_router(pages_router)
app.include_router(inspections_router)
app.include_router(reports_router)


@app.get("/health/db")
def database_health():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"database": "connected"}
