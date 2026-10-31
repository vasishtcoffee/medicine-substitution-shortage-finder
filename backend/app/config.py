"""Configuration read from the environment (.env at the repo root is loaded without overriding real env vars)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv():
    f = ROOT / ".env"
    if not f.exists():
        return
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


_load_dotenv()


def env(name: str, default: str | None = None) -> str:
    v = os.environ.get(name, default)
    if v is None:
        raise RuntimeError(f"Missing environment variable {name}")
    return v


MYSQL_HOST = env("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(env("MYSQL_PORT", "3306"))
MYSQL_DATABASE = env("MYSQL_DATABASE", "medsub")

# kind -> (login account env prefix, expected MySQL role)
ACCOUNTS = {
    "patient": ("PATIENT_SVC", "app_patient_role"),
    "pharmacist": ("PHARMACIST_SVC", "app_pharmacist_role"),
    "admin": ("ADMIN_SVC", "app_admin_role"),
    "auth": ("AUTH_SVC", "app_auth_role"),
}

MONGO_URI = env("MONGO_URI", "mongodb://127.0.0.1:27017")
MONGO_DATABASE = env("MONGO_DATABASE", "medsub_feed")

JWT_SECRET = env("JWT_SECRET", "dev-only-secret-change-me")
JWT_EXPIRE_MINUTES = int(env("JWT_EXPIRE_MINUTES", "60"))
COOKIE_NAME = "medsub_session"
COOKIE_SECURE = env("COOKIE_SECURE", "false").lower() == "true"

SYNC_INTERVAL_SECONDS = int(env("SYNC_INTERVAL_SECONDS", "15"))
SYNC_MAX_ATTEMPTS = int(env("SYNC_MAX_ATTEMPTS", "5"))
SYNC_BACKGROUND = env("SYNC_BACKGROUND", "true").lower() == "true"

SAFETY_NOTICE = (
    "This is an educational demonstration. Candidate matches are not medical advice or an authorization to "
    "substitute a medicine. A qualified pharmacist must verify the medicine and applicable prescription "
    "requirements before any substitution or sale."
)
