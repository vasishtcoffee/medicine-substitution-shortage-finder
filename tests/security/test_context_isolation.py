"""Pooled connections must never leak one request's identity into the next (section 6 / warning 4)."""
import pytest

from app import db


def ident(uid, role, ph=None):
    return db.Identity(id=uid, email=f"u{uid}@x", full_name=f"U{uid}", role=role, pharmacy_id=ph)


def ctx(cnx):
    c = cnx.cursor()
    c.execute("SELECT @app_user_id, @app_role, @app_pharmacy_id")
    r = c.fetchone()
    c.close()
    return r


def test_context_is_cleared_after_each_request_and_never_seen_by_the_next():
    db.reset_pools()
    seen_dirty = []
    for i in range(30):                                      # more checkouts than the pool size (6): connections are reused
        who = ident(2 + (i % 2), "pharmacist", 1 + (i % 2))
        with db.session("pharmacist", None) as cnx:          # anonymous checkout FIRST: must be clean
            seen_dirty.append(ctx(cnx))
        with db.session("pharmacist", who) as cnx:
            assert ctx(cnx) == (who.id, "pharmacist", who.pharmacy_id)
    assert all(c == (None, None, None) for c in seen_dirty)


def test_context_cleared_even_when_the_request_fails():
    db.reset_pools()
    with pytest.raises(RuntimeError):
        with db.session("patient", ident(4, "patient")):
            raise RuntimeError("request blew up")
    with db.session("patient", None) as cnx:
        assert ctx(cnx) == (None, None, None)


def test_raw_pool_connection_is_clean_after_use():
    db.reset_pools()
    with db.session("admin", ident(1, "admin")):
        pass
    raw = db._pool("admin").get_connection()
    try:
        assert ctx(raw) == (None, None, None)
    finally:
        raw.close()


def test_role_is_verified_on_checkout_and_roles_do_not_mix():
    with db.session("patient", ident(4, "patient")) as cnx:
        c = cnx.cursor()
        c.execute("SELECT CURRENT_ROLE()")
        assert "app_patient_role" in c.fetchone()[0]
    with db.session("admin", ident(1, "admin")) as cnx:
        c = cnx.cursor()
        c.execute("SELECT CURRENT_ROLE()")
        assert "app_admin_role" in c.fetchone()[0]
