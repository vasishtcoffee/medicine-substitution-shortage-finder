# Mini-project demo: what to bring and say

## Bring / have ready

| Item | Where |
|---|---|
| **ER diagram (hard copy)**, relational schema, strong/weak classification, attribute types | Open `docs/ER_AND_SCHEMA_PRINT.html` in a browser → Ctrl+P → landscape (4 pages). Standalone image: `docs/ER_diagram.svg` |
| **Two .sql files** (all DDL, all DML) | `submission/01_DDL.sql`, `submission/02_DML.sql` (rebuild: `python scripts/build_submission_sql.py`) |
| `SHOW CREATE TABLE …` on any table | `docs/VIVA_COMMANDS.md` (mysql window already connected to `medsub`) |
| Code of advanced queries, nested queries, triggers, functions, procedures + **where each is used** | `docs/CODE_MAP.md` (file:line + API endpoint + UI screen) |
| Running app for CRUD checks | `powershell -ExecutionPolicy Bypass -File scripts\start_demo.ps1` → UI http://localhost:3000, Swagger http://localhost:8000/docs |

Before the viva: start the demo, log in once as each role, keep a MySQL window open on `medsub`, and have `01_DDL.sql`, `02_DML.sql`, `docs/CODE_MAP.md` open in an editor.

## 5-minute script

**0:00 – 1:15 Problem statement.** When a medicine is out of stock, a patient or pharmacist needs to know (1) which pharmacies still have it, and (2) which *other* medicines contain exactly the same active ingredients, strengths, dosage form, route and release type. Matching is strictly rule-based (not guessing), and **a pharmacist must verify every substitution before any sale**. Stock, orders and the whole matching logic live in MySQL; MongoDB keeps a flexible event/feed copy. Three roles: patient (sees only availability bands), pharmacist (own pharmacy, reviews and sells), admin (catalog, users, shortages). Educational demo, synthetic data.

**1:15 – 2:45 ER diagram (hard copy).** Point at: users → orders → order_items; pharmacies ↔ medicines through inventory (M:N, carries quantity); medicines ↔ active_ingredients through medicine_ingredients (M:N, carries strength); medicine_categories is recursive (parent); inventory → low_stock_alerts / inventory_movements; order_items → substitution_reviews. 15 tables.

**2:45 – 4:00 Relational schema details.**
* **8 strong entities:** users, pharmacies, medicine_categories, active_ingredients, medicines, orders, shortage_entries, sync_outbox.
* **4 weak (existence-dependent) entities:** order_items (owner orders), substitution_reviews (owner order_items), inventory_movements and low_stock_alerts (owner inventory); each is identified through a NOT NULL foreign key to its owner.
* **3 associative entities (relationship tables):** inventory (pharmacies M:N medicines), medicine_ingredients (medicines M:N active_ingredients), pharmacist_assignments (users 1:1 pharmacies).
* **Attribute types:** key (17 PK columns, composite keys in inventory and medicine_ingredients), foreign keys (23), unique (email, medicine name), composite attributes decomposed (address → city + address), multivalued moved to its own table (ingredients), derived (stored generated `open_alert_key`; computed availability band, composition, eligibility), optional/NULL (16 columns, e.g. `parent_id`, `dispensed_medicine_id`, `resolved_at`), ENUM (13), relationship attributes (quantity, strength_mg). Table is on page 4 of the printout.

**4:00 – 5:00 Hand over / invite checks.** "All DDL and DML are in two files; I can run `SHOW CREATE TABLE` for any table. Here is the UI; after each create/update/delete I will show the row in MySQL." Then follow the CRUD table in `docs/VIVA_COMMANDS.md`.

## CRUD she may ask to verify in the UI (all update MySQL, all shown in `VIVA_COMMANDS.md`)

| Entity | Create | Read | Update | Delete |
|---|---|---|---|---|
| Medicines (+ composition) | Admin → Catalog → Create | Catalog table, Search | Admin → Catalog → Edit | Deactivate (soft delete, history kept; hard DELETE is blocked by FKs, shown in `dml_demo.sql`) |
| Pharmacies | Admin → Pharmacies | table | Edit | not offered (referenced by stock/orders) |
| Shortages | Admin → Shortages | table | Resolve | **Delete** (hard DELETE) |
| Users | Admin → Users | table | Deactivate / reassign pharmacy | deactivate (rows referenced by orders) |
| Orders | Patient: Search → Order | Orders | Pharmacist: review → approve → complete; Cancel | status machine (no deletes) |
| Stock | Pharmacist: Receive stock | Inventory, alerts | Set reorder level | — |
| MongoDB feed / events | Feed Lab: create event; sync | Feed Lab filters | Edit notes/metadata | Delete (MySQL untouched) |

## Likely follow-ups, with the answer location

* "Show a nested / correlated / recursive query" → Admin → SQL Demo, or `database/sql/queries.sql`.
* "Show the trigger" → `docs/CODE_MAP.md` → `R__30_triggers.sql`; run the demo in `VIVA_COMMANDS.md`.
* "Where is this procedure used?" → `docs/CODE_MAP.md` "Used by" column.
* "Show me the backend" → Swagger UI (`/docs`) + `backend/app/routers/orders.py` (it only calls stored procedures).
* More Q&A: `docs/VIVA_GUIDE.md`.
