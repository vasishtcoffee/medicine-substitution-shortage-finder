-- Query library (rubric 7). Each block: @name, @purpose, @why (why it qualifies), @expected (seed data).
-- The admin SQL Demo panel can run ONLY these named, read-only queries. Run all: python scripts/run_sql_demo.py database/sql/queries.sql

-- @name: q_join_availability
-- @purpose: Paracetamol-containing medicines with their ingredient, strength and stock at every pharmacy.
-- @why: JOIN across 5 tables (inventory x pharmacies x medicines x medicine_ingredients x active_ingredients) including the M:N junction.
-- @expected: one row per (pharmacy, paracetamol medicine) with the availability band, e.g. 'Pyrelief 500 Tablet' at 'Green Cross Pharmacy' = 80 / In stock.
SELECT p.name AS pharmacy, m.name AS medicine, ai.name AS ingredient, mi.strength_mg,
       i.quantity, fn_availability_band(i.quantity, i.reorder_level) AS availability
FROM inventory i
JOIN pharmacies p ON p.id = i.pharmacy_id
JOIN medicines m ON m.id = i.medicine_id
JOIN medicine_ingredients mi ON mi.medicine_id = m.id
JOIN active_ingredients ai ON ai.id = mi.ingredient_id
WHERE ai.name = 'Paracetamol' AND m.is_active = 1
ORDER BY p.name, m.name;

-- @name: q_nested_no_stock
-- @purpose: Active medicines that no pharmacy currently has in stock (shortage candidates).
-- @why: NESTED subquery - the inner SELECT runs once, independently of the outer query (NOT IN).
-- @expected: 'Febrix 500 Tablet' and 'Metformin 500 mg Tablet (Brand B)'.
SELECT m.id, m.name, m.brand
FROM medicines m
WHERE m.is_active = 1
  AND m.id NOT IN (SELECT medicine_id FROM inventory WHERE quantity > 0)
ORDER BY m.name;

-- @name: q_correlated_below_own_avg
-- @purpose: For each pharmacy, the medicines whose quantity is below THAT pharmacy's own average quantity.
-- @why: CORRELATED subquery - the inner query references the outer row (i.pharmacy_id) and is re-evaluated per row.
-- @expected: rows per pharmacy, each quantity lower than the pharmacy's average (e.g. City Care average is about 43).
SELECT p.name AS pharmacy, m.name AS medicine, i.quantity
FROM inventory i
JOIN pharmacies p ON p.id = i.pharmacy_id
JOIN medicines m ON m.id = i.medicine_id
WHERE i.quantity < (SELECT AVG(i2.quantity) FROM inventory i2 WHERE i2.pharmacy_id = i.pharmacy_id)
ORDER BY p.name, i.quantity;

-- @name: q_recursive_category_descendants
-- @purpose: Every descendant of the 'Analgesics' category with its depth and full path.
-- @why: RECURSIVE CTE - the anchor member selects the root, the recursive member joins children until none are left.
-- @expected: Antipyretic analgesics (depth 1) and NSAIDs (depth 1) under Analgesics.
WITH RECURSIVE descendants AS (
  SELECT id, name, parent_id, 0 AS depth, CAST(name AS CHAR(500)) AS path
  FROM medicine_categories WHERE name = 'Analgesics'
  UNION ALL
  SELECT c.id, c.name, c.parent_id, d.depth + 1, CONCAT(d.path, ' > ', c.name)
  FROM medicine_categories c JOIN descendants d ON c.parent_id = d.id
)
SELECT id, name, depth, path FROM descendants ORDER BY path;

-- @name: q_group_having_low_items
-- @purpose: Pharmacies with at least 3 medicines at or below their reorder level.
-- @why: aggregation with GROUP BY ... HAVING (the filter is on the aggregate, which WHERE cannot do).
-- @expected: Lakeside (6), City Care (5), Green Cross (5).
SELECT p.name AS pharmacy, COUNT(*) AS low_or_out_items, SUM(i.quantity) AS units_on_hand
FROM inventory i
JOIN pharmacies p ON p.id = i.pharmacy_id
WHERE i.quantity <= i.reorder_level
GROUP BY p.id, p.name
HAVING COUNT(*) >= 3
ORDER BY low_or_out_items DESC, p.name;

-- @name: q_open_shortages_with_stock
-- @purpose: Medicines with an OPEN shortage entry and how many units remain across all pharmacies.
-- @why: LEFT JOIN + aggregate so medicines with no inventory rows still appear (with 0).
-- @expected: Febrix 500 Tablet (0 units) and Amoxyl 500 Capsule (30 units).
SELECT m.name AS medicine, s.severity, s.reported_at, COALESCE(SUM(i.quantity), 0) AS units_all_pharmacies
FROM shortage_entries s
JOIN medicines m ON m.id = s.medicine_id
LEFT JOIN inventory i ON i.medicine_id = m.id
WHERE s.status = 'OPEN'
GROUP BY s.id, m.name, s.severity, s.reported_at
ORDER BY s.severity DESC, m.name;
