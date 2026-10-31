# Demo script (about 12 minutes)

Local demo accounts (seeded from `.env`, **local use only**): `admin@medsub.demo`, `pharmacist1@medsub.demo` (City Care, pharmacy 1), `pharmacist2@medsub.demo` (Green Cross, pharmacy 2), `patient1@medsub.demo`, `patient2@medsub.demo`. Passwords: `DEMO_ADMIN_PASSWORD`, `DEMO_PHARMACIST_PASSWORD`, `DEMO_PATIENT_PASSWORD` in `.env`.
Start: MySQL + MongoDB up, `python scripts/bootstrap_db.py && python scripts/migrate.py && python scripts/seed.py && python scripts/init_mongo.py`, then API (port 8000) and web (port 3000) — see README.

| # | Account | Step | Expected result |
|---|---|---|---|
| 1 | — | Open `http://localhost:3000` | Redirect to Login; safety notice visible |
| 2 | patient1 | Sign in with a wrong password | Generic "Invalid email or password"; same text for an unknown e-mail |
| 3 | patient1 | Sign in correctly | Dashboard; navigation shows only Dashboard, Search, Orders |
| 4 | patient1 | Search "paracetamol"; choose pharmacy *Green Cross* | List with **bands only** (In stock / Low / Out), "Open shortage" pill on Febrix |
| 5 | patient1 | "Find verified-composition candidates" on *Paracetamol 500 mg Tablet* | Eligible: Pyrelief (ranked 1, stocked at Green Cross), Febrix. Rejected with reasons: 650 mg (strength), caffeine combo (ingredient set), syrup (strength/basis/form), ER (release), Parasprin look-alike (ingredient set), discontinued. Status "pending pharmacist verification"; units shown as "hidden" |
| 6 | patient1 | "Order…" on *Pyrelief 500 Tablet*, pharmacy *City Care*, qty 3, confirm | "Order #N requested" |
| 7 | patient1 | Orders | Order #N `REQUESTED` |
| 8 | pharmacist1 | Orders → order #N → Start review | `UNDER_REVIEW`; pharmacist2 does **not** see this order (another pharmacy) |
| 9 | pharmacist1 | Show candidates → approve substitute / "Dispense as requested", then Approve order | `APPROVED`; decision recorded (`substitution_reviews`) |
| 10 | pharmacist1 | Complete sale (confirm) | `COMPLETED`; Inventory shows quantity down by 3, a SALE row in the ledger; Pyrelief at City Care already had an open low-stock alert (one, no duplicate) |
| 11 | pharmacist1 | Inventory → Receive 100 × Pyrelief | Quantity up; the open alert disappears (trigger resolved it) |
| 12 | pharmacist1 | Try receiving for pharmacy 2 (API: `POST /inventory/receive` with `pharmacy_id=2`) | 403 from the stored procedure |
| 13 | admin | Dashboard / Admin → SQL Demo → run `q_nested_no_stock`, `q_correlated_below_own_avg`, `cte_category_tree` | Febrix + Metformin Brand B; per-pharmacy rows; 12-row tree with paths |
| 14 | admin | Admin → Users: create a pharmacist for Lakeside; Catalog: add a medicine | Rows appear; duplicate e-mail → 409 message |
| 15 | admin | Feed Lab → Run sync | Outbox `DONE`; `inventory_feed` shows `ph1:med2` with the new quantity; `feed_events` has `sale` and `receipt` events |
| 16 | admin | Feed Lab → Edit a feed doc (notes/metadata); try quantity via API → 422 | Only metadata/notes/flags change |
| 17 | admin | Feed Lab → Delete `ph2:med2`, then "Resync all from MySQL" | Document gone, MySQL stock unchanged; resync recreates it |
| 18 | admin | Stop MongoDB, complete another sale as pharmacist1, look at Feed Lab | Sale succeeded; outbox rows `PENDING`/`FAILED`; start MongoDB, Run sync → drained |
| 19 | — | `python -m pytest tests -q` and `python scripts/check_schema_docs.py` | All pass; ER diagram matches schema |
