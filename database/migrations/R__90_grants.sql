-- R__90: least-privilege grants to the four MySQL roles (section 6). Run by the migrator account (has GRANT OPTION).
-- MySQL has NO native row-level security. Row scoping is done by: no direct base-table access for patients and
-- pharmacists, SECURITY DEFINER views/procedures, and the trusted request context (fn_ctx_*).
-- Helper/guard routines (sp_require_*, sp_eval_low_stock, sp_write_outbox) are intentionally NOT granted to anyone.

-- ===================================================== patient
GRANT SELECT ON {{DB}}.medicines            TO 'app_patient_role'@'{{HOST}}';
GRANT SELECT ON {{DB}}.medicine_ingredients TO 'app_patient_role'@'{{HOST}}';
GRANT SELECT ON {{DB}}.active_ingredients   TO 'app_patient_role'@'{{HOST}}';
GRANT SELECT ON {{DB}}.medicine_categories  TO 'app_patient_role'@'{{HOST}}';
GRANT SELECT ON {{DB}}.pharmacies           TO 'app_patient_role'@'{{HOST}}';
GRANT SELECT ON {{DB}}.shortage_entries     TO 'app_patient_role'@'{{HOST}}';
GRANT SELECT ON {{DB}}.v_availability       TO 'app_patient_role'@'{{HOST}}';
GRANT EXECUTE ON PROCEDURE {{DB}}.sp_create_my_order       TO 'app_patient_role'@'{{HOST}}';
GRANT EXECUTE ON PROCEDURE {{DB}}.sp_list_my_orders        TO 'app_patient_role'@'{{HOST}}';
GRANT EXECUTE ON PROCEDURE {{DB}}.sp_cancel_order          TO 'app_patient_role'@'{{HOST}}';
GRANT EXECUTE ON PROCEDURE {{DB}}.sp_list_reviews          TO 'app_patient_role'@'{{HOST}}';
GRANT EXECUTE ON PROCEDURE {{DB}}.sp_equivalent_candidates TO 'app_patient_role'@'{{HOST}}';
GRANT EXECUTE ON PROCEDURE {{DB}}.sp_candidate_rejections  TO 'app_patient_role'@'{{HOST}}';
GRANT EXECUTE ON PROCEDURE {{DB}}.sp_rank_candidates       TO 'app_patient_role'@'{{HOST}}';

-- ===================================================== pharmacist
GRANT SELECT ON {{DB}}.medicines            TO 'app_pharmacist_role'@'{{HOST}}';
GRANT SELECT ON {{DB}}.medicine_ingredients TO 'app_pharmacist_role'@'{{HOST}}';
GRANT SELECT ON {{DB}}.active_ingredients   TO 'app_pharmacist_role'@'{{HOST}}';
GRANT SELECT ON {{DB}}.medicine_categories  TO 'app_pharmacist_role'@'{{HOST}}';
GRANT SELECT ON {{DB}}.pharmacies           TO 'app_pharmacist_role'@'{{HOST}}';
GRANT SELECT ON {{DB}}.shortage_entries     TO 'app_pharmacist_role'@'{{HOST}}';
GRANT SELECT ON {{DB}}.v_availability       TO 'app_pharmacist_role'@'{{HOST}}';
GRANT SELECT ON {{DB}}.v_my_inventory       TO 'app_pharmacist_role'@'{{HOST}}';
GRANT SELECT ON {{DB}}.v_my_alerts          TO 'app_pharmacist_role'@'{{HOST}}';
GRANT SELECT ON {{DB}}.v_my_movements       TO 'app_pharmacist_role'@'{{HOST}}';
GRANT EXECUTE ON PROCEDURE {{DB}}.sp_receive_stock         TO 'app_pharmacist_role'@'{{HOST}}';
GRANT EXECUTE ON PROCEDURE {{DB}}.sp_adjust_stock          TO 'app_pharmacist_role'@'{{HOST}}';
GRANT EXECUTE ON PROCEDURE {{DB}}.sp_set_reorder_level     TO 'app_pharmacist_role'@'{{HOST}}';
GRANT EXECUTE ON PROCEDURE {{DB}}.sp_list_pharmacy_orders  TO 'app_pharmacist_role'@'{{HOST}}';
GRANT EXECUTE ON PROCEDURE {{DB}}.sp_list_reviews          TO 'app_pharmacist_role'@'{{HOST}}';
GRANT EXECUTE ON PROCEDURE {{DB}}.sp_start_review          TO 'app_pharmacist_role'@'{{HOST}}';
GRANT EXECUTE ON PROCEDURE {{DB}}.sp_decide_substitution   TO 'app_pharmacist_role'@'{{HOST}}';
GRANT EXECUTE ON PROCEDURE {{DB}}.sp_approve_order         TO 'app_pharmacist_role'@'{{HOST}}';
GRANT EXECUTE ON PROCEDURE {{DB}}.sp_reject_order          TO 'app_pharmacist_role'@'{{HOST}}';
GRANT EXECUTE ON PROCEDURE {{DB}}.sp_complete_order        TO 'app_pharmacist_role'@'{{HOST}}';
GRANT EXECUTE ON PROCEDURE {{DB}}.sp_cancel_order          TO 'app_pharmacist_role'@'{{HOST}}';
GRANT EXECUTE ON PROCEDURE {{DB}}.sp_equivalent_candidates TO 'app_pharmacist_role'@'{{HOST}}';
GRANT EXECUTE ON PROCEDURE {{DB}}.sp_candidate_rejections  TO 'app_pharmacist_role'@'{{HOST}}';
GRANT EXECUTE ON PROCEDURE {{DB}}.sp_rank_candidates       TO 'app_pharmacist_role'@'{{HOST}}';

