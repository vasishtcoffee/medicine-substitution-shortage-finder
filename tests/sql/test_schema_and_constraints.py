"""P0: schema loads twice without duplicates; every constraint class rejects bad data; trigger behaviour."""
import mysql.connector
import pytest

from support import TEST_DB, migrator
import migrate
import seed as seed_mod


def one(cur, sql, params=()):
    cur.execute(sql, params)
    return cur.fetchone()[0]


def test_schema_and_seed_load_twice_without_duplicates():
    m = migrator()
    c = m.cursor()
    before = {t: one(c, f"SELECT COUNT(*) FROM {t}") for t in ("users", "medicines", "inventory", "medicine_ingredients", "pharmacies")}
    migrate.migrate(TEST_DB, verbose=False)      # second schema load
    seed_mod.seed(TEST_DB, verbose=False)        # second seed
    after = {t: one(c, f"SELECT COUNT(*) FROM {t}") for t in before}
    assert before == after
    assert one(c, "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=%s AND table_type='BASE TABLE'", (TEST_DB,)) == 16  # 15 + schema_migrations


@pytest.mark.parametrize("sql, errno, label", [
    ("INSERT INTO users (email, full_name, role, password_hash) VALUES (NULL,'x','patient','h')", 1048, "NOT NULL"),
    ("INSERT INTO users (email, full_name, role, password_hash) VALUES ('patient1@medsub.demo','x','patient','h')", 1062, "UNIQUE email"),
    ("INSERT INTO users (email, full_name, role, password_hash) VALUES ('not-an-email','x','patient','h')", 3819, "CHECK email"),
    ("INSERT INTO users (email, full_name, role, password_hash) VALUES ('a@b.c','x','superuser','h')", 1265, "ENUM role"),
    ("UPDATE inventory SET quantity = -1 WHERE pharmacy_id=1 AND medicine_id=1", 3819, "CHECK negative stock"),
    ("UPDATE inventory SET reorder_level = -1 WHERE pharmacy_id=1 AND medicine_id=1", 3819, "CHECK reorder_level"),
    ("INSERT INTO inventory (pharmacy_id, medicine_id, quantity) VALUES (99, 1, 5)", 1452, "FK inventory->pharmacy"),
    ("INSERT INTO order_items (order_id, requested_medicine_id, quantity) VALUES (1, 1, 0)", 3819, "CHECK quantity > 0"),
    ("INSERT INTO medicine_ingredients (medicine_id, ingredient_id, strength_mg) VALUES (2, 2, 0)", 3819, "CHECK strength > 0"),
    ("INSERT INTO pharmacist_assignments (user_id, pharmacy_id) VALUES (2, 3)", 1062, "UNIQUE one pharmacy per pharmacist"),
    ("UPDATE medicines SET name = ' ' WHERE id = 3", 3819, "CHECK from ALTER TABLE (non-blank name)"),
    ("INSERT INTO inventory_movements (pharmacy_id, medicine_id, movement_type, delta, actor_user_id) VALUES (1,1,'SALE',5,2)", 3819, "CHECK sale delta < 0 (ALTER)"),
    ("DELETE FROM pharmacies WHERE id = 1", 1451, "FK RESTRICT on delete"),
    ("INSERT INTO shortage_entries (medicine_id, status, reported_at, resolved_at) VALUES (1,'RESOLVED','2026-01-02','2026-01-01')", 3819, "CHECK dates"),
])
def test_constraint_violation(sql, errno, label):
    c = migrator().cursor()
    with pytest.raises(mysql.connector.Error) as e:
        c.execute(sql)
    assert e.value.errno == errno, f"{label}: got {e.value}"


def test_default_values():
    c = migrator().cursor()
    c.execute("INSERT INTO medicines (id, name, brand, category_id, dosage_form, strength_basis) "
              "VALUES (950,'Default Test Tablet','X',3,'tablet','per tablet')")
    c.execute("SELECT route, release_type, requires_prescription, substitution_allowed, is_active FROM medicines WHERE id=950")
    assert c.fetchone() == ("oral", "immediate", 0, 1, 1)
    c.execute("DELETE FROM medicines WHERE id=950")


