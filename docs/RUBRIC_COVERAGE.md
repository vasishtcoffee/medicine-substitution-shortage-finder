# PDF rubric coverage — evidence, not awarded marks

Visually inspected the accessible one-page PES University DBMS Aug–Dec 2026 Level 3 PDF, “DBMS Level 3 (1).pdf”, from the existing local browser tab. Its main table totals 50 marks; **ER diagram (2 marks) is excluded from this task**. The following maps its remaining components. No score, full execution or individual contribution is inferred from code existence.

| PDF component | Marks | Implementation/demo | Observed evidence and limitations |
|---|---:|---|---|
| Relational schema: keys/relationships/constraints | 3 | V001/V002 migrations; viva/mysql/01_ddl.sql | Real MySQL schema/constraint tests and native DDL ran. ER artifacts were not edited or revalidated. |
| SQL DDL with constraints | 4 | Existing migrations, rendered native 01 DDL | Real migrations/constraints tested; mysql CLI DDL executed on a new viva schema. MySQL 8.0.33; 8.4 unverified. |
| NoSQL database creation | 4 | app/mongo.py ensure_collections; init_mongo.py | Real MongoDB 8.2.1 validator/index/idempotency tests passed. |
| Technology justification | 1 | DESIGN.md; VIVA_GUIDE.md | Documented rationale; viva evaluation is for the examiner. |
| DML operations | 4 | Catalog API; viva/mysql/02_dml_cascade_rollback.sql | mysql CLI insert/select/update/delete, cascade and rollback executed; API CRUD tested. |
| Nested/correlated/recursive/join queries | 4 | database/sql/queries.sql; native 03 queries | Existing result assertions passed on MySQL; native joins/CTEs executed. |
| Procedure/function/trigger/CTE | 6 | R__10/R__30/R__40/R__50; native 03/04 | Real boundary/ranking/trigger/sale/rollback/concurrency tests passed; native function/procedure/trigger/CTE output reviewed. |
| NoSQL read/update/delete | 7 | routers/feed.py, sync.py; viva/mongodb/01_crud.js | Real pymongo/API CRUD and outage/recovery passed. Mongosh executable absent: native JS script not run. No Feed Lab UI. |
| Next.js interface | 3 | Six retained screens, shared shell | Lint/typecheck/build and 17 frontend tests passed. Chrome patient views/search tested; full role workflow, 200% zoom, keyboard audit and other role layouts remain incomplete after browser policy stop. |
| Backend/API and database integration | 2 | FastAPI, role pools, outbox; 55 documented OpenAPI operations | Real integration tests passed. Public schema/documented exact methods/paths matched. |
| Frontend auth + minimum two database RBAC roles | 4 | Three app roles; four SQL service roles, grants/definer objects; native 05 | Login/logout, invalid/expired JWT, API 401/403 and direct SQL denials tested. Full browser session scenarios unverified. |
| Documentation, Git/GitHub | 2 | README, tests guide, viva, phased local branch | Separate phase commits; no push/merge/deploy. External PR/review participation was not verified. |
| Originality, individual contribution, modification/viva | 4 | TEAM_CONTRIBUTIONS.md; native sequence | **Unverified individual ownership/originality and live viva performance.** User confirmation needed beyond git metadata. |

See [actual command results](TESTING.md), [browser evidence](BROWSER_VERIFICATION.md), [test explanations](../tests/TESTS_EXPLAINED.md) and [native execution order](../viva/README.md). Full WCAG conformance is not claimed.
