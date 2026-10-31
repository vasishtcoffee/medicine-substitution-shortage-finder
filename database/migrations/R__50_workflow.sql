-- R__50: guarded workflow procedures. All SQL SECURITY DEFINER; each checks the trusted request context.
-- Error numbers: 45401 unauthenticated, 45403 forbidden, 45404 not found, 45409 conflict, 45422 invalid input.

DROP PROCEDURE IF EXISTS sp_auth_lookup;
DROP PROCEDURE IF EXISTS sp_auth_identity;
DROP PROCEDURE IF EXISTS sp_write_outbox;
DROP PROCEDURE IF EXISTS sp_receive_stock;
DROP PROCEDURE IF EXISTS sp_adjust_stock;
DROP PROCEDURE IF EXISTS sp_set_reorder_level;
DROP PROCEDURE IF EXISTS sp_create_my_order;
DROP PROCEDURE IF EXISTS sp_list_my_orders;
DROP PROCEDURE IF EXISTS sp_list_pharmacy_orders;
DROP PROCEDURE IF EXISTS sp_list_reviews;
DROP PROCEDURE IF EXISTS sp_cancel_order;
DROP PROCEDURE IF EXISTS sp_start_review;
DROP PROCEDURE IF EXISTS sp_decide_substitution;
DROP PROCEDURE IF EXISTS sp_approve_order;
DROP PROCEDURE IF EXISTS sp_reject_order;
DROP PROCEDURE IF EXISTS sp_complete_order;
DROP PROCEDURE IF EXISTS sp_enqueue_full_resync;
DROP PROCEDURE IF EXISTS sp_admin_create_user;
DROP PROCEDURE IF EXISTS sp_admin_assign_pharmacist;
DROP PROCEDURE IF EXISTS sp_admin_set_user_active;

DELIMITER $$

-- ---------------------------------------------------------------- authentication lookups (auth account only)
CREATE DEFINER={{DEFINER}} PROCEDURE sp_auth_lookup(IN p_email VARCHAR(190))
  SQL SECURITY DEFINER
BEGIN
  SELECT id, role, password_hash, is_active FROM users WHERE email = p_email;
END$$

CREATE DEFINER={{DEFINER}} PROCEDURE sp_auth_identity(IN p_user_id INT)
  SQL SECURITY DEFINER
BEGIN
  SELECT u.id, u.email, u.full_name, u.role, u.is_active, pa.pharmacy_id
  FROM users u LEFT JOIN pharmacist_assignments pa ON pa.user_id = u.id
  WHERE u.id = p_user_id;
END$$

-- ---------------------------------------------------------------- outbox (internal; same transaction as the change)
-- Contract with MongoDB (docs/NOSQL.md): two rows per stock change.
CREATE DEFINER={{DEFINER}} PROCEDURE sp_write_outbox(IN p_pharmacy_id INT, IN p_medicine_id INT, IN p_source VARCHAR(20),
    IN p_movement_id INT, IN p_delta INT, IN p_order_id INT, IN p_batch_no VARCHAR(40), IN p_expiry DATE)
  SQL SECURITY DEFINER
BEGIN
  DECLARE v_qty INT;
  DECLARE v_reorder INT;
  DECLARE v_now VARCHAR(19);
  SELECT quantity, reorder_level INTO v_qty, v_reorder
  FROM inventory WHERE pharmacy_id = p_pharmacy_id AND medicine_id = p_medicine_id;
  SET v_now = DATE_FORMAT(UTC_TIMESTAMP(), '%Y-%m-%dT%H:%i:%s');
  INSERT INTO sync_outbox (operation, entity_id, payload) VALUES
    ('UPSERT_INVENTORY_FEED', CONCAT('ph', p_pharmacy_id, ':med', p_medicine_id),
     JSON_OBJECT('pharmacy_id', p_pharmacy_id, 'medicine_id', p_medicine_id, 'quantity', v_qty,
                 'reorder_level', v_reorder, 'availability', fn_availability_band(v_qty, v_reorder),
                 'low_stock', IF(v_qty <= v_reorder, CAST('true' AS JSON), CAST('false' AS JSON)),
                 'source', p_source, 'occurred_at', v_now,
                 'metadata', JSON_OBJECT('last_batch_no', p_batch_no, 'last_expiry_date', p_expiry)));
  -- p_movement_id = 0 means "no ledger movement" (e.g. reorder-level change): only the document upsert is needed
  IF p_movement_id > 0 THEN
    INSERT INTO sync_outbox (operation, entity_id, payload) VALUES
      ('APPEND_FEED_EVENT', CONCAT(p_source, ':', p_movement_id),
       JSON_OBJECT('source', p_source, 'pharmacy_id', p_pharmacy_id, 'medicine_id', p_medicine_id,
                   'delta', p_delta, 'order_id', p_order_id, 'quantity_after', v_qty, 'occurred_at', v_now,
                   'details', JSON_OBJECT('batch_no', p_batch_no, 'expiry_date', p_expiry)));
  END IF;
