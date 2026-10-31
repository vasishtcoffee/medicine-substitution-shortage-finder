"""P0 NoSQL tests: Mongo CRUD through the API, outbox sync, outage tolerance, repair by resync.
Runs on mongomock unless MONGO_TEST_URI points at a real MongoDB (then the validator tests also run)."""
import os

import pytest
from pymongo.errors import ServerSelectionTimeoutError

from api_support import make_client
from helpers import scalar
from support import migrator

REAL_MONGO = bool(os.environ.get("MONGO_TEST_URI"))
needs_real_mongo = pytest.mark.skipif(not REAL_MONGO, reason="needs a real MongoDB (set MONGO_TEST_URI); mongomock has no $jsonSchema validation")


@pytest.fixture
def admin():
    return make_client("admin")


@pytest.fixture
def ph1():
    return make_client("pharmacist1")


@pytest.fixture
def synced(admin, mongo_db, reset_data):
    """Seeded MySQL drained into an empty Mongo."""
    r = admin.post("/sync/run")
    assert r.status_code == 200 and r.json()["remaining"] == 0, r.text
    return mongo_db


# ------------------------------------------------------------------ create / read
def test_sync_creates_one_feed_document_per_inventory_row(synced):
    assert synced["inventory_feed"].count_documents({}) == scalar(migrator(), "SELECT COUNT(*) FROM inventory") == 37
    d = synced["inventory_feed"].find_one({"_id": "ph1:med2"})
    assert d["quantity"] == 8 and d["availability"] == "Low" and d["low_stock"] is True and d["pharmacy_id"] == 1


def test_sync_is_idempotent(admin, synced):
    n_before = synced["inventory_feed"].count_documents({})
    assert admin.post("/sync/resync").json()["remaining"] == 0
    assert admin.post("/sync/resync").json()["remaining"] == 0
    assert synced["inventory_feed"].count_documents({}) == n_before


def test_read_with_filters_and_pagination(admin, synced):
    r = admin.get("/feed/inventory", params={"pharmacy_id": 1, "page_size": 5, "page": 1})
    d = r.json()
    assert d["total"] == 15 and len(d["items"]) == 5 and d["page_size"] == 5
    p3 = admin.get("/feed/inventory", params={"pharmacy_id": 1, "page_size": 5, "page": 3}).json()
    assert len(p3["items"]) == 5 and {i["_id"] for i in p3["items"]}.isdisjoint({i["_id"] for i in d["items"]})
    assert all(i["pharmacy_id"] == 1 for i in d["items"])
    assert admin.get("/feed/inventory", params={"medicine_id": 2}).json()["total"] == 3
    assert admin.get("/feed/inventory/ph1:med2").json()["quantity"] == 8
    assert admin.get("/feed/inventory/ph9:med9").status_code == 404


def test_events_are_created_by_sales_and_filterable(admin, ph1, synced):
    assert ph1.post("/orders/3/complete").status_code == 200       # seed order 3 is APPROVED at pharmacy 1
    ev = admin.get("/feed/events", params={"source": "sale", "pharmacy_id": 1}).json()
    assert ev["total"] == 1 and ev["items"][0]["payload"]["delta"] == -2 and ev["items"][0]["payload"]["order_id"] == 3
    assert admin.get("/feed/events", params={"source": "receipt"}).json()["total"] == 0
    assert admin.get("/feed/events", params={"date_from": "2999-01-01"}).json()["total"] == 0
    assert admin.get("/feed/events", params={"date_from": "2020-01-01", "date_to": "2999-01-01"}).json()["total"] == 1


def test_admin_can_create_manual_event(admin, mongo_db):
    r = admin.post("/feed/events", json={"source": "import", "pharmacy_id": 2, "medicine_id": 1,
                                         "payload": {"supplier": "Demo Supplies", "eta_days": 4, "lots": [{"batch": "X1"}]}, "notes": "unverified"})
    assert r.status_code == 201 and r.json()["_id"].startswith("manual:") and "unverified" in r.json()["flags"]
    assert admin.post("/feed/events", json={"source": "bogus"}).status_code == 422
    assert mongo_db["feed_events"].count_documents({"source": "import"}) == 1


# ------------------------------------------------------------------ update (non-authoritative fields only)
def test_update_only_metadata_notes_flags(admin, synced):
    r = admin.patch("/feed/inventory/ph1:med1", json={"metadata": {"supplier": "Demo Supplies", "shelf": "A3"}, "notes": "check expiry", "flags": ["audit"]})
    assert r.status_code == 200
    d = synced["inventory_feed"].find_one({"_id": "ph1:med1"})
    assert d["metadata"]["shelf"] == "A3" and d["notes"] == "check expiry" and d["flags"] == ["audit"] and d["quantity"] == 120
    assert admin.patch("/feed/inventory/ph1:med1", json={"quantity": 5}).status_code == 422       # quantity is MySQL-owned
    assert admin.patch("/feed/inventory/ph1:med1", json={}).status_code == 422
    assert admin.patch("/feed/inventory/ph9:med9", json={"notes": "x"}).status_code == 404
    assert scalar(migrator(), "SELECT quantity FROM inventory WHERE pharmacy_id=1 AND medicine_id=1") == 120


def test_synced_updates_do_not_wipe_admin_annotations(admin, ph1, synced):
    admin.patch("/feed/inventory/ph1:med1", json={"notes": "keep me", "flags": ["audit"]})
    assert ph1.post("/inventory/receive", json={"pharmacy_id": 1, "medicine_id": 1, "quantity": 10, "batch_no": "N1"}).status_code == 201
    d = synced["inventory_feed"].find_one({"_id": "ph1:med1"})
    assert d["quantity"] == 130 and d["notes"] == "keep me" and d["flags"] == ["audit"] and d["metadata"]["last_batch_no"] == "N1"


