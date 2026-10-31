"""Keep the ER diagram / schema docs honest (rubric 1 and 2).

  python scripts/check_schema_docs.py --write   regenerate docs/SCHEMA_REFERENCE.md and the ER block in docs/DESIGN.md
                                                from information_schema (the live MySQL schema)
  python scripts/check_schema_docs.py           CHECK: every table and column of the live schema is in the Mermaid ER
                                                diagram in docs/DESIGN.md and vice versa; exit 1 on any difference
"""
import re
import sys
from collections import defaultdict

import mysql.connector

from envload import ROOT, env, load_env
from migrate import connect

load_env()
DESIGN = ROOT / "docs" / "DESIGN.md"
REF = ROOT / "docs" / "SCHEMA_REFERENCE.md"
START, END = "<!-- ER:START -->", "<!-- ER:END -->"
SKIP = {"schema_migrations"}


def load(db):
    cnx = connect(db)
    c = cnx.cursor(dictionary=True)
    q = lambda sql, p=(): (c.execute(sql, p), c.fetchall())[1]  # noqa: E731
    cols = q("SELECT TABLE_NAME t, COLUMN_NAME c, DATA_TYPE d, COLUMN_TYPE ct, IS_NULLABLE n, COLUMN_KEY k, COLUMN_DEFAULT dflt, EXTRA e, "
             "GENERATION_EXPRESSION g FROM information_schema.columns WHERE table_schema=%s AND TABLE_NAME IN "
             "(SELECT TABLE_NAME FROM information_schema.tables WHERE table_schema=%s AND TABLE_TYPE='BASE TABLE') "
             "ORDER BY TABLE_NAME, ORDINAL_POSITION", (db, db))
    fks = q("SELECT k.CONSTRAINT_NAME name, k.TABLE_NAME child, k.COLUMN_NAME ccol, k.REFERENCED_TABLE_NAME parent, "
            "k.REFERENCED_COLUMN_NAME pcol, r.DELETE_RULE del FROM information_schema.key_column_usage k "
            "JOIN information_schema.referential_constraints r ON r.constraint_schema=k.table_schema AND r.constraint_name=k.constraint_name "
            "WHERE k.table_schema=%s AND k.REFERENCED_TABLE_NAME IS NOT NULL ORDER BY k.CONSTRAINT_NAME, k.ORDINAL_POSITION", (db,))
    uniq = q("SELECT tc.TABLE_NAME t, tc.CONSTRAINT_NAME name, tc.CONSTRAINT_TYPE ty, GROUP_CONCAT(k.COLUMN_NAME ORDER BY k.ORDINAL_POSITION) cols "
             "FROM information_schema.table_constraints tc JOIN information_schema.key_column_usage k "
             "ON k.constraint_schema=tc.constraint_schema AND k.table_name=tc.table_name AND k.constraint_name=tc.constraint_name "
             "WHERE tc.table_schema=%s AND tc.CONSTRAINT_TYPE IN ('PRIMARY KEY','UNIQUE') GROUP BY tc.TABLE_NAME, tc.CONSTRAINT_NAME, tc.CONSTRAINT_TYPE", (db,))
    checks = q("SELECT tc.TABLE_NAME t, cc.CONSTRAINT_NAME name, cc.CHECK_CLAUSE clause FROM information_schema.check_constraints cc "
               "JOIN information_schema.table_constraints tc ON tc.constraint_schema=cc.constraint_schema AND tc.constraint_name=cc.constraint_name "
               "WHERE cc.constraint_schema=%s AND tc.CONSTRAINT_TYPE='CHECK' ORDER BY tc.TABLE_NAME, cc.CONSTRAINT_NAME", (db,))
    cnx.close()
    return cols, fks, uniq, checks


def build(db):
    cols, fks, uniq, checks = load(db)
    tables = defaultdict(list)
    for r in cols:
        if r["t"] not in SKIP:
            tables[r["t"]].append(r)
    fk_cols = {(f["child"], f["ccol"]) for f in fks}
    uk_single = {(u["t"], u["cols"]) for u in uniq if u["ty"] == "UNIQUE" and "," not in u["cols"]}
    pk_single = {(u["t"], u["cols"]) for u in uniq if u["ty"] == "PRIMARY KEY" and "," not in u["cols"]}
    lines = ["erDiagram"]
    # relationships (one line per FK constraint)
    done = set()
    for f in fks:
        if f["name"] in done or f["child"] in SKIP:
            continue
        done.add(f["name"])
        cols_of = [x["ccol"] for x in fks if x["name"] == f["name"]]
        nullable = any(c["n"] == "YES" for c in tables[f["child"]] if c["c"] in cols_of)
        one_to_one = len(cols_of) == 1 and ((f["child"], cols_of[0]) in uk_single or (f["child"], cols_of[0]) in pk_single)
        left = "|o" if nullable else "||"
        right = "o|" if one_to_one else "o{"
        lines.append(f'    {f["parent"]} {left}--{right} {f["child"]} : "{f["name"].removeprefix("fk_")}"')
    for t, rows in tables.items():
        lines.append(f"    {t} {{")
        for r in rows:
            keys = []
            if r["k"] == "PRI":
                keys.append("PK")
            if (t, r["c"]) in fk_cols:
                keys.append("FK")
            if (t, r["c"]) in uk_single:
                keys.append("UK")
            lines.append(f'        {r["d"]} {r["c"]}' + (f" {','.join(keys)}" if keys else ""))
        lines.append("    }")
    return "\n".join(lines), tables, fks, uniq, checks


