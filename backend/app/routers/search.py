"""Search + availability + substitution candidates (eligibility and ranking are computed by MySQL)."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from .. import config, db, security
from .medicines import COMPOSITION_SQL

router = APIRouter(prefix="/search", tags=["search"])


def _like(q: str) -> str:
    return "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _bands(cnx, medicine_ids: list[int], pharmacies: list[dict]) -> dict:
    out: dict[int, list[dict]] = {m: [] for m in medicine_ids}
    if not medicine_ids:
        return out
    marks = ",".join(["%s"] * len(medicine_ids))
    got = {(r["medicine_id"], r["pharmacy_id"]): r["availability"] for r in
           db.query(cnx, f"SELECT medicine_id, pharmacy_id, availability FROM v_availability WHERE medicine_id IN ({marks})",
                    medicine_ids)}
    for m in medicine_ids:
        for p in pharmacies:
            out[m].append({"pharmacy_id": p["id"], "pharmacy_name": p["name"],
                           "availability": got.get((m, p["id"]), "Out")})
    return out


@router.get("")
def search(q: str = Query("", max_length=100), identity: db.Identity = Depends(security.get_identity)):
    """Case-insensitive LIKE over name, brand, category and ingredient (utf8mb4_0900_ai_ci)."""
    like = _like(q.strip())
    with db.session(identity.role, identity) as cnx:
        meds = db.query(
            cnx, f"SELECT m.id, m.name, m.brand, c.name AS category, m.dosage_form, m.route, m.release_type, "
                 f"m.requires_prescription, m.substitution_allowed, {COMPOSITION_SQL} AS composition, "
                 f"EXISTS(SELECT 1 FROM shortage_entries s WHERE s.medicine_id = m.id AND s.status = 'OPEN') AS in_shortage "
                 f"FROM medicines m JOIN medicine_categories c ON c.id = m.category_id "
                 f"WHERE m.is_active = 1 AND (m.name LIKE %s OR m.brand LIKE %s OR c.name LIKE %s OR EXISTS ("
                 f" SELECT 1 FROM medicine_ingredients mi JOIN active_ingredients ai ON ai.id = mi.ingredient_id "
                 f" WHERE mi.medicine_id = m.id AND ai.name LIKE %s)) ORDER BY m.name LIMIT 50",
            (like, like, like, like))
        pharmacies = db.query(cnx, "SELECT id, name FROM pharmacies ORDER BY id")
        bands = _bands(cnx, [m["id"] for m in meds], pharmacies)
    for m in meds:
        m["availability"] = bands[m["id"]]
    return {"query": q, "results": meds, "notice": config.SAFETY_NOTICE}


@router.get("/availability/{medicine_id}")
def availability(medicine_id: int, identity: db.Identity = Depends(security.get_identity)):
    with db.session(identity.role, identity) as cnx:
        if not db.query(cnx, "SELECT 1 FROM medicines WHERE id=%s AND is_active=1", (medicine_id,)):
            raise HTTPException(404, "Medicine not found")
        pharmacies = db.query(cnx, "SELECT id, name FROM pharmacies ORDER BY id")
        return _bands(cnx, [medicine_id], pharmacies)[medicine_id]


@router.get("/candidates/{medicine_id}")
def candidates(medicine_id: int, pharmacy_id: Optional[int] = None, identity: db.Identity = Depends(security.get_identity)):
    """Eligible candidates (ranked), rejected near-misses with reasons. Always 'pending pharmacist verification'."""
    with db.session(identity.role, identity) as cnx:
        req = db.query(cnx, "SELECT id, name, brand, substitution_allowed, is_active FROM medicines WHERE id=%s", (medicine_id,))
        if not req or (not req[0]["is_active"] and identity.role != "admin"):
            raise HTTPException(404, "Medicine not found")
        ph = pharmacy_id if pharmacy_id is not None else (identity.pharmacy_id or 0)
        ranked = db.call_one(cnx, "sp_rank_candidates", (medicine_id, ph))
        rejected = db.call_one(cnx, "sp_candidate_rejections", (medicine_id,))
    resp = {"requested": req[0], "pharmacy_id": ph, "candidates": ranked, "rejected": rejected,
            "status": "PENDING_PHARMACIST_VERIFICATION", "notice": config.SAFETY_NOTICE}
    if not ranked:
        resp["message"] = "No verified composition-matching candidate"
    return resp
