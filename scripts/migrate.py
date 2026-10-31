"""Idempotent migration runner (plain .sql files, no ORM).

  V###__name.sql  versioned: applied once, recorded in schema_migrations
  R__name.sql     repeatable: re-applied on every run (routines, views, triggers, grants)

Handles the mysql-client 'DELIMITER' command itself, because drivers do not understand it.
Placeholders: {{DB}} -> database name, {{DEFINER}} -> `definer`@`host`.

Usage: python scripts/migrate.py [database_name]
"""
import re
import sys
from pathlib import Path

import mysql.connector

from envload import ROOT, env, load_env

load_env()
MIG_DIR = ROOT / "database" / "migrations"


def split_statements(text):
    """Split a SQL script into statements, honouring DELIMITER changes."""
    delim, buf, out = ";", [], []
    for line in text.splitlines():
        m = re.match(r"^\s*DELIMITER\s+(\S+)\s*$", line, re.I)
        if m:
            delim = m.group(1)
            continue
        buf.append(line)
        joined = "\n".join(buf).rstrip()
        if joined.endswith(delim):
            stmt = joined[: -len(delim)].strip()
            if stmt and not all(l.strip().startswith("--") or not l.strip() for l in stmt.splitlines()):
                out.append(stmt)
            buf = []
    rest = "\n".join(buf).strip()
    if rest and not all(l.strip().startswith("--") or not l.strip() for l in rest.splitlines()):
        out.append(rest)
    return out


def connect(db):
    return mysql.connector.connect(
        host=env("MYSQL_HOST", "127.0.0.1"), port=int(env("MYSQL_PORT", "3306")),
        user=env("MIGRATOR_USER"), password=env("MIGRATOR_PASSWORD"), database=db, autocommit=True)


def render(sql, db):
    host = env("APP_ACCOUNT_HOST", "%")
    definer = f"`{env('DEFINER_USER', 'medsub_definer')}`@`{host}`"
    return (sql.replace("{{DB}}", db).replace("{{DEFINER}}", definer)
               .replace("{{HOST}}", host))


def migrate(db=None, verbose=True):
    db = db or env("MYSQL_DATABASE", "medsub")
    cnx = connect(db)
    cur = cnx.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS schema_migrations ("
                "version VARCHAR(100) NOT NULL PRIMARY KEY, applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)")
    cur.execute("SELECT version FROM schema_migrations")
    applied = {r[0] for r in cur.fetchall()}
    files = sorted(MIG_DIR.glob("*.sql"), key=lambda p: (0 if p.name.startswith("V") else 1, p.name))
    for f in files:
        repeatable = f.name.startswith("R__")
        if not repeatable and f.name in applied:
            if verbose:
                print(f"skip   {f.name} (already applied)")
            continue
        for stmt in split_statements(render(f.read_text(encoding="utf-8"), db)):
            try:
                cur.execute(stmt)
                while cur.nextset():
                    pass
            except mysql.connector.Error as e:
                raise SystemExit(f"FAILED in {f.name}: {e}\n--- statement ---\n{stmt[:600]}")
        if not repeatable:
            cur.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (f.name,))
        if verbose:
            print(f"apply  {f.name}")
    cnx.close()


if __name__ == "__main__":
    migrate(sys.argv[1] if len(sys.argv) > 1 else None)
