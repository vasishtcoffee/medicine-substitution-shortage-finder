-- Demonstrates real CREATE/ALTER TABLE, constraints, views, routines, triggers and grants.
-- Run FROM REPOSITORY ROOT: mysql --host=... --port=... --user=<migrator> -p
-- Then: SOURCE viva/mysql/01_ddl.sql
-- Prerequisite: python viva/prepare_sql.py medsub_viva_<suffix>, fresh bootstrapped schema.
-- AFFECTED: all app objects in the generated script's explicitly named viva schema.
-- Expected: CREATE/ALTER succeed; SHOW CREATE shows medicine_ingredients ON DELETE CASCADE.
-- Cleanup: none automatically; retain schema for remaining demonstrations. Never use normal app DB.
SOURCE work/viva-schema.sql
SHOW CREATE TABLE medicines;
SHOW CREATE TABLE medicine_ingredients;
SHOW TRIGGERS;