END$$

-- ---------------------------------------------------------------- stock
CREATE DEFINER={{DEFINER}} PROCEDURE sp_receive_stock(IN p_pharmacy_id INT, IN p_medicine_id INT, IN p_quantity INT,
    IN p_batch_no VARCHAR(40), IN p_expiry DATE)
  SQL SECURITY DEFINER
BEGIN
  DECLARE v_mov INT;
  DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
  CALL sp_require_pharmacy_access(p_pharmacy_id, 1);
  IF p_quantity IS NULL OR p_quantity <= 0 THEN
    SIGNAL SQLSTATE '45000' SET MYSQL_ERRNO = 45422, MESSAGE_TEXT = 'Received quantity must be positive';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM medicines WHERE id = p_medicine_id AND is_active = 1)
     OR NOT EXISTS (SELECT 1 FROM pharmacies WHERE id = p_pharmacy_id) THEN
    SIGNAL SQLSTATE '45000' SET MYSQL_ERRNO = 45404, MESSAGE_TEXT = 'Medicine or pharmacy not found';
  END IF;
  START TRANSACTION;
  INSERT INTO inventory (pharmacy_id, medicine_id, quantity) VALUES (p_pharmacy_id, p_medicine_id, p_quantity) AS n
    ON DUPLICATE KEY UPDATE quantity = inventory.quantity + n.quantity;
  INSERT INTO inventory_movements (pharmacy_id, medicine_id, movement_type, delta, batch_no, expiry_date, actor_user_id)
    VALUES (p_pharmacy_id, p_medicine_id, 'RECEIPT', p_quantity, p_batch_no, p_expiry, fn_ctx_user_id());
  SET v_mov = LAST_INSERT_ID();
  CALL sp_write_outbox(p_pharmacy_id, p_medicine_id, 'receipt', v_mov, p_quantity, NULL, p_batch_no, p_expiry);
  COMMIT;
  SELECT quantity, reorder_level FROM inventory WHERE pharmacy_id = p_pharmacy_id AND medicine_id = p_medicine_id;
END$$

CREATE DEFINER={{DEFINER}} PROCEDURE sp_adjust_stock(IN p_pharmacy_id INT, IN p_medicine_id INT, IN p_delta INT, IN p_note VARCHAR(200))
  SQL SECURITY DEFINER
BEGIN
  DECLARE v_qty INT;
  DECLARE v_mov INT;
  DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
  CALL sp_require_pharmacy_access(p_pharmacy_id, 1);
  IF p_delta IS NULL OR p_delta = 0 THEN
    SIGNAL SQLSTATE '45000' SET MYSQL_ERRNO = 45422, MESSAGE_TEXT = 'Adjustment must be non-zero';
  END IF;
  START TRANSACTION;
  SELECT quantity INTO v_qty FROM inventory WHERE pharmacy_id = p_pharmacy_id AND medicine_id = p_medicine_id FOR UPDATE;
  IF v_qty IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MYSQL_ERRNO = 45404, MESSAGE_TEXT = 'No inventory row for this pharmacy and medicine';
  END IF;
  IF v_qty + p_delta < 0 THEN
    SIGNAL SQLSTATE '45000' SET MYSQL_ERRNO = 45409, MESSAGE_TEXT = 'Adjustment would make stock negative';
  END IF;
  UPDATE inventory SET quantity = quantity + p_delta WHERE pharmacy_id = p_pharmacy_id AND medicine_id = p_medicine_id;
  INSERT INTO inventory_movements (pharmacy_id, medicine_id, movement_type, delta, note, actor_user_id)
    VALUES (p_pharmacy_id, p_medicine_id, 'ADJUSTMENT', p_delta, p_note, fn_ctx_user_id());
  SET v_mov = LAST_INSERT_ID();
  CALL sp_write_outbox(p_pharmacy_id, p_medicine_id, 'adjustment', v_mov, p_delta, NULL, NULL, NULL);
  COMMIT;
  SELECT quantity, reorder_level FROM inventory WHERE pharmacy_id = p_pharmacy_id AND medicine_id = p_medicine_id;
