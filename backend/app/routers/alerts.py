from typing import Optional

from fastapi import APIRouter, Depends

from .. import db, security

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("")
def list_alerts(status: Optional[str] = "OPEN", identity: db.Identity = Depends(security.require_roles("pharmacist", "admin"))):
    """Low-stock alerts created by the inventory trigger (pharmacist: own pharmacy only, enforced by the view)."""
    sql = "SELECT * FROM v_my_alerts"
    params: list = []
    if status:
        sql += " WHERE status = %s"
        params.append(status)
    with db.session(identity.role, identity) as cnx:
        return db.query(cnx, sql + " ORDER BY opened_at DESC, id DESC", params)
