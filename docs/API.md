# API reference

Interactive OpenAPI: `http://localhost:8000/docs` (FastAPI directly) — the browser uses the same routes under `/api/*` on the Next.js origin (`/api/orders/mine` → `/orders/mine`). Auth is an httpOnly `medsub_session` cookie set by `/auth/login`. Common errors: **401** not signed in / bad token / inactive user, **403** role or pharmacy not allowed, **404** not found, **409** conflict (state, duplicate, constraint, insufficient stock), **422** invalid input, **503** MongoDB unavailable (feed routes only).

`tests/api/test_docs_match.py` fails if this table and the routes in the code differ. Roles: `any` = any signed-in role, `P` patient, `Ph` pharmacist, `A` admin.

| Method | Path | Role | Purpose | Key errors |
|---|---|---|---|---|
| POST | `/auth/login` | public | Verify password (argon2), set cookie | 401 (same message for unknown e-mail / wrong password / inactive) |
| POST | `/auth/logout` | public | Clear cookie (stateless token; see limitations) | — |
| GET | `/auth/me` | any | Current user | 401 |
| GET | `/dashboard` | any | Role-specific counters | 401 |
| GET | `/medicines` | any | Catalog (`category_id`, admin-only `include_inactive`) | 403 |
| GET | `/medicines/{medicine_id}` | any | One medicine with ingredients | 404 |
| POST | `/medicines` | A | Create medicine + composition (transaction) | 409 unique/enum, 422 |
| PUT | `/medicines/{medicine_id}` | A | Replace medicine + composition | 404, 409 |
| DELETE | `/medicines/{medicine_id}` | A | Soft delete (`is_active=0`) | 404 |
| GET | `/ingredients` | any | Active ingredients | — |
| GET | `/pharmacies` | any | Pharmacies | — |
| POST | `/pharmacies` | A | Create pharmacy | 409 duplicate name, 422 |
| PUT | `/pharmacies/{pharmacy_id}` | A | Rename / update pharmacy | 404, 409 |
| GET | `/categories/tree` | any | Category tree (recursive CTE) | — |
| GET | `/shortages` | any | Shortage entries (synthetic) | — |
| POST | `/shortages` | A | Add shortage entry | 409 |
| PATCH | `/shortages/{shortage_id}/resolve` | A | Resolve | 404 |
| DELETE | `/shortages/{shortage_id}` | A | Hard delete a shortage entry | 404 |
| GET | `/admin/users` | A | Users (no password hashes) | 403 |
| POST | `/admin/users` | A | Create user (`sp_admin_create_user`) | 409 e-mail, 422 |
| PATCH | `/admin/users/{user_id}/active` | A | Activate/deactivate | 409 (self) |
| PUT | `/admin/users/{user_id}/pharmacy` | A | Assign pharmacist to pharmacy | 404 |
| GET | `/search` | any | LIKE search + availability **bands** | — |
| GET | `/search/availability/{medicine_id}` | any | Bands per pharmacy | 404 |
| GET | `/search/candidates/{medicine_id}` | any | Eligible ranked candidates + rejected near-misses (`pharmacy_id`) | 404 |
| GET | `/inventory` | Ph, A | Exact stock (Ph: own pharmacy) | 403 |
| GET | `/inventory/movements` | Ph, A | Ledger | 403 |
| POST | `/inventory/receive` | Ph, A | Receive stock (`sp_receive_stock`) | 403 other pharmacy, 422 |
| POST | `/inventory/adjust` | Ph, A | Adjust stock (`sp_adjust_stock`) | 409 negative, 403 |
| PUT | `/inventory/reorder-level` | Ph, A | Set reorder level | 404, 403 |
| GET | `/alerts` | Ph, A | Low-stock alerts (`status`) | 403 |
| POST | `/orders` | P | Create order for the signed-in patient | 404, 422 |
| GET | `/orders/mine` | P | My orders | — |
| GET | `/orders` | Ph, A | Orders of my pharmacy / all (`status`) | 403 |
| GET | `/orders/{order_id}/reviews` | any | Pharmacist decisions (owner / pharmacy / admin) | 403, 404 |
| POST | `/orders/{order_id}/cancel` | any | Cancel (owner / pharmacy / admin) | 403, 409 terminal |
| POST | `/orders/{order_id}/start-review` | Ph | REQUESTED → UNDER_REVIEW | 403, 409 |
| POST | `/orders/items/{item_id}/decision` | Ph | Record substitution decision | 422 not eligible, 409 |
| POST | `/orders/{order_id}/approve` | Ph | UNDER_REVIEW → APPROVED | 422 needs Rx note, 409 |
| POST | `/orders/{order_id}/reject` | Ph | UNDER_REVIEW → REJECTED | 409 |
| POST | `/orders/{order_id}/complete` | Ph | The sale (`sp_complete_order`) | 409 not approved / insufficient stock, 403 |
| GET | `/feed/inventory` | A | MongoDB feed docs, filters + pagination | 503 |
| GET | `/feed/inventory/{doc_id}` | A | One feed doc | 404 |
| PATCH | `/feed/inventory/{doc_id}` | A | Update `metadata`/`notes`/`flags` only | 422 other fields, 404 |
| DELETE | `/feed/inventory/{doc_id}` | A | Delete doc (MySQL untouched) | 404 |
| GET | `/feed/events` | A | Events, filter source/pharmacy/medicine/date, paginated | 503 |
| POST | `/feed/events` | A | Create manual (unverified) event | 422 |
| GET | `/feed/events/{event_id}` | A | One event | 404 |
| PATCH | `/feed/events/{event_id}` | A | Annotate event | 404 |
| DELETE | `/feed/events/{event_id}` | A | Delete event | 404 |
| POST | `/sync/run` | A | Drain the outbox now | — |
| GET | `/sync/outbox` | A | Outbox rows + counts | — |
| POST | `/sync/resync` | A | Re-enqueue all MySQL inventory and drain | — |
| POST | `/sync/retry-failed` | A | Reset exhausted FAILED rows and drain | — |
| GET | `/admin/sql-demo` | A | List whitelisted named queries | 403 |
| POST | `/admin/sql-demo/{name}/run` | A | Run one whitelisted read-only query | 404 unknown, 409 not runnable |
| GET | `/health` | public | Liveness + safety notice | — |
