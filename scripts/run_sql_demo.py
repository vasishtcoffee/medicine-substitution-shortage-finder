"""Run a demo .sql file statement by statement and print results (used for the expected-output evidence).

Usage: python scripts/run_sql_demo.py database/sql/dml_demo.sql [--out docs/dml_demo_output.txt]

Runs as the migrator account with an admin request context (@app_role='admin', @app_user_id=1).
"""
import re
import sys
from pathlib import Path

import mysql.connector

from envload import ROOT, env, load_env
from migrate import connect, split_statements

load_env()


def parse_blocks(text: str):
    """Yield (name, purpose, runnable, sql) for each '-- @name:' block."""
    blocks, cur = [], None
    for line in text.splitlines():
        m = re.match(r"^--\s*@name:\s*(\S+)", line)
        if m:
            cur = {"name": m.group(1), "meta": {}, "lines": []}
            blocks.append(cur)
            continue
        if cur is None:
            continue
        m = re.match(r"^--\s*@(\w+):\s*(.*)$", line)
        if m:
            cur["meta"][m.group(1)] = m.group(2).strip()
        else:
            cur["lines"].append(line)
    return blocks


def main():
    args = sys.argv[1:]
    out_path = None
    if "--out" in args:
        i = args.index("--out")
        out_path = Path(args[i + 1])
        del args[i:i + 2]
    path = Path(args[0])
    text = path.read_text(encoding="utf-8")
    cnx = connect(env('MYSQL_DATABASE', 'medsub'))
    cur = cnx.cursor()
    cur.execute("SET @app_user_id = 1, @app_role = 'admin', @app_pharmacy_id = NULL")
    lines = [f"== {path.name} =="]
    failures = 0
    for b in parse_blocks(text):
        lines.append(f"\n--- {b['name']} ---")
        for k in ("purpose", "why", "expected"):
            if k in b["meta"]:
                lines.append(f"{k}: {b['meta'][k]}")
        body = "\n".join(b["lines"])
        expect_err = None
        m = re.search(r"--\s*EXPECT ERROR\s+(\d+)", body)
        if m:
            expect_err = int(m.group(1))
        for stmt in split_statements(body):
            lines.append(f"> {' '.join(stmt.split())[:160]}")
            try:
                cur.execute(stmt)
                if cur.with_rows:
                    rows = cur.fetchall()
                    cols = [d[0] for d in cur.description]
                    lines.append("  " + " | ".join(cols))
                    for r in rows:
                        lines.append("  " + " | ".join("NULL" if v is None else str(v) for v in r))
                    while cur.nextset():
                        if cur.with_rows:
                            rows = cur.fetchall()
                            cols = [d[0] for d in cur.description]
                            lines.append("  -- next result set --")
                            lines.append("  " + " | ".join(cols))
                            for r in rows:
                                lines.append("  " + " | ".join("NULL" if v is None else str(v) for v in r))
                else:
                    lines.append(f"  OK ({cur.rowcount} rows affected)")
                if expect_err:
                    lines.append(f"  !! expected error {expect_err} but statement succeeded")
                    failures += 1
            except mysql.connector.Error as e:
                if expect_err and e.errno == expect_err:
                    lines.append(f"  EXPECTED ERROR {e.errno}: {e.msg}")
                else:
                    lines.append(f"  !! UNEXPECTED ERROR {e.errno}: {e.msg}")
                    failures += 1
    cnx.close()
    out = "\n".join(lines)
    print(out)
    if out_path:
        out_path.write_text(out + "\n", encoding="utf-8")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
