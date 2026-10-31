from fastapi import APIRouter, Depends

from .. import db, security

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
def dashboard(identity: db.Identity = Depends(security.get_identity)):
    """Role-specific summary, assembled only from what that role's DB account may read."""
    out: dict = {"role": identity.role, "user": identity.full_name}
    with db.session(identity.role, identity) as cnx:
        if identity.role == "patient":
            rows = db.call_one(cnx, "sp_list_my_orders")
            counts: dict = {}
            for r in rows:
                counts[r["status"]] = counts.get(r["status"], 0) + 1
            out["my_orders_by_status"] = counts
            out["open_shortages"] = db.query(cnx, "SELECT COUNT(*) AS n FROM shortage_entries WHERE status='OPEN'")[0]["n"]
        else:
            orders = db.call_one(cnx, "sp_list_pharmacy_orders", (None,))
            seen: dict = {}
            for r in orders:
                seen[r["order_id"]] = r["status"]
            counts = {}
            for s in seen.values():
                counts[s] = counts.get(s, 0) + 1
            out["orders_by_status"] = counts
            out["open_low_stock_alerts"] = db.query(cnx, "SELECT COUNT(*) AS n FROM v_my_alerts WHERE status='OPEN'")[0]["n"]
            out["open_shortages"] = db.query(cnx, "SELECT COUNT(*) AS n FROM shortage_entries WHERE status='OPEN'")[0]["n"]
            if identity.role == "pharmacist":
                out["pharmacy"] = db.query(cnx, "SELECT name FROM pharmacies WHERE id=%s", (identity.pharmacy_id,))[0]["name"]
            else:
                out["sync_pending"] = db.query(cnx, "SELECT COUNT(*) AS n FROM sync_outbox WHERE status IN ('PENDING','FAILED')")[0]["n"]
                out["users"] = db.query(cnx, "SELECT COUNT(*) AS n FROM v_users_public")[0]["n"]
    return out
