-- R__30: triggers. MySQL triggers are per event, so the low-stock rule is one procedure
-- (sp_eval_low_stock) called by an AFTER INSERT and an AFTER UPDATE trigger on inventory.

DROP TRIGGER IF EXISTS trg_inventory_low_stock_ins;
DROP TRIGGER IF EXISTS trg_inventory_low_stock_upd;
DROP TRIGGER IF EXISTS trg_orders_status_transition;
DROP PROCEDURE IF EXISTS sp_eval_low_stock;

DELIMITER $$

-- Internal (not granted to any role). Opens an alert when quantity <= reorder_level, resolves it otherwise.
CREATE DEFINER={{DEFINER}} PROCEDURE sp_eval_low_stock(IN p_pharmacy_id INT, IN p_medicine_id INT, IN p_quantity INT, IN p_reorder_level INT)
  SQL SECURITY DEFINER
BEGIN
  DECLARE CONTINUE HANDLER FOR 1062 BEGIN END;   -- unique open-alert key: a concurrent insert already opened it
  IF p_quantity <= p_reorder_level THEN
    INSERT INTO low_stock_alerts (pharmacy_id, medicine_id, status, quantity_at_open)
    SELECT p_pharmacy_id, p_medicine_id, 'OPEN', p_quantity FROM DUAL
    WHERE NOT EXISTS (SELECT 1 FROM low_stock_alerts
                      WHERE pharmacy_id = p_pharmacy_id AND medicine_id = p_medicine_id AND status = 'OPEN');
  ELSE
    UPDATE low_stock_alerts SET status = 'RESOLVED', resolved_at = NOW()
    WHERE pharmacy_id = p_pharmacy_id AND medicine_id = p_medicine_id AND status = 'OPEN';
  END IF;
END$$

CREATE DEFINER={{DEFINER}} TRIGGER trg_inventory_low_stock_ins AFTER INSERT ON inventory FOR EACH ROW
BEGIN
  CALL sp_eval_low_stock(NEW.pharmacy_id, NEW.medicine_id, NEW.quantity, NEW.reorder_level);
END$$

CREATE DEFINER={{DEFINER}} TRIGGER trg_inventory_low_stock_upd AFTER UPDATE ON inventory FOR EACH ROW
BEGIN
  CALL sp_eval_low_stock(NEW.pharmacy_id, NEW.medicine_id, NEW.quantity, NEW.reorder_level);
END$$

-- Order status machine: REQUESTED -> UNDER_REVIEW -> APPROVED | REJECTED ; APPROVED -> COMPLETED ;
-- CANCELLED from any non-terminal state. COMPLETED / REJECTED / CANCELLED are terminal.
CREATE DEFINER={{DEFINER}} TRIGGER trg_orders_status_transition BEFORE UPDATE ON orders FOR EACH ROW
BEGIN
  IF NEW.status <> OLD.status THEN
    IF NOT ( (OLD.status = 'REQUESTED'    AND NEW.status IN ('UNDER_REVIEW', 'CANCELLED'))
          OR (OLD.status = 'UNDER_REVIEW' AND NEW.status IN ('APPROVED', 'REJECTED', 'CANCELLED'))
          OR (OLD.status = 'APPROVED'     AND NEW.status IN ('COMPLETED', 'CANCELLED')) ) THEN
      SIGNAL SQLSTATE '45000' SET MYSQL_ERRNO = 45409, MESSAGE_TEXT = 'Invalid order status transition';
    END IF;
  END IF;
END$$

DELIMITER ;
