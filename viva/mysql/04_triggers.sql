-- Demonstrates existing inventory low-stock and outbox triggers, followed by rollback.
-- Run: mysql ... --database=medsub_viva_<suffix> -p < viva/mysql/04_triggers.sql
-- Workbench: select the seeded viva schema and execute all statements.
-- AFFECTED: new medicine + its inventory/alert/outbox rows inside one transaction only.
-- Expected: open_alerts 0 -> 1 -> 1 -> 0; outbox rows exist inside transaction.
-- Cleanup: ROLLBACK removes all demonstration rows; no seeded stock changed.
START TRANSACTION;
INSERT INTO medicines(name,brand,category_id,dosage_form,strength_basis)
VALUES (CONCAT('Viva trigger ',UUID()),'Viva',4,'tablet','per tablet');
SET @viva_medicine=LAST_INSERT_ID();
INSERT INTO inventory(pharmacy_id,medicine_id,quantity,reorder_level) VALUES (3,@viva_medicine,50,10);
SELECT COUNT(*) AS open_alerts FROM low_stock_alerts WHERE medicine_id=@viva_medicine AND status='OPEN';
UPDATE inventory SET quantity=10 WHERE pharmacy_id=3 AND medicine_id=@viva_medicine;
SELECT COUNT(*) AS open_alerts FROM low_stock_alerts WHERE medicine_id=@viva_medicine AND status='OPEN';
UPDATE inventory SET quantity=4 WHERE pharmacy_id=3 AND medicine_id=@viva_medicine;
SELECT COUNT(*) AS open_alerts FROM low_stock_alerts WHERE medicine_id=@viva_medicine AND status='OPEN';
UPDATE inventory SET quantity=40 WHERE pharmacy_id=3 AND medicine_id=@viva_medicine;
SELECT COUNT(*) AS open_alerts FROM low_stock_alerts WHERE medicine_id=@viva_medicine AND status='OPEN';
SELECT COUNT(*) AS outbox_rows FROM sync_outbox WHERE entity_id=CONCAT('ph3:med',@viva_medicine);
ROLLBACK;
