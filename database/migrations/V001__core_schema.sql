-- V001: core tables (15). InnoDB, utf8mb4 (case-insensitive collation).
-- Rubric 3 (DDL): CREATE TABLE with PK, FK, UNIQUE, NOT NULL, CHECK, DEFAULT, ENUM, generated-column unique key.

CREATE TABLE IF NOT EXISTS users (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  email         VARCHAR(190) NOT NULL,
  full_name     VARCHAR(120) NOT NULL,
  role          ENUM('patient','pharmacist','admin') NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  is_active     TINYINT(1) NOT NULL DEFAULT 1,
  created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT uq_users_email UNIQUE (email),
  CONSTRAINT chk_users_email CHECK (email LIKE '%_@_%'),
  CONSTRAINT chk_users_active CHECK (is_active IN (0,1))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS pharmacies (
  id      INT AUTO_INCREMENT PRIMARY KEY,
  name    VARCHAR(120) NOT NULL,
  city    VARCHAR(80)  NOT NULL,
  address VARCHAR(200) NULL,
  CONSTRAINT uq_pharmacies_name UNIQUE (name)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS pharmacist_assignments (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  user_id     INT NOT NULL,
  pharmacy_id INT NOT NULL,
  CONSTRAINT uq_assignment_user UNIQUE (user_id),
  CONSTRAINT fk_assign_user FOREIGN KEY (user_id) REFERENCES users(id),
  CONSTRAINT fk_assign_pharmacy FOREIGN KEY (pharmacy_id) REFERENCES pharmacies(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS medicine_categories (
  id        INT AUTO_INCREMENT PRIMARY KEY,
  name      VARCHAR(100) NOT NULL,
  parent_id INT NULL,
  CONSTRAINT uq_category UNIQUE (parent_id, name),
  CONSTRAINT fk_category_parent FOREIGN KEY (parent_id) REFERENCES medicine_categories(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS active_ingredients (
  id   INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  CONSTRAINT uq_ingredient_name UNIQUE (name)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS medicines (
  id                    INT AUTO_INCREMENT PRIMARY KEY,
  name                  VARCHAR(150) NOT NULL,
  brand                 VARCHAR(100) NOT NULL,
  category_id           INT NOT NULL,
  dosage_form           ENUM('tablet','capsule','syrup','injection','ointment') NOT NULL,
  route                 ENUM('oral','topical','injection') NOT NULL DEFAULT 'oral',
  release_type          ENUM('immediate','extended') NOT NULL DEFAULT 'immediate',
  strength_basis        ENUM('per tablet','per capsule','per 5 ml','per ml','per gram') NOT NULL,
  requires_prescription TINYINT(1) NOT NULL DEFAULT 0,
  substitution_allowed  TINYINT(1) NOT NULL DEFAULT 1,
  is_active             TINYINT(1) NOT NULL DEFAULT 1,
  created_at            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT uq_medicines_name UNIQUE (name),
  CONSTRAINT fk_medicines_category FOREIGN KEY (category_id) REFERENCES medicine_categories(id),
  CONSTRAINT chk_med_flags CHECK (requires_prescription IN (0,1) AND substitution_allowed IN (0,1) AND is_active IN (0,1))
) ENGINE=InnoDB;

-- M:N between medicines and ingredients; strength is normalised to mg, in the basis of the medicine.
CREATE TABLE IF NOT EXISTS medicine_ingredients (
  medicine_id   INT NOT NULL,
  ingredient_id INT NOT NULL,
  strength_mg   DECIMAL(10,3) NOT NULL,
  PRIMARY KEY (medicine_id, ingredient_id),
  CONSTRAINT fk_mi_medicine FOREIGN KEY (medicine_id) REFERENCES medicines(id) ON DELETE CASCADE,
  CONSTRAINT fk_mi_ingredient FOREIGN KEY (ingredient_id) REFERENCES active_ingredients(id),
  CONSTRAINT chk_mi_strength CHECK (strength_mg > 0)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS shortage_entries (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  medicine_id INT NOT NULL,
  status      ENUM('OPEN','RESOLVED') NOT NULL DEFAULT 'OPEN',
  reported_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  resolved_at DATETIME NULL,
  source      ENUM('demo') NOT NULL DEFAULT 'demo',
  note        VARCHAR(200) NULL,
  CONSTRAINT fk_shortage_medicine FOREIGN KEY (medicine_id) REFERENCES medicines(id),
  CONSTRAINT chk_shortage_dates CHECK (resolved_at IS NULL OR resolved_at >= reported_at)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS inventory (
  pharmacy_id   INT NOT NULL,
  medicine_id   INT NOT NULL,
  quantity      INT NOT NULL DEFAULT 0,
  reorder_level INT NOT NULL DEFAULT 10,
  updated_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (pharmacy_id, medicine_id),
  CONSTRAINT fk_inv_pharmacy FOREIGN KEY (pharmacy_id) REFERENCES pharmacies(id),
  CONSTRAINT fk_inv_medicine FOREIGN KEY (medicine_id) REFERENCES medicines(id),
  CONSTRAINT chk_inv_qty CHECK (quantity >= 0),
  CONSTRAINT chk_inv_reorder CHECK (reorder_level >= 0)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS orders (
  id                INT AUTO_INCREMENT PRIMARY KEY,
  patient_id        INT NOT NULL,
  pharmacy_id       INT NOT NULL,
  status            ENUM('REQUESTED','UNDER_REVIEW','APPROVED','REJECTED','COMPLETED','CANCELLED') NOT NULL DEFAULT 'REQUESTED',
  prescription_note VARCHAR(500) NULL,
  created_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_orders_patient FOREIGN KEY (patient_id) REFERENCES users(id),
  CONSTRAINT fk_orders_pharmacy FOREIGN KEY (pharmacy_id) REFERENCES pharmacies(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS order_items (
  id                     INT AUTO_INCREMENT PRIMARY KEY,
  order_id               INT NOT NULL,
  requested_medicine_id  INT NOT NULL,
  dispensed_medicine_id  INT NULL,
  quantity               INT NOT NULL,
  CONSTRAINT fk_oi_order FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
  CONSTRAINT fk_oi_requested FOREIGN KEY (requested_medicine_id) REFERENCES medicines(id),
  CONSTRAINT fk_oi_dispensed FOREIGN KEY (dispensed_medicine_id) REFERENCES medicines(id),
  CONSTRAINT chk_oi_qty CHECK (quantity > 0)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS inventory_movements (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  pharmacy_id   INT NOT NULL,
  medicine_id   INT NOT NULL,
  movement_type ENUM('RECEIPT','SALE','ADJUSTMENT') NOT NULL,
  delta         INT NOT NULL,
  batch_no      VARCHAR(40) NULL,
  expiry_date   DATE NULL,
  order_id      INT NULL,
  actor_user_id INT NOT NULL,
  note          VARCHAR(200) NULL,
  created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_mov_inventory FOREIGN KEY (pharmacy_id, medicine_id) REFERENCES inventory(pharmacy_id, medicine_id),
  CONSTRAINT fk_mov_order FOREIGN KEY (order_id) REFERENCES orders(id),
  CONSTRAINT fk_mov_actor FOREIGN KEY (actor_user_id) REFERENCES users(id),
  CONSTRAINT chk_mov_delta CHECK (delta <> 0)
) ENGINE=InnoDB;

-- Only ONE open alert per pharmacy+medicine. MySQL has no partial indexes, so a generated column is
-- NULL while the alert is closed (UNIQUE ignores NULLs) and 'pharmacy-medicine' while it is open.
CREATE TABLE IF NOT EXISTS low_stock_alerts (
  id               INT AUTO_INCREMENT PRIMARY KEY,
  pharmacy_id      INT NOT NULL,
  medicine_id      INT NOT NULL,
  status           ENUM('OPEN','RESOLVED') NOT NULL DEFAULT 'OPEN',
  quantity_at_open INT NOT NULL,
  opened_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  resolved_at      DATETIME NULL,
  open_alert_key   VARCHAR(40) GENERATED ALWAYS AS (IF(status = 'OPEN', CONCAT(pharmacy_id, '-', medicine_id), NULL)) STORED,
  CONSTRAINT uq_one_open_alert UNIQUE (open_alert_key),
  CONSTRAINT fk_alert_inventory FOREIGN KEY (pharmacy_id, medicine_id) REFERENCES inventory(pharmacy_id, medicine_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS substitution_reviews (
  id                   INT AUTO_INCREMENT PRIMARY KEY,
  order_item_id        INT NOT NULL,
  proposed_medicine_id INT NOT NULL,
  reviewer_id          INT NOT NULL,
  decision             ENUM('APPROVED','REJECTED') NOT NULL,
  decided_at           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  note                 VARCHAR(300) NULL,
  eligibility_reason   VARCHAR(300) NOT NULL,
  ranking_snapshot     JSON NULL,
  CONSTRAINT fk_sr_item FOREIGN KEY (order_item_id) REFERENCES order_items(id) ON DELETE CASCADE,
  CONSTRAINT fk_sr_medicine FOREIGN KEY (proposed_medicine_id) REFERENCES medicines(id),
  CONSTRAINT fk_sr_reviewer FOREIGN KEY (reviewer_id) REFERENCES users(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS sync_outbox (
  id           INT AUTO_INCREMENT PRIMARY KEY,
  operation    VARCHAR(40) NOT NULL,
  entity_id    VARCHAR(80) NOT NULL,
  payload      JSON NOT NULL,
  status       ENUM('PENDING','DONE','FAILED') NOT NULL DEFAULT 'PENDING',
  attempts     INT NOT NULL DEFAULT 0,
  last_error   VARCHAR(500) NULL,
  created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  processed_at DATETIME NULL,
  CONSTRAINT chk_outbox_op CHECK (operation IN ('UPSERT_INVENTORY_FEED','APPEND_FEED_EVENT')),
  CONSTRAINT chk_outbox_attempts CHECK (attempts >= 0)
) ENGINE=InnoDB;