END$$

CREATE DEFINER={{DEFINER}} PROCEDURE sp_set_reorder_level(IN p_pharmacy_id INT, IN p_medicine_id INT, IN p_level INT)
  SQL SECURITY DEFINER
BEGIN
  DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
  CALL sp_require_pharmacy_access(p_pharmacy_id, 1);
  IF p_level IS NULL OR p_level < 0 THEN
    SIGNAL SQLSTATE '45000' SET MYSQL_ERRNO = 45422, MESSAGE_TEXT = 'Reorder level must be >= 0';
  END IF;
  START TRANSACTION;
  UPDATE inventory SET reorder_level = p_level WHERE pharmacy_id = p_pharmacy_id AND medicine_id = p_medicine_id;
  IF ROW_COUNT() = 0 AND NOT EXISTS (SELECT 1 FROM inventory WHERE pharmacy_id = p_pharmacy_id AND medicine_id = p_medicine_id) THEN
    SIGNAL SQLSTATE '45000' SET MYSQL_ERRNO = 45404, MESSAGE_TEXT = 'No inventory row for this pharmacy and medicine';
  END IF;
  CALL sp_write_outbox(p_pharmacy_id, p_medicine_id, 'adjustment', 0, 0, NULL, NULL, NULL);
  COMMIT;
  SELECT quantity, reorder_level FROM inventory WHERE pharmacy_id = p_pharmacy_id AND medicine_id = p_medicine_id;
END$$

-- ---------------------------------------------------------------- orders (patient)
CREATE DEFINER={{DEFINER}} PROCEDURE sp_create_my_order(IN p_pharmacy_id INT, IN p_medicine_id INT, IN p_quantity INT, IN p_prescription_note VARCHAR(500))
  SQL SECURITY DEFINER
BEGIN
  DECLARE v_order INT;
  DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
  CALL sp_require_role('patient', NULL);
  IF p_quantity IS NULL OR p_quantity <= 0 THEN
    SIGNAL SQLSTATE '45000' SET MYSQL_ERRNO = 45422, MESSAGE_TEXT = 'Quantity must be positive';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pharmacies WHERE id = p_pharmacy_id)
     OR NOT EXISTS (SELECT 1 FROM medicines WHERE id = p_medicine_id AND is_active = 1) THEN
    SIGNAL SQLSTATE '45000' SET MYSQL_ERRNO = 45404, MESSAGE_TEXT = 'Medicine or pharmacy not found';
  END IF;
  START TRANSACTION;
  INSERT INTO orders (patient_id, pharmacy_id, prescription_note) VALUES (fn_ctx_user_id(), p_pharmacy_id, p_prescription_note);
  SET v_order = LAST_INSERT_ID();
  INSERT INTO order_items (order_id, requested_medicine_id, quantity) VALUES (v_order, p_medicine_id, p_quantity);
  COMMIT;
  SELECT v_order AS order_id, 'REQUESTED' AS status;
END$$

CREATE DEFINER={{DEFINER}} PROCEDURE sp_list_my_orders()
  SQL SECURITY DEFINER
BEGIN
  CALL sp_require_role('patient', NULL);
  SELECT o.id AS order_id, o.status, o.pharmacy_id, ph.name AS pharmacy_name, o.prescription_note, o.created_at,
         oi.id AS item_id, oi.requested_medicine_id, rm.name AS requested_name,
         oi.dispensed_medicine_id, dm.name AS dispensed_name, oi.quantity
  FROM orders o
  JOIN pharmacies ph ON ph.id = o.pharmacy_id
  JOIN order_items oi ON oi.order_id = o.id
  JOIN medicines rm ON rm.id = oi.requested_medicine_id
  LEFT JOIN medicines dm ON dm.id = oi.dispensed_medicine_id
  WHERE o.patient_id = fn_ctx_user_id()
  ORDER BY o.id DESC, oi.id;
