"""Generate docs/CODE_MAP.md: where every advanced SQL object is defined (file:line) and where it is used.

Line numbers come from the real files, so the map cannot go stale: re-run  python scripts/build_code_map.py
"""
import re

from envload import ROOT

MIG = ROOT / "database" / "migrations"
SQLD = ROOT / "database" / "sql"

USED = {
    # functions
    "fn_availability_band": "Views v_availability / v_my_inventory; procedures sp_rank_candidates, sp_decide_substitution, sp_write_outbox. UI: availability pills on Search, Inventory. API: GET /search, /inventory",
    "fn_ctx_user_id": "Procedures (owner checks) and views; value set per request by backend/app/db.py `session()`",
    "fn_ctx_role": "sp_require_role, v_my_* views, sp_rank_candidates (hides quantities from patients)",
    "fn_ctx_pharmacy_id": "sp_require_pharmacy_access, v_my_* views, sp_list_pharmacy_orders",
    # views
    "v_availability": "Patient-safe bands. API: GET /search, /search/availability/{id}. UI: Search screen",
    "v_users_public": "API: GET /admin/users. UI: Admin → Users",
    "v_my_inventory": "API: GET /inventory. UI: Inventory screen (pharmacist = own pharmacy only)",
    "v_my_alerts": "API: GET /alerts, /dashboard. UI: Inventory → alerts, Dashboard",
    "v_my_movements": "API: GET /inventory/movements. UI: Inventory → ledger",
    "v_candidate_check": "Base of v_candidate_eligibility (NESTED + CORRELATED NOT EXISTS set-equality in both directions)",
    "v_candidate_eligibility": "sp_equivalent_candidates, sp_candidate_rejections, sp_rank_candidates, sp_decide_substitution",
    # triggers
    "trg_inventory_low_stock_ins": "Fires on every INSERT into inventory (sp_receive_stock, seed). Alerts show in UI Inventory → alerts",
    "trg_inventory_low_stock_upd": "Fires on every UPDATE of inventory (sp_receive_stock, sp_adjust_stock, sp_complete_order, sp_set_reorder_level). Alerts show in UI Inventory → alerts",
    "trg_orders_status_transition": "Fires on every UPDATE of orders.status (sp_start_review, sp_approve_order, sp_reject_order, sp_complete_order, sp_cancel_order). UI: Orders screen buttons",
    # procedures
    "sp_eval_low_stock": "Called by both inventory triggers (one place for the low-stock rule)",
    "sp_equivalent_candidates": "API: GET /search/candidates/{id} (eligible list). UI: Search → 'Find verified-composition candidates'",
    "sp_candidate_rejections": "API: GET /search/candidates/{id} (rejected list with reasons). UI: Search, Orders",
    "sp_rank_candidates": "API: GET /search/candidates/{id} (ranking). UI: Search, Orders (pharmacist)",
    "sp_receive_stock": "API: POST /inventory/receive. UI: Inventory → Receive stock",
    "sp_adjust_stock": "API: POST /inventory/adjust",
    "sp_set_reorder_level": "API: PUT /inventory/reorder-level. UI: Inventory → Set reorder level",
    "sp_create_my_order": "API: POST /orders. UI: Search → Order…",
    "sp_list_my_orders": "API: GET /orders/mine, /dashboard. UI: Orders (patient)",
    "sp_list_pharmacy_orders": "API: GET /orders, /dashboard. UI: Orders (pharmacist)",
    "sp_list_reviews": "API: GET /orders/{id}/reviews. UI: Orders → pharmacist decisions",
    "sp_cancel_order": "API: POST /orders/{id}/cancel. UI: Orders → Cancel",
    "sp_start_review": "API: POST /orders/{id}/start-review. UI: Orders → Start review",
    "sp_decide_substitution": "API: POST /orders/items/{id}/decision. UI: Orders → Approve substitute / Dispense as requested",
    "sp_approve_order": "API: POST /orders/{id}/approve. UI: Orders → Approve order",
    "sp_reject_order": "API: POST /orders/{id}/reject. UI: Orders → Reject order",
    "sp_complete_order": "API: POST /orders/{id}/complete. UI: Orders → Complete sale. The transaction: lock, check, deduct, ledger, outbox, status",
    "sp_write_outbox": "Called inside sp_receive_stock, sp_adjust_stock, sp_set_reorder_level, sp_complete_order (same transaction)",
    "sp_enqueue_full_resync": "API: POST /sync/resync. UI: Feed Lab → Resync",
    "sp_admin_create_user": "API: POST /admin/users. UI: Admin → Users",
    "sp_admin_assign_pharmacist": "API: PUT /admin/users/{id}/pharmacy. UI: Admin → Users",
    "sp_admin_set_user_active": "API: PATCH /admin/users/{id}/active. UI: Admin → Users",
    "sp_auth_lookup": "API: POST /auth/login (backend/app/routers/auth.py)",
    "sp_auth_identity": "Every authenticated request (backend/app/security.py get_identity)",
    "sp_require_authenticated": "Guard used by the candidate procedures and sp_cancel_order",
    "sp_require_role": "Guard used by patient/admin procedures",
    "sp_require_pharmacy_access": "Guard: pharmacist may only touch the assigned pharmacy",
}
QUERY_USED = {
    "q_join_availability": "UI: Admin → SQL Demo (Run). API: POST /admin/sql-demo/{name}/run. Test: test_query_library_runs…",
    "q_nested_no_stock": "Same (nested subquery). Idea reused in sp_complete_order (IN subquery)",
    "q_correlated_below_own_avg": "Same (correlated subquery)",
    "q_recursive_category_descendants": "Same (recursive CTE rooted at a name)",
    "q_group_having_low_items": "Same (GROUP BY … HAVING)",
    "q_open_shortages_with_stock": "Same (LEFT JOIN + aggregate)",
    "cte_pharmacy_stock_summary": "Same (normal CTE + RANK() window)",
    "cte_category_tree": "Same; also used live by API GET /categories/tree (backend/app/routers/medicines.py CATEGORY_TREE_SQL) and the Admin category dropdown",
    "fn_availability_band_demo": "Same (function demo)",
}


