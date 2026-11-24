from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from models import Inspection, Rental, Report
from services.inspection_service import (
    create_pickup_report,
    finalize_return_report,
    serialize_charge_candidates,
    compare_damage,
    save_and_analyze_video,
    validate_video_upload,
)
from services.progress_service import get_progress, set_progress

router = APIRouter(prefix="/api")
BASE_DIR = Path(__file__).resolve().parents[1]
UPLOAD_DIR = BASE_DIR / "uploaded_videos"
DETECTED_FRAMES_DIR = BASE_DIR / "detected_frames"
DETECTION_JSON_DIR = BASE_DIR / "detection_json"
REPORTS_DIR = BASE_DIR / "reports"
ALLOWED_VIDEO_TYPES = {
    "video/mp4",
    "video/quicktime",
    "video/x-msvideo",
    "video/x-matroska",
    "video/webm",
}
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}


class DamageChargeEntry(BaseModel):
    detection_id: int
    amount: Decimal = Field(ge=0)


class DamageChargesRequest(BaseModel):
    charges: list[DamageChargeEntry]


def _validate_video(video: UploadFile):
    try:
        return validate_video_upload(
            video.filename,
            video.content_type,
            ALLOWED_VIDEO_EXTENSIONS,
            ALLOWED_VIDEO_TYPES,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/inspections/{rental_id}/progress")
def inspection_progress(rental_id: str):
    return get_progress(rental_id)


@router.post("/pickup-inspections")
async def create_pickup_inspection(
    rental_id: Annotated[str, Form()],
    vehicle_registration: Annotated[str, Form()],
    customer_name: Annotated[str, Form()],
    customer_phone: Annotated[str, Form()],
    video: Annotated[UploadFile, File()],
    db: Session = Depends(get_db),
):
    rental_id = rental_id.strip()
    vehicle_registration = vehicle_registration.strip()
    customer_name = customer_name.strip()
    customer_phone = customer_phone.strip()
    if not all((rental_id, vehicle_registration, customer_name, customer_phone)):
        raise HTTPException(status_code=422, detail="All rental and customer fields are required")
    if not video.filename:
        raise HTTPException(status_code=422, detail="A pickup video is required")
    _validate_video(video)

    rental = db.scalar(select(Rental).where(Rental.rental_id == rental_id))
    if rental is None:
        rental = Rental(
            rental_id=rental_id,
            vehicle_registration=vehicle_registration,
            customer_name=customer_name,
            customer_phone=customer_phone,
            currency="INR",
        )
        db.add(rental)
        db.flush()
    else:
        rental.vehicle_registration = vehicle_registration
        rental.customer_name = customer_name
        rental.customer_phone = customer_phone

    existing = db.scalar(select(Inspection).where(
        Inspection.rental_id == rental_id,
        Inspection.inspection_type == "pickup",
    ))
    if existing:
        raise HTTPException(status_code=409, detail="A pickup inspection already exists for this rental")

    inspection = Inspection(
        rental_id=rental_id,
        inspection_type="pickup",
        status="pending",
        inspection_time=datetime.now(timezone.utc),
    )
    db.add(inspection)
    set_progress(rental_id, "analyzing", 0, "Video uploaded; preparing analysis")

    def report_frame_progress(processed, total):
        percent = round(processed * 100 / total) if total else 0
        set_progress(
            rental_id,
            "analyzing",
            percent,
            f"Analyzed {processed} of {total} sampled frames",
        )

    try:
        db.flush()
        detections = await save_and_analyze_video(
            db,
            rental,
            inspection,
            video,
            UPLOAD_DIR,
            DETECTED_FRAMES_DIR,
            DETECTION_JSON_DIR,
            report_frame_progress,
        )
        set_progress(rental_id, "finalizing", 0, "Saving pickup inspection report")
        create_pickup_report(
            db,
            rental,
            inspection,
            detections,
            REPORTS_DIR,
            DETECTED_FRAMES_DIR,
        )
        db.commit()
        set_progress(rental_id, "completed", 100, "Pickup inspection report is ready")
    except IntegrityError as exc:
        db.rollback()
        set_progress(rental_id, "failed", 0, "Pickup inspection could not be saved")
        raise HTTPException(status_code=409, detail="A pickup inspection already exists for this rental") from exc
    except Exception:
        db.rollback()
        set_progress(rental_id, "failed", 0, "Pickup inspection analysis failed")
        raise
    finally:
        await video.close()

    return {
        "rental_id": rental_id,
        "inspection_id": inspection.id,
        "inspection_type": "pickup",
        "status": inspection.status,
        "detection_count": len(detections),
        "report_type": "pickup_inspection",
    }


@router.post("/return-inspections")
async def create_return_inspection(
    rental_id: Annotated[str, Form()],
    video: Annotated[UploadFile, File()],
    db: Session = Depends(get_db),
):
    rental_id = rental_id.strip()
    if not rental_id:
        raise HTTPException(status_code=422, detail="Rental ID is required")
    rental = db.scalar(select(Rental).where(Rental.rental_id == rental_id))
    if rental is None:
        raise HTTPException(status_code=404, detail="Rental not found")

    pickup = db.scalar(select(Inspection).where(
        Inspection.rental_id == rental_id,
        Inspection.inspection_type == "pickup",
    ))
    if pickup is None or pickup.status != "completed":
        raise HTTPException(status_code=409, detail="A completed pickup inspection is required")
    existing = db.scalar(select(Inspection).where(
        Inspection.rental_id == rental_id,
        Inspection.inspection_type == "return",
    ))
    if existing:
        raise HTTPException(status_code=409, detail="A return inspection already exists for this rental")
    if not video.filename:
        raise HTTPException(status_code=422, detail="A return video is required")
    _validate_video(video)

    inspection = Inspection(
        rental_id=rental_id,
        inspection_type="return",
        status="pending",
        inspection_time=datetime.now(timezone.utc),
    )
    db.add(inspection)
    set_progress(rental_id, "analyzing", 0, "Video uploaded; preparing analysis")

    def report_frame_progress(processed, total):
        percent = round(processed * 100 / total) if total else 0
        set_progress(
            rental_id,
            "analyzing",
            percent,
            f"Analyzed {processed} of {total} sampled frames",
        )

    try:
        db.flush()
        return_detections = await save_and_analyze_video(
            db,
            rental,
            inspection,
            video,
            UPLOAD_DIR,
            DETECTED_FRAMES_DIR,
            DETECTION_JSON_DIR,
            report_frame_progress,
        )
        db.flush()
        comparison = compare_damage(list(pickup.detections), return_detections)
        candidates = serialize_charge_candidates(
            comparison["charge_candidates"],
            DETECTED_FRAMES_DIR,
        )

        if not candidates:
            _, charges = finalize_return_report(
                db,
                rental,
                pickup,
                inspection,
                {},
                REPORTS_DIR,
                DETECTED_FRAMES_DIR,
            )
            set_progress(rental_id, "completed", 100, "Final comparison report is ready")
            return {
                "rental_id": rental_id,
                "inspection_id": inspection.id,
                "status": "completed",
                "charge_required": False,
                "charge_candidates": [],
                **charges,
            }

        db.commit()
        set_progress(
            rental_id,
            "reviewing",
            0,
            f"Review 0 of {len(candidates)} chargeable damage items",
        )
        return {
            "rental_id": rental_id,
            "inspection_id": inspection.id,
            "status": "awaiting_damage_charges",
            "charge_required": True,
            "charge_candidates": candidates,
        }
    except IntegrityError as exc:
        db.rollback()
        set_progress(rental_id, "failed", 0, "Return inspection could not be saved")
        raise HTTPException(status_code=409, detail="A return inspection already exists for this rental") from exc
    except Exception:
        db.rollback()
        set_progress(rental_id, "failed", 0, "Return inspection analysis failed")
        raise
    finally:
        await video.close()


@router.post("/return-inspections/{inspection_id}/charges")
def submit_damage_charges(
    inspection_id: int,
    payload: DamageChargesRequest,
    db: Session = Depends(get_db),
):
    returned = db.get(Inspection, inspection_id)
    if returned is None or returned.inspection_type != "return":
        raise HTTPException(status_code=404, detail="Return inspection not found")
    if returned.status != "completed":
        raise HTTPException(status_code=409, detail="Return inspection is not ready for charges")
    if db.scalar(select(Report).where(
        Report.rental_id == returned.rental_id,
        Report.report_type == "final_comparison",
    )):
        raise HTTPException(status_code=409, detail="Final report has already been generated")

    pickup = db.scalar(select(Inspection).where(
        Inspection.rental_id == returned.rental_id,
        Inspection.inspection_type == "pickup",
    ))
    if pickup is None:
        raise HTTPException(status_code=409, detail="Pickup inspection was not found")

    comparison = compare_damage(list(pickup.detections), list(returned.detections))
    expected_ids = {item["detection_id"] for item in comparison["charge_candidates"]}
    submitted_ids = [entry.detection_id for entry in payload.charges]
    if len(submitted_ids) != len(set(submitted_ids)) or set(submitted_ids) != expected_ids:
        raise HTTPException(
            status_code=422,
            detail="Submit exactly one charge for each new or worsened damage item",
        )

    charge_by_id = {
        entry.detection_id: entry.amount.quantize(Decimal("0.01"))
        for entry in payload.charges
    }
    try:
        _, charges = finalize_return_report(
            db,
            returned.rental,
            pickup,
            returned,
            charge_by_id,
            REPORTS_DIR,
            DETECTED_FRAMES_DIR,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    set_progress(
        returned.rental_id,
        "completed",
        100,
        "Final comparison report is ready",
    )
    return {
        "rental_id": returned.rental_id,
        "inspection_id": returned.id,
        "status": "completed",
        **charges,
    }
