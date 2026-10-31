"""P0: sale transaction - exact deduction, atomicity, no overselling under concurrency, repeat fails."""
import threading

import mysql.connector
import pytest

from support import direct, migrator
from helpers import call, scalar


def mk_order(m, oid, pharmacy, status, items):
    """Insert an order directly (as migrator) with items [(requested, dispensed, qty)]."""
    c = m.cursor()
    c.execute("INSERT INTO orders (id, patient_id, pharmacy_id, status) VALUES (%s,4,%s,%s)", (oid, pharmacy, status))
    for i, (req, disp, qty) in enumerate(items):
        c.execute("INSERT INTO order_items (order_id, requested_medicine_id, dispensed_medicine_id, quantity) VALUES (%s,%s,%s,%s)",
                  (oid, req, disp, qty))


def qty(m, ph, med):
    return scalar(m, "SELECT quantity FROM inventory WHERE pharmacy_id=%s AND medicine_id=%s", (ph, med))


def test_valid_sale_deducts_exactly_and_writes_ledger_and_outbox(reset_data):
    m, ph1 = migrator(), direct("pharmacist", 2, "pharmacist", 1)
    before = qty(m, 1, 2)                                   # seed order 3: 2 x Pyrelief (med 2) at pharmacy 1
    row = call(ph1, "CALL sp_complete_order(3, 2)")[0]
    assert row["status"] == "COMPLETED"
    assert qty(m, 1, 2) == before - 2
    assert scalar(m, "SELECT status FROM orders WHERE id=3") == "COMPLETED"
    assert scalar(m, "SELECT COUNT(*) FROM inventory_movements WHERE order_id=3 AND movement_type='SALE' AND delta=-2 AND actor_user_id=2") == 1
    ops = [r[0] for r in _all(m, "SELECT operation FROM sync_outbox WHERE entity_id IN ('ph1:med2') OR entity_id LIKE 'sale:%' ORDER BY id") ]
    assert "UPSERT_INVENTORY_FEED" in ops and "APPEND_FEED_EVENT" in ops
    assert scalar(m, "SELECT COUNT(*) FROM low_stock_alerts WHERE pharmacy_id=1 AND medicine_id=2 AND status='OPEN'") == 1


def _all(m, sql):
    c = m.cursor()
    c.execute(sql)
    return c.fetchall()


def test_repeating_complete_order_fails(reset_data):
    m, ph1 = migrator(), direct("pharmacist", 2, "pharmacist", 1)
    call(ph1, "CALL sp_complete_order(3, 2)")
    after_first = qty(m, 1, 2)
    with pytest.raises(mysql.connector.Error) as e:
        call(ph1, "CALL sp_complete_order(3, 2)")
    assert e.value.errno == 45409
    assert qty(m, 1, 2) == after_first                     # not deducted twice


def test_insufficient_stock_rejected_with_no_partial_rows(reset_data):
    m, ph1 = migrator(), direct("pharmacist", 2, "pharmacist", 1)
    # item A (med 1, plenty of stock) is processed before item B (med 3, stock 0): A must be rolled back
    mk_order(m, 810, 1, "APPROVED", [(1, 1, 5), (3, 3, 1)])
    a_before, outbox_before = qty(m, 1, 1), scalar(m, "SELECT COUNT(*) FROM sync_outbox")
    with pytest.raises(mysql.connector.Error) as e:
        call(ph1, "CALL sp_complete_order(810, 2)")
    assert e.value.errno == 45409 and "Insufficient" in e.value.msg
    assert qty(m, 1, 1) == a_before
    assert scalar(m, "SELECT COUNT(*) FROM inventory_movements WHERE order_id=810") == 0
    assert scalar(m, "SELECT COUNT(*) FROM sync_outbox") == outbox_before
    assert scalar(m, "SELECT status FROM orders WHERE id=810") == "APPROVED"


