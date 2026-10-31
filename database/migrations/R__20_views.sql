-- R__20: views. All run as the definer, so roles can read them without direct table access.

CREATE OR REPLACE DEFINER={{DEFINER}} SQL SECURITY DEFINER VIEW v_availability AS
SELECT i.pharmacy_id, p.name AS pharmacy_name, i.medicine_id,
       fn_availability_band(i.quantity, i.reorder_level) AS availability
FROM inventory i
JOIN pharmacies p ON p.id = i.pharmacy_id
JOIN medicines m ON m.id = i.medicine_id AND m.is_active = 1;

CREATE OR REPLACE DEFINER={{DEFINER}} SQL SECURITY DEFINER VIEW v_users_public AS
SELECT u.id, u.email, u.full_name, u.role, u.is_active, u.created_at, pa.pharmacy_id
FROM users u LEFT JOIN pharmacist_assignments pa ON pa.user_id = u.id;

-- Exact stock: pharmacists see their own pharmacy, admin sees all, everyone else sees nothing.
CREATE OR REPLACE DEFINER={{DEFINER}} SQL SECURITY DEFINER VIEW v_my_inventory AS
SELECT i.pharmacy_id, p.name AS pharmacy_name, i.medicine_id, m.name AS medicine_name, m.brand,
       i.quantity, i.reorder_level, fn_availability_band(i.quantity, i.reorder_level) AS availability, i.updated_at
FROM inventory i
JOIN pharmacies p ON p.id = i.pharmacy_id
JOIN medicines m ON m.id = i.medicine_id
WHERE fn_ctx_role() = 'admin' OR (fn_ctx_role() = 'pharmacist' AND i.pharmacy_id = fn_ctx_pharmacy_id());

CREATE OR REPLACE DEFINER={{DEFINER}} SQL SECURITY DEFINER VIEW v_my_alerts AS
SELECT a.id, a.pharmacy_id, p.name AS pharmacy_name, a.medicine_id, m.name AS medicine_name,
       a.status, a.quantity_at_open, a.opened_at, a.resolved_at
FROM low_stock_alerts a
JOIN pharmacies p ON p.id = a.pharmacy_id
JOIN medicines m ON m.id = a.medicine_id
WHERE fn_ctx_role() = 'admin' OR (fn_ctx_role() = 'pharmacist' AND a.pharmacy_id = fn_ctx_pharmacy_id());

CREATE OR REPLACE DEFINER={{DEFINER}} SQL SECURITY DEFINER VIEW v_my_movements AS
SELECT mv.id, mv.pharmacy_id, mv.medicine_id, m.name AS medicine_name, mv.movement_type, mv.delta,
       mv.batch_no, mv.expiry_date, mv.order_id, mv.actor_user_id, mv.note, mv.created_at
FROM inventory_movements mv
JOIN medicines m ON m.id = mv.medicine_id
WHERE fn_ctx_role() = 'admin' OR (fn_ctx_role() = 'pharmacist' AND mv.pharmacy_id = fn_ctx_pharmacy_id());

-- Pairwise composition checks. The ONE place that decides substitution eligibility (section 8, step 1).
-- Set equality = NOT EXISTS in both directions over (ingredient, normalised strength).
CREATE OR REPLACE DEFINER={{DEFINER}} SQL SECURITY DEFINER VIEW v_candidate_check AS
SELECT a.id AS requested_id, b.id AS candidate_id,
  ( NOT EXISTS (SELECT 1 FROM medicine_ingredients x WHERE x.medicine_id = a.id
                  AND NOT EXISTS (SELECT 1 FROM medicine_ingredients y WHERE y.medicine_id = b.id AND y.ingredient_id = x.ingredient_id))
    AND NOT EXISTS (SELECT 1 FROM medicine_ingredients y WHERE y.medicine_id = b.id
                  AND NOT EXISTS (SELECT 1 FROM medicine_ingredients x WHERE x.medicine_id = a.id AND x.ingredient_id = y.ingredient_id))
  ) AS ingredients_same,
  ( NOT EXISTS (SELECT 1 FROM medicine_ingredients x WHERE x.medicine_id = a.id
                  AND NOT EXISTS (SELECT 1 FROM medicine_ingredients y WHERE y.medicine_id = b.id
                                    AND y.ingredient_id = x.ingredient_id AND y.strength_mg = x.strength_mg))
    AND NOT EXISTS (SELECT 1 FROM medicine_ingredients y WHERE y.medicine_id = b.id
                  AND NOT EXISTS (SELECT 1 FROM medicine_ingredients x WHERE x.medicine_id = a.id
                                    AND x.ingredient_id = y.ingredient_id AND x.strength_mg = y.strength_mg))
  ) AS strengths_same,
  (a.strength_basis = b.strength_basis) AS basis_same,
  (a.dosage_form = b.dosage_form)       AS form_same,
  (a.route = b.route)                   AS route_same,
  (a.release_type = b.release_type)     AS release_same,
  b.is_active                           AS candidate_active,
  a.substitution_allowed                AS requested_allows,
  b.substitution_allowed                AS candidate_allows
FROM medicines a JOIN medicines b ON a.id <> b.id;

CREATE OR REPLACE DEFINER={{DEFINER}} SQL SECURITY DEFINER VIEW v_candidate_eligibility AS
SELECT c.*,
  (ingredients_same AND strengths_same AND basis_same AND form_same AND route_same AND release_same
   AND candidate_active AND requested_allows AND candidate_allows) AS is_eligible
FROM v_candidate_check c;
