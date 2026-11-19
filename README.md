# Medicine Substitution & Shortage Finder

Academic DBMS project: search medicines and pharmacy availability, inspect exact composition-matching candidates, request an order, and let an assigned pharmacist review and complete it. MySQL owns stock/orders; MongoDB holds the eventually consistent feed/events.

This is an academic test project not intended for clinical use.

## Teammate checkout

The updated project is on branch **polish/viva-eight-phases**. Start with [teammate handoff](docs/TEAMMATE_HANDOFF.md) for checkout commands, setup, verification results and remaining work.

## Stack

MySQL 8/InnoDB, raw parameterized SQL, constraints/views/procedures/functions/triggers and database roles; MongoDB validators/indexes with outbox sync; FastAPI/Python 3.11+; Next.js 16.4.5 App Router, React 19.3.1 and TypeScript. The UI stays dark navy with coral primary actions.

## Setup and reliable startup (Windows PowerShell)

Use dedicated local databases/accounts. From the repository root:

    py -3.12 -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    Copy-Item .env.example .env

Edit .env for actual local server ports, database/account names and passwords. Start MySQL/MongoDB yourself, or use docker compose up -d if Docker is installed; choose free ports.

Only for a new dedicated app database:

    .\.venv\Scripts\python.exe scripts\bootstrap_db.py
    .\.venv\Scripts\python.exe scripts\migrate.py
    .\.venv\Scripts\python.exe scripts\seed.py
    .\.venv\Scripts\python.exe scripts\init_mongo.py

**Mutation scope:** bootstrap creates the selected schema, configures/updates the named server accounts/roles and attempts to set log_bin_trust_function_creators. Migrations create/replace objects in that schema. Seed resets its demo stock and inserts synthetic fixtures. Mongo initialization creates/updates the selected collections, validators and indexes. Name/review the target first. Setup/reset is separate from routine startup.

Terminal 1, repository root:

    .\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000

Terminal 2:

    cd frontend
    npm ci
    $env:BACKEND_URL='http://127.0.0.1:8000'
    npm run dev

UI: [localhost:3000](http://localhost:3000). Backend tools: [localhost:8000/docs](http://localhost:8000/docs); POST /auth/login before protected requests. Browser calls use same-origin /api rewrites. Next never holds SQL credentials. Use explicit virtual-environment Python: the Windows Store python alias may not run Python.

For production-mode local testing, set BACKEND_URL **before building**, then npm run build and npm run start -- --hostname 127.0.0.1. Override ports with --port. The observed production browser run used API 8011 and UI 3011; startup and build completed with those overrides.

Stop foreground servers with Ctrl+C. Legacy start_demo.ps1 bootstraps/seeds automatically and stop_demo.ps1 stops port owners without ownership checks. They were not used here; prefer the explicit commands above and do not run those legacy scripts against shared services.

## Environment

Copy .env.example; keep .env and frontend/.env.local untracked.

| Variables | Purpose |
|---|---|
| MYSQL_HOST/PORT/DATABASE | Authoritative app database |
| MYSQL_ROOT_USER/PASSWORD | Bootstrap only |
| MIGRATOR_USER/PASSWORD, DEFINER_USER, APP_ACCOUNT_HOST | Schema account and locked routine definer |
| PATIENT_SVC_*, PHARMACIST_SVC_*, ADMIN_SVC_*, AUTH_SVC_* | Separate limited runtime SQL accounts |
| MONGO_URI, MONGO_DATABASE | Feed/event database |
| JWT_SECRET, JWT_EXPIRE_MINUTES, COOKIE_SECURE | Signed httpOnly cookie; long secret and HTTPS/secure cookies outside local HTTP |
| SYNC_INTERVAL_SECONDS, SYNC_MAX_ATTEMPTS, SYNC_BACKGROUND | Outbox processing; background defaults on |
| DEMO_ADMIN_PASSWORD, DEMO_PHARMACIST_PASSWORD, DEMO_PATIENT_PASSWORD | Seed login passwords |
| BACKEND_URL (frontend) | Backend origin; set before production build |

## Synthetic demo logins

Passwords are your DEMO_*_PASSWORD values. The change-me-* values in .env.example are placeholders, not claims about an existing installation.

| Role | Email | Pharmacy |
|---|---|---|
| Admin | admin@medsub.demo | All |
| Pharmacist | pharmacist1@medsub.demo | City Care (1) |
| Pharmacist | pharmacist2@medsub.demo | Green Cross (2) |
| Patient | patient1@medsub.demo, patient2@medsub.demo | Selected per request |

## Verification

    .\.venv\Scripts\python.exe scripts\check_all.py

This command requires V: and real MySQL/MongoDB server executables; set MYSQLD_EXE/MONGOD_EXE for other binary locations. It starts its own servers on V:, creates unique test databases, refuses pre-existing names, prints exact cleanup scope and stops only owned processes. Missing services produce blocked/nonzero results. Individual test counts and exclusions are separate from lint/typecheck/contrast/build/audit checks. Logs/JSON are under work/checks_<run>/.

Final full command: **130 passed, 0 failed, 0 skipped** (110 real backend + 3 separate fault-injection stubs + 17 frontend). The three stubs were excluded from the real-server invocation and then executed separately. See [current results](docs/TESTING.md). Audit remains failing: 8 moderate and 2 critical affected development-tool packages; Next no longer appears in that audit.

[Test explanations](tests/TESTS_EXPLAINED.md), [dependency review](docs/DEPENDENCY_REVIEW.md), [browser evidence/limits](docs/BROWSER_VERIFICATION.md). Browser control stopped at a native confirmation because the current Windows URL could not be determined confidently. Full browser workflow, 200% zoom, keyboard traversal, screen readers and real devices remain unverified. API/DB tests are separate evidence.

## Viva and structure

Use [native database viva scripts](viva/README.md) and [short demonstration sequence](docs/VIVA_COMMANDS.md). Feed Lab and the in-app SQL Demo are removed. Admin feed/event APIs and sync recovery remain operational. Native mysql scripts were exercised; mongosh was unavailable, so its script remains unexecuted.

| Location | Purpose |
|---|---|
| database/migrations, database/seed, database/sql | Existing SQL schema, fixtures and query library |
| backend/app | FastAPI, role-specific pools, MongoDB/outbox |
| frontend/app | Login, dashboard, search, orders, inventory, admin |
| frontend/components | Shared shell, feedback, statuses and tables |
| viva/mysql, viva/mongodb | Native DDL/DML/queries/routines/triggers/denials and isolated Mongo CRUD |
| tests | SQL, security, API, MongoDB and plain-language explanations |
| scripts/check_all.py | Full check command with owned real services on V: |

## Limits

MySQL has no native row-level security: grants, definer views/procedures and trusted backend request context implement scoping. JWT logout clears a cookie without token revocation. Search is keyword-based; no FEFO depletion; MongoDB is eventually consistent. Exercised MySQL 8.0.33 and MongoDB 8.2.1; Docker/MySQL 8.4 and full WCAG conformance are unverified. [Rubric status](docs/RUBRIC_COVERAGE.md) excludes ER-diagram work and awards no marks. [Contributions](docs/TEAM_CONTRIBUTIONS.md) require evidence beyond git author metadata.
