-- R__10: request-context functions, availability band function, internal guard procedures.
-- The backend sets @app_user_id / @app_role / @app_pharmacy_id from the VERIFIED identity (never from the browser).
-- Routines read them through these functions. Guards are internal (not granted to any role).

DROP FUNCTION IF EXISTS fn_ctx_user_id;
DROP FUNCTION IF EXISTS fn_ctx_role;
DROP FUNCTION IF EXISTS fn_ctx_pharmacy_id;
DROP FUNCTION IF EXISTS fn_availability_band;
DROP PROCEDURE IF EXISTS sp_require_authenticated;
DROP PROCEDURE IF EXISTS sp_require_role;
DROP PROCEDURE IF EXISTS sp_require_pharmacy_access;

CREATE DEFINER={{DEFINER}} FUNCTION fn_ctx_user_id() RETURNS INT
  NOT DETERMINISTIC NO SQL SQL SECURITY DEFINER
  RETURN @app_user_id;

CREATE DEFINER={{DEFINER}} FUNCTION fn_ctx_role() RETURNS VARCHAR(20)
  NOT DETERMINISTIC NO SQL SQL SECURITY DEFINER
  RETURN @app_role;

CREATE DEFINER={{DEFINER}} FUNCTION fn_ctx_pharmacy_id() RETURNS INT
  NOT DETERMINISTIC NO SQL SQL SECURITY DEFINER
  RETURN @app_pharmacy_id;

-- Rubric 8: stored function. Patient-safe availability band (never the exact quantity).
CREATE DEFINER={{DEFINER}} FUNCTION fn_availability_band(p_quantity INT, p_reorder_level INT) RETURNS VARCHAR(10)
  DETERMINISTIC NO SQL SQL SECURITY DEFINER
  RETURN CASE WHEN p_quantity IS NULL OR p_quantity <= 0 THEN 'Out'
              WHEN p_quantity <= p_reorder_level THEN 'Low'
              ELSE 'In stock' END;

DELIMITER $$

CREATE DEFINER={{DEFINER}} PROCEDURE sp_require_authenticated()
  SQL SECURITY DEFINER
BEGIN
  IF fn_ctx_role() IS NULL OR fn_ctx_user_id() IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MYSQL_ERRNO = 45401, MESSAGE_TEXT = 'Not authenticated: no request context';
  END IF;
END$$

CREATE DEFINER={{DEFINER}} PROCEDURE sp_require_role(IN p_role_a VARCHAR(20), IN p_role_b VARCHAR(20))
  SQL SECURITY DEFINER
BEGIN
  IF COALESCE(fn_ctx_role() IN (p_role_a, COALESCE(p_role_b, '')), 0) = 0 OR fn_ctx_user_id() IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MYSQL_ERRNO = 45403, MESSAGE_TEXT = 'Access denied: role not permitted for this operation';
  END IF;
END$$

-- Pharmacists may touch only their assigned pharmacy. Admin passes only if p_allow_admin = 1.
CREATE DEFINER={{DEFINER}} PROCEDURE sp_require_pharmacy_access(IN p_pharmacy_id INT, IN p_allow_admin TINYINT)
  SQL SECURITY DEFINER
BEGIN
  IF COALESCE(
       (fn_ctx_role() = 'admin' AND p_allow_admin = 1)
       OR (fn_ctx_role() = 'pharmacist' AND fn_ctx_pharmacy_id() = p_pharmacy_id), 0) = 0 THEN
    SIGNAL SQLSTATE '45000' SET MYSQL_ERRNO = 45403, MESSAGE_TEXT = 'Access denied: not allowed for this pharmacy';
  END IF;
END$$

DELIMITER ;
