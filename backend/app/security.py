"""Password hashing (argon2id), JWT cookie token, and FastAPI identity dependencies."""
from datetime import datetime, timedelta, timezone
from typing import Callable

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import Depends, HTTPException, Request

from . import config, db

_ph = PasswordHasher()
# verified against when the e-mail is unknown, so unknown-user and wrong-password take similar time
_DUMMY_HASH = _ph.hash("not-a-real-password")


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(stored_hash: str | None, password: str) -> bool:
    try:
        return _ph.verify(stored_hash or _DUMMY_HASH, password) and stored_hash is not None
    except (VerifyMismatchError, InvalidHashError):
        return False


def create_token(user_id: int, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "role": role, "iat": now,
               "exp": now + timedelta(minutes=config.JWT_EXPIRE_MINUTES)}
    return jwt.encode(payload, config.JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> dict:
    return jwt.decode(token, config.JWT_SECRET, algorithms=["HS256"])


def get_identity(request: Request) -> db.Identity:
    """Authoritative identity: the token only names the user; role and pharmacy are re-read from MySQL each request."""
    token = request.cookies.get(config.COOKIE_NAME)
    if not token:
        raise HTTPException(401, "Not authenticated")
    try:
        data = decode_token(token)
        user_id = int(data["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(401, "Invalid or expired session")
    with db.session("auth") as cnx:
        rows = db.call_one(cnx, "sp_auth_identity", (user_id,))
    if not rows or not rows[0]["is_active"]:
        raise HTTPException(401, "Invalid or expired session")
    r = rows[0]
    return db.Identity(id=r["id"], email=r["email"], full_name=r["full_name"], role=r["role"],
                       pharmacy_id=r["pharmacy_id"])


def require_roles(*roles: str) -> Callable:
    def dep(identity: db.Identity = Depends(get_identity)) -> db.Identity:
        if identity.role not in roles:
            raise HTTPException(403, "Your role is not allowed to do this")
        return identity
    return dep
