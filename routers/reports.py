import json
from html import escape
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from models import Report

router = APIRouter()
TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
DETECTED_FRAMES_DIR = Path(__file__).resolve().parents[1] / "detected_frames"


REPORT_TYPES = {
    "pickup_inspection",
    "return_inspection",
    "final_comparison",
}


@router.get("/reports")
def report_lookup_redirect(
    rental_id: str = Query(..., min_length=1, max_length=80),
    report_type: str = Query("final_comparison"),
):
    if report_type not in REPORT_TYPES:
        raise HTTPException(status_code=422, detail="Unsupported report type")
    return RedirectResponse(
        f"/reports/{quote(rental_id, safe='')}?report_type={quote(report_type, safe='')}",
        status_code=303,
    )


def _load_report(rental_id: str, report_type: str, db: Session):
    if report_type not in REPORT_TYPES:
        raise HTTPException(status_code=422, detail="Unsupported report type")
    report_record = db.scalar(select(Report).where(
        Report.rental_id == rental_id,
        Report.report_type == report_type,
    ))
    if report_record is None:
        raise HTTPException(status_code=404, detail="Final report not found")

    report_path = Path(report_record.file_path)
    if not report_path.is_file():
        raise HTTPException(status_code=404, detail="Final report file is missing")
    try:
        report_data = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail="Could not read the final report") from exc
    _add_legacy_frame_urls(report_data)
    return report_data


def _add_legacy_frame_urls(value):
    if isinstance(value, dict):
        frame_path = value.get("frame_path")
        if frame_path and "frame_url" not in value:
            try:
                relative_path = Path(frame_path).resolve().relative_to(
                    DETECTED_FRAMES_DIR.resolve()
                )
            except ValueError:
                pass
            else:
                value["frame_url"] = "/detected_frames/" + relative_path.as_posix()
                value.setdefault("frame_urls", [value["frame_url"]])
        for nested_value in value.values():
            _add_legacy_frame_urls(nested_value)
    elif isinstance(value, list):
        for item in value:
            _add_legacy_frame_urls(item)


@router.get("/reports/{rental_id}", response_class=HTMLResponse)
def report_page(
    rental_id: str,
    report_type: str = Query("final_comparison"),
    db: Session = Depends(get_db),
):
    _load_report(rental_id, report_type, db)
    template = (TEMPLATES_DIR / "report.html").read_text(encoding="utf-8")
    return HTMLResponse(
        content=template.replace("__RENTAL_ID__", escape(rental_id, quote=True)).replace(
            "__REPORT_TYPE__",
            escape(report_type, quote=True),
        )
    )


@router.get("/api/reports/{rental_id}")
def get_report(
    rental_id: str,
    report_type: str = Query("final_comparison"),
    db: Session = Depends(get_db),
):
    return JSONResponse(content=_load_report(rental_id, report_type, db))