def reference_md(db, mermaid, tables, fks, uniq, checks):
    out = ["# Schema reference (generated)", "",
           "Generated from the live MySQL schema by `python scripts/check_schema_docs.py --write`. Do not edit by hand.", "",
           "```mermaid", mermaid, "```", ""]
    for t, rows in tables.items():
        out += [f"## `{t}`", "", "| Column | Type | Null | Key | Default | Notes |", "|---|---|---|---|---|---|"]
        for r in rows:
            note = []
            if r["g"]:
                note.append(f"GENERATED: `{r['g']}`")
            if r["e"] and "auto_increment" in r["e"]:
                note.append("AUTO_INCREMENT")
            for f in fks:
                if f["child"] == t and f["ccol"] == r["c"]:
                    note.append(f"FK -> {f['parent']}.{f['pcol']} (ON DELETE {f['del']})")
            out.append(f"| {r['c']} | `{r['ct']}` | {'YES' if r['n'] == 'YES' else 'NOT NULL'} | {r['k'] or ''} | {r['dflt'] if r['dflt'] is not None else ''} | {'; '.join(note)} |")
        cons = [f"- **{u['ty']}** `{u['name']}` ({u['cols']})" for u in uniq if u["t"] == t]
        cons += [f"- **CHECK** `{c['name']}`: `{c['clause']}`" for c in checks if c["t"] == t]
        if cons:
            out += ["", "Constraints:", *cons]
        out.append("")
    return "\n".join(out)


def parse_mermaid(text):
    """Return {table: {columns}} from the ER block in DESIGN.md."""
    m = re.search(re.escape(START) + r"\s*```mermaid\n(.*?)```", text, re.S)
    if not m:
        raise SystemExit("ER block not found in docs/DESIGN.md (run with --write)")
    tables, cur = {}, None
    for line in m.group(1).splitlines():
        s = line.strip()
        mt = re.match(r"^(\w+)\s*\{$", s)
        if mt:
            cur = mt.group(1)
            tables[cur] = set()
        elif s == "}":
            cur = None
        elif cur and s:
            parts = s.split()
            if len(parts) >= 2:
                tables[cur].add(parts[1])
    return tables


def main():
    db = env("MYSQL_DATABASE", "medsub")
    mermaid, tables, fks, uniq, checks = build(db)
    if "--write" in sys.argv:
        REF.write_text(reference_md(db, mermaid, tables, fks, uniq, checks), encoding="utf-8")
        text = DESIGN.read_text(encoding="utf-8") if DESIGN.exists() else f"{START}\n{END}\n"
        block = f"{START}\n```mermaid\n{mermaid}\n```\n{END}"
        if START in text:
            text = re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _: block, text, flags=re.S)
        else:
            text += "\n" + block + "\n"
        DESIGN.write_text(text, encoding="utf-8")
        print(f"wrote {REF.name} and the ER block in {DESIGN.name} ({len(tables)} tables)")
        return
    documented = parse_mermaid(DESIGN.read_text(encoding="utf-8"))
    live = {t: {r["c"] for r in rows} for t, rows in tables.items()}
    problems = []
    for t in sorted(set(live) | set(documented)):
        if t not in documented:
            problems.append(f"table {t} is in MySQL but not in the ER diagram")
        elif t not in live:
            problems.append(f"table {t} is in the ER diagram but not in MySQL")
        else:
            for c in sorted(live[t] - documented[t]):
                problems.append(f"column {t}.{c} missing from the ER diagram")
            for c in sorted(documented[t] - live[t]):
                problems.append(f"column {t}.{c} in the ER diagram does not exist in MySQL")
    if problems:
        print("ER diagram does NOT match the schema:")
        print("\n".join(" - " + p for p in problems))
        sys.exit(1)
    print(f"OK: ER diagram matches the live schema ({len(live)} tables, {sum(len(v) for v in live.values())} columns)")


if __name__ == "__main__":
    main()
