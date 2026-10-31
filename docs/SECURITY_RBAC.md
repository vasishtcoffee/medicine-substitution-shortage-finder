# Security and role-based access control (rubric 12)

> MySQL has **no native row-level security (RLS)**. This project does not pretend otherwise. Database-level separation is built from: MySQL **roles and grants**, **no direct access** to protected base tables for patients and pharmacists, **`SQL SECURITY DEFINER` views and stored procedures** that check a trusted request context, and a **locked definer account**. Session context is trusted only because the DB credentials stay backend-only. This is a coursework RBAC design, not a claim that MySQL provides native RLS.

## 1. Accounts and roles

| MySQL account | Default role | Used for | Can log in |
|---|---|---|---|
| `root` | — | Only `scripts/bootstrap_db.py` (once). The app never uses it. | yes |
| `medsub_migrator` | — (ALL on the schema + GRANT OPTION + `SET_USER_ID`) | `migrate.py`, `seed.py` | yes |
| `medsub_definer` | — (DML + EXECUTE + TRIGGER on the schema, no DDL) | `DEFINER` of every routine/view/trigger | **no** (`ACCOUNT LOCK`) |
| `app_patient_svc` | `app_patient_role` | API requests of signed-in patients | yes |
| `app_pharmacist_svc` | `app_pharmacist_role` | API requests of pharmacists | yes |
| `app_admin_svc` | `app_admin_role` | API requests of admins + sync worker | yes |
| `app_auth_svc` | `app_auth_role` | login lookup and per-request identity read | yes |

The backend verifies `CURRENT_ROLE()` on every connection checkout and refuses a connection whose active role is not the expected one.

## 2. Permission matrix (what the DB itself allows)

| Object | patient | pharmacist | admin | auth |
|---|---|---|---|---|
| `medicines`, `medicine_ingredients`, `active_ingredients`, `medicine_categories`, `pharmacies`, `shortage_entries` | SELECT | SELECT | SELECT, INSERT, UPDATE, DELETE (`pharmacies`: no DELETE) | — |
| `v_availability` (band only, **no quantity column**) | SELECT | SELECT | SELECT | — |
| `v_my_inventory`, `v_my_alerts`, `v_my_movements` (exact stock; context-scoped) | — | SELECT (own pharmacy rows only) | SELECT (all) | — |
| `inventory`, `inventory_movements`, `low_stock_alerts`, `orders`, `order_items`, `substitution_reviews`, `pharmacist_assignments` | **none** | **none** | SELECT only | — |
| `users` (incl. `password_hash`) | none | none | none (reads `v_users_public`) | via `sp_auth_*` only |
| `sync_outbox` | none | none | SELECT, UPDATE | — |
| `sp_create_my_order`, `sp_list_my_orders` | EXECUTE | — | — | — |
| `sp_receive_stock`, `sp_adjust_stock`, `sp_set_reorder_level` | — | EXECUTE (own pharmacy) | EXECUTE (any pharmacy) | — |
| `sp_list_pharmacy_orders` | — | EXECUTE (own pharmacy) | EXECUTE (all) | — |
| `sp_start_review`, `sp_decide_substitution`, `sp_approve_order`, `sp_reject_order`, `sp_complete_order` | — | EXECUTE (own pharmacy; admin cannot) | — | — |
| `sp_cancel_order`, `sp_list_reviews` | own orders | own pharmacy | any | — |
| `sp_equivalent_candidates`, `sp_candidate_rejections`, `sp_rank_candidates` | EXECUTE (bands only) | EXECUTE (exact qty only for own pharmacy) | EXECUTE (exact) | — |
| `sp_admin_create_user`, `sp_admin_assign_pharmacist`, `sp_admin_set_user_active`, `sp_enqueue_full_resync` | — | — | EXECUTE | — |
| `sp_auth_lookup`, `sp_auth_identity` | — | — | — | EXECUTE |
| internal helpers `sp_require_*`, `sp_eval_low_stock`, `sp_write_outbox` | none | none | none | none |

Grants live in `database/migrations/R__90_grants.sql`.

## 3. How identity reaches MySQL

