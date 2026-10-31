"""P0: candidate procedure returns the eligible cases and rejects every ineligible seed case; query library runs."""
import re
from pathlib import Path

from support import direct, migrator
from helpers import call
from run_sql_demo import parse_blocks

ROOT = Path(__file__).resolve().parents[2]


def names(rows):
    return {r["name"] for r in rows}


def test_eligible_candidates_for_paracetamol_500():
    c = direct("patient", 4, "patient")
    elig = call(c, "CALL sp_equivalent_candidates(1)")
    assert names(elig) == {"Pyrelief 500 Tablet", "Febrix 500 Tablet"}
    assert all(r["verification_status"] == "PENDING_PHARMACIST_VERIFICATION" for r in elig)


def test_every_ineligible_seed_case_is_rejected_with_reason():
    c = direct("patient", 4, "patient")
    rej = {r["name"]: r["reject_reason"] for r in call(c, "CALL sp_candidate_rejections(1)")}
    assert "different strength" in rej["Paracetamol 650 mg Tablet"]
    assert "different active-ingredient set" in rej["Paracetamol + Caffeine Tablet"]
    assert "different dosage form" in rej["Paracetamol Oral Syrup 250 mg/5 ml"]
    assert "different release type" in rej["Paracetamol 500 mg ER Tablet"]
    assert "inactive" in rej["Paracetamol 500 mg Tablet (Discontinued)"]
    # look-alike: similar name + same category, different active ingredient -> must be rejected
    assert "different active-ingredient set" in rej["Parasprin 500 Tablet"]
    eligible = names(call(c, "CALL sp_equivalent_candidates(1)"))
    assert not (eligible & set(rej))


def test_substitution_not_allowed_flag_blocks_candidate():
    c = direct("patient", 4, "patient")
    assert names(call(c, "CALL sp_equivalent_candidates(15)")) == set()       # 16 does not allow substitution
    rej = {r["name"]: r["reject_reason"] for r in call(c, "CALL sp_candidate_rejections(15)")}
    assert "substitution not allowed" in rej["Metformin 500 mg Tablet (Brand B)"]


def test_combination_product_requires_complete_set_match():
    c = direct("patient", 4, "patient")
    # medicine 5 = paracetamol 500 + caffeine 30; nothing else has both -> no candidate (never manufactured)
    assert call(c, "CALL sp_equivalent_candidates(5)") == []


def test_empty_candidate_case_via_unknown_medicine():
    c = direct("patient", 4, "patient")
    assert call(c, "CALL sp_equivalent_candidates(9999)") == []


def test_other_ingredient_families_pair_up():
    c = direct("patient", 4, "patient")
    assert names(call(c, "CALL sp_equivalent_candidates(9)")) == {"Ibufen 400 Tablet"}
    assert names(call(c, "CALL sp_equivalent_candidates(11)")) == {"Amoxyl 500 Capsule"}


def test_ranking_orders_by_availability_and_hides_quantities_from_patients():
    p = direct("patient", 4, "patient")
    ranked = call(p, "CALL sp_rank_candidates(1, 2)")
    assert [r["name"] for r in ranked] == ["Pyrelief 500 Tablet", "Febrix 500 Tablet"]   # stocked at pharmacy 2 first
    for r in ranked:
        assert r["quantity_here"] is None and r["total_quantity"] is None
    assert ranked[0]["availability_here"] == "In stock" and ranked[1]["availability_here"] == "Out"


def test_ranking_exact_quantities_only_for_own_pharmacy_or_admin():
    ph1 = direct("pharmacist", 2, "pharmacist", 1)
    own = call(ph1, "CALL sp_rank_candidates(1, 1)")
    assert own[0]["quantity_here"] is not None and own[0]["total_quantity"] is None
    other = call(ph1, "CALL sp_rank_candidates(1, 2)")
    assert all(r["quantity_here"] is None for r in other)
    adm = direct("admin", 1, "admin")
    assert all(r["total_quantity"] is not None for r in call(adm, "CALL sp_rank_candidates(1, 2)"))


def test_candidates_require_authenticated_context():
    import mysql.connector, pytest
    c = direct("patient")  # no context
    with pytest.raises(mysql.connector.Error) as e:
        call(c, "CALL sp_equivalent_candidates(1)")
    assert e.value.errno == 45401


def _runnable_blocks():
    out = []
    for f in ("queries.sql", "advanced.sql"):
        for b in parse_blocks((ROOT / "database" / "sql" / f).read_text(encoding="utf-8")):
            if b["meta"].get("runnable", "yes") == "yes":
                out.append((f, b))
    return out


def test_query_library_runs_and_returns_documented_rows():
    m = migrator()
    got = {}
    for f, b in _runnable_blocks():
        sql = "\n".join(l for l in b["lines"] if not l.strip().startswith("--")).strip().rstrip(";")
        cur = m.cursor(dictionary=True)
        cur.execute(sql)
        got[b["name"]] = cur.fetchall()
        cur.close()
    assert {r["name"] for r in got["q_nested_no_stock"]} == {"Febrix 500 Tablet", "Metformin 500 mg Tablet (Brand B)"}
    assert len(got["q_join_availability"]) > 10
    corr = got["q_correlated_below_own_avg"]
    assert corr and all(r["quantity"] is not None for r in corr)
    assert {r["name"] for r in got["q_recursive_category_descendants"]} == {"Analgesics", "Antipyretic analgesics", "NSAIDs"}
    assert [r["pharmacy"] for r in got["q_group_having_low_items"]][0] == "Lakeside Pharmacy"
    assert {r["medicine"] for r in got["q_open_shortages_with_stock"]} == {"Febrix 500 Tablet", "Amoxyl 500 Capsule"}
    assert len(got["cte_category_tree"]) == 12 and got["cte_category_tree"][0]["depth"] == 0
    assert got["cte_pharmacy_stock_summary"][0]["risk_rank"] == 1
    assert list(got["fn_availability_band_demo"][0].values()) == ["Out", "Low", "Low", "In stock"]
