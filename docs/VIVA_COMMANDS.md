# Viva cheat sheet: show anything, on demand

Live database: `medsub`. Connect once and keep the window open:

```powershell
mysql -u root -p medsub          # or open MySQL Workbench on database medsub
```

## "Show CREATE TABLE for ..." (any of the 15 tables)

```sql
SHOW TABLES;
SHOW CREATE TABLE users\G
SHOW CREATE TABLE medicines\G
SHOW CREATE TABLE inventory\G
SHOW CREATE TABLE low_stock_alerts\G      -- generated column + unique key
SHOW CREATE TABLE orders\G
SHOW CREATE TABLE order_items\G
SHOW CREATE TABLE medicine_ingredients\G
SHOW CREATE TABLE inventory_movements\G
SHOW CREATE TABLE substitution_reviews\G
SHOW CREATE TABLE sync_outbox\G
DESCRIBE medicines;                        -- quick column view
```

## "Show the code of the trigger / function / procedure / view"

```sql
SHOW TRIGGERS;
SHOW CREATE TRIGGER trg_inventory_low_stock_upd\G
SHOW CREATE TRIGGER trg_orders_status_transition\G
SHOW CREATE FUNCTION fn_availability_band\G
SHOW CREATE PROCEDURE sp_equivalent_candidates\G
SHOW CREATE PROCEDURE sp_complete_order\G
SHOW CREATE PROCEDURE sp_eval_low_stock\G
SHOW CREATE VIEW v_candidate_check\G
SHOW CREATE VIEW v_availability\G
SHOW PROCEDURE STATUS WHERE Db = 'medsub';
SHOW FUNCTION STATUS  WHERE Db = 'medsub';
SELECT ROUTINE_NAME, ROUTINE_TYPE FROM information_schema.routines WHERE routine_schema = 'medsub';
```

The same code is in the files; `docs/CODE_MAP.md` gives file:line for each object and says **where it is used** (API endpoint, UI screen).

## Run the objects live (set the request context first; the backend does this for you in the app)

```sql
SET @app_user_id = 1, @app_role = 'admin', @app_pharmacy_id = NULL;
CALL sp_equivalent_candidates(1);          -- eligible substitutes for Paracetamol 500 mg
CALL sp_candidate_rejections(1);           -- rejected near-misses with reasons
CALL sp_rank_candidates(1, 2);             -- ranking at pharmacy 2
SELECT fn_availability_band(0,10), fn_availability_band(5,10), fn_availability_band(50,10);

-- trigger demo: drop stock to the reorder level -> an alert appears; restock -> it resolves
SELECT quantity, reorder_level FROM inventory WHERE pharmacy_id = 2 AND medicine_id = 11;   -- 5 / 20: already low
SELECT * FROM low_stock_alerts WHERE pharmacy_id = 2 AND medicine_id = 11;
UPDATE inventory SET quantity = 100 WHERE pharmacy_id = 2 AND medicine_id = 11;
SELECT * FROM low_stock_alerts WHERE pharmacy_id = 2 AND medicine_id = 11;                   -- status RESOLVED
UPDATE inventory SET quantity = 3 WHERE pharmacy_id = 2 AND medicine_id = 11;
SELECT * FROM low_stock_alerts WHERE pharmacy_id = 2 AND medicine_id = 11;                   -- new OPEN row

-- invalid order transition is refused by the trigger
UPDATE orders SET status = 'REQUESTED' WHERE id = 4;                                         -- ERROR 45409
```

## Advanced / nested / correlated queries

All in `database/sql/queries.sql` and `advanced.sql`; run them in the app (Admin → SQL Demo, with the "why it qualifies" text) or all at once:

```powershell
python scripts/run_sql_demo.py database/sql/queries.sql
python scripts/run_sql_demo.py database/sql/advanced.sql
python scripts/run_sql_demo.py database/sql/dml_demo.sql
```

## The two submission files

`submission/01_DDL.sql` (every CREATE/ALTER/VIEW/FUNCTION/PROCEDURE/TRIGGER/ROLE/GRANT) and `submission/02_DML.sql` (every INSERT/UPDATE/DELETE/SELECT, queries, procedure calls). Rebuild after any change: `python scripts/build_submission_sql.py`.

## "Verify the UI CRUD updates the database"

After each action in the UI, show the row in MySQL:

| UI action (role) | Verify in MySQL |
|---|---|
| Admin → Catalog → Create / Edit / Deactivate medicine | `SELECT id, name, brand, is_active FROM medicines ORDER BY id DESC LIMIT 5;` and `SELECT * FROM medicine_ingredients WHERE medicine_id = <id>;` |
| Admin → Pharmacies → Add / Edit | `SELECT * FROM pharmacies;` |
| Admin → Shortages → Add / Resolve / Delete | `SELECT * FROM shortage_entries;` |
| Admin → Users → Create / Deactivate / reassign | `SELECT id, email, role, is_active FROM users; SELECT * FROM pharmacist_assignments;` |
| Patient → Order | `SELECT * FROM orders ORDER BY id DESC LIMIT 3; SELECT * FROM order_items ORDER BY id DESC LIMIT 3;` |
| Pharmacist → Start review / Approve / Complete sale | `SELECT id, status FROM orders; SELECT * FROM substitution_reviews; SELECT * FROM inventory_movements ORDER BY id DESC LIMIT 3; SELECT quantity FROM inventory WHERE pharmacy_id=1 AND medicine_id=2;` |
| Pharmacist → Receive stock / reorder level | `SELECT * FROM inventory WHERE pharmacy_id = 1; SELECT * FROM low_stock_alerts ORDER BY id DESC LIMIT 5;` |
| Admin → Feed Lab → edit / delete (MongoDB) | `mongosh`: `use medsub_feed; db.inventory_feed.find({_id:"ph1:med2"})` (or the Feed Lab table itself); MySQL `inventory` unchanged |

## Interact with the backend

* **Swagger UI** <http://localhost:8000/docs>: `POST /auth/login` (Try it out) with a demo login, then call any endpoint; the cookie is kept by the browser.
* Raw: `curl -c jar -X POST localhost:8000/auth/login -H "Content-Type: application/json" -d "{\"email\":\"admin@medsub.demo\",\"password\":\"<DEMO_ADMIN_PASSWORD>\"}"`, then `curl -b jar localhost:8000/medicines`.
* Backend code to open: `backend/app/db.py` (pools, context), `security.py` (auth), `routers/orders.py` (stored procedure calls), `sync.py` (outbox → MongoDB).
* Start everything: `powershell -ExecutionPolicy Bypass -File scripts\start_demo.ps1`; stop: `scripts\stop_demo.ps1`.
