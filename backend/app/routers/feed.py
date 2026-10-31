"""Feed Lab API: CRUD over the MongoDB inventory_feed and feed_events collections (admin only).

MySQL stays authoritative: quantities are written only by the outbox sync. UPDATE here touches only
metadata / notes / flags, and DELETE never touches MySQL (a resync recreates the document).
"""
import uuid
from datetime import date, datetime, time, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from pymongo.errors import PyMongoError, WriteError

from .. import db, mongo, security

router = APIRouter(prefix="/feed", tags=["feed (MongoDB)"])
admin = security.require_roles("admin")


def _mdb():
    try:
        return mongo.get_db()
    except PyMongoError as e:
        raise HTTPException(503, f"MongoDB unavailable: {e}")


def _guard(fn):
    try:
        return fn()
    except WriteError as e:
        raise HTTPException(422, f"Rejected by MongoDB validation: {e}")
    except PyMongoError as e:
        raise HTTPException(503, f"MongoDB unavailable: {e}")


def _page(col, flt: dict, sort_field: str, page: int, page_size: int) -> dict:
    total = col.count_documents(flt)
    items = list(col.find(flt).sort([(sort_field, -1), ("_id", 1)]).skip((page - 1) * page_size).limit(page_size))
    return {"total": total, "page": page, "page_size": page_size, "items": items}


class PatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")   # quantity etc. cannot be edited here
    metadata: Optional[dict[str, Any]] = None
    notes: Optional[str] = Field(default=None, max_length=500)
    flags: Optional[list[str]] = None


def _patch_doc(body: PatchIn) -> dict:
    upd = body.model_dump(exclude_none=True)
    if not upd:
        raise HTTPException(422, "Nothing to update (allowed: metadata, notes, flags)")
    return upd


@router.get("/inventory")
def list_feed(pharmacy_id: Optional[int] = None, medicine_id: Optional[int] = None,
              page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), _: db.Identity = Depends(admin)):
    flt: dict = {}
    if pharmacy_id is not None:
        flt["pharmacy_id"] = pharmacy_id
    if medicine_id is not None:
        flt["medicine_id"] = medicine_id
    return _guard(lambda: _page(_mdb()[mongo.INVENTORY_FEED], flt, "last_updated", page, page_size))


@router.get("/inventory/{doc_id}")
def get_feed(doc_id: str, _: db.Identity = Depends(admin)):
    doc = _guard(lambda: _mdb()[mongo.INVENTORY_FEED].find_one({"_id": doc_id}))
    if not doc:
        raise HTTPException(404, "Feed document not found")
    return doc


@router.patch("/inventory/{doc_id}")
def patch_feed(doc_id: str, body: PatchIn, _: db.Identity = Depends(admin)):
    r = _guard(lambda: _mdb()[mongo.INVENTORY_FEED].update_one({"_id": doc_id}, {"$set": _patch_doc(body)}))
    if r.matched_count == 0:
        raise HTTPException(404, "Feed document not found")
    return _guard(lambda: _mdb()[mongo.INVENTORY_FEED].find_one({"_id": doc_id}))


@router.delete("/inventory/{doc_id}")
def delete_feed(doc_id: str, _: db.Identity = Depends(admin)):
    r = _guard(lambda: _mdb()[mongo.INVENTORY_FEED].delete_one({"_id": doc_id}))
    if r.deleted_count == 0:
        raise HTTPException(404, "Feed document not found")
    return {"deleted": doc_id, "note": "MySQL inventory untouched; POST /sync/resync recreates the document"}


@router.get("/events")
def list_events(source: Optional[str] = None, pharmacy_id: Optional[int] = None, medicine_id: Optional[int] = None,
                date_from: Optional[date] = None, date_to: Optional[date] = None,
                page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), _: db.Identity = Depends(admin)):
    flt: dict = {}
    if source:
        flt["source"] = source
    if pharmacy_id is not None:
        flt["pharmacy_id"] = pharmacy_id
    if medicine_id is not None:
        flt["medicine_id"] = medicine_id
    rng: dict = {}
    if date_from:
        rng["$gte"] = datetime.combine(date_from, time.min, tzinfo=timezone.utc)
    if date_to:
        rng["$lte"] = datetime.combine(date_to, time.max, tzinfo=timezone.utc)
    if rng:
        flt["occurred_at"] = rng
    return _guard(lambda: _page(_mdb()[mongo.FEED_EVENTS], flt, "occurred_at", page, page_size))


class EventIn(BaseModel):
    source: str = Field(pattern="^(sale|receipt|adjustment|import)$")
    pharmacy_id: Optional[int] = None
    medicine_id: Optional[int] = None
    payload: dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = Field(default="", max_length=500)
    flags: list[str] = Field(default_factory=lambda: ["manual", "unverified"])


@router.post("/events", status_code=201)
def create_event(body: EventIn, _: db.Identity = Depends(admin)):
    """Admin-created event (e.g. a supplier import note). Stored unverified; it never changes MySQL stock."""
    doc = {"_id": f"manual:{uuid.uuid4().hex[:12]}", "source": body.source, "occurred_at": datetime.now(timezone.utc),
           "payload": body.payload, "notes": body.notes or "", "flags": body.flags}
    if body.pharmacy_id is not None:
        doc["pharmacy_id"] = body.pharmacy_id
    if body.medicine_id is not None:
        doc["medicine_id"] = body.medicine_id
    _guard(lambda: _mdb()[mongo.FEED_EVENTS].insert_one(doc))
    return doc


@router.get("/events/{event_id}")
def get_event(event_id: str, _: db.Identity = Depends(admin)):
    doc = _guard(lambda: _mdb()[mongo.FEED_EVENTS].find_one({"_id": event_id}))
    if not doc:
        raise HTTPException(404, "Event not found")
    return doc


@router.patch("/events/{event_id}")
def patch_event(event_id: str, body: PatchIn, _: db.Identity = Depends(admin)):
    upd = _patch_doc(body)
    if "metadata" in upd:
        upd["payload.metadata"] = upd.pop("metadata")   # events keep annotations inside their payload
    r = _guard(lambda: _mdb()[mongo.FEED_EVENTS].update_one({"_id": event_id}, {"$set": upd}))
    if r.matched_count == 0:
        raise HTTPException(404, "Event not found")
    return _guard(lambda: _mdb()[mongo.FEED_EVENTS].find_one({"_id": event_id}))


@router.delete("/events/{event_id}")
def delete_event(event_id: str, _: db.Identity = Depends(admin)):
    r = _guard(lambda: _mdb()[mongo.FEED_EVENTS].delete_one({"_id": event_id}))
    if r.deleted_count == 0:
        raise HTTPException(404, "Event not found")
    return {"deleted": event_id}
