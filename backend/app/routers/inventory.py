"""Pharmacist/admin inventory. Writes go through guarded stored procedures; reads through context-scoped views."""
from datetime import date
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel, Field

from .. import db, security, sync

router = APIRouter(prefix="/inventory", tags=["inventory"])
staff = security.require_roles("pharmacist", "admin")


@router.get("")
def list_inventory(pharmacy_id: Optional[int] = None, identity: db.Identity = Depends(staff)):
    sql = "SELECT * FROM v_my_inventory"
    params: list = []
    if pharmacy_id is not None:
        sql += " WHERE pharmacy_id = %s"
        params.append(pharmacy_id)
    with db.session(identity.role, identity) as cnx:
        return db.query(cnx, sql + " ORDER BY pharmacy_id, medicine_name", params)


@router.get("/movements")
def movements(medicine_id: Optional[int] = None, limit: int = 100, identity: db.Identity = Depends(staff)):
    sql = "SELECT * FROM v_my_movements"
    params: list = []
    if medicine_id is not None:
        sql += " WHERE medicine_id = %s"
        params.append(medicine_id)
    with db.session(identity.role, identity) as cnx:
        return db.query(cnx, sql + " ORDER BY id DESC LIMIT %s", params + [min(max(limit, 1), 500)])


class ReceiveIn(BaseModel):
    pharmacy_id: int
    medicine_id: int
    quantity: int = Field(gt=0)
    batch_no: Optional[str] = Field(default=None, max_length=40)
    expiry_date: Optional[date] = None


class AdjustIn(BaseModel):
    pharmacy_id: int
    medicine_id: int
    delta: int
    note: Optional[str] = Field(default=None, max_length=200)


class ReorderIn(BaseModel):
    pharmacy_id: int
    medicine_id: int
    reorder_level: int = Field(ge=0)


@router.post("/receive", status_code=201)
def receive(body: ReceiveIn, bg: BackgroundTasks, identity: db.Identity = Depends(staff)):
    with db.session(identity.role, identity) as cnx:
        rows = db.with_retry(lambda: db.call_one(cnx, "sp_receive_stock", (
            body.pharmacy_id, body.medicine_id, body.quantity, body.batch_no, body.expiry_date)))
    bg.add_task(sync.run_sync_safe)
    return rows[0]


@router.post("/adjust")
def adjust(body: AdjustIn, bg: BackgroundTasks, identity: db.Identity = Depends(staff)):
    with db.session(identity.role, identity) as cnx:
        rows = db.with_retry(lambda: db.call_one(cnx, "sp_adjust_stock", (
            body.pharmacy_id, body.medicine_id, body.delta, body.note)))
    bg.add_task(sync.run_sync_safe)
    return rows[0]


@router.put("/reorder-level")
def reorder_level(body: ReorderIn, bg: BackgroundTasks, identity: db.Identity = Depends(staff)):
    with db.session(identity.role, identity) as cnx:
        rows = db.with_retry(lambda: db.call_one(cnx, "sp_set_reorder_level", (
            body.pharmacy_id, body.medicine_id, body.reorder_level)))
    bg.add_task(sync.run_sync_safe)
    return rows[0]
