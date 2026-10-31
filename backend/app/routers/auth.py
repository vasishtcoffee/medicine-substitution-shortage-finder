from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from .. import config, db, security

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    email: str
    password: str


def _user(i: db.Identity) -> dict:
    return {"id": i.id, "email": i.email, "full_name": i.full_name, "role": i.role, "pharmacy_id": i.pharmacy_id}


@router.post("/login")
def login(body: LoginIn, response: Response):
    with db.session("auth") as cnx:
        rows = db.call_one(cnx, "sp_auth_lookup", (body.email.strip(),))
    row = rows[0] if rows else None
    ok = security.verify_password(row["password_hash"] if row else None, body.password)
    if not (row and ok and row["is_active"]):
        # identical message for unknown e-mail, wrong password and inactive account: no user enumeration
        raise HTTPException(401, "Invalid email or password")
    token = security.create_token(row["id"], row["role"])
    response.set_cookie(config.COOKIE_NAME, token, httponly=True, samesite="lax", secure=config.COOKIE_SECURE,
                        max_age=config.JWT_EXPIRE_MINUTES * 60, path="/")
    with db.session("auth") as cnx:
        i = db.call_one(cnx, "sp_auth_identity", (row["id"],))[0]
    return {"id": i["id"], "email": i["email"], "full_name": i["full_name"], "role": i["role"],
            "pharmacy_id": i["pharmacy_id"]}


@router.post("/logout")
def logout(response: Response):
    # Tokens are stateless: logout only clears the cookie (documented limitation).
    response.delete_cookie(config.COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me")
def me(identity: db.Identity = Depends(security.get_identity)):
    return _user(identity)
