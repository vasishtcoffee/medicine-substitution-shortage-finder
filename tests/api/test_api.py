"""API-level tests: authentication, role checks, catalog/search, order flow (integration with real MySQL)."""
import json
import os

from api_support import make_client
from helpers import scalar
from support import migrator


# ------------------------------------------------------------------ authentication / authorization
def test_openapi_served(anon):
    r = anon.get("/openapi.json")
    assert r.status_code == 200 and "/orders/{order_id}/complete" in r.json()["paths"]
    assert anon.get("/docs").status_code == 200


def test_unauthenticated_requests_get_401(anon):
    for method, path in [("get", "/orders/mine"), ("get", "/inventory"), ("get", "/search?q=a"), ("get", "/dashboard"),
                         ("post", "/sync/run"), ("get", "/feed/inventory"), ("get", "/admin/users"), ("get", "/auth/me")]:
        assert getattr(anon, method)(path).status_code == 401, path


def test_wrong_role_gets_403(pat1, ph1, admin):
    assert pat1.get("/inventory").status_code == 403
    assert pat1.get("/alerts").status_code == 403
    assert pat1.get("/admin/users").status_code == 403
    assert pat1.get("/admin/sql-demo").status_code == 403
    assert pat1.post("/orders/1/approve").status_code == 403
    assert ph1.post("/sync/run").status_code == 403
    assert ph1.get("/feed/inventory").status_code == 403
    assert ph1.get("/admin/users").status_code == 403
    assert ph1.post("/orders", json={"pharmacy_id": 1, "medicine_id": 1, "quantity": 1}).status_code == 403
    assert admin.post("/orders/1/complete").status_code == 403       # sales are a pharmacist action
    assert ph1.post("/medicines", json={}).status_code == 403


def test_login_failures_do_not_reveal_which_part_was_wrong(anon):
    bad_pw = anon.post("/auth/login", json={"email": "admin@medsub.demo", "password": "wrong-password"})
    no_user = anon.post("/auth/login", json={"email": "nobody@medsub.demo", "password": "wrong-password"})
    assert bad_pw.status_code == no_user.status_code == 401
    assert bad_pw.json() == no_user.json()
    assert "medsub_session" not in bad_pw.cookies


def test_login_sets_httponly_cookie_and_logout_clears_it(anon):
    r = anon.post("/auth/login", json={"email": "patient1@medsub.demo", "password": os.environ["DEMO_PATIENT_PASSWORD"]})
    assert r.status_code == 200 and r.json()["role"] == "patient"
    assert "httponly" in r.headers["set-cookie"].lower() and "samesite=lax" in r.headers["set-cookie"].lower()
    assert "password" not in json.dumps(r.json()).lower()
    assert anon.get("/auth/me").json()["email"] == "patient1@medsub.demo"
    assert anon.post("/auth/logout").status_code == 200
    assert anon.get("/auth/me").status_code == 401


def test_tampered_or_garbage_token_is_rejected(anon):
    anon.cookies.set("medsub_session", "not.a.jwt")
    assert anon.get("/auth/me").status_code == 401


def test_inactive_user_cannot_login_or_use_existing_session(admin, reset_data):
    victim = make_client("patient2")
    uid = victim.get("/auth/me").json()["id"]
    assert admin.patch(f"/admin/users/{uid}/active", json={"is_active": False}).status_code == 200
    assert victim.get("/auth/me").status_code == 401                 # existing cookie stops working immediately
    r = victim.post("/auth/login", json={"email": "patient2@medsub.demo", "password": os.environ["DEMO_PATIENT_PASSWORD"]})
    assert r.status_code == 401
    admin.patch(f"/admin/users/{uid}/active", json={"is_active": True})


def test_admin_cannot_deactivate_self(admin):
    me = admin.get("/auth/me").json()["id"]
    assert admin.patch(f"/admin/users/{me}/active", json={"is_active": False}).status_code == 409