def scan():
    rows = []
    pat = re.compile(r"CREATE\s+(?:OR REPLACE\s+)?(?:DEFINER=\S+\s+)?(?:SQL SECURITY DEFINER\s+)?(FUNCTION|PROCEDURE|TRIGGER|VIEW)\s+(\w+)", re.I)
    for f in sorted(MIG.glob("R__*.sql")):
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            m = pat.search(line)
            if m:
                rows.append((m.group(1).lower(), m.group(2), f"database/migrations/{f.name}:{i}"))
    return rows


def queries():
    out = []
    for fn in ("queries.sql", "advanced.sql"):
        for i, line in enumerate((SQLD / fn).read_text(encoding="utf-8").splitlines(), 1):
            m = re.match(r"^--\s*@name:\s*(\S+)", line)
            if m:
                out.append((m.group(1), f"database/sql/{fn}:{i}"))
    return out


def main():
    objs = scan()
    lines = ["# Code map: where each SQL object lives and where it is used", "",
             "Generated by `python scripts/build_code_map.py` from the real files (line numbers are exact). "
             "Open the file at the line shown to show the code in the viva; use `docs/VIVA_COMMANDS.md` to show it from MySQL itself.", ""]
    for kind, title in (("function", "Functions"), ("view", "Views"), ("trigger", "Triggers"), ("procedure", "Stored procedures")):
        lines += [f"## {title}", "", "| Name | Defined at | Used by |", "|---|---|---|"]
        for k, n, where in objs:
            if k == kind:
                lines.append(f"| `{n}` | `{where}` | {USED.get(n, '—')} |")
        lines.append("")
    lines += ["## Queries: JOIN, nested, correlated, recursive, CTE, aggregate", "", "| Name | Defined at | Used by |", "|---|---|---|"]
    for n, where in queries():
        if n in QUERY_USED:
            lines.append(f"| `{n}` | `{where}` | {QUERY_USED[n]} |")
    lines += ["", "## Nested / correlated subqueries inside the stored objects", "",
              "| Where | What |", "|---|---|",
              "| `v_candidate_check` (`R__20_views.sql`) | Correlated `NOT EXISTS (… NOT EXISTS …)` twice: set equality of ingredient (and strength) sets |",
              "| `sp_candidate_rejections` (`R__40_candidates.sql`) | Scalar subquery for the category + correlated `EXISTS` for a shared ingredient |",
              "| `sp_rank_candidates` (`R__40_candidates.sql`) | Derived-table subqueries (totals, open alerts) + `ROW_NUMBER() OVER` |",
              "| `sp_complete_order` (`R__50_workflow.sql`) | `IN (SELECT …)` to lock rows; derived table for the stock check |",
              "| `sp_eval_low_stock` (`R__30_triggers.sql`) | `INSERT … SELECT … WHERE NOT EXISTS (SELECT …)` |", "",
              "## Backend (FastAPI) files", "", "| File | What it does |", "|---|---|",
              "| `backend/app/main.py` | App, routers, MySQL-error → HTTP handler, background sync |",
              "| `backend/app/db.py` | Role-specific connection pools, request context, `call()` for stored procedures, deadlock retry |",
              "| `backend/app/security.py` | argon2 hashing, JWT cookie, `get_identity`, `require_roles` |",
              "| `backend/app/routers/*.py` | One router per domain: auth, medicines (catalog/admin), search, inventory, alerts, orders, feed (MongoDB CRUD), syncr, sqldemo, dashboard |",
              "| `backend/app/sync.py`, `mongo.py` | Outbox worker, MongoDB collections/validators |",
              "| `frontend/src/app/*/page.tsx` | The 7 screens; `frontend/src/lib/api.ts` is the only place that talks to the backend |",
              "", "Interactive backend: with the API running open http://localhost:8000/docs (Swagger UI): `POST /auth/login`, then call any endpoint (the session cookie is kept by the browser)."]
    (ROOT / "docs" / "CODE_MAP.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote docs/CODE_MAP.md ({len(objs)} objects, {len(queries())} named queries)")


if __name__ == "__main__":
    main()
