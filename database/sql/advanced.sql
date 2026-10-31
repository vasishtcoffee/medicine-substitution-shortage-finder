-- Advanced objects demo (rubric 8). The objects themselves are defined in database/migrations/R__*.sql:
--   sp_equivalent_candidates / sp_candidate_rejections / sp_rank_candidates : R__40_candidates.sql
--   sp_complete_order, sp_receive_stock, ...                                : R__50_workflow.sql
--   fn_availability_band                                                    : R__10_context_and_guards.sql
--   trg_inventory_low_stock_ins / _upd, trg_orders_status_transition        : R__30_triggers.sql
-- Run all: python scripts/run_sql_demo.py database/sql/advanced.sql   (runs as the migrator with an admin context)

-- @name: cte_pharmacy_stock_summary
-- @purpose: Per-pharmacy stock totals and low-stock counts, then ranked by risk (most low items first).
-- @why: ordinary (non-recursive) CTE feeding a window function RANK().
-- @expected: Three rows; Lakeside ranks 1 (6 low/out items, 132 units), Green Cross 2, City Care 3.
-- @runnable: yes
WITH cte_pharmacy_stock_summary AS (
  SELECT p.id, p.name, COUNT(*) AS items, SUM(i.quantity) AS total_units,
         SUM(i.quantity <= i.reorder_level) AS low_items
  FROM pharmacies p JOIN inventory i ON i.pharmacy_id = p.id
  GROUP BY p.id, p.name
)
SELECT s.name AS pharmacy, s.items, s.total_units, s.low_items,
       RANK() OVER (ORDER BY s.low_items DESC, s.total_units ASC) AS risk_rank
FROM cte_pharmacy_stock_summary s
ORDER BY risk_rank;

-- @name: cte_category_tree
-- @purpose: The whole medicine-category tree with depth and full path (also served by GET /categories/tree).
-- @why: RECURSIVE CTE over the self-referencing table medicine_categories.
-- @expected: 12 rows: Pharmaceuticals (depth 0) down to 3-level leaves such as 'Pharmaceuticals > Analgesics > NSAIDs'.
-- @runnable: yes
WITH RECURSIVE cte_category_tree AS (
  SELECT id, name, parent_id, 0 AS depth, CAST(name AS CHAR(500)) AS path
  FROM medicine_categories WHERE parent_id IS NULL
  UNION ALL
  SELECT c.id, c.name, c.parent_id, t.depth + 1, CONCAT(t.path, ' > ', c.name)
  FROM medicine_categories c JOIN cte_category_tree t ON c.parent_id = t.id
)
SELECT id, name, parent_id, depth, path FROM cte_category_tree ORDER BY path;

-- @name: fn_availability_band_demo
-- @purpose: The stored function maps quantity + reorder level to a patient-safe band.
-- @why: shows the stored FUNCTION on boundary values (0, at reorder level, above it).
-- @expected: Out, Low, Low, In stock.
-- @runnable: yes
SELECT fn_availability_band(0, 10) AS q0, fn_availability_band(5, 10) AS q5,
       fn_availability_band(10, 10) AS q10, fn_availability_band(11, 10) AS q11;

-- ---- demos below call procedures that need a request context, so they are not offered in the web SQL panel ----

-- @name: demo_candidates
-- @purpose: Substitution eligibility for 'Paracetamol 500 mg Tablet' (medicine 1) - eligible, ranked, and rejected near-misses.
-- @expected: eligible = Pyrelief 500 Tablet, Febrix 500 Tablet; rejected = 650 mg, caffeine combo, syrup, ER, look-alike Parasprin, discontinued.
-- @runnable: no
CALL sp_equivalent_candidates(1);
CALL sp_rank_candidates(1, 2);
CALL sp_candidate_rejections(1);

-- @name: demo_trigger_low_stock
-- @purpose: Trigger demo - dropping stock to the reorder level opens exactly ONE alert; restocking resolves it.
-- @expected: open alerts 0 -> 1 -> still 1 (no duplicate) -> 0; the scratch row is removed at the end.
-- @runnable: no
INSERT INTO medicines (id, name, brand, category_id, dosage_form, strength_basis)
  VALUES (901, 'Trigger Demo Tablet', 'Demo Labs', 4, 'tablet', 'per tablet') ON DUPLICATE KEY UPDATE id = id;
INSERT INTO inventory (pharmacy_id, medicine_id, quantity, reorder_level) VALUES (3, 901, 50, 10)
  ON DUPLICATE KEY UPDATE quantity = 50, reorder_level = 10;
SELECT COUNT(*) AS open_alerts FROM low_stock_alerts WHERE pharmacy_id = 3 AND medicine_id = 901 AND status = 'OPEN';
UPDATE inventory SET quantity = 10 WHERE pharmacy_id = 3 AND medicine_id = 901;
SELECT COUNT(*) AS open_alerts FROM low_stock_alerts WHERE pharmacy_id = 3 AND medicine_id = 901 AND status = 'OPEN';
UPDATE inventory SET quantity = 4 WHERE pharmacy_id = 3 AND medicine_id = 901;
SELECT COUNT(*) AS open_alerts FROM low_stock_alerts WHERE pharmacy_id = 3 AND medicine_id = 901 AND status = 'OPEN';
UPDATE inventory SET quantity = 40 WHERE pharmacy_id = 3 AND medicine_id = 901;
SELECT COUNT(*) AS open_alerts, (SELECT COUNT(*) FROM low_stock_alerts WHERE pharmacy_id = 3 AND medicine_id = 901 AND status = 'RESOLVED') AS resolved_alerts
  FROM low_stock_alerts WHERE pharmacy_id = 3 AND medicine_id = 901 AND status = 'OPEN';
DELETE FROM low_stock_alerts WHERE medicine_id = 901;
DELETE FROM inventory WHERE medicine_id = 901;
DELETE FROM medicines WHERE id = 901;

-- @name: demo_sale_transaction
-- @purpose: sp_complete_order on seed order 3 (APPROVED, 2 x Pyrelief at City Care) needs the pharmacist context of City Care;
--           run it from the app (Orders screen) or tests/sql/test_sale.py, which exercise it with real accounts.
-- @runnable: no
-- SET @app_user_id = 2, @app_role = 'pharmacist', @app_pharmacy_id = 1;  CALL sp_complete_order(3, 2);
