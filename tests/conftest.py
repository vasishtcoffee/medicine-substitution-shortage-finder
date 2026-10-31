"""Shared fixtures. Tests run against a throw-away MySQL database `medsub_test` (rebuilt once per session)
and an in-memory MongoDB double (mongomock) unless MONGO_TEST_URI points at a real MongoDB."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

os.environ["MYSQL_DATABASE"] = "medsub_test"
os.environ["MONGO_DATABASE"] = "medsub_feed_test"
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
    """Drop and rebuild the test database: bootstrap -> migrate -> seed."""
    c = root_conn()
    c.cursor().execute(f"DROP DATABASE IF EXISTS `{TEST_DB}`")
    c.close()
    bootstrap_db.main(TEST_DB)
    migrate.migrate(TEST_DB, verbose=False)
    seed_mod.seed(TEST_DB, verbose=False)
    yield TEST_DB


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
def mongo_db(monkeypatch):
    """A clean MongoDB database for the test (mongomock by default, real MongoDB if MONGO_TEST_URI is set)."""
    from app import mongo
    uri = os.environ.get("MONGO_TEST_URI")
    if uri:
        import pymongo
        client = pymongo.MongoClient(uri, tz_aware=True, serverSelectionTimeoutMS=2000)
        client.drop_database("medsub_feed_test")
        d = client["medsub_feed_test"]
    else:
        import mongomock
        d = mongomock.MongoClient(tz_aware=True)["medsub_feed_test"]
    monkeypatch.setattr(mongo, "get_db", lambda: d)
    return d
