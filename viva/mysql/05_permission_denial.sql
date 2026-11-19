-- Demonstrates MySQL-level permission denial, bypassing HTTP entirely.
-- Run in a NEW limited-privilege connection (not root/migrator/admin):
-- mysql ... --user=<PATIENT_SVC_USER> -p --database=medsub_viva_<suffix>
-- Then SOURCE viva/mysql/05_permission_denial.sql from repository root.
-- Workbench: use a separate connection with the patient service credentials.
-- Expected: current role app_patient_role, availability SELECT allowed;
-- SELECT inventory rejected with 1142; UPDATE rejected with 1142 (or 1143).
-- AFFECTED: no records; UPDATE is also WHERE 1=0 in case wrong credentials are used.
-- Cleanup: none. Do not use --force to mask unexpected errors in other scripts.
SELECT CURRENT_USER(),CURRENT_ROLE();
SELECT * FROM v_availability LIMIT 3;
SELECT quantity FROM inventory;
UPDATE inventory SET quantity=0 WHERE 1=0;