END$$

-- ---------------------------------------------------------------- orders (pharmacist / admin read)
CREATE DEFINER={{DEFINER}} PROCEDURE sp_list_pharmacy_orders(IN p_status VARCHAR(20))
  SQL SECURITY DEFINER
BEGIN
  CALL sp_require_role('pharmacist', 'admin');
  SELECT o.id AS order_id, o.status, o.pharmacy_id, ph.name AS pharmacy_name, u.full_name AS patient_name,
         o.prescription_note, o.created_at,
         oi.id AS item_id, oi.requested_medicine_id, rm.name AS requested_name, rm.requires_prescription,
         oi.dispensed_medicine_id, dm.name AS dispensed_name, oi.quantity
  FROM orders o
  JOIN pharmacies ph ON ph.id = o.pharmacy_id
  JOIN users u ON u.id = o.patient_id
  JOIN order_items oi ON oi.order_id = o.id
  JOIN medicines rm ON rm.id = oi.requested_medicine_id
  LEFT JOIN medicines dm ON dm.id = oi.dispensed_medicine_id
  WHERE (p_status IS NULL OR o.status = p_status)
    AND (fn_ctx_role() = 'admin' OR o.pharmacy_id = fn_ctx_pharmacy_id())
  ORDER BY o.id DESC, oi.id;
END$$

CREATE DEFINER={{DEFINER}} PROCEDURE sp_list_reviews(IN p_order_id INT)
  SQL SECURITY DEFINER
BEGIN
  DECLARE v_patient INT;
  DECLARE v_pharmacy INT;
  CALL sp_require_authenticated();
  SELECT patient_id, pharmacy_id INTO v_patient, v_pharmacy FROM orders WHERE id = p_order_id;
  IF v_patient IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MYSQL_ERRNO = 45404, MESSAGE_TEXT = 'Order not found';
  END IF;
  IF COALESCE(fn_ctx_role() = 'admin' OR (fn_ctx_role() = 'patient' AND v_patient = fn_ctx_user_id())
              OR (fn_ctx_role() = 'pharmacist' AND v_pharmacy = fn_ctx_pharmacy_id()), 0) = 0 THEN
    SIGNAL SQLSTATE '45000' SET MYSQL_ERRNO = 45403, MESSAGE_TEXT = 'Access denied: not your order';
  END IF;
  SELECT r.id, r.order_item_id, r.proposed_medicine_id, m.name AS proposed_name, r.decision, r.decided_at,
         r.note, r.eligibility_reason, r.ranking_snapshot, rv.full_name AS reviewer_name
  FROM substitution_reviews r
  JOIN order_items oi ON oi.id = r.order_item_id
  JOIN medicines m ON m.id = r.proposed_medicine_id
  JOIN users rv ON rv.id = r.reviewer_id
  WHERE oi.order_id = p_order_id ORDER BY r.id;
END$$

-- ---------------------------------------------------------------- order workflow
CREATE DEFINER={{DEFINER}} PROCEDURE sp_cancel_order(IN p_order_id INT)
  SQL SECURITY DEFINER
BEGIN
  DECLARE v_patient INT;
  DECLARE v_pharmacy INT;
  DECLARE v_status VARCHAR(20);
  DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
  CALL sp_require_authenticated();
  START TRANSACTION;
  SELECT patient_id, pharmacy_id, status INTO v_patient, v_pharmacy, v_status FROM orders WHERE id = p_order_id FOR UPDATE;
  IF v_status IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MYSQL_ERRNO = 45404, MESSAGE_TEXT = 'Order not found';
  END IF;
  IF COALESCE(fn_ctx_role() = 'admin' OR (fn_ctx_role() = 'patient' AND v_patient = fn_ctx_user_id())
              OR (fn_ctx_role() = 'pharmacist' AND v_pharmacy = fn_ctx_pharmacy_id()), 0) = 0 THEN
    SIGNAL SQLSTATE '45000' SET MYSQL_ERRNO = 45403, MESSAGE_TEXT = 'Access denied: not your order';
  END IF;
  UPDATE orders SET status = 'CANCELLED' WHERE id = p_order_id;   -- trigger rejects terminal states
  COMMIT;
  SELECT p_order_id AS order_id, 'CANCELLED' AS status;
END$$