1. Login: `app_auth_svc` runs `sp_auth_lookup(email)`; the backend verifies the **argon2id** hash (a dummy hash is verified for unknown e-mails; the error text is identical, so no user enumeration). A JWT (`sub`, 60-minute expiry) is set in an **httpOnly, SameSite=Lax** cookie. Nothing is stored in `localStorage`.
2. Every request: the backend decodes the cookie, then re-reads the user through `sp_auth_identity` (role, `is_active`, assigned pharmacy). The **role in the token is not trusted**. Deactivating a user therefore ends their session immediately.
3. The backend takes a connection from the **pool of the user's role** (`db.session`), verifies `CURRENT_ROLE()`, and runs `SET @app_user_id, @app_role, @app_pharmacy_id`. Routines read them through `fn_ctx_user_id()/fn_ctx_role()/fn_ctx_pharmacy_id()` (MySQL views cannot reference user variables; functions can).
4. In `finally` the variables are set to NULL and the connection returns to the pool, which also resets the session. `tests/security/test_context_isolation.py` proves a reused connection never carries the previous identity (including after an exception).
5. Routines never accept an owner / pharmacy identity from the browser: `sp_create_my_order` has no owner parameter; pharmacist routines compare the pharmacy of the row with `fn_ctx_pharmacy_id()`; `sp_complete_order(p_order_id, p_actor)` rejects an `p_actor` that differs from the context.
6. A forged context is not enough: a patient DB connection that claims `@app_role='admin'` still has no EXECUTE/SELECT grants for admin objects (tested).

## 4. Safeguards against over-sharing by privileged routines

* `v_availability` has no quantity column; `sp_rank_candidates` returns `quantity_here` only to admin or the pharmacist of the chosen pharmacy and `total_quantity` only to admin, otherwise NULL (tested for patients and cross-pharmacy pharmacists).
* All definer objects use unqualified table names inside their own schema, the dedicated locked definer, strict input validation (`SIGNAL` 45422) and explicit ownership checks (`SIGNAL` 45403).
* Error numbers: 45401 unauthenticated, 45403 forbidden, 45404 not found, 45409 conflict, 45422 invalid; the API maps them to 401/403/404/409/422.

## 5. Tests that prove it (run against real MySQL, not through the API)

`tests/security/test_db_rbac.py` and `tests/security/test_context_isolation.py` (22 tests), `tests/api/test_api.py` (API-level 401/403, login without enumeration). Highlights:

| Requirement | Test |
|---|---|
| Patient direct `UPDATE inventory` denied | `test_patient_direct_update_inventory_denied` (MySQL error 1142) |
| Patient direct `SELECT` of orders denied; `CALL sp_list_my_orders()` returns only own rows | `test_patient_direct_reads_of_protected_tables_denied`, `test_patient_sees_only_own_orders_via_procedure` |
| Pharmacist direct writes to inventory tables denied; pharmacy-2 row rejected under pharmacy-1 context | `test_pharmacist_direct_writes_to_protected_tables_denied`, `test_stock_procedure_rejects_other_pharmacy_row` |
| Pharmacist direct `INSERT` into `medicines` denied | `test_pharmacist_cannot_insert_medicines_or_read_users` |
| Patients never receive exact quantities | `test_patient_never_gets_exact_quantities`, `test_search_is_case_insensitive_and_shows_bands_not_quantities_to_patients` |
| Unauthenticated → 401, wrong role → 403, invalid credentials → 401 without enumeration | `test_unauthenticated_requests_get_401`, `test_wrong_role_gets_403`, `test_login_failures_do_not_reveal_which_part_was_wrong` |
| Pooled connection never leaks identity | `test_context_isolation.py` |

## 6. Known limitations (stated honestly)

* No native RLS; context variables are trusted because only the backend holds the DB credentials. Anyone who obtains a service-account password could set any context.
* JWTs are stateless: logout only clears the cookie, and a copied token works until it expires (60 min) unless the user is deactivated. No refresh tokens, no login rate limiting, no CSRF token (SameSite=Lax cookie + JSON-only API).
* The `COOKIE_SECURE` flag must be `true` behind HTTPS in any non-local use.
* Local demo passwords come from `.env` and are for local use only.
