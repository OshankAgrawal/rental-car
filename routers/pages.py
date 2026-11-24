from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()
TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"


@router.get("/", response_class=HTMLResponse)
def home_page():
    return HTMLResponse(content=(TEMPLATES_DIR / "index.html").read_text(encoding="utf-8"))


@router.get("/pickup", response_class=HTMLResponse)
def pickup_page():
    return HTMLResponse(content=(TEMPLATES_DIR / "pickup.html").read_text(encoding="utf-8"))


@router.get("/return", response_class=HTMLResponse)
def return_page():
    return HTMLResponse(content=(TEMPLATES_DIR / "return.html").read_text(encoding="utf-8"))
