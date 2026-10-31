"""Outbox sync controls (admin): run the worker, list outbox rows, re-enqueue everything, retry failures."""
from typing import Optional

from fastapi import APIRouter, Depends, Query

from .. import db, security, sync

router = APIRouter(prefix="/sync", tags=["sync"])
admin = security.require_roles("admin")


@router.post("/run")
def run(_: db.Identity = Depends(admin)):
    return sync.run_sync()


@router.get("/outbox")
def outbox(status: Optional[str] = None, limit: int = Query(50, ge=1, le=500), _: db.Identity = Depends(admin)):
    sql = "SELECT id, operation, entity_id, status, attempts, last_error, created_at, processed_at FROM sync_outbox"
    params: list = []
    if status:
        sql += " WHERE status = %s"
        params.append(status)
    with db.session("admin", _) as cnx:
        rows = db.query(cnx, sql + " ORDER BY id DESC LIMIT %s", params + [limit])
        counts = db.query(cnx, "SELECT status, COUNT(*) AS n FROM sync_outbox GROUP BY status")
    return {"counts": {c["status"]: c["n"] for c in counts}, "rows": rows}


@router.post("/resync")
def resync(identity: db.Identity = Depends(admin)):
    """Re-enqueue every MySQL inventory row (MySQL is authoritative) and drain the outbox."""
    with db.session("admin", identity) as cnx:
        enq = db.call_one(cnx, "sp_enqueue_full_resync")[0]["enqueued"]
    return {"enqueued": enq, **sync.run_sync()}


@router.post("/retry-failed")
def retry_failed(identity: db.Identity = Depends(admin)):
    with db.session("admin", identity) as cnx:
        n = db.execute(cnx, "UPDATE sync_outbox SET status='PENDING', attempts=0 WHERE status='FAILED'")
    return {"reset": n, **sync.run_sync()}
