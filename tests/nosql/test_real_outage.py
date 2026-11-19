"""Real mongod outage/recovery; never stops an existing/shared application server."""
import os
from pathlib import Path
import uuid

from pymongo import MongoClient
import pytest

from app import mongo
from api_support import make_client
from disposable_databases import MongoServer
from helpers import scalar
from support import migrator


@pytest.fixture
def admin():
    return make_client("admin")


@pytest.fixture
def ph1():
    return make_client("pharmacist1")


def test_real_mongo_outage_preserves_sale_and_recovers(admin, ph1, reset_data, monkeypatch):
    directory = Path(os.environ.get("MEDSUB_TEST_WORK", "V:/Codex/medsub-checks")) / f"outage_{uuid.uuid4().hex[:12]}"
    server = MongoServer(directory)
    name = "medsub_outage_test_" + uuid.uuid4().hex[:12]
    client = None
    created = False
    try:
        server.start()
        client = MongoClient(server.uri, serverSelectionTimeoutMS=500, tz_aware=True)
        assert name not in client.list_database_names()
        real = client[name]
        mongo.ensure_collections(real)
        created = True
        monkeypatch.setattr(mongo, "get_db", lambda: real)  # real server, not an in-memory double
        assert admin.post("/sync/run").json()["remaining"] == 0
        cnx = migrator()
        query = "SELECT quantity FROM inventory WHERE pharmacy_id=1 AND medicine_id=2"
        before = scalar(cnx, query)
        print(f"Stopping ONLY disposable mongod PID {server.process.pid}; data directory {server.data}")
        server.stop()
        assert server.process.poll() is not None
        assert admin.get("/feed/inventory").status_code == 503
        result = ph1.post("/orders/3/complete")
        assert result.status_code == 200 and result.json()["status"] == "COMPLETED"
        assert scalar(cnx, query) == before - 2
        assert scalar(cnx, "SELECT COUNT(*) FROM sync_outbox WHERE status IN ('PENDING','FAILED')") > 0
        server.start()  # same on-disk DB, same port: actual recovery, no fake success
        client.admin.command("ping")
        result = admin.post("/sync/run")
        assert result.status_code == 200 and result.json()["remaining"] == 0
        assert real.inventory_feed.find_one({"_id": "ph1:med2"})["quantity"] == before - 2
        assert real.feed_events.count_documents({"source": "sale"}) == 1
    finally:
        if client and created:
            if server.process.poll() is not None:
                server.start()
            print(f"Cleanup removes ONLY newly created MongoDB database `{name}` on {server.uri}")
            client.drop_database(name)
        if client:
            client.close()
        server.stop()
