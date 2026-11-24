from html import escape
from pathlib import Path
from urllib.parse import urlsplit

import hmac
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from services.auth_service import (
    AuthConfigurationError,
    SESSION_COOKIE,
    SESSION_LIFETIME_SECONDS,
    create_session_token,
    get_auth_settings,
)

router = APIRouter()
LOGIN_TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "login.html"


def _login_page(next_path: str, error: str = "", status_code: int = 200):
    template = LOGIN_TEMPLATE.read_text(encoding="utf-8")
    content = template.replace("__NEXT_PATH__", escape(next_path, quote=True))
    content = content.replace("__LOGIN_ERROR__", escape(error))
    return HTMLResponse(content=content, status_code=status_code)


def _safe_next_path(value: str):
    parsed = urlsplit(value)
    if (
        value.startswith("/")
        and not value.startswith("//")
        and "\\" not in value
        and not parsed.scheme
        and not parsed.netloc
    ):
        return value
    return "/"


@router.get("/login", response_class=HTMLResponse)
def login_page(next: str = "/"):
    try:
        get_auth_settings()
    except AuthConfigurationError as exc:
        return _login_page("/", str(exc), status_code=503)
    return _login_page(_safe_next_path(next))


@router.post("/auth/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form("/"),
):
    try:
        settings = get_auth_settings()
    except AuthConfigurationError as exc:
        return _login_page("/", str(exc), status_code=503)

    valid_username = hmac.compare_digest(
        username.encode("utf-8"),
        settings.username.encode("utf-8"),
    )
    valid_password = hmac.compare_digest(
        password.encode("utf-8"),
        settings.password.encode("utf-8"),
    )
    if not (valid_username and valid_password):
        return _login_page(_safe_next_path(next), "Invalid username or password.", 401)

    response = RedirectResponse(_safe_next_path(next), status_code=303)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=create_session_token(settings.username, settings.session_secret),
        max_age=SESSION_LIFETIME_SECONDS,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return response


@router.post("/auth/logout")
def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(
        key=SESSION_COOKIE,
        path="/",
        httponly=True,
        samesite="lax",
    )
    return response