CREATE DEFINER={{DEFINER}} PROCEDURE sp_start_review(IN p_order_id INT)
  SQL SECURITY DEFINER
BEGIN
  DECLARE v_pharmacy INT;
  DECLARE v_status VARCHAR(20);
  DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
  START TRANSACTION;
  SELECT pharmacy_id, status INTO v_pharmacy, v_status FROM orders WHERE id = p_order_id FOR UPDATE;
  IF v_status IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MYSQL_ERRNO = 45404, MESSAGE_TEXT = 'Order not found';
  END IF;
  CALL sp_require_pharmacy_access(v_pharmacy, 0);
  IF v_status <> 'REQUESTED' THEN
    SIGNAL SQLSTATE '45000' SET MYSQL_ERRNO = 45409, MESSAGE_TEXT = 'Order is not in REQUESTED state';
  END IF;
  UPDATE orders SET status = 'UNDER_REVIEW' WHERE id = p_order_id AND status = 'REQUESTED';
  COMMIT;
  SELECT p_order_id AS order_id, 'UNDER_REVIEW' AS status;
END$$

-- The pharmacist's decision on one proposed medicine (section 8, step 3). Nothing is substituted without it.
CREATE DEFINER={{DEFINER}} PROCEDURE sp_decide_substitution(IN p_item_id INT, IN p_proposed_medicine_id INT,
    IN p_decision VARCHAR(10), IN p_note VARCHAR(300))
  SQL SECURITY DEFINER
BEGIN
  DECLARE v_order INT;
  DECLARE v_requested INT;
  DECLARE v_pharmacy INT;
  DECLARE v_status VARCHAR(20);
  DECLARE v_eligible INT DEFAULT 0;
  DECLARE v_reason VARCHAR(300);
  DECLARE v_band VARCHAR(10);
  DECLARE v_stocking INT;
  DECLARE v_review INT;
  DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
  IF p_decision IS NULL OR p_decision NOT IN ('APPROVED', 'REJECTED') THEN
    SIGNAL SQLSTATE '45000' SET MYSQL_ERRNO = 45422, MESSAGE_TEXT = 'Decision must be APPROVED or REJECTED';
  END IF;
  START TRANSACTION;
  SELECT oi.order_id, oi.requested_medicine_id, o.pharmacy_id, o.status
    INTO v_order, v_requested, v_pharmacy, v_status
  FROM order_items oi JOIN orders o ON o.id = oi.order_id WHERE oi.id = p_item_id FOR UPDATE;
  IF v_order IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MYSQL_ERRNO = 45404, MESSAGE_TEXT = 'Order item not found';
  END IF;
  CALL sp_require_pharmacy_access(v_pharmacy, 0);
  IF v_status <> 'UNDER_REVIEW' THEN
    SIGNAL SQLSTATE '45000' SET MYSQL_ERRNO = 45409, MESSAGE_TEXT = 'Order is not UNDER_REVIEW';
  END IF;
  IF p_proposed_medicine_id = v_requested THEN
    SET v_eligible = 1;
    SET v_reason = 'Requested medicine itself (no substitution)';
  ELSE
    SELECT COUNT(*) INTO v_eligible FROM v_candidate_eligibility
    WHERE requested_id = v_requested AND candidate_id = p_proposed_medicine_id AND is_eligible = 1;
    SET v_reason = IF(v_eligible = 1, 'Same active ingredients and strengths, dosage form, route and release type',
                      'NOT an eligible composition match');
  END IF;
  IF p_decision = 'APPROVED' AND v_eligible = 0 THEN
    SIGNAL SQLSTATE '45000' SET MYSQL_ERRNO = 45422, MESSAGE_TEXT = 'Proposed medicine is not an eligible composition match';
  END IF;
  SELECT fn_availability_band(COALESCE(quantity, 0), COALESCE(reorder_level, 0)) INTO v_band
  FROM inventory WHERE pharmacy_id = v_pharmacy AND medicine_id = p_proposed_medicine_id;
  SELECT COUNT(*) INTO v_stocking FROM inventory WHERE medicine_id = p_proposed_medicine_id AND quantity > 0;
  INSERT INTO substitution_reviews (order_item_id, proposed_medicine_id, reviewer_id, decision, note, eligibility_reason, ranking_snapshot)
  VALUES (p_item_id, p_proposed_medicine_id, fn_ctx_user_id(), p_decision, p_note, v_reason,
          JSON_OBJECT('pharmacy_id', v_pharmacy, 'availability_here', COALESCE(v_band, 'Out'), 'pharmacies_stocking', v_stocking));
  SET v_review = LAST_INSERT_ID();
  IF p_decision = 'APPROVED' THEN
    UPDATE order_items SET dispensed_medicine_id = p_proposed_medicine_id WHERE id = p_item_id;
  END IF;
  COMMIT;
  SELECT v_review AS review_id, p_decision AS decision, v_reason AS eligibility_reason;
