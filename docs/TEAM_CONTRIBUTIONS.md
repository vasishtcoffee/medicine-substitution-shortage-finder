# Team contributions and Git workflow

> **Fill in before submission.** Names and GitHub users were not provided, so none are invented here. This repository was produced in a single AI-assisted working session by one authenticated user; it contains **no commits** yet. Do not fabricate history: each member must commit their own slice from their own account.

| | Member A | Member B |
|---|---|---|
| Name / GitHub user | `<fill>` | `<fill>` |
| Slice | Relational core and inventory/sale flow | Identity, catalog, search and NoSQL |

## Vertical slices (database + API + UI each)

| Member A | Member B |
|---|---|
| ER, DDL, constraints, seed, DML and query library (rubric 1, 2, 3, 6, 7): `database/migrations/V*.sql`, `database/seed`, `database/sql/*`, `scripts/check_schema_docs.py` | FastAPI shell, config, errors, OpenAPI (11): `backend/app/{main,config,errors}.py` |
| `sp_equivalent_candidates`, `sp_complete_order`, triggers, CTEs (8): `R__30`, `R__40`, `R__50`, `advanced.sql` | Auth: hashing, JWT cookie, login/logout, dependencies (12): `security.py`, `routers/auth.py` |
| **MySQL roles/grants + routine authorization (SQL side):** `bootstrap_db.py`, `R__10`, `R__90` | **Request-to-DB identity context + all security tests:** `db.py`, `tests/security/*` |
| Orders and inventory routers + screens (4, 5): `routers/{orders,inventory,alerts}.py`, `app/orders`, `app/inventory` | Catalog/admin router + screen (6); search & candidates API + screen (3): `routers/{medicines,search}.py`, `app/admin`, `app/search` |
| `sync_outbox` writes (`sp_write_outbox`) and the worker `sync.py` | **MongoDB collections, validation, indexes, CRUD API, Feed Lab, Mongo tests (4, 9):** `mongo.py`, `routers/feed.py`, `app/feed-lab`, `tests/nosql` |
| SQL Demo panel (backend `routers/sqldemo.py`) and SQL tests `tests/sql/*` | Next.js shell: layout, proxy, login, dashboard (1, 2, 10): `frontend/{app/layout,proxy,lib}` |
| `docs/SQL_REFERENCE.md`, `docs/DESIGN.md` schema sections | `docs/SECURITY_RBAC.md`, `docs/NOSQL.md`, `docs/API.md` |

**Interface contract agreed in P1:** the Mongo document shapes and the `sync_outbox` payload format are in `docs/NOSQL.md`. Member A writes the outbox rows and the worker; Member B owns the collections and everything that reads, updates or deletes them.

## Git rules to follow

* Feature branches `feat/a-<topic>` and `feat/b-<topic>`; small commits with descriptive messages; each member commits from their own account.
* Every PR states: what was built, rubric rows covered, how it was tested, limitations, and the reviewer. The other member reviews and approves; both must have merged work to `main`.
* Suggested first PRs: A — `feat/a-schema-and-seed`, `feat/a-sale-flow`; B — `feat/b-auth-and-rbac`, `feat/b-mongo-feed`, `feat/b-nextjs-shell`.
* Never commit `.env`, virtualenvs, `node_modules`, caches (`.gitignore` already excludes them).

## Contribution log (fill in with real commits/PRs)

| Date | Member | Commit / PR | What |
|---|---|---|---|
| | | | |
