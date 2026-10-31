"""Catalog (read: all roles) and admin writes: medicines, shortages, pharmacies, users, assignments."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import db, security

router = APIRouter(tags=["catalog"])

any_user = security.get_identity
admin_only = security.require_roles("admin")

COMPOSITION_SQL = (
    "(SELECT GROUP_CONCAT(CONCAT(ai.name, ' ', TRIM(TRAILING '.' FROM TRIM(TRAILING '0' FROM mi.strength_mg)), ' mg') "
    "ORDER BY ai.name SEPARATOR ' + ') FROM medicine_ingredients mi JOIN active_ingredients ai ON ai.id = mi.ingredient_id "
    "WHERE mi.medicine_id = m.id)")


class IngredientIn(BaseModel):
    ingredient_id: int
    strength_mg: float = Field(gt=0)


class MedicineIn(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    brand: str = Field(min_length=1, max_length=100)
    category_id: int
    dosage_form: str
    route: str = "oral"
    release_type: str = "immediate"
    strength_basis: str
    requires_prescription: bool = False
    substitution_allowed: bool = True
    is_active: bool = True
    ingredients: list[IngredientIn] = Field(min_length=1)


def _sess(identity):
    return db.session(identity.role, identity)


@router.get("/medicines")
def list_medicines(category_id: Optional[int] = None, include_inactive: bool = False,
                   identity: db.Identity = Depends(any_user)):
    if include_inactive and identity.role != "admin":
        raise HTTPException(403, "Only admin can list inactive medicines")
    sql = (f"SELECT m.id, m.name, m.brand, m.category_id, c.name AS category, m.dosage_form, m.route, m.release_type, "
           f"m.strength_basis, m.requires_prescription, m.substitution_allowed, m.is_active, {COMPOSITION_SQL} AS composition "
           f"FROM medicines m JOIN medicine_categories c ON c.id = m.category_id WHERE 1=1")
    params: list = []
    if not include_inactive:
        sql += " AND m.is_active = 1"
    if category_id:
        sql += " AND m.category_id = %s"
        params.append(category_id)
    with _sess(identity) as cnx:
        return db.query(cnx, sql + " ORDER BY m.name", params)


@router.get("/medicines/{medicine_id}")
def get_medicine(medicine_id: int, identity: db.Identity = Depends(any_user)):
    with _sess(identity) as cnx:
        rows = db.query(cnx, f"SELECT m.*, c.name AS category, {COMPOSITION_SQL} AS composition FROM medicines m "
                             "JOIN medicine_categories c ON c.id = m.category_id WHERE m.id = %s", (medicine_id,))
        if not rows or (not rows[0]["is_active"] and identity.role != "admin"):
            raise HTTPException(404, "Medicine not found")
        rows[0]["ingredients"] = db.query(
            cnx, "SELECT mi.ingredient_id, ai.name, mi.strength_mg FROM medicine_ingredients mi "
                 "JOIN active_ingredients ai ON ai.id = mi.ingredient_id WHERE mi.medicine_id = %s ORDER BY ai.name",
            (medicine_id,))
        return rows[0]


def _write_ingredients(cnx, medicine_id: int, items: list[IngredientIn]):
    db.execute(cnx, "DELETE FROM medicine_ingredients WHERE medicine_id = %s", (medicine_id,))
    for it in items:
        db.execute(cnx, "INSERT INTO medicine_ingredients (medicine_id, ingredient_id, strength_mg) VALUES (%s,%s,%s)",
                   (medicine_id, it.ingredient_id, it.strength_mg))


@router.post("/medicines", status_code=201)
def create_medicine(body: MedicineIn, identity: db.Identity = Depends(admin_only)):
    with _sess(identity) as cnx:
        db.execute(cnx, "START TRANSACTION")
        try:
            cur = cnx.cursor()
            cur.execute(
                "INSERT INTO medicines (name, brand, category_id, dosage_form, route, release_type, strength_basis, "
                "requires_prescription, substitution_allowed, is_active) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (body.name, body.brand, body.category_id, body.dosage_form, body.route, body.release_type,
                 body.strength_basis, body.requires_prescription, body.substitution_allowed, body.is_active))
            new_id = cur.lastrowid
            cur.close()
            _write_ingredients(cnx, new_id, body.ingredients)
            db.execute(cnx, "COMMIT")
        except Exception:
            db.execute(cnx, "ROLLBACK")
            raise
    return {"id": new_id}


@router.put("/medicines/{medicine_id}")
def update_medicine(medicine_id: int, body: MedicineIn, identity: db.Identity = Depends(admin_only)):
    with _sess(identity) as cnx:
        db.execute(cnx, "START TRANSACTION")
        try:
            n = db.execute(
                cnx, "UPDATE medicines SET name=%s, brand=%s, category_id=%s, dosage_form=%s, route=%s, release_type=%s, "
                     "strength_basis=%s, requires_prescription=%s, substitution_allowed=%s, is_active=%s WHERE id=%s",
                (body.name, body.brand, body.category_id, body.dosage_form, body.route, body.release_type,
                 body.strength_basis, body.requires_prescription, body.substitution_allowed, body.is_active, medicine_id))
            if n == 0 and not db.query(cnx, "SELECT 1 FROM medicines WHERE id=%s", (medicine_id,)):
                raise HTTPException(404, "Medicine not found")
            _write_ingredients(cnx, medicine_id, body.ingredients)
            db.execute(cnx, "COMMIT")
        except Exception:
            db.execute(cnx, "ROLLBACK")
            raise
    return {"id": medicine_id}


@router.delete("/medicines/{medicine_id}")
def deactivate_medicine(medicine_id: int, identity: db.Identity = Depends(admin_only)):
    """Soft delete (is_active = 0): stock history and orders keep referencing the medicine."""
    with _sess(identity) as cnx:
        n = db.execute(cnx, "UPDATE medicines SET is_active = 0 WHERE id = %s", (medicine_id,))
        if n == 0 and not db.query(cnx, "SELECT 1 FROM medicines WHERE id=%s", (medicine_id,)):
            raise HTTPException(404, "Medicine not found")
    return {"id": medicine_id, "is_active": False}


@router.get("/ingredients")
def list_ingredients(identity: db.Identity = Depends(any_user)):
    with _sess(identity) as cnx:
        return db.query(cnx, "SELECT id, name FROM active_ingredients ORDER BY name")


@router.get("/pharmacies")
def list_pharmacies(identity: db.Identity = Depends(any_user)):
    with _sess(identity) as cnx:
        return db.query(cnx, "SELECT id, name, city, address FROM pharmacies ORDER BY name")


class PharmacyIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    city: str = Field(min_length=1, max_length=80)
    address: Optional[str] = Field(default=None, max_length=200)


@router.post("/pharmacies", status_code=201)
def create_pharmacy(body: PharmacyIn, identity: db.Identity = Depends(admin_only)):
    with _sess(identity) as cnx:
        cur = cnx.cursor()
        cur.execute("INSERT INTO pharmacies (name, city, address) VALUES (%s,%s,%s)", (body.name, body.city, body.address))
        new_id = cur.lastrowid
        cur.close()
    return {"id": new_id}


@router.put("/pharmacies/{pharmacy_id}")
def update_pharmacy(pharmacy_id: int, body: PharmacyIn, identity: db.Identity = Depends(admin_only)):
    with _sess(identity) as cnx:
        db.execute(cnx, "UPDATE pharmacies SET name=%s, city=%s, address=%s WHERE id=%s",
                   (body.name, body.city, body.address, pharmacy_id))
        if not db.query(cnx, "SELECT 1 FROM pharmacies WHERE id=%s", (pharmacy_id,)):
            raise HTTPException(404, "Pharmacy not found")
    return {"id": pharmacy_id}


# Rubric 8: recursive CTE (same text as database/sql/advanced.sql)
CATEGORY_TREE_SQL = (
    "WITH RECURSIVE cte_category_tree AS ("
    " SELECT id, name, parent_id, 0 AS depth, CAST(name AS CHAR(500)) AS path FROM medicine_categories WHERE parent_id IS NULL"
    " UNION ALL"
    " SELECT c.id, c.name, c.parent_id, t.depth + 1, CONCAT(t.path, ' > ', c.name)"
    " FROM medicine_categories c JOIN cte_category_tree t ON c.parent_id = t.id)"
    " SELECT id, name, parent_id, depth, path FROM cte_category_tree ORDER BY path")


@router.get("/categories/tree")
def category_tree(identity: db.Identity = Depends(any_user)):
    with _sess(identity) as cnx:
        return db.query(cnx, CATEGORY_TREE_SQL)


@router.get("/shortages")
def list_shortages(status: Optional[str] = None, identity: db.Identity = Depends(any_user)):
    sql = ("SELECT s.id, s.medicine_id, m.name AS medicine_name, s.status, s.severity, s.reported_at, s.resolved_at, "
           "s.source, s.note FROM shortage_entries s JOIN medicines m ON m.id = s.medicine_id")
    params: list = []
    if status:
        sql += " WHERE s.status = %s"
        params.append(status)
    with _sess(identity) as cnx:
        return db.query(cnx, sql + " ORDER BY s.reported_at DESC", params)


class ShortageIn(BaseModel):
    medicine_id: int
    severity: str = "MEDIUM"
    note: Optional[str] = Field(default=None, max_length=200)


@router.post("/shortages", status_code=201)
def create_shortage(body: ShortageIn, identity: db.Identity = Depends(admin_only)):
    with _sess(identity) as cnx:
        cur = cnx.cursor()
        cur.execute("INSERT INTO shortage_entries (medicine_id, severity, note) VALUES (%s,%s,%s)",
                    (body.medicine_id, body.severity, body.note))
        new_id = cur.lastrowid
        cur.close()
    return {"id": new_id}


@router.patch("/shortages/{shortage_id}/resolve")
def resolve_shortage(shortage_id: int, identity: db.Identity = Depends(admin_only)):
    with _sess(identity) as cnx:
        n = db.execute(cnx, "UPDATE shortage_entries SET status='RESOLVED', resolved_at=NOW() "
                            "WHERE id=%s AND status='OPEN'", (shortage_id,))
        if n == 0:
            raise HTTPException(404, "Open shortage not found")
    return {"id": shortage_id, "status": "RESOLVED"}


@router.delete("/shortages/{shortage_id}")
def delete_shortage(shortage_id: int, identity: db.Identity = Depends(admin_only)):
    """Hard DELETE (nothing references shortage_entries, so no foreign key blocks it)."""
    with _sess(identity) as cnx:
        if db.execute(cnx, "DELETE FROM shortage_entries WHERE id=%s", (shortage_id,)) == 0:
            raise HTTPException(404, "Shortage not found")
    return {"deleted": shortage_id}


# ------------------------------------------------------------------ admin: users and assignments
class UserIn(BaseModel):
    email: str
    full_name: str = Field(min_length=1, max_length=120)
    role: str
    password: str = Field(min_length=8)
    pharmacy_id: Optional[int] = None


@router.get("/admin/users")
def list_users(identity: db.Identity = Depends(admin_only)):
    with _sess(identity) as cnx:
        return db.query(cnx, "SELECT u.id, u.email, u.full_name, u.role, u.is_active, u.created_at, u.pharmacy_id, "
                             "p.name AS pharmacy_name FROM v_users_public u LEFT JOIN pharmacies p ON p.id = u.pharmacy_id "
                             "ORDER BY u.id")


@router.post("/admin/users", status_code=201)
def create_user(body: UserIn, identity: db.Identity = Depends(admin_only)):
    with _sess(identity) as cnx:
        rows = db.call_one(cnx, "sp_admin_create_user",
                           (body.email.strip(), body.full_name, body.role, security.hash_password(body.password), body.pharmacy_id))
    return rows[0]


class ActiveIn(BaseModel):
    is_active: bool


@router.patch("/admin/users/{user_id}/active")
def set_user_active(user_id: int, body: ActiveIn, identity: db.Identity = Depends(admin_only)):
    with _sess(identity) as cnx:
        return db.call_one(cnx, "sp_admin_set_user_active", (user_id, 1 if body.is_active else 0))[0]


class AssignIn(BaseModel):
    pharmacy_id: int


@router.put("/admin/users/{user_id}/pharmacy")
def assign_pharmacist(user_id: int, body: AssignIn, identity: db.Identity = Depends(admin_only)):
    with _sess(identity) as cnx:
        return db.call_one(cnx, "sp_admin_assign_pharmacist", (user_id, body.pharmacy_id))[0]
