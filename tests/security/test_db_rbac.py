"""Section 6 security tests, run directly against MySQL with the backend service accounts (NOT through the API).
MySQL error numbers: 1142 table/view access denied, 1370 routine EXECUTE denied, 454xx raised by our routines."""
import mysql.connector
import pytest

from support import direct, migrator
from helpers import call, scalar


def errno_of(fn):
    with pytest.raises(mysql.connector.Error) as e:
        fn()
    return e.value.errno


def test_each_service_account_has_exactly_its_mysql_role():
    expect = {"patient": "app_patient_role", "pharmacist": "app_pharmacist_role", "admin": "app_admin_role", "auth": "app_auth_role"}
    for kind, role in expect.items():
        assert f"`{role}`" in scalar(direct(kind), "SELECT CURRENT_ROLE()")


# ---------------------------------------------------------------- patient
def test_patient_direct_update_inventory_denied():
    c = direct("patient", 4, "patient")
    assert errno_of(lambda: c.cursor().execute("UPDATE inventory SET quantity = 9999 WHERE pharmacy_id=1 AND medicine_id=1")) == 1142


def test_patient_direct_reads_of_protected_tables_denied():
    c = direct("patient", 4, "patient")
    for t in ("orders", "order_items", "inventory", "inventory_movements", "users", "substitution_reviews", "sync_outbox", "low_stock_alerts"):
        assert errno_of(lambda t=t: call(c, f"SELECT * FROM {t}")) == 1142, t


def test_patient_sees_only_own_orders_via_procedure(reset_data):
    p1 = direct("patient", 4, "patient")
    p2 = direct("patient", 5, "patient")
    assert {r["order_id"] for r in call(p1, "CALL sp_list_my_orders()")} == {1, 3, 5}
    assert {r["order_id"] for r in call(p2, "CALL sp_list_my_orders()")} == {2, 4}


def test_patient_procedure_cannot_be_pointed_at_another_owner(reset_data):
    p1 = direct("patient", 4, "patient")
    # sp_create_my_order has no owner parameter: the owner is always the verified context
    oid = call(p1, "CALL sp_create_my_order(1, 1, 2, NULL)")[0]["order_id"]
    assert scalar(migrator(), "SELECT patient_id FROM orders WHERE id=%s", (oid,)) == 4
    # a patient cannot cancel somebody else's order
    assert errno_of(lambda: call(p1, "CALL sp_cancel_order(2)")) == 45403


def test_patient_never_gets_exact_quantities():
    p = direct("patient", 4, "patient")
    cols = {r["COLUMN_NAME"] for r in call(migrator(), "SELECT COLUMN_NAME FROM information_schema.columns "
                                                       "WHERE table_schema='medsub_test' AND table_name='v_availability'")}
    assert "quantity" not in cols and "reorder_level" not in cols
    rows = call(p, "SELECT * FROM v_availability")
    assert rows and set(rows[0]) == {"pharmacy_id", "pharmacy_name", "medicine_id", "availability"}
    assert {r["availability"] for r in rows} <= {"In stock", "Low", "Out"}
    assert errno_of(lambda: call(p, "SELECT * FROM v_my_inventory")) == 1142
    for r in call(p, "CALL sp_rank_candidates(1, 1)"):
        assert r["quantity_here"] is None and r["total_quantity"] is None


def test_patient_cannot_run_staff_or_admin_procedures():
    p = direct("patient", 4, "patient")
    for stmt in ("CALL sp_receive_stock(1,1,5,NULL,NULL)", "CALL sp_complete_order(3,4)", "CALL sp_enqueue_full_resync()",
                 "CALL sp_admin_create_user('x@y.z','X','admin','h',NULL)", "CALL sp_start_review(1)"):
        assert errno_of(lambda s=stmt: call(p, s)) == 1370, stmt


def test_forged_context_does_not_grant_privileges():
    """Even if the context claims 'admin', a patient DB account has no grants for admin objects."""
    p = direct("patient", 1, "admin")
    assert errno_of(lambda: call(p, "CALL sp_admin_create_user('x@y.z','X','admin','h',NULL)")) == 1370
    assert errno_of(lambda: call(p, "SELECT * FROM v_my_inventory")) == 1142
    assert errno_of(lambda: call(p, "SELECT * FROM users")) == 1142


def test_no_context_means_no_access_even_to_granted_procedures():
    p = direct("patient")
    assert errno_of(lambda: call(p, "CALL sp_list_my_orders()")) == 45403
    assert errno_of(lambda: call(p, "CALL sp_create_my_order(1,1,1,NULL)")) == 45403


# ---------------------------------------------------------------- pharmacist
def test_pharmacist_direct_writes_to_protected_tables_denied():
    c = direct("pharmacist", 2, "pharmacist", 1)
    for stmt in ("UPDATE inventory SET quantity=1 WHERE pharmacy_id=1 AND medicine_id=1",
                 "INSERT INTO inventory (pharmacy_id, medicine_id, quantity) VALUES (1, 17, 5)",
                 "DELETE FROM inventory WHERE pharmacy_id=1",
                 "INSERT INTO inventory_movements (pharmacy_id, medicine_id, movement_type, delta, actor_user_id) VALUES (1,1,'RECEIPT',5,2)",
                 "UPDATE orders SET status='COMPLETED' WHERE id=3",
                 "UPDATE low_stock_alerts SET status='RESOLVED'"):
        assert errno_of(lambda s=stmt: c.cursor().execute(s)) == 1142, stmt


