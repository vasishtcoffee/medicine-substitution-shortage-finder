# Native database viva

Run from the repository root. Expected results below are expectations, not recorded passes.
Use a **new dedicated** MySQL schema and MongoDB database, e.g. `medsub_viva_20261119`.
Do not use your normal application data. Passwords come from your local environment; never commit them.

1. Set `MYSQL_DATABASE=medsub_viva_20261119` in the process environment. Confirm that this schema does not already exist. `python scripts/bootstrap_db.py` creates that schema and configures service accounts/roles. Bootstrap also sets `log_bin_trust_function_creators` on the selected server and updates the configured service-account passwords: use an isolated server or dedicated credentials, never someone else's server/accounts.
2. `python viva/prepare_sql.py medsub_viva_20261119` renders the **existing** migrations into `work/viva-schema.sql`. It executes nothing. Run `SOURCE viva/mysql/01_ddl.sql` in mysql from repository root, as the configured migrator; or open the generated file in Workbench. This applies CREATE/ALTER, views, stored routines, triggers and grants in the named schema. Run once on the fresh schema. Do not use `--force`.
3. `python scripts/seed.py` seeds only the selected schema (resets its stock). Run `02_dml_cascade_rollback.sql`, `03_queries_routines.sql`, `04_triggers.sql` in order with `--database=medsub_viva_20261119`. Each file states mutations and cleanup. DML/cascade/triggers roll back isolated records; queries are read-only. Native mysql redirection examples use a shell supporting `<`; in PowerShell use `SOURCE` interactively.
4. Open a **separate patient-service** connection and run `05_permission_denial.sql`. The expected denial is a MySQL error, not HTTP 403. Never share runtime service passwords with browser clients.
5. Set `MONGO_DATABASE=medsub_viva_20261119` and the intended `MONGO_URI`; run `python scripts/init_mongo.py`. Run `mongosh <URI> --file viva/mongodb/01_crud.js`. Only a new UUID document is inserted, updated and deleted. `inventory_feed` is read-only in this demo; MySQL owns stock.
6. Keep the databases for review, or remove **only databases you created**, after naming them and reviewing their contents. No script here drops an existing database.

| App feature | Implementation | Demonstration |
|---|---|---|
| Catalog and composition | `database/migrations/V001__core_schema.sql`, `V002__alter_constraints.sql` | 01 DDL; 02 DML/cascade/rollback |
| Search, availability and candidate ranking | `R__10_context_and_guards.sql`, `R__40_candidates.sql`, `backend/app/routers/search.py` | 03 joins/aggregates/CTEs/functions/procedure |
| Stock alerts | `R__30_triggers.sql` | 04 triggers |
| Transactional outbox and sync | `R__50_workflow.sql`, `backend/app/sync.py` | sale/rollback integration tests; Mongo feed inspection |
| Database RBAC | `R__90_grants.sql`, `backend/app/db.py` | 05 separate limited connection |
| Feed/events | `backend/app/mongo.py`, `sync.py`, `routers/feed.py` | MongoDB 01 CRUD |

## Removed and retained

Deleted `/feed-lab` (`frontend/app/feed-lab/page.tsx`), its navigation/quick links/proxy matcher; SQL Demo tab/component in `frontend/app/admin/page.tsx`; `backend/app/routers/sqldemo.py`, its registration and its two endpoints (`GET /admin/sql-demo`, `POST /admin/sql-demo/{name}/run`). Removed only their endpoint-specific test/assertion and documentation rows. Existing SQL files and CLI runner remain.

Retained all nine `/feed/*` operations: admin inspection, metadata/notes/flag updates and repairs of feed/event documents are operational backend capabilities, used by integration tests and available through real backend tools. They do not authorize editing MySQL-owned quantities. Retained all four `/sync/*` endpoints: outbox inspection, draining, full resync and failed-row retry support production workflow recovery; `/sync/outbox` is also used by the Next server connection helper. Retained `mongo.py`, `sync.py`, database outbox/trigger routines and SQL CLI tooling: sales/receipts and eventual consistency depend on them.

Removed visible global/search/order/login safety notices and shortage demo disclaimers. Kept functional candidate verification status, eligibility/rejection reasons, prescription requirements, staff-only quantity explanation, and confirmations describing mutations. The combined candidate notice was reduced to the functional pending-verification status; no replacement banner. No ambiguous remaining disclaimer identified in retained UI source. Backend notice fields remain in existing API contracts and are not rendered.
