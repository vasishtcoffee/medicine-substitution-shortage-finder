# Medicine Substitution & Shortage Finder

DBMS Level 3 mini-project (PES University, Aug–Dec 2026): find in-stock medicines and **pharmacist-verified composition-matching** candidates when a medicine is short.

> **Safety notice.** This is an educational demonstration. Candidate matches are not medical advice or an authorization to substitute a medicine. A qualified pharmacist must verify the medicine and applicable prescription requirements before any substitution or sale. All data is synthetic; shortages are demo records, not live or official data.

## Stack

| Layer | Technology |
|---|---|
| Relational (authoritative) | MySQL 8 (InnoDB, utf8mb4), plain `.sql` migrations, **raw parameterised SQL**, roles/grants, stored procedures/functions/triggers |
| NoSQL | MongoDB (inventory feed + event log) via outbox sync |
| Backend | FastAPI (Python 3.11+), `mysql-connector-python` pools, `pymongo`, argon2, JWT in an httpOnly cookie |
| Frontend | Next.js 16 (App Router) + TypeScript; browser calls only `/api/*` (rewrite to FastAPI) |
| Vector DB | deliberately not used (see `docs/DESIGN.md` §3) |

## Prerequisites

Python 3.11+, Node 20+, and **either** Docker Desktop **or** a local MySQL 8.x and MongoDB 7. Repo docs: [`docs/`](docs/).

## Setup (Windows PowerShell; bash equivalents in the comments)

```powershell
# 1. environment
Copy-Item .env.example .env          # cp .env.example .env     -> then edit passwords (local demo values only)
pip install -r requirements.txt

# 2. databases (Docker)            -> if MySQL is already installed on 3306, set MYSQL_PORT=3307 in .env first
docker compose up -d                 # MySQL 8.4 + MongoDB 7 (healthchecks)
# ...or use your local MySQL/MongoDB and set MYSQL_ROOT_PASSWORD / MONGO_URI in .env

# 3. create DB, accounts, roles (needs MySQL root once), schema, demo data, Mongo collections
python scripts/bootstrap_db.py
python scripts/migrate.py            # idempotent; safe to re-run
python scripts/seed.py               # idempotent; resets demo stock to the seeded values
python scripts/init_mongo.py         # idempotent

# 4. run
python -m uvicorn app.main:app --app-dir backend --port 8000        # API + OpenAPI at http://localhost:8000/docs
cd frontend; npm install; npm run dev                                # UI at http://localhost:3000
```

Open <http://localhost:3000>. The API's background worker pushes stock changes to MongoDB every `SYNC_INTERVAL_SECONDS`; the Feed Lab has a **Run sync** button.

## Environment variables (`.env.example` lists all)

`MYSQL_HOST/PORT/DATABASE`, `MYSQL_ROOT_USER/PASSWORD` (bootstrap only), `MIGRATOR_*`, `DEFINER_USER`, `PATIENT_SVC_* / PHARMACIST_SVC_* / ADMIN_SVC_* / AUTH_SVC_*` (one DB account per role), `MONGO_URI`, `MONGO_DATABASE`, `JWT_SECRET`, `JWT_EXPIRE_MINUTES`, `COOKIE_SECURE`, `SYNC_INTERVAL_SECONDS`, `SYNC_MAX_ATTEMPTS`, `DEMO_*_PASSWORD`. `BACKEND_URL` (frontend, default `http://127.0.0.1:8000`).

## Demo logins (local only; passwords are the `DEMO_*_PASSWORD` values in `.env`)

| Role | Email |
|---|---|
| admin | `admin@medsub.demo` |
| pharmacist (City Care, pharmacy 1) | `pharmacist1@medsub.demo` |
| pharmacist (Green Cross, pharmacy 2) | `pharmacist2@medsub.demo` |
| patient | `patient1@medsub.demo`, `patient2@medsub.demo` |

Follow [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md).

## Tests

```powershell
python -m pytest tests -q               # SQL, security, API, NoSQL (uses throw-away DB medsub_test; mongomock unless MONGO_TEST_URI is set)
python scripts/check_schema_docs.py     # ER diagram vs live schema
python scripts/run_sql_demo.py database/sql/queries.sql
cd frontend; npm run lint; npm run typecheck; npm run build; npm test
```

