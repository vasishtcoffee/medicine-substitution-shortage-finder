"""Orders: patient create/track; pharmacist review -> approve -> complete. All logic lives in stored procedures."""
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel, Field

from .. import config, db, security, sync

router = APIRouter(prefix="/orders", tags=["orders"])
patient = security.require_roles("patient")
staff = security.require_roles("pharmacist", "admin")
pharmacist = security.require_roles("pharmacist")
anyone = security.get_identity


def _group(rows: list[dict]) -> list[dict]:
    orders: dict[int, dict] = {}
    for r in rows:
        o = orders.setdefault(r["order_id"], {k: r[k] for k in r if k not in (
            "item_id", "requested_medicine_id", "requested_name", "requires_prescription",
            "dispensed_medicine_id", "dispensed_name", "quantity")} | {"items": []})
        o["items"].append({k: r.get(k) for k in ("item_id", "requested_medicine_id", "requested_name", "requires_prescription",
                                                  "dispensed_medicine_id", "dispensed_name", "quantity")})
    return list(orders.values())


class OrderIn(BaseModel):
    pharmacy_id: int
    medicine_id: int
    quantity: int = Field(gt=0, le=1000)
    prescription_note: Optional[str] = Field(default=None, max_length=500)


@router.post("", status_code=201)
def create_order(body: OrderIn, identity: db.Identity = Depends(patient)):
    with db.session("patient", identity) as cnx:   # owner is the verified identity, never a client-supplied id
        rows = db.call_one(cnx, "sp_create_my_order", (body.pharmacy_id, body.medicine_id, body.quantity, body.prescription_note))
    return rows[0]


@router.get("/mine")
def my_orders(identity: db.Identity = Depends(patient)):
    with db.session("patient", identity) as cnx:
        return _group(db.call_one(cnx, "sp_list_my_orders"))


@router.get("")
def pharmacy_orders(status: Optional[str] = None, identity: db.Identity = Depends(staff)):
    with db.session(identity.role, identity) as cnx:
        return _group(db.call_one(cnx, "sp_list_pharmacy_orders", (status,)))


@router.get("/{order_id}/reviews")
def reviews(order_id: int, identity: db.Identity = Depends(anyone)):
    with db.session(identity.role, identity) as cnx:
        return db.call_one(cnx, "sp_list_reviews", (order_id,))


@router.post("/{order_id}/cancel")
def cancel(order_id: int, identity: db.Identity = Depends(anyone)):
    with db.session(identity.role, identity) as cnx:
        return db.call_one(cnx, "sp_cancel_order", (order_id,))[0]


@router.post("/{order_id}/start-review")
def start_review(order_id: int, identity: db.Identity = Depends(pharmacist)):
    with db.session("pharmacist", identity) as cnx:
        return db.call_one(cnx, "sp_start_review", (order_id,))[0]


class DecisionIn(BaseModel):
    proposed_medicine_id: int
    decision: str = Field(pattern="^(APPROVED|REJECTED)$")
    note: Optional[str] = Field(default=None, max_length=300)


@router.post("/items/{item_id}/decision")
def decide(item_id: int, body: DecisionIn, identity: db.Identity = Depends(pharmacist)):
    with db.session("pharmacist", identity) as cnx:
        return db.call_one(cnx, "sp_decide_substitution", (item_id, body.proposed_medicine_id, body.decision, body.note))[0]


@router.post("/{order_id}/approve")
def approve(order_id: int, identity: db.Identity = Depends(pharmacist)):
    with db.session("pharmacist", identity) as cnx:
        return db.call_one(cnx, "sp_approve_order", (order_id,))[0]


@router.post("/{order_id}/reject")
def reject(order_id: int, identity: db.Identity = Depends(pharmacist)):
    with db.session("pharmacist", identity) as cnx:
        return db.call_one(cnx, "sp_reject_order", (order_id,))[0]


@router.post("/{order_id}/complete")
def complete(order_id: int, bg: BackgroundTasks, identity: db.Identity = Depends(pharmacist)):
    """The sale. One DB transaction; a deadlock victim is retried. Mongo is updated afterwards by the outbox worker."""
    with db.session("pharmacist", identity) as cnx:
        row = db.with_retry(lambda: db.call_one(cnx, "sp_complete_order", (order_id, identity.id)))[0]
    bg.add_task(sync.run_sync_safe)
    return row | {"notice": config.SAFETY_NOTICE}
