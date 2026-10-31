-- DML demo (rubric 6): INSERT / SELECT / UPDATE / DELETE on real tables, a safe delete and a blocked delete.
-- Self-cleaning and repeatable. Run: python scripts/run_sql_demo.py database/sql/dml_demo.sql
-- Lines "-- EXPECT ERROR <errno>" mean the NEXT statement must fail with that MySQL error.

-- @name: step0_cleanup
DELETE FROM medicines WHERE id = 900;

-- @name: step1_insert
INSERT INTO medicines (id, name, brand, category_id, dosage_form, route, release_type, strength_basis)
VALUES (900, 'DML Demo Tablet 100 mg', 'Demo Labs', 4, 'tablet', 'oral', 'immediate', 'per tablet');
INSERT INTO medicine_ingredients (medicine_id, ingredient_id, strength_mg) VALUES (900, 3, 100);

-- @name: step2_select
SELECT m.id, m.name, ai.name AS ingredient, mi.strength_mg
FROM medicines m JOIN medicine_ingredients mi ON mi.medicine_id = m.id JOIN active_ingredients ai ON ai.id = mi.ingredient_id
WHERE m.id = 900;

-- @name: step3_update
UPDATE medicines SET brand = 'Demo Labs Ltd', substitution_allowed = 0 WHERE id = 900;
SELECT id, brand, substitution_allowed FROM medicines WHERE id = 900;

-- @name: step4_update_blocked_by_check
-- EXPECT ERROR 3819
UPDATE medicine_ingredients SET strength_mg = -5 WHERE medicine_id = 900;

-- @name: step5_blocked_delete
-- Medicine 1 is referenced by inventory and orders, so the foreign keys refuse the delete (soft delete is_active=0 is the app's way).
-- EXPECT ERROR 1451
DELETE FROM medicines WHERE id = 1;

-- @name: step6_safe_delete
-- Nothing else references medicine 900; its medicine_ingredients rows go with it (ON DELETE CASCADE).
DELETE FROM medicines WHERE id = 900;
SELECT (SELECT COUNT(*) FROM medicines WHERE id = 900) AS medicine_rows_left,
       (SELECT COUNT(*) FROM medicine_ingredients WHERE medicine_id = 900) AS ingredient_rows_left;