def test_only_one_open_alert_per_pharmacy_medicine(reset_data):
    c = migrator().cursor()
    # (1,2) is already low -> one OPEN alert exists; a second OPEN row must violate the generated-column unique key
    assert one(c, "SELECT COUNT(*) FROM low_stock_alerts WHERE pharmacy_id=1 AND medicine_id=2 AND status='OPEN'") == 1
    with pytest.raises(mysql.connector.Error) as e:
        c.execute("INSERT INTO low_stock_alerts (pharmacy_id, medicine_id, status, quantity_at_open) VALUES (1,2,'OPEN',1)")
    assert e.value.errno == 1062


def test_trigger_one_alert_no_duplicate_then_auto_resolve(reset_data):
    c = migrator().cursor()
    c.execute("INSERT INTO medicines (id, name, brand, category_id, dosage_form, strength_basis) VALUES (951,'Trigger Test','X',3,'tablet','per tablet')")
    c.execute("INSERT INTO inventory (pharmacy_id, medicine_id, quantity, reorder_level) VALUES (3,951,50,10)")
    q = "SELECT COUNT(*) FROM low_stock_alerts WHERE pharmacy_id=3 AND medicine_id=951 AND status=%s"
    assert one(c, q, ("OPEN",)) == 0
    c.execute("UPDATE inventory SET quantity=10 WHERE pharmacy_id=3 AND medicine_id=951")
    assert one(c, q, ("OPEN",)) == 1
    c.execute("UPDATE inventory SET quantity=3 WHERE pharmacy_id=3 AND medicine_id=951")   # still low: no duplicate
    assert one(c, q, ("OPEN",)) == 1
    c.execute("UPDATE inventory SET quantity=40 WHERE pharmacy_id=3 AND medicine_id=951")  # replenished: auto-resolve
    assert one(c, q, ("OPEN",)) == 0 and one(c, q, ("RESOLVED",)) == 1
    c.execute("UPDATE inventory SET quantity=2 WHERE pharmacy_id=3 AND medicine_id=951")   # low again: reopened (new row)
    assert one(c, q, ("OPEN",)) == 1 and one(c, q, ("RESOLVED",)) == 1


def test_trigger_fires_on_insert_when_already_low(reset_data):
    c = migrator().cursor()
    c.execute("INSERT INTO medicines (id, name, brand, category_id, dosage_form, strength_basis) VALUES (952,'Trigger Test 2','X',3,'tablet','per tablet')")
    c.execute("INSERT INTO inventory (pharmacy_id, medicine_id, quantity, reorder_level) VALUES (3,952,0,5)")
    assert one(c, "SELECT COUNT(*) FROM low_stock_alerts WHERE pharmacy_id=3 AND medicine_id=952 AND status='OPEN'") == 1


@pytest.mark.parametrize("old, new", [("COMPLETED", "REQUESTED"), ("REJECTED", "APPROVED"), ("CANCELLED", "UNDER_REVIEW"),
                                      ("REQUESTED", "APPROVED"), ("REQUESTED", "COMPLETED"), ("UNDER_REVIEW", "COMPLETED")])
def test_invalid_status_transition_rejected(old, new, reset_data):
    c = migrator().cursor()
    c.execute("INSERT INTO orders (id, patient_id, pharmacy_id, status) VALUES (800,4,1,%s)", (old,))
    with pytest.raises(mysql.connector.Error) as e:
        c.execute("UPDATE orders SET status=%s WHERE id=800", (new,))
    assert e.value.errno == 45409
    c.execute("DELETE FROM orders WHERE id=800")


@pytest.mark.parametrize("old, new", [("REQUESTED", "UNDER_REVIEW"), ("UNDER_REVIEW", "APPROVED"), ("UNDER_REVIEW", "REJECTED"),
                                      ("APPROVED", "COMPLETED"), ("REQUESTED", "CANCELLED"), ("APPROVED", "CANCELLED")])
def test_valid_status_transition_allowed(old, new, reset_data):
    c = migrator().cursor()
    c.execute("INSERT INTO orders (id, patient_id, pharmacy_id, status) VALUES (801,4,1,%s)", (old,))
    c.execute("UPDATE orders SET status=%s WHERE id=801", (new,))
    c.execute("DELETE FROM orders WHERE id=801")
