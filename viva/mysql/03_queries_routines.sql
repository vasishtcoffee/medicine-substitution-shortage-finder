-- Demonstrates SELECT, joins, aggregates, ordinary/recursive CTEs, function and procedure.
-- Run: mysql ... --database=medsub_viva_<suffix> -p < viva/mysql/03_queries_routines.sql
-- Workbench: select the seeded viva schema and execute this file.
-- Expected: stock summary reflects selected DB; category tree has seeded paths;
-- function outputs Out/Low/In stock; medicine 1 candidates have eligibility reasons.
-- Affected/cleanup: read-only; session context is cleared at end. No persistent mutations.
SELECT m.name,p.name AS pharmacy,i.quantity,fn_availability_band(i.quantity,i.reorder_level) AS availability
FROM medicines m JOIN inventory i ON i.medicine_id=m.id JOIN pharmacies p ON p.id=i.pharmacy_id
ORDER BY m.id,p.id;
WITH stock AS (
 SELECT pharmacy_id,COUNT(*) AS medicines,SUM(quantity) AS units FROM inventory GROUP BY pharmacy_id
)
SELECT p.name,s.medicines,s.units FROM stock s JOIN pharmacies p ON p.id=s.pharmacy_id;
WITH RECURSIVE tree AS (
 SELECT id,name,parent_id,0 AS depth FROM medicine_categories WHERE parent_id IS NULL
 UNION ALL SELECT c.id,c.name,c.parent_id,t.depth+1 FROM medicine_categories c JOIN tree t ON c.parent_id=t.id
)
SELECT * FROM tree ORDER BY depth,id;
SELECT fn_availability_band(0,10),fn_availability_band(10,10),fn_availability_band(11,10);
SET @app_user_id=1,@app_role='admin',@app_pharmacy_id=NULL;
CALL sp_rank_candidates(1,2);
SET @app_user_id=NULL,@app_role=NULL,@app_pharmacy_id=NULL;
