# Testing — actual results

Recorded on 2026-10-15, Windows 11, Python 3.12.3, Node 24, **MySQL 8.0.33 (local install)**. Docker was **not installed**. MongoDB tests ran twice: on **mongomock** (default) and against a **real MongoDB 7.0.14** (portable Windows zip from fastdl.mongodb.org, run locally from `.tools/`, git-ignored). Nothing below is claimed unless it was executed; "not run" means it was not executed here, with the command to run it.

Run everything:

```powershell
python scripts/bootstrap_db.py medsub_test   # once (tests rebuild medsub_test themselves)
python -m pytest tests -q                    # backend: SQL, security, API, NoSQL
cd frontend; npm run lint; npm run typecheck; npm run build; npm test
python scripts/check_schema_docs.py          # ER diagram vs live schema
```

Do not run two pytest processes at once — they share the `medsub_test` database.

## Summary

| Suite | Result |
|---|---|
| `pytest tests` (backend, mongomock) | **105 passed, 1 skipped** (the skipped one needs a real MongoDB) |
| `MONGO_TEST_URI=mongodb://127.0.0.1:27017 pytest tests/nosql` (real MongoDB 7.0.14) | **14 passed, 0 skipped** |
| `python scripts/init_mongo.py` run twice on real MongoDB | 1st: both collections `created`; 2nd: `validator updated`; same 3+3 indexes, no error (idempotent) |
| Concurrency test repeated 5× | 5/5 passed |
| Frontend `eslint .`, `tsc --noEmit`, `next build` | passed (0 errors) |
| Frontend `vitest run` | 6 passed |
| `check_schema_docs.py` | OK (15 tables, 97 columns) |
| `run_sql_demo.py` on `dml_demo.sql`, `queries.sql`, `advanced.sql` | exit 0; outputs in `docs/sql_output/` |
| Browser check (built-in browser) | login, role-filtered nav, search with bands, candidate explanations, Feed Lab outbox/outage state were exercised. The full patient → pharmacist → sale click-through was **not** driven through the browser; the same flow is covered by `test_full_flow_patient_order_to_completed_sale` at API level. |

## P0 tests (section 12)

| Test | Purpose | Expected | Actual | Status |
|---|---|---|---|---|
| `test_schema_and_seed_load_twice_without_duplicates` | idempotent migrate + seed | same row counts; 16 base tables | as expected | passed |
| `test_constraint_violation[…]` (14 cases) | each constraint class rejects bad data (NOT NULL, UNIQUE, CHECK incl. negative stock, ENUM, FK, ALTER-added CHECKs) | MySQL errno 1048/1062/3819/1265/1452/1451 | as expected | passed |
| `test_trigger_one_alert_no_duplicate_then_auto_resolve` | trigger creates one alert, no duplicate, auto-resolves, reopens | counts 0→1→1→0→1 | as expected | passed |
| `test_only_one_open_alert_per_pharmacy_medicine` | generated-column unique key | duplicate OPEN rejected (1062) | as expected | passed |
| `test_valid/invalid_status_transition_*` (12 cases) | order state machine in the DB | invalid → 45409 | as expected | passed |
| `test_valid_sale_deducts_exactly_and_writes_ledger_and_outbox` | exact deduction | qty − 2, SALE row, outbox rows | as expected | passed |
| `test_insufficient_stock_rejected_with_no_partial_rows` | atomicity | 45409; item A rolled back; no outbox rows | as expected | passed |
| `test_two_concurrent_sales_cannot_oversell` | concurrency | one COMPLETED, one 45409, qty 20 | as expected (after the locking-read fix; see DESIGN decisions) | passed |
| `test_repeating_complete_order_fails` | idempotency guard | 45409, no double deduction | as expected | passed |
| `test_candidates…` (10 tests) | eligible cases, every ineligible seed case incl. look-alike, combination product, empty result, ranking, no quantity leak | see file | as expected | passed |
| `tests/security/*` (22) | all section 6 DB-level tests + context isolation | 1142/1370/454xx errors; own-rows only | as expected | passed |
| `tests/api/test_api.py` (21) + `test_docs_match.py` | 401/403, login without enumeration, search bands, candidates, CRUD, full flow, isolation, SQL demo whitelist, docs match routes | see file | as expected | passed |
| `tests/nosql` — create/read/filter/paginate/update/delete, sale → Mongo update, outage keeps sale + outbox pending + resync repairs, bounded retries, delete leaves MySQL untouched | NoSQL behaviour | see file | as expected on mongomock **and real MongoDB** | passed |
| `test_validator_rejects_bad_documents_and_init_is_idempotent` | `$jsonSchema` validation, `init_mongo.py` idempotency | WriteError on bad docs; same result twice | WriteError on bad docs; same result twice | passed (real MongoDB 7.0.14) |
| Real MongoDB end to end (server `$jsonSchema`, index creation, `collMod`) | rubric 4 | validator + indexes work | as expected | passed |
| Real-MongoDB run found a bug: `test_read_with_filters_and_pagination` failed because many documents share one `last_updated`, so page order was unstable | pagination | disjoint pages | fixed by sorting on `(last_updated desc, _id asc)` in `routers/feed.py`; mongomock had hidden it | passed after fix |
| MySQL 8.4 via `docker compose up` | compose health, same schema on 8.4 | — | — | **not run** (Docker not installed) |

## P1

| Test | Status |
|---|---|
| Frontend lint / type check / build | passed |
| Page-render tests (shared components, api client) | passed (6) |
| One end-to-end browser flow (patient search → order → pharmacist approve → complete → stock and feed updated) | **partially run** (see summary); API-level equivalent passed |
| `scripts/check_schema_docs.py` | passed |

## Known test caveats

* `npm audit` reports vulnerabilities in dev tooling dependencies; not triaged.
* The API tests use FastAPI's `TestClient`; the real uvicorn + Next.js proxy path was exercised only manually in the browser.