Results and what was **not** run: [`docs/TESTING.md`](docs/TESTING.md). Rubric evidence: [`docs/RUBRIC_COVERAGE.md`](docs/RUBRIC_COVERAGE.md).

## Layout

```
database/migrations   V001, V002 (once) and R__* (routines, views, triggers, grants; re-applied)
database/seed         S001_seed.sql (+ scripts/seed.py for users/hashes)
database/sql          dml_demo.sql, queries.sql, advanced.sql  (named, labelled demos)
scripts               bootstrap_db, migrate, seed, init_mongo, run_sql_demo, check_schema_docs
backend/app           FastAPI (routers per domain), db.py, security.py, sync.py, mongo.py
frontend/src          Next.js app (7 screens), proxy.ts, lib/, components/
tests                 sql/, security/, api/, nosql/
docs                  DESIGN, SQL_REFERENCE, NOSQL, SECURITY_RBAC, API, TESTING, RUBRIC_COVERAGE, DEMO_SCRIPT, VIVA_GUIDE, TEAM_CONTRIBUTIONS
```

## Limitations

* MySQL has **no native row-level security**: row scoping uses restricted views, definer stored procedures and a trusted request context (credentials stay backend-only).
* No FEFO batch depletion (batch/expiry only on receipt ledger rows); stateless JWT (logout clears the cookie; no server-side revocation); keyword-only search (no semantic matching); MongoDB is eventually consistent; educational synthetic data only.
* Verified on MySQL 8.0.33; MySQL 8.4 (compose) was not available in the development environment; MongoDB was verified on a locally run 7.0.14 — see `docs/TESTING.md`.

## Viva / demo material

| What | Where |
|---|---|
| Hard-copy ER diagram, relational schema, strong/weak/associative entities, attribute types | `docs/ER_AND_SCHEMA_PRINT.html` (open, Ctrl+P, landscape); image `docs/ER_diagram.svg`; regenerate `python scripts/build_er_print.py` |
| All DDL and all DML in two files | `submission/01_DDL.sql`, `submission/02_DML.sql`; regenerate `python scripts/build_submission_sql.py` |
| 5-minute talk + CRUD checklist | `docs/VIVA_PRESENTATION.md` |
| `SHOW CREATE …`, live trigger/procedure demos, UI-CRUD-to-SQL verification | `docs/VIVA_COMMANDS.md` |
| Where every procedure/function/trigger/query is defined and used (file:line, API, screen) | `docs/CODE_MAP.md`; regenerate `python scripts/build_code_map.py` |
| One command to start MySQL check, MongoDB, API, UI | `powershell -ExecutionPolicy Bypass -File scripts\start_demo.ps1` (stop: `scripts\stop_demo.ps1`) |

## Frontend structure (matches the course template)

```
frontend/                      (the "MyApp")
├── app/
│   ├── page.tsx               home: redirects to /dashboard
│   ├── login, dashboard, search, orders, inventory, admin, feed-lab   (the 7 screens, each a page.tsx)
│   └── api/
│       └── hello/
│           └── route.ts       Next.js route handler: GET /api/hello (browser → Next → FastAPI → MySQL check)
├── lib/
│   ├── db.ts                  server-side connection pool (keep-alive pool to the backend that owns MySQL)
│   ├── mongo.ts               NoSQL connection helper (the template's redis.ts; this project uses MongoDB)
│   ├── api.ts, auth.tsx       browser-side API client and auth context
├── components/                shared UI (Header, SafetyNotice, Table, …)
├── proxy.ts                   redirects unauthenticated users to /login
├── .env.local                 BACKEND_URL (git-ignored; copy .env.local.example)
└── package.json               dependencies and commands (dev, build, lint, test)
```

| File | Responsibility |
|---|---|
| `app/page.tsx` etc. | Display the user interface |
| `app/api/hello/route.ts` | Handles the API request `GET /api/hello`; every other `/api/*` call is rewritten to FastAPI (`next.config.ts`) |
| `lib/db.ts` | Creates the connection pool to the backend that owns the MySQL pools |
| `lib/mongo.ts` | Connects to the MongoDB feed (through the backend) |
| `.env.local` | Stores local connection settings (`BACKEND_URL`) |
| `package.json` | Defines dependencies and commands |

MySQL and MongoDB are opened only by the FastAPI backend (`backend/app/db.py`, `mongo.py`): the database-level role design requires that Next.js never holds database credentials.
