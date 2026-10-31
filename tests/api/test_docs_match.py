"""docs/API.md must list exactly the routes the code serves."""
import re
from pathlib import Path

from app.main import app

DOC = Path(__file__).resolve().parents[2] / "docs" / "API.md"


def test_api_doc_matches_routes():
    documented = set(re.findall(r"^\| (GET|POST|PUT|PATCH|DELETE) \| `([^`]+)`", DOC.read_text(encoding="utf-8"), re.M))
    served = {(m, r.path) for r in app.routes if hasattr(r, "methods") for m in r.methods - {"HEAD", "OPTIONS"}
              if r.path not in ("/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc")}
    assert documented == served, f"only in docs: {documented - served}; only in code: {served - documented}"