def test_pharmacist_cannot_insert_medicines_or_read_users():
    c = direct("pharmacist", 2, "pharmacist", 1)
    assert errno_of(lambda: c.cursor().execute(
        "INSERT INTO medicines (name, brand, category_id, dosage_form, strength_basis) VALUES ('X','Y',3,'tablet','per tablet')")) == 1142
    assert errno_of(lambda: call(c, "SELECT * FROM users")) == 1142
    assert errno_of(lambda: call(c, "SELECT * FROM orders")) == 1142


def test_stock_procedure_rejects_other_pharmacy_row(reset_data):
    c = direct("pharmacist", 2, "pharmacist", 1)              # verified context: pharmacy 1
    m = migrator()
    before = scalar(m, "SELECT quantity FROM inventory WHERE pharmacy_id=2 AND medicine_id=1")
    assert errno_of(lambda: call(c, "CALL sp_receive_stock(2, 1, 100, 'B1', NULL)")) == 45403
    assert errno_of(lambda: call(c, "CALL sp_adjust_stock(2, 1, 10, 'x')")) == 45403
    assert errno_of(lambda: call(c, "CALL sp_set_reorder_level(2, 1, 99)")) == 45403
    assert scalar(m, "SELECT quantity FROM inventory WHERE pharmacy_id=2 AND medicine_id=1") == before
    # own pharmacy works and is audited
    row = call(c, "CALL sp_receive_stock(1, 1, 10, 'B1', '2027-12-31')")[0]
    assert row["quantity"] == 130
    assert scalar(m, "SELECT actor_user_id FROM inventory_movements WHERE movement_type='RECEIPT' AND batch_no='B1'") == 2


def test_pharmacist_views_are_scoped_to_assigned_pharmacy(reset_data):
    c1 = direct("pharmacist", 2, "pharmacist", 1)
    c2 = direct("pharmacist", 3, "pharmacist", 2)
    assert {r["pharmacy_id"] for r in call(c1, "SELECT pharmacy_id FROM v_my_inventory")} == {1}
    assert {r["pharmacy_id"] for r in call(c2, "SELECT pharmacy_id FROM v_my_inventory")} == {2}
    assert {r["pharmacy_id"] for r in call(c1, "SELECT pharmacy_id FROM v_my_alerts")} <= {1}
    assert {r["pharmacy_id"] for r in call(c1, "SELECT pharmacy_id FROM v_my_movements")} <= {1}
    assert {r["order_id"] for r in call(c1, "CALL sp_list_pharmacy_orders(NULL)")} == {1, 3, 5}
    assert {r["order_id"] for r in call(c2, "CALL sp_list_pharmacy_orders(NULL)")} == {2, 4}


def test_pharmacist_cannot_act_on_other_pharmacys_order(reset_data):
    c1 = direct("pharmacist", 2, "pharmacist", 1)
    for stmt in ("CALL sp_start_review(2)", "CALL sp_approve_order(2)", "CALL sp_reject_order(2)",
                 "CALL sp_decide_substitution(2, 2, 'APPROVED', NULL)", "CALL sp_complete_order(2, 2)"):
        assert errno_of(lambda s=stmt: call(c1, s)) == 45403, stmt


def test_pharmacist_cannot_run_admin_procedures():
    c = direct("pharmacist", 2, "pharmacist", 1)
    assert errno_of(lambda: call(c, "CALL sp_admin_assign_pharmacist(3, 1)")) == 1370
    assert errno_of(lambda: call(c, "CALL sp_enqueue_full_resync()")) == 1370


# ---------------------------------------------------------------- admin
def test_admin_catalog_writes_allowed_but_no_direct_stock_writes():
    a = direct("admin", 1, "admin")
    a.cursor().execute("INSERT INTO active_ingredients (id, name) VALUES (990, 'Test Ingredient')")
    a.cursor().execute("DELETE FROM active_ingredients WHERE id=990")
    assert errno_of(lambda: a.cursor().execute("UPDATE inventory SET quantity=1")) == 1142
    assert errno_of(lambda: a.cursor().execute("UPDATE users SET role='admin'")) == 1142
    assert errno_of(lambda: call(a, "SELECT password_hash FROM users")) == 1142   # hashes unreadable even to admin


def test_auth_account_can_only_run_lookup_procedures():
    a = direct("auth")
    assert call(a, "CALL sp_auth_lookup('admin@medsub.demo')")[0]["role"] == "admin"
    assert errno_of(lambda: call(a, "SELECT * FROM users")) == 1142
    assert errno_of(lambda: call(a, "SELECT * FROM medicines")) == 1142


def test_definer_account_cannot_log_in():
    from app import config
    import os
    with pytest.raises(mysql.connector.Error):
        mysql.connector.connect(host=config.MYSQL_HOST, port=config.MYSQL_PORT, user=os.environ["DEFINER_USER"],
                                password="anything", database="medsub_test")
