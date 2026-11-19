-- Demonstrates INSERT, SELECT, UPDATE, DELETE, cascade and ROLLBACK on existing tables.
-- Run: mysql ... --database=medsub_viva_<suffix> -p < viva/mysql/02_dml_cascade_rollback.sql
-- Workbench: select the dedicated schema, open this file, execute all statements.
-- Requires seeded category 4 and ingredient 3. No fixed record IDs are overwritten.
-- AFFECTED: one newly inserted medicine and its composition row in this transaction only.
-- Expected: brand becomes Viva updated; cascade_children = 0; remaining_after_rollback = 0.
-- Cleanup: rollback removes all inserted data (auto-increment counters may advance).
START TRANSACTION;
INSERT INTO medicines(name,brand,category_id,dosage_form,strength_basis)
VALUES (CONCAT('Viva ', UUID()), 'Viva', 4, 'tablet', 'per tablet');
SET @viva_medicine = LAST_INSERT_ID();
INSERT INTO medicine_ingredients VALUES (@viva_medicine, 3, 100);
SELECT id,name,brand FROM medicines WHERE id=@viva_medicine;
UPDATE medicines SET brand='Viva updated' WHERE id=@viva_medicine;
SELECT brand FROM medicines WHERE id=@viva_medicine;
DELETE FROM medicines WHERE id=@viva_medicine;
SELECT COUNT(*) AS cascade_children FROM medicine_ingredients WHERE medicine_id=@viva_medicine;
ROLLBACK;
SELECT COUNT(*) AS remaining_after_rollback FROM medicines WHERE id=@viva_medicine;
