# Demonstration sequence — expected behavior

Start with the explicit [README commands](../README.md) and dedicated synthetic demo databases. Passwords are the local DEMO_*_PASSWORD values; use the seeded patient, assigned pharmacist and admin emails documented there. These are **future demonstration steps**, not a claim the whole sequence ran in Chrome. See [actual browser results](BROWSER_VERIFICATION.md).

1. Open the UI; try a wrong password, then sign in as patient1. Dashboard shows only existing patient data and valid role navigation.
2. Search Paracetamol; choose a pharmacy. Inspect availability bands, composition, candidates, verification status and rejected near-matches. Changing pharmacy clears old candidate results; run the candidate action again.
3. In the dedicated demo database, request an order for a stocked medicine. Confirm the explicit quantity/medicine. Check its requested status under Orders.
4. Log out and sign in as the assigned pharmacist. Start review, record a medicine decision, approve the order, then confirm completion. Read stock and ledger effects in Inventory.
5. Verify the persisted order, stock, inventory_movements, low_stock_alerts and sync_outbox in the actual selected MySQL database. Read matching inventory_feed/feed_events documents in MongoDB. A UI success message alone is insufficient.
6. As admin, demonstrate Catalog, Pharmacies, Shortages and Users. Use synthetic, isolated records and review confirmations before mutations.
7. Use [native viva commands](VIVA_COMMANDS.md) for SQL and MongoDB demonstrations. Feed Lab and in-app SQL Demo do not exist.
8. Run python scripts/check_all.py for real SQL/Mongo tests, including an owned-server outage/recovery test. Never stop a shared MongoDB service. This command currently returns nonzero for unresolved dependency-audit findings.

Before mutation, name the dedicated database/records affected. The browser test in this task planned a 115-unit order for medicine 1 at pharmacy 1, but browser control stopped at confirmation and the database read found no order with its unique test note. The intended 120→5 stock change was not observed. Do not repeat it blindly.
