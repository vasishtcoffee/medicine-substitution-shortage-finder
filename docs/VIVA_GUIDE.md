# Viva guide — answers tied to this code

Both members should be able to answer every section. Commands assume the repo root. "Rerun" lines say which test proves your change.

## 1. Rubric items — what to say and show

**ER diagram (2).** `docs/DESIGN.md` §4 (generated Mermaid). 15 tables. Show `python scripts/check_schema_docs.py`: it compares the diagram's tables/columns with `information_schema` and fails on any drift.

**Schema, keys, constraints, 3NF (3).** `docs/SCHEMA_REFERENCE.md` (generated per table). M:N = `medicine_ingredients` (carries `strength_mg`, the attribute of the pair) and `inventory` (carries quantity). 3NF: composition is not repeated columns on `medicines`; categories stored once; order header/lines split. Denormalizations on purpose: `substitution_reviews.ranking_snapshot`, `low_stock_alerts.quantity_at_open`, `sync_outbox.payload` (audit/transport snapshots).

**DDL (4).** `V001__core_schema.sql` (CREATE TABLE, PK, FK, UNIQUE, NOT NULL, CHECK, DEFAULT, ENUM, generated column), `V002__alter_constraints.sql` (ALTER TABLE). Generated column: `open_alert_key = IF(status='OPEN', CONCAT(pharmacy_id,'-',medicine_id), NULL)` + `UNIQUE` — MySQL has no partial index, and UNIQUE ignores NULLs, so only one OPEN alert can exist. Proof: `test_only_one_open_alert_per_pharmacy_medicine`.

**NoSQL creation (4).** `app/mongo.py: ensure_collections` + `scripts/init_mongo.py` (`$jsonSchema`, indexes, idempotent). Honest caveat: validated only with mongomock here; run the real-Mongo test (see `docs/NOSQL.md`).

**Technology justification (1).** `docs/DESIGN.md` §3. MySQL = truth and transactions; MongoDB = flexible feed/events, eventually consistent; **why not a vector DB?** Matching must be *deterministic*: same ingredient set, strengths, form, route, release. A similarity score cannot prove equivalence, so a vector DB would add an embedding model, another sync target and risk for no gain. The rubric accepts NoSQL *or* vector.

**DML (4).** `database/sql/dml_demo.sql` + recorded output `docs/sql_output/dml_demo.txt`. Safe delete = medicine 900 (cascades its `medicine_ingredients`); blocked delete = medicine 1 (FK 1451 from `inventory`); the app soft-deletes (`is_active`).

**JOIN / nested / correlated / recursive (4).** `database/sql/queries.sql`. Correlated: inner `AVG(...) WHERE i2.pharmacy_id = i.pharmacy_id` refers to the outer row. Nested: `NOT IN (SELECT …)` is independent. Recursive: anchor + `UNION ALL` join on itself.

**Procedure, function, trigger, CTE (6).** `sp_equivalent_candidates` (set equality with two `NOT EXISTS`, in `v_candidate_check`), `sp_complete_order` (transaction; locks in PK order; `FOR UPDATE` stock check; `EXIT HANDLER … ROLLBACK; RESIGNAL`), `fn_availability_band`, triggers on `inventory` (+ `trg_orders_status_transition`), CTEs in `advanced.sql`.
*Be ready to explain the bug the concurrency test found:* the stock check was a plain `SELECT`, which reads the transaction snapshot taken before waiting for the row lock, so the second sale did not see the first. The `CHECK (quantity >= 0)` still protected the data (error 3819); the fix is a locking read (`… FOR UPDATE`) in `R__50_workflow.sql`.

**NoSQL read/update/delete (7).** `routers/feed.py`; Feed Lab screen. Update only `metadata/notes/flags` (quantities belong to MySQL; `extra="forbid"` → 422). Delete never touches MySQL; resync recreates. Outbox pattern: change + outbox row in one MySQL transaction → worker applies idempotently → eventual consistency; Mongo outage cannot roll back a sale (`test_mongo_outage_does_not_roll_back_sale_and_resync_repairs`).

**Next.js (3).** 7 screens: login, dashboard, search, inventory, orders, admin (+SQL Demo), Feed Lab. `/api/*` rewrite → no CORS; httpOnly cookie; `proxy.ts` only redirects, backend enforces.

**Backend (2).** `backend/app`, routers per domain, raw parameterised SQL, OpenAPI at `/docs`.

