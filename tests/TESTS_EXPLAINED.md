# What the tests prove

Run `python scripts/check_all.py` from the repository root after installing backend requirements and `npm ci` in `frontend`. On Windows, use your virtual environment's Python. The command checks V:, locates `mysqld.exe` and `mongod.exe` (override with `MYSQLD_EXE` / `MONGOD_EXE`), starts **its own** servers with data/logs on V:, runs checks, stops only those processes and writes `work/checks_<run>/summary.json`. It never stops a normal application service.

It prints passed/failed/skipped **individual test** counts, real-run exclusions with reasons, and separate lint/TypeScript/build/audit **check** statuses. Any failed or blocked check returns exit code 1. In particular, unresolved audit findings or unavailable real services never count as success. Database initialization and check logs remain on V: for review; no recursive folder cleanup is performed.

## Backend groups

| Group | Plain-language purpose | Real dependency |
|---|---|---|
| `sql/test_schema_and_constraints.py` | Loads migrations/seed twice; verifies keys, defaults, checks, foreign keys, unique open alerts and permitted/forbidden order transitions. Inserts/updates inventory to prove low-stock triggers open, deduplicate and resolve alerts. | MySQL |
| `sql/test_candidates_and_queries.py` | Checks exact composition eligibility, rejected near-matches, ranking, hidden patient quantities, joins, nested/correlated queries, recursive categories, CTEs and function outputs. | MySQL |
| `sql/test_sale.py` | Completes sales and verifies stock, ledger and outbox. Insufficient stock rolls back earlier item changes. Concurrent purchases cannot oversell. Repeat completion is refused. | MySQL |
| `sql/test_cascade_and_rollback.py` | Deletes a newly inserted medicine and verifies its composition rows cascade away while another medicine is untouched. Explicit rollback restores stock plus trigger-created alerts/outbox. | MySQL |
| `security/test_db_rbac.py` | Uses each limited service account directly, outside HTTP. MySQL denies forbidden tables, stock writes and routines; patients see their own orders and pharmacists only their assigned pharmacy. Locked definer cannot log in. | MySQL |
| `security/test_context_isolation.py` | Reuses pooled connections to check that a previous user's identity does not leak into a later request, including after exceptions. | MySQL |
| `api/test_api.py` | Checks login/logout, cookies, 401 vs 403, role restrictions, search, catalog/pharmacy/shortage CRUD, dashboard, inventory and the full patient-to-pharmacist sale flow. | MySQL; real Mongo for sync during the full command |
| `api/test_sessions.py` | Tries malformed, expired, wrongly signed and missing-subject JWTs; verifies 401 expires the cookie. Verifies an authenticated 403 keeps the valid session usable. | MySQL |
| `api/test_docs_match.py` | Reads public `/openapi.json` and compares exact HTTP method/path pairs against `docs/API.md`; avoids internal lazy router representations. | ASGI TestClient; session setup uses MySQL |
| `nosql/test_feed_and_sync.py` | Verifies real feed/events creation, filtering/pagination, annotation-only updates, delete/resync repair, sale events, idempotency, JSON-schema rejection and indexes. Three existing fault-injection cases are separated below. | MySQL + real MongoDB when `MONGO_TEST_URI` is set |
| `nosql/test_real_outage.py` | Starts a separate real mongod on V:, syncs, stops only that process, verifies feed 503 and a committed sale/stock/outbox in MySQL, restarts it and verifies persisted Mongo feed and sale event recovery. | MySQL + owned real mongod |

## Excluded from the real-server count, still executed separately

These three existing tests intentionally replace Mongo access with `_MongoDown`, a deterministic exception stub. They are marked `stub_mongo` during collection and run by the same command as a separate pytest invocation with mongomock. They cannot prove an actual server outage:

- `test_mongo_outage_does_not_roll_back_sale_and_resync_repairs`: simulated failure retains the sale and later repairs the feed.
- `test_failed_rows_are_retried_a_bounded_number_of_times`: deterministic failure reaches the retry ceiling, then explicit retry drains it.
- `test_feed_api_returns_503_when_mongo_is_down`: simulated driver failure maps to HTTP 503.

The real outage test above uses a physical server stop/restart. Other real tests may inject a **real pymongo database connection** to select an isolated database; that is dependency injection, not an in-memory database substitute. Frontend tests stub fetch/router deliberately and are reported as frontend unit/component tests, never real-database evidence.

## Frontend groups

`frontend/tests/render.test.tsx` covers loading/error/success messages, table rows/empty states, stock badges and same-origin API requests/error details. The former mandatory-notice assertion now verifies operational feedback without a notice because Phase 2 intentionally removed notices. `frontend/tests/session.test.tsx` covers the cookie-presence redirect loop, absent-cookie routing, backend validation, 401 recovery and 403 preservation. Browser checks are documented separately; jsdom is not a browser rendering or assistive-technology test.

## Data isolation and cleanup

The session fixture creates `medsub_test_<run_id>` and (for real Mongo) `medsub_feed_test_<run_id>`. It refuses a pre-existing name. It prints the exact names before creation and before removal, and removes only those newly created databases. Transactional table resets are limited to that session's MySQL schema. The outage test owns a separate `medsub_outage_test_<uuid>` database and prints its cleanup scope. Standalone pytest still requires dedicated server credentials: bootstrap configures server accounts/roles; use `check_all.py` for full server isolation.

Expected results described here are test intent. Observed counts and limitations belong in `docs/TESTING.md` and the delivered report.
