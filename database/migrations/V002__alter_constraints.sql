-- V002: ALTER TABLE examples (rubric 3). Applied once; recorded in schema_migrations.
ALTER TABLE medicines ADD CONSTRAINT chk_med_name_nonblank CHECK (CHAR_LENGTH(TRIM(name)) > 0);
ALTER TABLE medicines ADD INDEX idx_medicines_category (category_id);
ALTER TABLE orders ADD INDEX idx_orders_pharmacy_status (pharmacy_id, status);
ALTER TABLE sync_outbox ADD INDEX idx_outbox_status_id (status, id);
ALTER TABLE inventory_movements ADD CONSTRAINT chk_mov_sign CHECK (
  (movement_type = 'SALE' AND delta < 0) OR (movement_type = 'RECEIPT' AND delta > 0) OR movement_type = 'ADJUSTMENT');
ALTER TABLE shortage_entries ADD COLUMN severity ENUM('LOW','MEDIUM','HIGH') NOT NULL DEFAULT 'MEDIUM' AFTER status;
ALTER TABLE low_stock_alerts ADD INDEX idx_alert_status (status);
