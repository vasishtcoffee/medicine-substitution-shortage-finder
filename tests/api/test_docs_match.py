"""docs/API.md must list exactly the routes the code serves."""
import re
from pathlib import Path

DOC = Path(__file__).resolve().parents[2] / "docs" / "API.md"


def test_api_doc_matches_routes(anon):
    documented = set(re.findall(r"^\| (GET|POST|PUT|PATCH|DELETE) \| `([^`]+)`", DOC.read_text(encoding="utf-8"), re.M))
    response = anon.get("/openapi.json")
    assert response.status_code == 200
    # Included routers may be lazy objects. Public OpenAPI is the documented contract.
    methods = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}
    served = {(method.upper(), path) for path, operations in response.json()["paths"].items()
              for method in operations if method in methods}
    assert served  # An empty/malformed schema must never make this check vacuously pass.
    assert documented == served, f"only in docs: {documented - served}; only in code: {served - documented}"
