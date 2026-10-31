-- R__40: substitution-candidate procedures (section 8). All structured eligibility lives in v_candidate_eligibility.
-- Pipeline: (1) eligibility  (2) ranking of eligible candidates  (3) pharmacist decision (R__50).
-- MySQL has no table-returning functions, so these are procedures that return result sets.

DROP PROCEDURE IF EXISTS sp_equivalent_candidates;
DROP PROCEDURE IF EXISTS sp_candidate_rejections;
DROP PROCEDURE IF EXISTS sp_rank_candidates;

DELIMITER $$

-- Rubric 8: procedure. Identical ingredient set and strengths, same form/route/release, active, substitution allowed.
CREATE DEFINER={{DEFINER}} PROCEDURE sp_equivalent_candidates(IN p_medicine_id INT)
  SQL SECURITY DEFINER
BEGIN
  CALL sp_require_authenticated();
  SELECT m.id AS medicine_id, m.name, m.brand, m.dosage_form, m.route, m.release_type, m.requires_prescription,
         'Same active ingredients and strengths, dosage form, route and release type' AS eligibility_reason,
         'PENDING_PHARMACIST_VERIFICATION' AS verification_status
  FROM v_candidate_eligibility e
  JOIN medicines m ON m.id = e.candidate_id
  WHERE e.requested_id = p_medicine_id AND e.is_eligible = 1
  ORDER BY m.name;
END$$

-- Near-misses (same category or sharing an ingredient) with a human-readable reason for every failed rule.
CREATE DEFINER={{DEFINER}} PROCEDURE sp_candidate_rejections(IN p_medicine_id INT)
  SQL SECURITY DEFINER
BEGIN
  CALL sp_require_authenticated();
  SELECT m.id AS medicine_id, m.name, m.brand,
         CONCAT_WS('; ',
           IF(e.ingredients_same = 0, 'different active-ingredient set', NULL),
           IF(e.ingredients_same = 1 AND e.strengths_same = 0, 'different strength', NULL),
           IF(e.basis_same = 0, 'different strength basis', NULL),
           IF(e.form_same = 0, 'different dosage form', NULL),
           IF(e.route_same = 0, 'different route', NULL),
           IF(e.release_same = 0, 'different release type', NULL),
           IF(e.candidate_active = 0, 'candidate is inactive or discontinued', NULL),
           IF(e.requested_allows = 0, 'substitution not allowed for the requested medicine', NULL),
           IF(e.candidate_allows = 0, 'substitution not allowed for this medicine', NULL)) AS reject_reason
  FROM v_candidate_eligibility e
  JOIN medicines m ON m.id = e.candidate_id
  WHERE e.requested_id = p_medicine_id AND e.is_eligible = 0
    AND ( m.category_id = (SELECT r.category_id FROM medicines r WHERE r.id = p_medicine_id)
          OR EXISTS (SELECT 1 FROM medicine_ingredients x JOIN medicine_ingredients y ON y.ingredient_id = x.ingredient_id
                     WHERE x.medicine_id = p_medicine_id AND y.medicine_id = m.id) )
  ORDER BY m.name;
END$$

-- Ranking of ELIGIBLE candidates only (never changes eligibility):
--   stocked at the chosen pharmacy first, then higher total quantity, then fewer open low-stock alerts, then name.
-- Exact quantities are returned only to an admin or to the pharmacist of p_pharmacy_id; everyone else gets bands.
CREATE DEFINER={{DEFINER}} PROCEDURE sp_rank_candidates(IN p_medicine_id INT, IN p_pharmacy_id INT)
  SQL SECURITY DEFINER
BEGIN
  DECLARE v_role VARCHAR(20);
  DECLARE v_exact_here TINYINT DEFAULT 0;
  CALL sp_require_authenticated();
  SET v_role = fn_ctx_role();
  SET v_exact_here = COALESCE(v_role = 'admin' OR (v_role = 'pharmacist' AND p_pharmacy_id = fn_ctx_pharmacy_id()), 0);

  SELECT ROW_NUMBER() OVER (ORDER BY (COALESCE(h.quantity, 0) > 0) DESC, COALESCE(tot.total_qty, 0) DESC,
                                     COALESCE(al.open_alerts, 0), m.name) AS rank_position,
         m.id AS medicine_id, m.name, m.brand, m.requires_prescription,
         fn_availability_band(COALESCE(h.quantity, 0), COALESCE(h.reorder_level, 0)) AS availability_here,
         IF(v_exact_here = 1, COALESCE(h.quantity, 0), NULL) AS quantity_here,
         COALESCE(tot.pharmacies_stocking, 0) AS pharmacies_stocking,
         IF(v_role = 'admin', COALESCE(tot.total_qty, 0), NULL) AS total_quantity,
         COALESCE(al.open_alerts, 0) AS open_low_stock_alerts,
         'Same active ingredients and strengths, dosage form, route and release type' AS eligibility_reason,
         'PENDING_PHARMACIST_VERIFICATION' AS verification_status
  FROM v_candidate_eligibility e
  JOIN medicines m ON m.id = e.candidate_id
  LEFT JOIN inventory h ON h.medicine_id = m.id AND h.pharmacy_id = p_pharmacy_id
  LEFT JOIN (SELECT medicine_id, SUM(quantity) AS total_qty, SUM(quantity > 0) AS pharmacies_stocking
             FROM inventory GROUP BY medicine_id) tot ON tot.medicine_id = m.id
  LEFT JOIN (SELECT medicine_id, COUNT(*) AS open_alerts
             FROM low_stock_alerts WHERE status = 'OPEN' GROUP BY medicine_id) al ON al.medicine_id = m.id
  WHERE e.requested_id = p_medicine_id AND e.is_eligible = 1
  ORDER BY rank_position;
END$$

DELIMITER ;