# ------------------------------------------------------------------ catalog / search / candidates
def test_search_is_case_insensitive_and_shows_bands_not_quantities_to_patients(pat1):
    r = pat1.get("/search", params={"q": "PARACETAMOL"})
    assert r.status_code == 200
    body = r.json()
    names = {m["name"] for m in body["results"]}
    assert "Paracetamol 500 mg Tablet" in names and "Pyrelief 500 Tablet" in names
    assert "educational demonstration" in body["notice"]
    flat = json.dumps(body)
    assert '"quantity"' not in flat and '"reorder_level"' not in flat
    assert {a["availability"] for m in body["results"] for a in m["availability"]} <= {"In stock", "Low", "Out"}
    assert pat1.get("/search", params={"q": "caffeine"}).json()["results"][0]["name"] == "Paracetamol + Caffeine Tablet"  # by ingredient
    assert pat1.get("/search", params={"q": "%"}).json()["results"] == []                                               # wildcards escaped


def test_candidates_endpoint_explains_eligible_and_rejected(pat1):
    r = pat1.get("/search/candidates/1", params={"pharmacy_id": 2})
    assert r.status_code == 200
    d = r.json()
    assert [c["name"] for c in d["candidates"]] == ["Pyrelief 500 Tablet", "Febrix 500 Tablet"]
    assert d["status"] == "PENDING_PHARMACIST_VERIFICATION"
    assert {x["name"] for x in d["rejected"]} >= {"Parasprin 500 Tablet", "Paracetamol 650 mg Tablet"}
    assert all(c["quantity_here"] is None and c["total_quantity"] is None for c in d["candidates"])


def test_no_candidate_returns_clear_message(pat1):
    d = pat1.get("/search/candidates/5").json()
    assert d["candidates"] == [] and d["message"] == "No verified composition-matching candidate"
    assert pat1.get("/search/candidates/9999").status_code == 404


def test_category_tree_endpoint_uses_recursive_cte(pat1):
    rows = pat1.get("/categories/tree").json()
    assert len(rows) == 12 and rows[0]["path"] == "Pharmaceuticals"
    assert any(r["path"] == "Pharmaceuticals > Analgesics > NSAIDs" and r["depth"] == 2 for r in rows)


def test_admin_medicine_crud_and_validation(admin, pat1, reset_data):
    body = {"name": "API Test Tablet 250 mg", "brand": "Test", "category_id": 4, "dosage_form": "tablet",
            "strength_basis": "per tablet", "ingredients": [{"ingredient_id": 3, "strength_mg": 250}]}
    r = admin.post("/medicines", json=body)
    assert r.status_code == 201
    mid = r.json()["id"]
    assert admin.post("/medicines", json=body).status_code == 409                                  # unique name
    assert admin.post("/medicines", json=dict(body, name="Bad Enum", dosage_form="gel")).status_code == 409   # ENUM rejected by MySQL
    assert admin.post("/medicines", json=dict(body, name="No Ingredients", ingredients=[])).status_code == 422
    assert pat1.get(f"/medicines/{mid}").json()["composition"] == "Ibuprofen 250 mg"
    assert admin.delete(f"/medicines/{mid}").status_code == 200
    assert pat1.get(f"/medicines/{mid}").status_code == 404                                        # soft-deleted: hidden
    assert admin.get(f"/medicines/{mid}").status_code == 200


def test_admin_user_management(admin, reset_data):
    r = admin.post("/admin/users", json={"email": "newpharm@medsub.demo", "full_name": "New Pharm", "role": "pharmacist",
                                         "password": "LongEnough#1", "pharmacy_id": 3})
    assert r.status_code == 201
    assert admin.post("/admin/users", json={"email": "newpharm@medsub.demo", "full_name": "Dup", "role": "patient",
                                            "password": "LongEnough#1"}).status_code == 409
    assert admin.post("/admin/users", json={"email": "x@medsub.demo", "full_name": "P", "role": "pharmacist",
                                            "password": "LongEnough#1"}).status_code == 422       # needs a pharmacy
    uid = r.json()["user_id"]
    assert admin.put(f"/admin/users/{uid}/pharmacy", json={"pharmacy_id": 1}).status_code == 200
    users = {u["email"]: u for u in admin.get("/admin/users").json()}
    assert users["newpharm@medsub.demo"]["pharmacy_id"] == 1 and "password_hash" not in users["admin@medsub.demo"]


