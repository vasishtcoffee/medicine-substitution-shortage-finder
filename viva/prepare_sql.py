"""Render existing app DDL for mysql/Workbench, without connecting or executing it.

Run from repository root: python viva/prepare_sql.py medsub_viva_20261119
Then follow viva/README.md. Output is deliberately outside version control.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from migrate import MIG_DIR, render

name = sys.argv[1] if len(sys.argv) == 2 else ""
if not re.fullmatch(r"medsub_viva_[a-z0-9_]+", name):
    raise SystemExit("Use a dedicated medsub_viva_<suffix> schema name")
out = ROOT / "work" / "viva-schema.sql"
out.parent.mkdir(exist_ok=True)
parts = [f"-- AFFECTS ONLY {name}. Run once in a fresh bootstrapped schema.\nUSE `{name}`;",
         "CREATE TABLE schema_migrations (version VARCHAR(100) PRIMARY KEY, applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"]
for path in sorted(MIG_DIR.glob("*.sql"), key=lambda p: (not p.name.startswith("V"), p.name)):
    parts.append(f"-- {path.name}\n" + render(path.read_text(encoding="utf-8"), name))
    if path.name.startswith("V"):
        parts.append(f"INSERT INTO schema_migrations(version) VALUES ('{path.name}');")
out.write_text("\n\n".join(parts), encoding="utf-8")
print(f"Generated {out}; not executed. Creates existing app objects and grants in {name}.")
