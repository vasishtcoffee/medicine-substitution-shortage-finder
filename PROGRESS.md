# PROGRESS

## Status: P1–P7 implemented; gates passed except items listed under "Not executed here".

### Environment probe (2026-10-15, Windows 11)
Python 3.12.3 ✔ · Node 24 ✔ · MySQL **8.0.33** local service (root access given by the user) ✔ · git ✔ · **Docker ✘** · MongoDB was absent at first; a portable MongoDB 7.0.14 zip was later downloaded (user-approved) to `.tools/` and used.
Fields in the prompt left as `<fill>` (members, repo name) were not guessed; students' OS = Windows.

### Phases
| Phase | State | Evidence |
|---|---|---|
| P1 skeleton, compose, ER, coverage | done | `docker-compose.yml` written but **not run** (no Docker); ER diagram generated and checked |
| P2 schema, seed, roles | done | migrations load twice; 31 constraint/trigger tests pass |
| P3 SQL library | done | `database/sql/*`, outputs in `docs/sql_output`; concurrency test passes (5/5 reruns) |
| P4 FastAPI | done | 22 API tests, OpenAPI served, RBAC tests at API + DB level |
| P5 outbox + Mongo | done | mongomock (105 pass) and real MongoDB 7.0.14 (14/14 nosql pass); init_mongo idempotent |
| P6 Next.js | done | lint, tsc, build, vitest pass; browser spot-checked |
| P7 docs | done | `docs/*`, honest `TESTING.md` |

### Not executed here
* `docker compose up` (MySQL 8.4 + MongoDB 7).
* Full patient→pharmacist→sale flow clicked through in the browser (API-level equivalent passes).
* No Git repository/commits exist; Member A/B names are not filled in.

### Decisions (see docs/DESIGN.md §6)
Locking read in `sp_complete_order`; fourth role for auth lookups; context via `fn_ctx_*`; per-event triggers; local MySQL 8.0.33 with 8.4 in compose; `proxy.ts`.

### Next
1. Install Docker Desktop (or MongoDB Community), run the not-executed items above.
2. Fill `docs/TEAM_CONTRIBUTIONS.md`, create the repo, each member commits/PRs their slice.
3. Optionally export the ER diagram as an image.
