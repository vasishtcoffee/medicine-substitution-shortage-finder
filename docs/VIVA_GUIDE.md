# Viva technical guide

Use [the short sequence](VIVA_COMMANDS.md) for implementation/script links and [rubric coverage](RUBRIC_COVERAGE.md) for evidence. Demonstration expectations and executed results are separate.

## Explain the design

- Raw parameterized SQL keeps the course's grants, stored objects and transactions visible. MySQL owns stock/orders; MongoDB is a flexible, eventually consistent projection/event log. Exact composition checks use ingredient-set equality plus strength/form/route/release conditions; an embedding similarity score would not prove those conditions.
- fn_availability_band maps 0/at-reorder/above-reorder values to Out/Low/In stock. Patients receive availability bands, not exact stock.
- sp_complete_order locks stock, checks actor/pharmacy and order status, writes stock/ledger/outbox in one transaction and rolls back on failure. The concurrency and insufficient-stock tests validate its current behavior; no new historical development story is asserted.
- The two inventory triggers call sp_eval_low_stock. They create/deduplicate/resolve alerts. They do not independently enqueue stock projections; workflow procedures call sp_write_outbox.
- MySQL has no native row-level security. Separate limited accounts/roles, definer procedures/views and backend-set request context provide access control. Context is cleared after each pooled request. A compromised trusted backend is a documented boundary.
- MongoDB inventory_feed is not authoritative. Admin annotations cannot change MySQL-owned quantity. Sync uses stable IDs and persisted outbox retries; real outage tests stop only a separately owned server.
- Six UI screens remain. Feed Lab and SQL Demo were intentionally removed. Native backend tools and viva scripts cover demonstrations.

## Likely questions

| Question | Evidence to show |
|---|---|
| What prevents direct patient stock access? | R__90 grants and tests/security/test_db_rbac.py; native 05 permission-denial connection |
| Can one pharmacist act at another pharmacy? | sp_require_pharmacy_access and direct security/API tests |
| What happens after an expired session? | Backend 401 expires cookie, UI returns to login; /login does not trust cookie presence |
| Does 403 log a user out? | No; test_403_does_not_expire_valid_session and frontend session tests |
| Does Mongo failure undo a sale? | No; tests/nosql/test_real_outage.py verifies committed SQL and recovered persisted Mongo effects |
| Why not claim full accessibility? | Source/contrast and partial browser checks do not verify every interaction or assistive technology |
| Who implemented which part? | Only confirmed evidence; git author metadata alone is not ownership |

## Small modification exercise

On another branch and a dedicated database, add a named read-only query to database/sql/queries.sql, run the CLI query runner, and add a meaningful result assertion in tests/sql/test_candidates_and_queries.py. There is no automatic in-app SQL panel. For schema edits, add a new versioned migration; do not rewrite already-applied versioned migrations.