# ------------------------------------------------------------------ orders end to end
def test_full_flow_patient_order_to_completed_sale(pat1, ph1, mongo_db, reset_data):
    r = pat1.post("/orders", json={"pharmacy_id": 1, "medicine_id": 2, "quantity": 3, "prescription_note": None})
    assert r.status_code == 201
    oid = r.json()["order_id"]
    mine = {o["order_id"]: o for o in pat1.get("/orders/mine").json()}
    assert mine[oid]["status"] == "REQUESTED"
    item_id = mine[oid]["items"][0]["item_id"]

    assert ph1.post(f"/orders/{oid}/complete").status_code == 409            # not approved yet
    assert ph1.post(f"/orders/{oid}/start-review").status_code == 200
    assert ph1.post(f"/orders/{oid}/start-review").status_code == 409        # repeat: guarded transition
    d = ph1.post(f"/orders/items/{item_id}/decision", json={"proposed_medicine_id": 2, "decision": "APPROVED", "note": "as requested"})
    assert d.status_code == 200
    assert ph1.post(f"/orders/items/{item_id}/decision", json={"proposed_medicine_id": 8, "decision": "APPROVED"}).status_code == 422
    assert ph1.post(f"/orders/{oid}/approve").status_code == 200
    assert pat1.post(f"/orders/{oid}/complete").status_code == 403           # patients cannot sell

    before = scalar(migrator(), "SELECT quantity FROM inventory WHERE pharmacy_id=1 AND medicine_id=2")
    done = ph1.post(f"/orders/{oid}/complete")
    assert done.status_code == 200 and done.json()["status"] == "COMPLETED"
    assert "educational demonstration" in done.json()["notice"]
    assert scalar(migrator(), "SELECT quantity FROM inventory WHERE pharmacy_id=1 AND medicine_id=2") == before - 3
    assert ph1.post(f"/orders/{oid}/complete").status_code == 409            # repeat fails
    assert pat1.post(f"/orders/{oid}/cancel").status_code == 409             # terminal state

    # the background sync already pushed the sale into MongoDB (mongomock here)
    doc = mongo_db["inventory_feed"].find_one({"_id": "ph1:med2"})
    assert doc and doc["quantity"] == before - 3
    assert mongo_db["feed_events"].count_documents({"source": "sale", "payload.order_id": oid}) == 1
    revs = pat1.get(f"/orders/{oid}/reviews").json()
    assert revs and revs[0]["decision"] == "APPROVED"


def test_patient_cannot_see_or_touch_other_patients_orders(pat1, pat2, reset_data):
    assert {o["order_id"] for o in pat2.get("/orders/mine").json()} == {2, 4}
    assert pat1.post("/orders/2/cancel").status_code == 403
    assert pat1.get("/orders/2/reviews").status_code == 403
    assert pat1.get("/orders/999/reviews").status_code == 404


def test_pharmacist_isolation_across_pharmacies(ph1, ph2, reset_data):
    assert {o["order_id"] for o in ph1.get("/orders").json()} == {1, 3, 5}
    assert {o["order_id"] for o in ph2.get("/orders").json()} == {2, 4}
    assert {i["pharmacy_id"] for i in ph1.get("/inventory").json()} == {1}
    assert ph1.post("/inventory/receive", json={"pharmacy_id": 2, "medicine_id": 1, "quantity": 5}).status_code == 403
    assert ph1.post("/orders/2/approve").status_code == 403
    r = ph1.post("/inventory/receive", json={"pharmacy_id": 1, "medicine_id": 3, "quantity": 40, "batch_no": "L1", "expiry_date": "2027-06-30"})
    assert r.status_code == 201 and r.json()["quantity"] == 40
    assert ph1.post("/inventory/receive", json={"pharmacy_id": 1, "medicine_id": 3, "quantity": 0}).status_code == 422
    assert ph1.post("/inventory/adjust", json={"pharmacy_id": 1, "medicine_id": 3, "delta": -1000}).status_code == 409