-- ===================================================== admin
GRANT SELECT, INSERT, UPDATE, DELETE ON {{DB}}.medicines            TO 'app_admin_role'@'{{HOST}}';
GRANT SELECT, INSERT, UPDATE, DELETE ON {{DB}}.medicine_ingredients TO 'app_admin_role'@'{{HOST}}';
GRANT SELECT, INSERT, UPDATE, DELETE ON {{DB}}.active_ingredients   TO 'app_admin_role'@'{{HOST}}';
GRANT SELECT, INSERT, UPDATE, DELETE ON {{DB}}.medicine_categories  TO 'app_admin_role'@'{{HOST}}';
GRANT SELECT, INSERT, UPDATE, DELETE ON {{DB}}.shortage_entries     TO 'app_admin_role'@'{{HOST}}';
GRANT SELECT, INSERT, UPDATE         ON {{DB}}.pharmacies           TO 'app_admin_role'@'{{HOST}}';
GRANT SELECT ON {{DB}}.pharmacist_assignments TO 'app_admin_role'@'{{HOST}}';
GRANT SELECT ON {{DB}}.inventory              TO 'app_admin_role'@'{{HOST}}';
GRANT SELECT ON {{DB}}.inventory_movements    TO 'app_admin_role'@'{{HOST}}';
GRANT SELECT ON {{DB}}.low_stock_alerts       TO 'app_admin_role'@'{{HOST}}';
GRANT SELECT ON {{DB}}.orders                 TO 'app_admin_role'@'{{HOST}}';
GRANT SELECT ON {{DB}}.order_items            TO 'app_admin_role'@'{{HOST}}';
GRANT SELECT ON {{DB}}.substitution_reviews   TO 'app_admin_role'@'{{HOST}}';
GRANT SELECT, UPDATE ON {{DB}}.sync_outbox    TO 'app_admin_role'@'{{HOST}}';   -- the sync worker runs as admin
GRANT SELECT ON {{DB}}.v_users_public         TO 'app_admin_role'@'{{HOST}}';
GRANT SELECT ON {{DB}}.v_availability         TO 'app_admin_role'@'{{HOST}}';
GRANT SELECT ON {{DB}}.v_my_inventory         TO 'app_admin_role'@'{{HOST}}';
GRANT SELECT ON {{DB}}.v_my_alerts            TO 'app_admin_role'@'{{HOST}}';
GRANT SELECT ON {{DB}}.v_my_movements         TO 'app_admin_role'@'{{HOST}}';
GRANT EXECUTE ON PROCEDURE {{DB}}.sp_admin_create_user       TO 'app_admin_role'@'{{HOST}}';
GRANT EXECUTE ON PROCEDURE {{DB}}.sp_admin_assign_pharmacist TO 'app_admin_role'@'{{HOST}}';
GRANT EXECUTE ON PROCEDURE {{DB}}.sp_admin_set_user_active   TO 'app_admin_role'@'{{HOST}}';
GRANT EXECUTE ON PROCEDURE {{DB}}.sp_enqueue_full_resync     TO 'app_admin_role'@'{{HOST}}';
GRANT EXECUTE ON PROCEDURE {{DB}}.sp_receive_stock           TO 'app_admin_role'@'{{HOST}}';
GRANT EXECUTE ON PROCEDURE {{DB}}.sp_adjust_stock            TO 'app_admin_role'@'{{HOST}}';
GRANT EXECUTE ON PROCEDURE {{DB}}.sp_set_reorder_level       TO 'app_admin_role'@'{{HOST}}';
GRANT EXECUTE ON PROCEDURE {{DB}}.sp_list_pharmacy_orders    TO 'app_admin_role'@'{{HOST}}';
GRANT EXECUTE ON PROCEDURE {{DB}}.sp_list_reviews            TO 'app_admin_role'@'{{HOST}}';
GRANT EXECUTE ON PROCEDURE {{DB}}.sp_cancel_order            TO 'app_admin_role'@'{{HOST}}';
GRANT EXECUTE ON PROCEDURE {{DB}}.sp_equivalent_candidates   TO 'app_admin_role'@'{{HOST}}';
GRANT EXECUTE ON PROCEDURE {{DB}}.sp_candidate_rejections    TO 'app_admin_role'@'{{HOST}}';
GRANT EXECUTE ON PROCEDURE {{DB}}.sp_rank_candidates         TO 'app_admin_role'@'{{HOST}}';

-- ===================================================== auth lookups (login only)
GRANT EXECUTE ON PROCEDURE {{DB}}.sp_auth_lookup   TO 'app_auth_role'@'{{HOST}}';
GRANT EXECUTE ON PROCEDURE {{DB}}.sp_auth_identity TO 'app_auth_role'@'{{HOST}}';

-- the availability function is called directly by some named queries and views' callers
GRANT EXECUTE ON FUNCTION {{DB}}.fn_availability_band TO 'app_patient_role'@'{{HOST}}';
GRANT EXECUTE ON FUNCTION {{DB}}.fn_availability_band TO 'app_pharmacist_role'@'{{HOST}}';
GRANT EXECUTE ON FUNCTION {{DB}}.fn_availability_band TO 'app_admin_role'@'{{HOST}}';
