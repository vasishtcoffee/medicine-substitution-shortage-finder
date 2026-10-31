"""Idempotent seed: demo users (argon2 hashes, passwords from .env) + database/seed/S001_seed.sql.

Usage: python scripts/seed.py [database_name]
"""
import sys

import mysql.connector
from argon2 import PasswordHasher

from envload import ROOT, env, load_env
from migrate import connect, split_statements, render

load_env()

# id, email, name, role, password env var, pharmacy
USERS = [
    (1, "admin@medsub.demo", "Demo Admin", "admin", "DEMO_ADMIN_PASSWORD", None),
    (2, "pharmacist1@medsub.demo", "Demo Pharmacist One", "pharmacist", "DEMO_PHARMACIST_PASSWORD", 1),
    (3, "pharmacist2@medsub.demo", "Demo Pharmacist Two", "pharmacist", "DEMO_PHARMACIST_PASSWORD", 2),
    (4, "patient1@medsub.demo", "Demo Patient One", "patient", "DEMO_PATIENT_PASSWORD", None),
    (5, "patient2@medsub.demo", "Demo Patient Two", "patient", "DEMO_PATIENT_PASSWORD", None),
]


def seed(db=None, verbose=True):
    db = db or env("MYSQL_DATABASE", "medsub")
    ph = PasswordHasher()
    cnx = connect(db)
    cur = cnx.cursor()
    # pharmacies are needed by pharmacist_assignments; the SQL seed is idempotent so run it in two steps
    seed_sql = (ROOT / "database" / "seed" / "S001_seed.sql").read_text(encoding="utf-8")
    stmts = split_statements(render(seed_sql, db))
    cur.execute(stmts[0])  # pharmacies first
    for uid, email, name, role, pw_var, pharmacy in USERS:
        pw = env(pw_var)
        if not pw:
            raise SystemExit(f"{pw_var} missing in .env")
        cur.execute("SELECT password_hash FROM users WHERE id=%s", (uid,))
        row = cur.fetchone()
        h = None
        if row:
            try:
                ph.verify(row[0], pw)
                h = row[0]  # password unchanged: keep the existing hash (idempotent, no churn)
            except Exception:
                h = None
        if h is None:
            h = ph.hash(pw)
        cur.execute(
            "INSERT INTO users (id, email, full_name, role, password_hash) VALUES (%s,%s,%s,%s,%s) AS n "
            "ON DUPLICATE KEY UPDATE email=n.email, full_name=n.full_name, role=n.role, password_hash=n.password_hash, is_active=1",
            (uid, email, name, role, h))
        if pharmacy:
            cur.execute(
                "INSERT INTO pharmacist_assignments (user_id, pharmacy_id) VALUES (%s,%s) AS n "
                "ON DUPLICATE KEY UPDATE pharmacy_id=n.pharmacy_id", (uid, pharmacy))
    for s in stmts[1:]:
        cur.execute(s)
    # prime the MongoDB feed from MySQL (once, while no sync is pending)
    cur.execute("SELECT COUNT(*) FROM sync_outbox WHERE status='PENDING'")
    if cur.fetchone()[0] == 0:
        cur.execute("SET @app_user_id = 1, @app_role = 'admin', @app_pharmacy_id = NULL")
        cur.execute("CALL sp_enqueue_full_resync()")
        cur.fetchall()
        while cur.nextset():
            if cur.with_rows:
                cur.fetchall()
        cur.execute("SET @app_user_id = NULL, @app_role = NULL, @app_pharmacy_id = NULL")
    cnx.close()
    if verbose:
        print(f"seed OK ({db})")


if __name__ == "__main__":
    seed(sys.argv[1] if len(sys.argv) > 1 else None)