END$$

CREATE DEFINER={{DEFINER}} PROCEDURE sp_approve_order(IN p_order_id INT)
  SQL SECURITY DEFINER
BEGIN
  DECLARE v_pharmacy INT;
  DECLARE v_status VARCHAR(20);
  DECLARE v_note VARCHAR(500);
  DECLARE v_rx INT;
  DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
  START TRANSACTION;
  SELECT pharmacy_id, status, prescription_note INTO v_pharmacy, v_status, v_note FROM orders WHERE id = p_order_id FOR UPDATE;
  IF v_status IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MYSQL_ERRNO = 45404, MESSAGE_TEXT = 'Order not found';
  END IF;
  CALL sp_require_pharmacy_access(v_pharmacy, 0);
  IF v_status <> 'UNDER_REVIEW' THEN
    SIGNAL SQLSTATE '45000' SET MYSQL_ERRNO = 45409, MESSAGE_TEXT = 'Order is not UNDER_REVIEW';
  END IF;
  -- items without a substitution decision are dispensed as requested
  UPDATE order_items SET dispensed_medicine_id = requested_medicine_id
  WHERE order_id = p_order_id AND dispensed_medicine_id IS NULL;
  SELECT COUNT(*) INTO v_rx FROM order_items oi JOIN medicines m ON m.id = oi.dispensed_medicine_id
  WHERE oi.order_id = p_order_id AND m.requires_prescription = 1;
  IF v_rx > 0 AND (v_note IS NULL OR CHAR_LENGTH(TRIM(v_note)) = 0) THEN
    SIGNAL SQLSTATE '45000' SET MYSQL_ERRNO = 45422, MESSAGE_TEXT = 'A prescription note is required for a prescription-only medicine';
  END IF;
  UPDATE orders SET status = 'APPROVED' WHERE id = p_order_id AND status = 'UNDER_REVIEW';
  COMMIT;
  SELECT p_order_id AS order_id, 'APPROVED' AS status;
END$$

CREATE DEFINER={{DEFINER}} PROCEDURE sp_reject_order(IN p_order_id INT)
  SQL SECURITY DEFINER
BEGIN
  DECLARE v_pharmacy INT;
  DECLARE v_status VARCHAR(20);
  DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
  START TRANSACTION;
  SELECT pharmacy_id, status INTO v_pharmacy, v_status FROM orders WHERE id = p_order_id FOR UPDATE;
  IF v_status IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MYSQL_ERRNO = 45404, MESSAGE_TEXT = 'Order not found';
  END IF;
  CALL sp_require_pharmacy_access(v_pharmacy, 0);
  IF v_status <> 'UNDER_REVIEW' THEN
    SIGNAL SQLSTATE '45000' SET MYSQL_ERRNO = 45409, MESSAGE_TEXT = 'Order is not UNDER_REVIEW';
  END IF;
  UPDATE orders SET status = 'REJECTED' WHERE id = p_order_id AND status = 'UNDER_REVIEW';
  COMMIT;
  SELECT p_order_id AS order_id, 'REJECTED' AS status;
END$$

-- ---------------------------------------------------------------- Rubric 8: the sale transaction
-- One transaction: lock order, lock inventory rows in primary-key order, check stock, deduct, write SALE movements
-- and outbox rows, mark COMPLETED. Any error rolls everything back. A repeat call fails the APPROVED guard.
-- Call it with no application transaction open (START TRANSACTION would implicitly commit it).
CREATE DEFINER={{DEFINER}} PROCEDURE sp_complete_order(IN p_order_id INT, IN p_actor INT)
  SQL SECURITY DEFINER
