# Rubric coverage matrix

Status "done" means the evidence exists **and was executed** (see `TESTING.md`). "partial" explains exactly what is missing. Owners follow `TEAM_CONTRIBUTIONS.md` (A = relational core, B = identity/catalog/NoSQL).

| # | Item | Marks | Owner | Implementation (file / object / endpoint / screen) | Test | Demo step | Status |
|---|---|---|---|---|---|---|---|
| 1 | ER diagram | 2 | A | `docs/DESIGN.md` §4 (generated Mermaid), `docs/SCHEMA_REFERENCE.md`, `scripts/check_schema_docs.py` | `python scripts/check_schema_docs.py` | — | done (no exported image; Mermaid renders on GitHub) |
| 2 | Relational schema, keys, constraints | 3 | A | `docs/DESIGN.md` §5, generated `docs/SCHEMA_REFERENCE.md` | check script | — | done |
| 3 | DDL with constraints | 4 | A | `database/migrations/V001__core_schema.sql`, `V002__alter_constraints.sql` | `tests/sql/test_schema_and_constraints.py` (31) | 19 | done (run on MySQL 8.0.33; 8.4 not run) |
| 4 | NoSQL database creation | 4 | B | `backend/app/mongo.py::ensure_collections`, `scripts/init_mongo.py` | `tests/nosql::test_validator_rejects_bad_documents_and_init_is_idempotent` | 15 | done (verified on real MongoDB 7.0.14) |
| 5 | Technology justification | 1 | both | `docs/DESIGN.md` §3 | — | — | done |
| 6 | DML | 4 | A | `database/sql/dml_demo.sql`, runner `scripts/run_sql_demo.py` | output `docs/sql_output/dml_demo.txt` | — | done |
| 7 | JOIN, nested, correlated, recursive | 4 | A | `database/sql/queries.sql`; Admin → SQL Demo | `tests/sql/test_candidates_and_queries.py::test_query_library_runs…`, `docs/sql_output/queries.txt` | 13 | done |
| 8 | Procedure/function, trigger, CTE | 6 | A | `sp_equivalent_candidates`, `sp_complete_order`, `fn_availability_band`, triggers, `cte_pharmacy_stock_summary`, `cte_category_tree` (`R__*.sql`, `advanced.sql`) | `tests/sql/*` | 5, 9–11, 13 | done |
| 9 | NoSQL read, update, delete | 7 | B | `backend/app/routers/feed.py`, `sync.py`; Feed Lab screen | `tests/nosql/test_feed_and_sync.py` | 15–18 | done (mongomock and real MongoDB 7.0.14) |
| 10 | Next.js interface | 3 | both | `frontend/app/*` (7 screens) | lint, tsc, build, vitest; browser spot-check | 1–18 | done (full click-through of every screen not driven in a browser) |
| 11 | Backend/API and DB integration | 2 | B | `backend/app`, `docs/API.md` | `tests/api` | — | done |
| 12 | Authentication and DB-level RBAC | 4 | B (SQL grants: A) | `scripts/bootstrap_db.py`, `R__10`, `R__20`, `R__90`, `security.py`, `db.py`, `docs/SECURITY_RBAC.md` | `tests/security` (22), API 401/403 | 2, 8, 12 | done |
| 13 | Documentation and Git/GitHub | 2 | both | `README.md`, `docs/*` | `test_docs_match.py` | — | **partial** — docs done; **no Git history/PRs/reviews exist yet** (needs the two members) |
| 14 | Originality, contribution, viva | 4 | both | `docs/VIVA_GUIDE.md` (with live-modification drills), `docs/TEAM_CONTRIBUTIONS.md` | — | — | **partial** — guide done; contribution evidence depends on real commits by both members |
