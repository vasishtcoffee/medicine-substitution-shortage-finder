"""MySQL access: raw parameterised SQL, one connection pool per MySQL role/account.

Request identity reaches MySQL as session variables (@app_user_id, @app_role, @app_pharmacy_id) that are set on
checkout from the VERIFIED identity and cleared (and the connection reset) before the connection returns to the pool.
"""
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Optional

import mysql.connector
from mysql.connector import errors, pooling

from . import config

_pools: dict[str, pooling.MySQLConnectionPool] = {}


@dataclass(frozen=True)
class Identity:
    id: int
    email: str
    full_name: str
    role: str  # patient | pharmacist | admin
    pharmacy_id: Optional[int] = None


def _pool(kind: str) -> pooling.MySQLConnectionPool:
    key = f"{config.MYSQL_DATABASE}:{kind}"
    if key not in _pools:
        prefix, _role = config.ACCOUNTS[kind]
        _pools[key] = pooling.MySQLConnectionPool(
            pool_name=f"medsub_{abs(hash(key))}", pool_size=6, pool_reset_session=True,
            host=config.MYSQL_HOST, port=config.MYSQL_PORT, database=config.MYSQL_DATABASE,
            user=config.env(prefix + "_USER"), password=config.env(prefix + "_PASSWORD"),
            autocommit=True, charset="utf8mb4")
    return _pools[key]


def reset_pools():
    for p in _pools.values():
        try:
            p._remove_connections()
        except Exception:
            pass
    _pools.clear()


_CLEAR = "SET @app_user_id = NULL, @app_role = NULL, @app_pharmacy_id = NULL"


@contextmanager
def session(kind: str, identity: Optional[Identity] = None):
    """Check out a connection for `kind` ('patient'|'pharmacist'|'admin'|'auth'), verify the active MySQL role,
    install the request context, and always clear it again."""
    cnx = _pool(kind).get_connection()
    try:
        cur = cnx.cursor()
        cur.execute("SELECT CURRENT_ROLE()")
        active = cur.fetchone()[0] or ""
        expected = config.ACCOUNTS[kind][1]
        if f"`{expected}`" not in active:
            raise RuntimeError(f"Connection for '{kind}' has role {active!r}, expected {expected}")
        if identity is not None:
            cur.execute("SET @app_user_id = %s, @app_role = %s, @app_pharmacy_id = %s",
                        (identity.id, identity.role, identity.pharmacy_id))
        else:
            cur.execute(_CLEAR)
        cur.close()
        yield cnx
    finally:
        try:
            c = cnx.cursor()
            c.execute(_CLEAR)
            c.close()
        except Exception:
            pass
        cnx.close()  # back to the pool (pool_reset_session also resets the session)


def query(cnx, sql: str, params: tuple | list = ()) -> list[dict[str, Any]]:
    cur = cnx.cursor(dictionary=True)
    try:
        cur.execute(sql, params)
        return cur.fetchall() if cur.with_rows else []
    finally:
        cur.close()


def execute(cnx, sql: str, params: tuple | list = ()) -> int:
    cur = cnx.cursor()
    try:
        cur.execute(sql, params)
        return cur.rowcount
    finally:
        cur.close()


def call(cnx, proc: str, args: tuple | list = ()) -> list[list[dict[str, Any]]]:
    """CALL a stored procedure; returns the list of result sets (each a list of dict rows)."""
    cur = cnx.cursor(dictionary=True)
    try:
        cur.callproc(proc, tuple(args))
        return [r.fetchall() for r in cur.stored_results()]
    finally:
        cur.close()


def call_one(cnx, proc: str, args: tuple | list = ()) -> list[dict[str, Any]]:
    res = call(cnx, proc, args)
    return res[0] if res else []


def with_retry(fn, attempts: int = 3):
    """Re-run a whole unit of work after an InnoDB deadlock (1213) or lock-wait timeout (1205)."""
    for i in range(attempts):
        try:
            return fn()
        except errors.DatabaseError as e:
            if e.errno in (1213, 1205) and i < attempts - 1:
                time.sleep(0.05 * (i + 1))
                continue
            raise
