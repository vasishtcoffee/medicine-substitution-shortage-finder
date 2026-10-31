"""Admin SQL Demo: runs ONLY whitelisted, named, read-only queries parsed from database/sql/*.sql. No arbitrary SQL."""
import re
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException

from .. import config, db, security

router = APIRouter(prefix="/admin/sql-demo", tags=["sql-demo"])
admin = security.require_roles("admin")
FILES = ["queries.sql", "advanced.sql"]


@lru_cache(maxsize=1)
def _catalog() -> dict:
    cat: dict = {}
    for fname in FILES:
        text = (config.ROOT / "database" / "sql" / fname).read_text(encoding="utf-8")
        cur = None
        for line in text.splitlines():
            m = re.match(r"^--\s*@name:\s*(\S+)", line)
            if m:
                cur = {"name": m.group(1), "file": fname, "purpose": "", "why": "", "expected": "", "runnable": True, "sql_lines": []}
                cat[cur["name"]] = cur
                continue
            if cur is None:
                continue
            m = re.match(r"^--\s*@(\w+):\s*(.*)$", line)
            if m:
                key, val = m.group(1), m.group(2).strip()
                if key == "runnable":
                    cur["runnable"] = val.lower() == "yes"
                elif key in ("purpose", "why", "expected"):
                    cur[key] = val
            elif not line.strip().startswith("--"):
                cur["sql_lines"].append(line)
    for c in cat.values():
        c["sql"] = "\n".join(c.pop("sql_lines")).strip().rstrip(";")
        # defence in depth: only a single SELECT/WITH statement can ever be run
        if not re.match(r"^(SELECT|WITH)\b", c["sql"], re.I) or ";" in c["sql"]:
            c["runnable"] = False
    return cat


@router.get("")
def list_queries(_: db.Identity = Depends(admin)):
    return [{k: v for k, v in c.items()} for c in _catalog().values()]


@router.post("/{name}/run")
def run_query(name: str, identity: db.Identity = Depends(admin)):
    c = _catalog().get(name)
    if not c:
        raise HTTPException(404, "Unknown query name")
    if not c["runnable"]:
        raise HTTPException(409, "This demo is not runnable from the web panel")
    with db.session("admin", identity) as cnx:
        db.execute(cnx, "SET SESSION TRANSACTION READ ONLY")
        try:
            rows = db.query(cnx, c["sql"])
        finally:
            db.execute(cnx, "SET SESSION TRANSACTION READ WRITE")
    cols = list(rows[0].keys()) if rows else []
    return {"name": name, "columns": cols, "rows": rows}
