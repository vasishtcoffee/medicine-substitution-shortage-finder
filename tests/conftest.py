"""Per-run databases. Never drop or reuse a database that existed before the run."""
import os
import re
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

RUN_ID = os.environ.setdefault("MEDSUB_TEST_RUN_ID", uuid.uuid4().hex[:12])
if not re.fullmatch(r"[a-z0-9_]{1,32}", RUN_ID):
    raise RuntimeError("MEDSUB_TEST_RUN_ID must contain 1–32 lowercase letters/digits/underscores")
os.environ["MYSQL_DATABASE"] = f"medsub_test_{RUN_ID}"
os.environ["MONGO_DATABASE"] = f"medsub_feed_test_{RUN_ID}"
os.environ["SYNC_BACKGROUND"] = "false"

import mysql.connector  # noqa: E402
import pytest  # noqa: E402

from envload import load_env  # noqa: E402

load_env()

import bootstrap_db  # noqa: E402
import migrate  # noqa: E402
import seed as seed_mod  # noqa: E402

from support import TEST_DB, migrator, direct  # noqa: E402,F401


def root_conn():
    return mysql.connector.connect(
        host=os.environ["MYSQL_HOST"], port=int(os.environ["MYSQL_PORT"]),
        user=os.environ["MYSQL_ROOT_USER"], password=os.environ["MYSQL_ROOT_PASSWORD"], autocommit=True)


@pytest.fixture(scope="session", autouse=True)
def database():
    """Create once, then remove only our newly created schema and Mongo database."""
    c = root_conn()
    cur = c.cursor()
    cur.execute("SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s", (TEST_DB,))
    if cur.fetchone():
        c.close()
        raise RuntimeError(f"Refusing to reuse or delete pre-existing schema {TEST_DB}")
    mongo_client = None
    mongo_name = os.environ["MONGO_DATABASE"]
    if os.environ.get("MONGO_TEST_URI"):
        from pymongo import MongoClient
        mongo_client = MongoClient(os.environ["MONGO_TEST_URI"], serverSelectionTimeoutMS=2000, tz_aware=True)
        mongo_client.admin.command("ping")
        if mongo_name in mongo_client.list_database_names():
            c.close()
            mongo_client.close()
            raise RuntimeError(f"Refusing to reuse or delete pre-existing Mongo database {mongo_name}")
    print(f"Creating test databases: MySQL {TEST_DB}; MongoDB {mongo_name if mongo_client else 'mongomock only'}")
    cur.execute(f"CREATE DATABASE `{TEST_DB}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
    c.close()
    try:
        bootstrap_db.main(TEST_DB)
        migrate.migrate(TEST_DB, verbose=False)
        seed_mod.seed(TEST_DB, verbose=False)
        yield TEST_DB
    finally:
        from app import db
        from support import _KEEP
        db.reset_pools()
        for connection in _KEEP:
            connection.close()
        _KEEP.clear()
        print(f"Cleanup removes ONLY this run's MySQL database `{TEST_DB}`"
              + (f" and MongoDB database `{mongo_name}`" if mongo_client else ""))
        c = root_conn()
        c.cursor().execute(f"DROP DATABASE `{TEST_DB}`")
        c.close()
        if mongo_client:
            mongo_client.drop_database(mongo_name)
            mongo_client.close()


RESET_TABLES = ["sync_outbox", "substitution_reviews", "inventory_movements", "low_stock_alerts",
                "order_items", "orders", "inventory"]


@pytest.fixture
def reset_data():
    """Return the transactional data to its seeded state (fast; schema untouched)."""
    cnx = migrate.connect(TEST_DB)
    cur = cnx.cursor()
    cur.execute("SET FOREIGN_KEY_CHECKS = 0")
    for t in RESET_TABLES:
        cur.execute(f"TRUNCATE TABLE {t}")
    cur.execute("SET FOREIGN_KEY_CHECKS = 1")
    cnx.close()
    seed_mod.seed(TEST_DB, verbose=False)


@pytest.fixture
def mongo_db(monkeypatch, database):
    """A clean MongoDB database for the test (mongomock by default, real MongoDB if MONGO_TEST_URI is set)."""
    from app import mongo
    uri = os.environ.get("MONGO_TEST_URI")
    if uri:
        import pymongo
        client = pymongo.MongoClient(uri, tz_aware=True, serverSelectionTimeoutMS=2000)
        d = client[os.environ["MONGO_DATABASE"]]
        # This database was checked absent and reserved by the session fixture.
        for name in ("inventory_feed", "feed_events"):
            d[name].delete_many({})
    else:
        import mongomock
        d = mongomock.MongoClient(tz_aware=True)[os.environ["MONGO_DATABASE"]]
    monkeypatch.setattr(mongo, "get_db", lambda: d)
    yield d
    if uri:
        client.close()


def pytest_collection_modifyitems(items):
    # Existing fault-injection tests intentionally use _MongoDown, not a real outage.
    names = {"test_mongo_outage_does_not_roll_back_sale_and_resync_repairs",
             "test_failed_rows_are_retried_a_bounded_number_of_times",
             "test_feed_api_returns_503_when_mongo_is_down"}
    for item in items:
        if item.name in names:
            item.add_marker(pytest.mark.stub_mongo)
