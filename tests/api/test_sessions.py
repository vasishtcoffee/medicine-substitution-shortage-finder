"""Integration: invalid sessions clear cookies; authenticated denials retain identity."""
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app import config


@pytest.mark.parametrize("kind", ["garbage", "expired", "bad_signature", "missing_subject"])
def test_invalid_sessions_expire_cookie(anon, kind):
    payload = {"sub": "4", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}
    if kind == "expired":
        payload["exp"] = datetime.now(timezone.utc) - timedelta(seconds=1)
    if kind == "missing_subject":
        payload.pop("sub")
    token = "garbage" if kind == "garbage" else jwt.encode(
        payload, "wrong-secret-at-least-32-characters" if kind == "bad_signature" else config.JWT_SECRET, algorithm="HS256")
    anon.cookies.set(config.COOKIE_NAME, token)
    response = anon.get("/auth/me")
    assert response.status_code == 401
    assert "Max-Age=0" in response.headers["set-cookie"]
    assert "Path=/" in response.headers["set-cookie"]


def test_403_does_not_expire_valid_session(pat1):
    response = pat1.get("/inventory")
    assert response.status_code == 403
    assert "set-cookie" not in response.headers
    assert pat1.get("/auth/me").status_code == 200