BEGIN
  DECLARE v_done INT DEFAULT 0;
  DECLARE v_status VARCHAR(20);
  DECLARE v_pharmacy INT;
  DECLARE v_med INT;
  DECLARE v_qty INT;
  DECLARE v_locked INT;
  DECLARE v_short INT;
  DECLARE v_mov INT;
  DECLARE cur CURSOR FOR
    SELECT COALESCE(dispensed_medicine_id, requested_medicine_id) AS med, SUM(quantity) AS qty
    FROM order_items WHERE order_id = p_order_id GROUP BY med ORDER BY med;
  DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_done = 1;
  DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;

  START TRANSACTION;
  SELECT status, pharmacy_id INTO v_status, v_pharmacy FROM orders WHERE id = p_order_id FOR UPDATE;
  IF v_status IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MYSQL_ERRNO = 45404, MESSAGE_TEXT = 'Order not found';
  END IF;
  CALL sp_require_pharmacy_access(v_pharmacy, 0);
  IF p_actor IS NULL OR p_actor <> fn_ctx_user_id() THEN
    SIGNAL SQLSTATE '45000' SET MYSQL_ERRNO = 45403, MESSAGE_TEXT = 'Actor does not match the authenticated user';
  END IF;
  IF v_status <> 'APPROVED' THEN
    SIGNAL SQLSTATE '45000' SET MYSQL_ERRNO = 45409, MESSAGE_TEXT = 'Order is not APPROVED (already completed or not ready)';
  END IF;

  -- lock inventory rows; index scan order = primary key (pharmacy_id, medicine_id) = deterministic lock order
  SELECT COUNT(*) INTO v_locked FROM inventory
  WHERE pharmacy_id = v_pharmacy
    AND medicine_id IN (SELECT COALESCE(dispensed_medicine_id, requested_medicine_id) FROM order_items WHERE order_id = p_order_id)
  FOR UPDATE;

  SELECT COUNT(*) INTO v_short
  FROM (SELECT COALESCE(dispensed_medicine_id, requested_medicine_id) AS med, SUM(quantity) AS qty
        FROM order_items WHERE order_id = p_order_id GROUP BY med) t
  LEFT JOIN inventory i ON i.pharmacy_id = v_pharmacy AND i.medicine_id = t.med
  WHERE COALESCE(i.quantity, 0) < t.qty
  FOR UPDATE;   -- locking read = CURRENT data. A plain SELECT would use the transaction snapshot taken before we
                -- waited for the row locks, and could miss a sale committed by a competing transaction meanwhile.
  IF v_short > 0 THEN
    SIGNAL SQLSTATE '45000' SET MYSQL_ERRNO = 45409, MESSAGE_TEXT = 'Insufficient stock to complete the order';
  END IF;

  SET v_done = 0;
  OPEN cur;
  item_loop: LOOP
    FETCH cur INTO v_med, v_qty;
    IF v_done = 1 THEN LEAVE item_loop; END IF;
    UPDATE inventory SET quantity = quantity - v_qty WHERE pharmacy_id = v_pharmacy AND medicine_id = v_med;
    INSERT INTO inventory_movements (pharmacy_id, medicine_id, movement_type, delta, order_id, actor_user_id)
      VALUES (v_pharmacy, v_med, 'SALE', -v_qty, p_order_id, p_actor);
    SET v_mov = LAST_INSERT_ID();
    CALL sp_write_outbox(v_pharmacy, v_med, 'sale', v_mov, -v_qty, p_order_id, NULL, NULL);
  END LOOP;
  CLOSE cur;

  UPDATE orders SET status = 'COMPLETED' WHERE id = p_order_id AND status = 'APPROVED';
  IF ROW_COUNT() <> 1 THEN
    SIGNAL SQLSTATE '45000' SET MYSQL_ERRNO = 45409, MESSAGE_TEXT = 'Order status changed concurrently';
  END IF;
  COMMIT;
  SELECT p_order_id AS order_id, 'COMPLETED' AS status;
END$$

-- ---------------------------------------------------------------- sync repair + admin
-- Re-enqueues every inventory row so MongoDB can be rebuilt from MySQL (the source of truth).
CREATE DEFINER={{DEFINER}} PROCEDURE sp_enqueue_full_resync()
  SQL SECURITY DEFINER