def test_alerts_follow_stock_changes(ph1, reset_data):
    assert 2 in {a["medicine_id"] for a in ph1.get("/alerts").json()}       # Pyrelief is low at pharmacy 1
    ph1.post("/inventory/receive", json={"pharmacy_id": 1, "medicine_id": 2, "quantity": 100})
    assert 2 not in {a["medicine_id"] for a in ph1.get("/alerts").json()}   # trigger auto-resolved it
    assert any(a["medicine_id"] == 2 for a in ph1.get("/alerts", params={"status": "RESOLVED"}).json())


def test_dashboards_per_role(pat1, ph1, admin):
    assert "my_orders_by_status" in pat1.get("/dashboard").json()
    d = ph1.get("/dashboard").json()
    assert d["pharmacy"] == "City Care Pharmacy" and "orders_by_status" in d
    assert "sync_pending" in admin.get("/dashboard").json()


def test_sql_demo_runs_only_whitelisted_queries(admin, ph1):
    lst = admin.get("/admin/sql-demo").json()
    assert {"q_nested_no_stock", "q_correlated_below_own_avg", "cte_category_tree"} <= {q["name"] for q in lst}
    r = admin.post("/admin/sql-demo/q_nested_no_stock/run")
    assert r.status_code == 200 and len(r.json()["rows"]) == 2
    assert admin.post("/admin/sql-demo/DROP TABLE users/run").status_code == 404
    assert admin.post("/admin/sql-demo/demo_candidates/run").status_code == 409     # CALL demos are not runnable from the web
    assert ph1.post("/admin/sql-demo/q_nested_no_stock/run").status_code == 403


def test_admin_crud_on_pharmacies_shortages_and_medicine_update(admin, pat1, reset_data):
    # pharmacies: create + update (+ duplicate name rejected by UNIQUE)
    r = admin.post("/pharmacies", json={"name": "Test Pharmacy", "city": "Hubballi", "address": None})
    assert r.status_code == 201
    pid = r.json()["id"]
    assert admin.post("/pharmacies", json={"name": "Test Pharmacy", "city": "X"}).status_code == 409
    assert admin.put(f"/pharmacies/{pid}", json={"name": "Test Pharmacy 2", "city": "Hubballi", "address": "1 Road"}).status_code == 200
    assert {p["name"] for p in pat1.get("/pharmacies").json()} >= {"Test Pharmacy 2"}
    assert admin.put("/pharmacies/9999", json={"name": "Nope", "city": "X"}).status_code == 404
    assert pat1.post("/pharmacies", json={"name": "Evil", "city": "X"}).status_code == 403
    # shortages: create + hard delete
    s = admin.post("/shortages", json={"medicine_id": 1, "severity": "LOW", "note": "t"})
    assert s.status_code == 201
    sid = s.json()["id"]
    assert admin.delete(f"/shortages/{sid}").status_code == 200
    assert admin.delete(f"/shortages/{sid}").status_code == 404
    assert pat1.delete("/shortages/1").status_code == 403
    # medicine UPDATE changes the row and its composition
    body = {"name": "Upd Test Tablet", "brand": "T", "category_id": 4, "dosage_form": "tablet", "strength_basis": "per tablet",
            "ingredients": [{"ingredient_id": 3, "strength_mg": 100}]}
    mid = admin.post("/medicines", json=body).json()["id"]
    body["brand"] = "T2"
    body["ingredients"] = [{"ingredient_id": 3, "strength_mg": 200}, {"ingredient_id": 2, "strength_mg": 5}]
    assert admin.put(f"/medicines/{mid}", json=body).status_code == 200
    m = admin.get(f"/medicines/{mid}").json()
    assert m["brand"] == "T2" and len(m["ingredients"]) == 2
    # clean up so later tests (e.g. "medicines with no stock") are not polluted by these rows
    assert admin.delete(f"/medicines/{mid}").status_code == 200
    c = migrator().cursor()
    c.execute("DELETE FROM pharmacies WHERE id = %s", (pid,))
