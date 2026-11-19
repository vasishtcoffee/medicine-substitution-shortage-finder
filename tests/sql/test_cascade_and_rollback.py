"""Direct DB invariants for composition cascade and explicit transaction rollback."""
from helpers import call, scalar
from support import migrator


def test_deleting_isolated_medicine_cascades_only_its_composition():
    cnx = migrator()
    cur = cnx.cursor()
    cur.execute("INSERT INTO medicines(name,brand,category_id,dosage_form,strength_basis) "
                "VALUES ('Cascade test tablet','Test',4,'tablet','per tablet')")
    mid = cur.lastrowid
    cur.execute("INSERT INTO medicine_ingredients VALUES (%s,3,100)", (mid,))
    other = scalar(cnx, "SELECT COUNT(*) FROM medicine_ingredients WHERE medicine_id=1")
    cur.execute("DELETE FROM medicines WHERE id=%s", (mid,))
    assert scalar(cnx, "SELECT COUNT(*) FROM medicine_ingredients WHERE medicine_id=%s", (mid,)) == 0
    assert scalar(cnx, "SELECT COUNT(*) FROM medicine_ingredients WHERE medicine_id=1") == other


def test_explicit_rollback_restores_stock_alerts_and_outbox(reset_data):
    cnx = migrator()
    queries = ["SELECT quantity FROM inventory WHERE pharmacy_id=1 AND medicine_id=1",
               "SELECT COUNT(*) FROM low_stock_alerts", "SELECT COUNT(*) FROM sync_outbox"]
    before = [scalar(cnx, q) for q in queries]
    cnx.start_transaction()
    try:
        cnx.cursor().execute("UPDATE inventory SET quantity=0 WHERE pharmacy_id=1 AND medicine_id=1")
        assert scalar(cnx, queries[0]) == 0
        assert scalar(cnx, queries[1]) > before[1]
        # Triggers own alerts. Workflow procedures explicitly call this internal
        # helper for outbox writes; it participates in the caller's transaction.
        call(cnx, "CALL sp_write_outbox(1,1,'adjustment',0,0,NULL,NULL,NULL)")
        assert scalar(cnx, queries[2]) > before[2]
    finally:
        cnx.rollback()
    assert [scalar(cnx, q) for q in queries] == before