def test_event_annotations(admin, synced):
    eid = admin.post("/feed/events", json={"source": "adjustment", "pharmacy_id": 1, "medicine_id": 1}).json()["_id"]
    assert admin.patch(f"/feed/events/{eid}", json={"notes": "reviewed", "flags": ["ok"]}).json()["notes"] == "reviewed"


# ------------------------------------------------------------------ delete / repair
def test_delete_mongo_document_leaves_mysql_untouched_and_resync_recreates_it(admin, synced):
    before = scalar(migrator(), "SELECT quantity FROM inventory WHERE pharmacy_id=2 AND medicine_id=2")
    assert admin.delete("/feed/inventory/ph2:med2").status_code == 200
    assert synced["inventory_feed"].find_one({"_id": "ph2:med2"}) is None
    assert scalar(migrator(), "SELECT quantity FROM inventory WHERE pharmacy_id=2 AND medicine_id=2") == before
    assert admin.delete("/feed/inventory/ph2:med2").status_code == 404
    assert admin.post("/sync/resync").status_code == 200
    assert synced["inventory_feed"].find_one({"_id": "ph2:med2"})["quantity"] == before


def test_delete_event(admin, synced):
    eid = admin.post("/feed/events", json={"source": "import"}).json()["_id"]
    assert admin.delete(f"/feed/events/{eid}").status_code == 200
    assert admin.get(f"/feed/events/{eid}").status_code == 404


# ------------------------------------------------------------------ outage tolerance
class _MongoDown:
    def __getitem__(self, name):
        raise ServerSelectionTimeoutError("simulated: MongoDB is down")


def test_mongo_outage_does_not_roll_back_sale_and_resync_repairs(admin, ph1, synced, monkeypatch):
    from app import mongo
    real = mongo.get_db
    monkeypatch.setattr(mongo, "get_db", lambda: _MongoDown())
    m = migrator()
    before = scalar(m, "SELECT quantity FROM inventory WHERE pharmacy_id=1 AND medicine_id=2")

    r = ph1.post("/orders/3/complete")                                 # sale while MongoDB is down
    assert r.status_code == 200 and r.json()["status"] == "COMPLETED"  # committed regardless
    assert scalar(m, "SELECT quantity FROM inventory WHERE pharmacy_id=1 AND medicine_id=2") == before - 2
    assert scalar(m, "SELECT status FROM orders WHERE id=3") == "COMPLETED"

    out = admin.get("/sync/outbox").json()
    assert out["counts"].get("PENDING", 0) + out["counts"].get("FAILED", 0) >= 1
    assert any(row["last_error"] and "simulated" in row["last_error"] for row in out["rows"] if row["status"] == "FAILED")
    assert synced["inventory_feed"].find_one({"_id": "ph1:med2"})["quantity"] == before          # Mongo is stale, MySQL is right

    monkeypatch.setattr(mongo, "get_db", real)                         # MongoDB comes back
    res = admin.post("/sync/run").json()
    assert res["remaining"] == 0 and res["done"] >= 1
    assert synced["inventory_feed"].find_one({"_id": "ph1:med2"})["quantity"] == before - 2      # repaired
    assert synced["feed_events"].count_documents({"source": "sale"}) == 1


def test_failed_rows_are_retried_a_bounded_number_of_times(admin, ph1, synced, monkeypatch):
    from app import config, mongo
    real = mongo.get_db
    monkeypatch.setattr(mongo, "get_db", lambda: _MongoDown())
    ph1.post("/orders/3/complete")
    for _ in range(config.SYNC_MAX_ATTEMPTS + 2):
        admin.post("/sync/run")
    attempts = scalar(migrator(), "SELECT MAX(attempts) FROM sync_outbox WHERE status='FAILED'")
    assert attempts == config.SYNC_MAX_ATTEMPTS                         # stops at the bound
    monkeypatch.setattr(mongo, "get_db", real)
    res = admin.post("/sync/run").json()                                # never-attempted PENDING rows now go through...
    assert res["remaining"] == 1                                        # ...but the exhausted FAILED row is not retried automatically
    assert scalar(migrator(), "SELECT attempts FROM sync_outbox WHERE status='FAILED'") == config.SYNC_MAX_ATTEMPTS
    r = admin.post("/sync/retry-failed").json()                         # explicit admin action resets and drains it
    assert r["reset"] == 1 and r["remaining"] == 0


def test_feed_api_returns_503_when_mongo_is_down(admin, monkeypatch):
    from app import mongo
    monkeypatch.setattr(mongo, "get_db", lambda: _MongoDown())
    assert admin.get("/feed/inventory").status_code == 503


# ------------------------------------------------------------------ real MongoDB only
@needs_real_mongo
def test_validator_rejects_bad_documents_and_init_is_idempotent(mongo_db):
    from app import mongo
    first = mongo.ensure_collections(mongo_db)
    second = mongo.ensure_collections(mongo_db)
    assert set(first) == set(second) == {"inventory_feed", "feed_events"}
    idx = mongo_db["inventory_feed"].index_information()
    assert {"ix_feed_pharmacy", "ix_feed_medicine", "ix_feed_last_updated"} <= set(idx)
    from pymongo.errors import WriteError
    with pytest.raises(WriteError):
        mongo_db["inventory_feed"].insert_one({"_id": "bad", "quantity": -1})
    with pytest.raises(WriteError):
        mongo_db["feed_events"].insert_one({"_id": "e1", "source": "nonsense", "occurred_at": 1, "payload": {}})
