# SQL reference — every topic mapped to a rubric row

Run everything against the demo database `medsub` (set `MYSQL_DATABASE` for another). Recorded real outputs are in [`docs/sql_output/`](sql_output/).

| Rubric | Topic | File / object | Run | Expected output |
|---|---|---|---|---|
| 3 (4) | DDL: CREATE TABLE, PK, FK, UNIQUE, NOT NULL, CHECK, DEFAULT, ENUM, generated-column unique key | `database/migrations/V001__core_schema.sql` | `python scripts/migrate.py` | 15 tables; second run prints `skip` lines |
| 3 (4) | ALTER TABLE (CHECKs, indexes, a new column) | `V002__alter_constraints.sql` | same | applied once, recorded in `schema_migrations` |
| 3 (4) | A violation of each constraint class | `tests/sql/test_schema_and_constraints.py` | `pytest tests/sql/test_schema_and_constraints.py` | 31 passed |
| 6 (4) | INSERT / SELECT / UPDATE / DELETE, **blocked** delete (FK 1451), **safe** delete (cascade), CHECK-blocked update (3819) | `database/sql/dml_demo.sql` | `python scripts/run_sql_demo.py database/sql/dml_demo.sql` | [`sql_output/dml_demo.txt`](sql_output/dml_demo.txt) |
| 7 (4) | JOIN (5 tables), nested (`NOT IN`), correlated, recursive CTE, `GROUP BY … HAVING`, LEFT JOIN aggregate | `database/sql/queries.sql` (each with `@purpose`, `@why`, `@expected`) | `python scripts/run_sql_demo.py database/sql/queries.sql` | [`sql_output/queries.txt`](sql_output/queries.txt); asserted by `tests/sql/test_candidates_and_queries.py` |
| 8 (6) | Stored procedure `sp_equivalent_candidates` (+ `sp_candidate_rejections`, `sp_rank_candidates`) | `R__40_candidates.sql`, view `v_candidate_eligibility` in `R__20_views.sql` | `CALL sp_equivalent_candidates(1)` as in `advanced.sql` | Pyrelief 500 Tablet, Febrix 500 Tablet |
| 8 (6) | Transactional procedure `sp_complete_order` | `R__50_workflow.sql` | app Orders screen; `tests/sql/test_sale.py` | stock deducted, ledger + outbox rows, status COMPLETED |
| 8 (6) | Stored function `fn_availability_band` | `R__10_context_and_guards.sql` | `advanced.sql` block `fn_availability_band_demo` | `Out, Low, Low, In stock` |
| 8 (6) | Triggers `trg_inventory_low_stock_ins/_upd`, `trg_orders_status_transition` | `R__30_triggers.sql` | `advanced.sql` block `demo_trigger_low_stock` | open alerts 0 → 1 → 1 → 0 |
| 8 (6) | Normal CTE `cte_pharmacy_stock_summary`; recursive CTE `cte_category_tree` | `database/sql/advanced.sql` | `python scripts/run_sql_demo.py database/sql/advanced.sql` | [`sql_output/advanced.txt`](sql_output/advanced.txt) |
| 12 (4) | Roles, grants, views, definer routines | `R__90_grants.sql`, `R__20_views.sql`, `R__10_context_and_guards.sql` | `pytest tests/security` | 22 passed |

## Named objects

**Functions** `fn_availability_band(quantity, reorder_level)`, `fn_ctx_user_id()`, `fn_ctx_role()`, `fn_ctx_pharmacy_id()`.

**Views** `v_availability`, `v_users_public`, `v_my_inventory`, `v_my_alerts`, `v_my_movements`, `v_candidate_check`, `v_candidate_eligibility`.

**Triggers** `trg_inventory_low_stock_ins` and `trg_inventory_low_stock_upd` (AFTER INSERT / AFTER UPDATE on `inventory`; both call `sp_eval_low_stock`), `trg_orders_status_transition` (BEFORE UPDATE on `orders`).

**Procedures (naming convention `sp_`)**

| Group | Procedures |
|---|---|
| Authentication | `sp_auth_lookup`, `sp_auth_identity` |
| Candidates | `sp_equivalent_candidates`, `sp_candidate_rejections`, `sp_rank_candidates` |
| Inventory | `sp_receive_stock`, `sp_adjust_stock`, `sp_set_reorder_level` |
| Orders (patient) | `sp_create_my_order`, `sp_list_my_orders` |
| Orders (staff) | `sp_list_pharmacy_orders`, `sp_start_review`, `sp_decide_substitution`, `sp_approve_order`, `sp_reject_order`, `sp_complete_order`, `sp_cancel_order`, `sp_list_reviews` |
| Sync | `sp_enqueue_full_resync` (admin), `sp_write_outbox` (internal) |
| Admin | `sp_admin_create_user`, `sp_admin_assign_pharmacist`, `sp_admin_set_user_active` |
| Internal guards / helpers | `sp_require_authenticated`, `sp_require_role`, `sp_require_pharmacy_access`, `sp_eval_low_stock` |

## Why each query qualifies (one line each, for the viva)

* **JOIN** — combines `inventory ⨝ pharmacies ⨝ medicines ⨝ medicine_ingredients ⨝ active_ingredients`, crossing the M:N junction.
* **Nested** — `NOT IN (SELECT …)`: the inner query is independent of the outer row.
* **Correlated** — the inner `AVG` references `i.pharmacy_id` of the outer row, so it runs per outer row.
* **Recursive CTE** — anchor row (root/`Analgesics`) `UNION ALL` children joined to the CTE itself, until no more children.
* **GROUP BY … HAVING** — the condition `COUNT(*) >= 3` is on an aggregate, which `WHERE` cannot express.

## Eligibility logic in one picture

```
v_candidate_check(a, b):   ingredients_same   NOT EXISTS (a-ingredient missing in b) AND NOT EXISTS (b-ingredient missing in a)
                           strengths_same     same two NOT EXISTS, matching (ingredient, strength_mg)
                           basis/form/route/release equal;  b active;  a and b allow substitution
v_candidate_eligibility:   is_eligible = all of the above
```