BEGIN
  CALL sp_require_role('admin', NULL);
  INSERT INTO sync_outbox (operation, entity_id, payload)
  SELECT 'UPSERT_INVENTORY_FEED', CONCAT('ph', i.pharmacy_id, ':med', i.medicine_id),
         JSON_OBJECT('pharmacy_id', i.pharmacy_id, 'medicine_id', i.medicine_id, 'quantity', i.quantity,
                     'reorder_level', i.reorder_level, 'availability', fn_availability_band(i.quantity, i.reorder_level),
                     'low_stock', IF(i.quantity <= i.reorder_level, CAST('true' AS JSON), CAST('false' AS JSON)),
                     'source', 'resync', 'occurred_at', DATE_FORMAT(UTC_TIMESTAMP(), '%Y-%m-%dT%H:%i:%s'),
                     'metadata', JSON_OBJECT())
  FROM inventory i;
  SELECT ROW_COUNT() AS enqueued;
END$$

CREATE DEFINER={{DEFINER}} PROCEDURE sp_admin_create_user(IN p_email VARCHAR(190), IN p_full_name VARCHAR(120),
    IN p_role VARCHAR(20), IN p_password_hash VARCHAR(255), IN p_pharmacy_id INT)
  SQL SECURITY DEFINER
BEGIN
  DECLARE v_id INT;
  DECLARE EXIT HANDLER FOR 1062 BEGIN ROLLBACK; SIGNAL SQLSTATE '45000' SET MYSQL_ERRNO = 45409, MESSAGE_TEXT = 'Email already registered'; END;
  DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
  CALL sp_require_role('admin', NULL);
  IF p_role NOT IN ('patient', 'pharmacist', 'admin') THEN
    SIGNAL SQLSTATE '45000' SET MYSQL_ERRNO = 45422, MESSAGE_TEXT = 'Invalid role';
  END IF;
  IF p_role = 'pharmacist' AND (p_pharmacy_id IS NULL OR NOT EXISTS (SELECT 1 FROM pharmacies WHERE id = p_pharmacy_id)) THEN
    SIGNAL SQLSTATE '45000' SET MYSQL_ERRNO = 45422, MESSAGE_TEXT = 'A pharmacist needs a valid pharmacy';
  END IF;
  START TRANSACTION;
  INSERT INTO users (email, full_name, role, password_hash) VALUES (p_email, p_full_name, p_role, p_password_hash);
  SET v_id = LAST_INSERT_ID();
  IF p_role = 'pharmacist' THEN
    INSERT INTO pharmacist_assignments (user_id, pharmacy_id) VALUES (v_id, p_pharmacy_id);
  END IF;
  COMMIT;
  SELECT v_id AS user_id;
END$$

CREATE DEFINER={{DEFINER}} PROCEDURE sp_admin_assign_pharmacist(IN p_user_id INT, IN p_pharmacy_id INT)
  SQL SECURITY DEFINER
BEGIN
  CALL sp_require_role('admin', NULL);
  IF NOT EXISTS (SELECT 1 FROM users WHERE id = p_user_id AND role = 'pharmacist')
     OR NOT EXISTS (SELECT 1 FROM pharmacies WHERE id = p_pharmacy_id) THEN
    SIGNAL SQLSTATE '45000' SET MYSQL_ERRNO = 45404, MESSAGE_TEXT = 'Pharmacist or pharmacy not found';
  END IF;
  INSERT INTO pharmacist_assignments (user_id, pharmacy_id) VALUES (p_user_id, p_pharmacy_id) AS n
    ON DUPLICATE KEY UPDATE pharmacy_id = n.pharmacy_id;
  SELECT p_user_id AS user_id, p_pharmacy_id AS pharmacy_id;
END$$

CREATE DEFINER={{DEFINER}} PROCEDURE sp_admin_set_user_active(IN p_user_id INT, IN p_active TINYINT)
  SQL SECURITY DEFINER
BEGIN
  CALL sp_require_role('admin', NULL);
  IF p_user_id = fn_ctx_user_id() AND p_active = 0 THEN
    SIGNAL SQLSTATE '45000' SET MYSQL_ERRNO = 45409, MESSAGE_TEXT = 'You cannot deactivate your own account';
  END IF;
  UPDATE users SET is_active = IF(p_active = 1, 1, 0) WHERE id = p_user_id;
  SELECT p_user_id AS user_id, p_active AS is_active;
END$$

DELIMITER ;
