"""Outbox worker: drains sync_outbox into MongoDB idempotently.

The outbox rows were written in the SAME MySQL transaction as the stock change, so a MongoDB outage can never roll
back or lose a committed sale: rows just stay PENDING/FAILED until a later run (eventual consistency).
"""
import json
import threading
from datetime import datetime, timezone

from pymongo.errors import ConnectionFailure, DuplicateKeyError, PyMongoError

from . import config, db, mongo

_lock = threading.Lock()


def _parse_ts(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)


def _payload(row) -> dict:
    p = row["payload"]
    if isinstance(p, (bytes, bytearray)):
        p = p.decode()
    return json.loads(p) if isinstance(p, str) else p


def _clean(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None}


def apply_row(mdb, row) -> None:
    p = _payload(row)
    ts = _parse_ts(p["occurred_at"])
    if row["operation"] == "UPSERT_INVENTORY_FEED":
        meta = {f"metadata.{k}": v for k, v in _clean(p.get("metadata") or {}).items()}
        doc_set = {"pharmacy_id": p["pharmacy_id"], "medicine_id": p["medicine_id"], "quantity": p["quantity"],
                   "reorder_level": p["reorder_level"], "availability": p["availability"],
                   "low_stock": bool(p["low_stock"]), "last_updated": ts, "source": p["source"], **meta}
        # Only apply if the stored document is not NEWER than this change (protects against out-of-order retries).
        # If a newer doc exists the upsert would insert a duplicate _id -> DuplicateKeyError -> already superseded.
        try:
            mdb[mongo.INVENTORY_FEED].update_one(
                {"_id": row["entity_id"], "$or": [{"last_updated": {"$lte": ts}}, {"last_updated": {"$exists": False}}]},
                {"$set": doc_set, "$setOnInsert": {"notes": "", "flags": [], **({} if meta else {"metadata": {}})}},
                upsert=True)
        except DuplicateKeyError:
            pass
    elif row["operation"] == "APPEND_FEED_EVENT":
        doc = {"source": p["source"], "pharmacy_id": p["pharmacy_id"], "medicine_id": p["medicine_id"],
               "occurred_at": ts,
               "payload": _clean({"delta": p.get("delta"), "order_id": p.get("order_id"),
                                  "quantity_after": p.get("quantity_after"), **(p.get("details") or {})}),
               "notes": "", "flags": []}
        mdb[mongo.FEED_EVENTS].update_one({"_id": row["entity_id"]}, {"$setOnInsert": doc}, upsert=True)
    else:
        raise ValueError(f"unknown operation {row['operation']}")


def run_sync(batch: int = 500) -> dict:
    """Process PENDING/FAILED outbox rows in id order. Returns counts. Never raises for Mongo problems."""
    with _lock:
        with db.session("admin") as cnx:
            rows = db.query(cnx, "SELECT id, operation, entity_id, payload, attempts FROM sync_outbox "
                                 "WHERE status IN ('PENDING','FAILED') AND attempts < %s ORDER BY id LIMIT %s",
                            (config.SYNC_MAX_ATTEMPTS, batch))
            done = failed = 0
            if not rows:
                return {"processed": 0, "done": 0, "failed": 0, "remaining": 0}
            try:
                mdb = mongo.get_db()
            except Exception as e:  # cannot even build a client
                mdb, err = None, e
            for r in rows:
                try:
                    if mdb is None:
                        raise err
                    apply_row(mdb, r)
                    db.execute(cnx, "UPDATE sync_outbox SET status='DONE', attempts=attempts+1, last_error=NULL, "
                                    "processed_at=UTC_TIMESTAMP() WHERE id=%s", (r["id"],))
                    done += 1
                except (PyMongoError, Exception) as e:
                    db.execute(cnx, "UPDATE sync_outbox SET status='FAILED', attempts=attempts+1, last_error=%s WHERE id=%s",
                               (str(e)[:480], r["id"]))
                    failed += 1
                    if isinstance(e, ConnectionFailure):
                        break  # MongoDB is down: stop hammering it; the remaining rows stay PENDING
            remaining = db.query(cnx, "SELECT COUNT(*) AS n FROM sync_outbox WHERE status IN ('PENDING','FAILED')")[0]["n"]
            return {"processed": done + failed, "done": done, "failed": failed, "remaining": remaining}


def run_sync_safe():
    try:
        return run_sync()
    except Exception as e:  # background use: log and continue
        print("sync error:", e)
        return None
