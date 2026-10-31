import os

from fastapi.testclient import TestClient

from app.main import app

ACCOUNTS = {
    "admin": ("admin@medsub.demo", "DEMO_ADMIN_PASSWORD"),
    "pharmacist1": ("pharmacist1@medsub.demo", "DEMO_PHARMACIST_PASSWORD"),
    "pharmacist2": ("pharmacist2@medsub.demo", "DEMO_PHARMACIST_PASSWORD"),
    "patient1": ("patient1@medsub.demo", "DEMO_PATIENT_PASSWORD"),
    "patient2": ("patient2@medsub.demo", "DEMO_PATIENT_PASSWORD"),
}


def make_client(who: str | None = None) -> TestClient:
    c = TestClient(app)
    if who:
        email, pw = ACCOUNTS[who]
        r = c.post("/auth/login", json={"email": email, "password": os.environ[pw]})
        assert r.status_code == 200, r.text
    return c


