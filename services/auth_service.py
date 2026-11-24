import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

SESSION_COOKIE = "rental_session"
SESSION_LIFETIME_SECONDS = 8 * 60 * 60
EXAMPLE_PASSWORD = "change-this-to-a-long-unique-password"
EXAMPLE_SESSION_SECRET = "replace-with-a-random-secret-at-least-32-characters"


class AuthConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class AuthSettings:
    username: str
    password: str
    session_secret: str
    cookie_secure: bool


def get_auth_settings():
    username = os.getenv("APP_USERNAME", "")
    password = os.getenv("APP_PASSWORD", "")
    session_secret = os.getenv("APP_SESSION_SECRET", "")
    if (
        not username
        or len(password) < 14
        or password == EXAMPLE_PASSWORD
        or len(session_secret) < 32
        or session_secret == EXAMPLE_SESSION_SECRET
    ):
        raise AuthConfigurationError(
            "Set APP_USERNAME, an APP_PASSWORD of at least 14 characters, "
            "and an APP_SESSION_SECRET of at least 32 characters."
        )

    return AuthSettings(
        username=username,
        password=password,
        session_secret=session_secret,
        cookie_secure=os.getenv("COOKIE_SECURE", "true").lower() == "true",
    )


def create_session_token(username, session_secret, now=None):
    issued_at = int(time.time() if now is None else now)
    payload = json.dumps({
        "username": username,
        "expires_at": issued_at + SESSION_LIFETIME_SECONDS,
    }, separators=(",", ":")).encode("utf-8")
    encoded_payload = base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")
    signature = hmac.new(
        session_secret.encode("utf-8"),
        encoded_payload.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    return f"{encoded_payload}.{signature}"


def validate_session_token(token, username, session_secret, now=None):
    if not token or "." not in token:
        return False
    encoded_payload, supplied_signature = token.rsplit(".", 1)
    expected_signature = hmac.new(
        session_secret.encode("utf-8"),
        encoded_payload.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(supplied_signature, expected_signature):
        return False

    try:
        padding = "=" * (-len(encoded_payload) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(encoded_payload + padding).decode("utf-8")
        )
        current_time = int(time.time() if now is None else now)
        return (
            payload.get("username") == username
            and int(payload.get("expires_at", 0)) > current_time
        )
    except (ValueError, TypeError, json.JSONDecodeError):
        return False
