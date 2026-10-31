"""Plain helpers shared by tests (kept out of conftest.py so test modules can import them safely)."""
import os

import mysql.connector

import migrate

TEST_DB = "medsub_test"


def direct(kind, user_id=None, role=None, pharmacy_id=None):
    """A raw connection for a backend service account (bypassing the API), optionally with a request context."""
    from app import config
    prefix = config.ACCOUNTS[kind][0]
    cnx = mysql.connector.connect(
        host=config.MYSQL_HOST, port=config.MYSQL_PORT, database=TEST_DB, autocommit=True,
        user=os.environ[prefix + "_USER"], password=os.environ[prefix + "_PASSWORD"])
    _KEEP.append(cnx)
    if role:
        cur = cnx.cursor()
        cur.execute("SET @app_user_id=%s, @app_role=%s, @app_pharmacy_id=%s", (user_id, role, pharmacy_id))
        cur.close()
    return cnx


_KEEP = []  # keep connections referenced so they are not closed by garbage collection mid-test


def migrator():
    c = migrate.connect(TEST_DB)
    _KEEP.append(c)
    return c