**Auth + DB RBAC (4).** `docs/SECURITY_RBAC.md`. Four MySQL roles; patients/pharmacists have no direct access to protected tables; definer procedures check `fn_ctx_*`. *MySQL has no native RLS — say so.* Tests in `tests/security`.

**Docs & Git (2) / Originality & modification (4).** `docs/TEAM_CONTRIBUTIONS.md`; be able to explain the other member's slice.

## 2. Likely questions

* **Why raw SQL and no ORM?** The course is SQL-centric; grants, procedures and transaction boundaries stay visible.
* **How does MySQL know who the user is?** Session variables set after pool checkout from the verified identity and read via `fn_ctx_*` (views cannot read user variables). Cleared in `finally`; tested.
* **What stops a patient reading stock?** No grant on `inventory`; `v_availability` has no quantity column; `sp_rank_candidates` returns NULL quantities unless admin/own-pharmacy pharmacist.
* **What if the app is compromised?** Context is trusted because only the backend holds credentials; a compromised backend could set any context. A forged context still cannot exceed the role's grants.
* **Deadlocks?** Locks are taken in primary-key order; the API retries 1213/1205 up to 3 times.
* **Why is `p_actor` a parameter of `sp_complete_order`?** Spec signature; the procedure rejects a value that differs from the verified context.
* **Why two triggers for one rule?** MySQL triggers are per event; both call `sp_eval_low_stock`.
* **Limitations?** No FEFO batch depletion; stateless JWT (logout = clear cookie); keyword-only search; educational synthetic data; MongoDB is eventually consistent.

## 3. Live-modification drills (file to edit → test to rerun)

| Drill | Edit | Rerun / verify |
|---|---|---|
| Add a column with a CHECK | New file `database/migrations/V003__add_max_daily.sql`: `ALTER TABLE medicines ADD COLUMN max_daily_units INT NULL, ADD CONSTRAINT chk_max_daily CHECK (max_daily_units IS NULL OR max_daily_units > 0);` then `python scripts/migrate.py` and `python scripts/check_schema_docs.py --write` | Add a row to the parametrized list in `tests/sql/test_schema_and_constraints.py`; `pytest tests/sql/test_schema_and_constraints.py`; `python scripts/check_schema_docs.py` |
| Write a new correlated query | Add a `-- @name:` block to `database/sql/queries.sql` (e.g. medicines whose price/stock exceeds the average of their own category) | `python scripts/run_sql_demo.py database/sql/queries.sql`; it appears in Admin → SQL Demo automatically |
| Add a permission to a role | `database/migrations/R__90_grants.sql`, e.g. `GRANT SELECT ON {{DB}}.low_stock_alerts TO 'app_pharmacist_role'@'{{HOST}}';` (but that bypasses the context view — explain why you would not) | `python scripts/migrate.py`; add a case to `tests/security/test_db_rbac.py` |
| Change the low-stock rule (`<=` → `<`) | `sp_eval_low_stock` in `R__30_triggers.sql` **and** `fn_availability_band` in `R__10_context_and_guards.sql` (keep the band consistent) | `pytest tests/sql/test_schema_and_constraints.py -k trigger`; update the expected band demo in `advanced.sql` |
| Add an order status | New migration: `ALTER TABLE orders MODIFY status ENUM(…,'ON_HOLD') …`; allow transitions in `trg_orders_status_transition` (`R__30`); add a pill colour in `globals.css` | `tests/sql/test_schema_and_constraints.py` (valid/invalid transition lists) |
| Make eligibility ignore release type | `is_eligible` expression in `v_candidate_eligibility` (`R__20_views.sql`): remove `release_same`; adjust the `release_same` rejection text in `sp_candidate_rejections` (`R__40`) | `tests/sql/test_candidates_and_queries.py` — the ER tablet now becomes eligible, so update `test_every_ineligible_seed_case…` |
| Add a field to the Mongo feed document | `sp_write_outbox` payload (`R__50`), `apply_row` in `backend/app/sync.py`, `FEED_VALIDATOR` in `backend/app/mongo.py`, `docs/NOSQL.md` | `pytest tests/nosql` (and the real-Mongo validator test) |
| Add a low-stock band "Critical" | `fn_availability_band` (`R__10`), pill class in `globals.css`, `tests/security/test_db_rbac.py` band set | `pytest tests/security tests/api` |

## 4. Be able to demo

`docs/DEMO_SCRIPT.md` end to end, and `pytest` live (`docs/TESTING.md` for the numbers).