def test_sale_requires_matching_actor_and_assigned_pharmacy(reset_data):
    m = migrator()
    mk_order(m, 811, 2, "APPROVED", [(2, 2, 1)])
    ph1 = direct("pharmacist", 2, "pharmacist", 1)
    with pytest.raises(mysql.connector.Error) as e:
        call(ph1, "CALL sp_complete_order(811, 2)")        # order belongs to pharmacy 2
    assert e.value.errno == 45403
    ph2 = direct("pharmacist", 3, "pharmacist", 2)
    with pytest.raises(mysql.connector.Error) as e:
        call(ph2, "CALL sp_complete_order(811, 2)")        # actor id is not the authenticated user
    assert e.value.errno == 45403
    assert call(ph2, "CALL sp_complete_order(811, 3)")[0]["status"] == "COMPLETED"


def test_two_concurrent_sales_cannot_oversell(reset_data):
    m = migrator()
    assert qty(m, 1, 4) == 50
    mk_order(m, 820, 1, "APPROVED", [(4, 4, 30)])
    mk_order(m, 821, 1, "APPROVED", [(4, 4, 30)])            # 30 + 30 > 50
    results, barrier = {}, threading.Barrier(2)

    def sell(order_id):
        cnx = direct("pharmacist", 2, "pharmacist", 1)
        barrier.wait()
        for attempt in range(3):                              # deadlock / lock-wait victims retry, like the API does
            try:
                results[order_id] = call(cnx, "CALL sp_complete_order(%s, 2)", (order_id,))[0]["status"]
                return
            except mysql.connector.Error as e:
                if e.errno in (1213, 1205):
                    continue
                results[order_id] = f"ERR {e.errno}"
                return

    ts = [threading.Thread(target=sell, args=(o,)) for o in (820, 821)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert sorted(results.values()) == ["COMPLETED", "ERR 45409"], results
    assert qty(m, 1, 4) == 20
    assert scalar(m, "SELECT COUNT(*) FROM inventory_movements WHERE medicine_id=4 AND movement_type='SALE' AND order_id IN (820,821)") == 1


def test_prescription_note_required_to_approve_rx_medicine(reset_data):
    m, ph1 = migrator(), direct("pharmacist", 2, "pharmacist", 1)
    mk_order(m, 830, 1, "UNDER_REVIEW", [(11, None, 2)])     # Amoxicillin requires a prescription; no note
    with pytest.raises(mysql.connector.Error) as e:
        call(ph1, "CALL sp_approve_order(830)")
    assert e.value.errno == 45422
    m.cursor().execute("UPDATE orders SET prescription_note='Synthetic note' WHERE id=830")
    assert call(ph1, "CALL sp_approve_order(830)")[0]["status"] == "APPROVED"


def test_substitution_decision_flow_records_review_and_dispenses_candidate(reset_data):
    m, ph2 = migrator(), direct("pharmacist", 3, "pharmacist", 2)
    # seed order 2 (UNDER_REVIEW at pharmacy 2) requests med 1 (out of stock there); propose eligible med 2
    row = call(ph2, "CALL sp_decide_substitution(2, 2, 'APPROVED', 'in stock here')")[0]
    assert row["decision"] == "APPROVED"
    assert scalar(m, "SELECT dispensed_medicine_id FROM order_items WHERE id=2") == 2
    assert scalar(m, "SELECT COUNT(*) FROM substitution_reviews WHERE order_item_id=2 AND reviewer_id=3") == 1
    # the look-alike (med 8) must be refused even though a pharmacist proposes it
    with pytest.raises(mysql.connector.Error) as e:
        call(ph2, "CALL sp_decide_substitution(2, 8, 'APPROVED', 'looks similar')")
    assert e.value.errno == 45422
    assert call(ph2, "CALL sp_approve_order(2)")[0]["status"] == "APPROVED"
    assert call(ph2, "CALL sp_complete_order(2, 3)")[0]["status"] == "COMPLETED"
    assert qty(m, 2, 2) == 75                                 # 80 - 5 units of the approved substitute
