# Five-minute viva outline

This is a speaking outline, not evidence of completed demonstrations. Use [native commands](VIVA_COMMANDS.md), [viva setup](../viva/README.md) and [observed tests](TESTING.md).

- **0:00–0:45 — Problem and roles.** Patients search availability and request orders; assigned pharmacists review and complete them; admins maintain catalog/shortages/users. Matching checks exact composition/form/route/release, with pharmacist decision before substitution.
- **0:45–1:30 — Data ownership.** MySQL is authoritative for stock and transactions; MongoDB holds flexible feed/event documents. Point to the existing schema references. ER-diagram work is outside this polishing task.
- **1:30–2:30 — SQL.** Show existing DDL/constraints, isolated DML and cascade/rollback, then join/nested/correlated/recursive queries using the native scripts and original query library.
- **2:30–3:30 — Advanced objects.** Call availability function and candidate procedure, explain CTEs, and update an isolated inventory row to show trigger-created/resolved alerts. Workflow procedures write the outbox in the same transaction.
- **3:30–4:15 — MongoDB.** Show the actual inventory_feed and feed_events collections, validator/index definitions and isolated CRUD script. Mongosh execution remains unverified in this environment; pymongo integration tests ran on a real server.
- **4:15–5:00 — Permissions and evidence.** Open the limited MySQL connection and show direct inventory denial. Explain 401 cookie recovery vs authenticated 403. Present actual checks, audit failures and browser limitations without claiming full WCAG compliance or unsupported individual ownership.

Keep local credentials out of slides/screenshots. The application has six retained screens; demo tooling lives in viva/. See [contributions](TEAM_CONTRIBUTIONS.md) for the evidence gap.
