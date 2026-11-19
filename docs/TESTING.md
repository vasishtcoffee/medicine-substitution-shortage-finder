# Testing — observed results, 19 November 2026

Windows environment, Python 3.12.6, Node 22.19.0, Next.js 16.4.5. Real MySQL **8.0.33** and MongoDB **8.2.1** executables were available; V: existed. All full-command server data/logs were created on V:. No Docker or MySQL 8.4 run is claimed.

## Final full-command run

Command, from repository root:

    .\.venv\Scripts\python.exe scripts/check_all.py

Run ID **2b158896a0aa**. Summary: work/checks_2b158896a0aa/summary.json; per-check logs, backend JUnit XML and frontend JSON are alongside it and included in delivered evidence.

| Individual test group | Passed | Failed | Skipped | Excluded from this invocation |
|---|---:|---:|---:|---|
| Real MySQL/MongoDB backend | 110 | 0 | 0 | 3 fault-injection stub tests, executed separately |
| Separate stub invocation | 3 | 0 | 0 | 110 already-run real tests (deselected to avoid duplicate counting) |
| Frontend jsdom/component/session/search | 17 | 0 | 0 | 0 |
| Unique individual tests executed | **130** | **0** | **0** | **0 left unrun within the collected suite** |

The three stub exclusions are named/explained in [TESTS_EXPLAINED.md](../tests/TESTS_EXPLAINED.md). They use _MongoDown and cannot prove a physical outage. The additional real outage test starts/stops/restarts only a server it created, then reads persisted MySQL stock/order/outbox and MongoDB feed/event results.

| Non-test check | Observed result |
|---|---|
| ESLint | Passed, exit 0 |
| TypeScript | Passed, exit 0 |
| Contrast script | Passed, 35/35 combinations |
| Production build | Passed, Next.js 16.4.5 |
| Real-service preflight | Passed; owned data on V: |
| Dependency audit | **Failed, exit 1:** 8 moderate and 2 critical affected development-tool packages |

These are **six non-test checks: five passed, one failed**. The full command correctly returned **exit 1**, despite all 130 tests passing. No service failure was silently replaced by a mock success. Admin native-button semantics/reduced-motion source corrections were also followed by lint, typecheck and production build; OS preference/browser behavior remains unverified.

The runner automatically creates a fresh server directory V:/Codex/medsub-checks/<run_id>, dynamic loopback ports, and per-invocation databases medsub_test_<run_id>_real and medsub_feed_test_<run_id>_real. The separate stub invocation uses medsub_test_<run_id>_stubs plus mongomock. The real-outage test owns a separate medsub_outage_test_<uuid> database. Fixtures reject pre-existing names and print their exact cleanup scope before dropping only databases created during that invocation. Owned processes are stopped in finally; folders/logs are retained for review.

## Verification commands and progression

| Actually run | Actual result |
|---|---|
| Initial npm ci in the C: clone | Failed ENOSPC; moved this task's clone to V: and reran successfully with cache/temp on V: |
| Phase 1 npm run lint; npm run typecheck; npm test | Lint/typecheck passed, 6 frontend tests passed |
| Phase 2 same frontend checks; python viva/prepare_sql.py medsub_viva_20261119 | Checks passed, 6 tests; renderer produced SQL without executing it |
| python -m pytest tests/api/test_sessions.py tests/security -q --junitxml=work/phase3.xml | 27 passed (5 new session + 22 security), 0 failed/skipped |
| Existing route-doc test invoked before change; public OpenAPI/document comparison | Existing test failed; documentation and schema agreed on all 55 operations. Internal lazy router enumeration omitted included routes. |
| python -m pytest tests/api/test_docs_match.py -q --junitxml=work/phase4.xml | 1 passed after public-schema correction |
| npm install --save-exact next@16.4.5 eslint-config-next@16.4.5; lint/typecheck/test/build/audit | Build/checks passed, 14 tests; audit failed with findings recorded in DEPENDENCY_REVIEW.md |
| First full check run a30aca62e2a6 | 126 passed, 1 failed, 0 skipped. My new rollback test wrongly expected direct UPDATE to enqueue outbox rows. Existing behavior was correct: procedures call sp_write_outbox. Corrected the test/native trigger-demo explanation without changing app logic. |
| Corrected Phase 6 full run e0e650cf3bab | 127 passed, 0 failed/skipped: 110 real + 3 stub + 14 frontend. Audit still failed. |
| Phase 7 new search tests | All 17 frontend tests passed. An initial TypeScript-only failure used an unsupported Testing Library option; removed it, reran typecheck/build successfully. |
| Final full check run 2b158896a0aa | 130 tests passed; check/audit status above |

Deprecation warnings were emitted by Starlette's current httpx TestClient integration and mysql-connector stored_results. They were not silently counted as failures or suppressed. Dependencies in requirements.txt remain ranges; this is the observed installed environment, not a universal reproducibility guarantee.

## Native tooling actually exercised

A new medsub_viva_polish_20261119 schema was confirmed absent before creation on the task-owned MySQL server at port 3311. Ran bootstrap, rendered existing migration SQL, mysql CLI SOURCE viva/mysql/01_ddl.sql, seed, and native 02/03/04 scripts. Reviewed DML brand update, cascade count 0, rollback count 0, category/function/ranking results and trigger alert counts **0→1→1→0**. The trigger demo initially described outbox writes incorrectly; corrected and reran it. A separate limited patient-service mysql connection could read availability; direct inventory SELECT and UPDATE each returned expected **1142** denial. Those expected SQL errors are security evidence, not failed unit tests.

Commands were executed via work/verify_viva.py and work/recheck_trigger.py, which invoke the actual mysql executable with source/execute arguments and local environment credentials (no secrets in output). Native stdout logs and results JSON are in delivered evidence. Mongo collection initialization also ran against the dedicated viva database.

**Mongosh unavailable:** no mongosh CLI script run is claimed. Pymongo real-server tests are independent evidence of MongoDB functionality.

## Browser and manual limits

See [browser verification](BROWSER_VERIFICATION.md) for exact actions, dimensions, reproduction steps and fixes. Patient login/dashboard/search/candidates were tested in real Chrome, including 320px table containment, pending login/loading and wrong-password feedback. Two stale task/candidate problems were reproduced and retested after fixing. Browser control stopped at native order confirmation because Windows URL confidence was insufficient. A database query found no order with the unique test note at the last read.

The full browser workflow, other-role browser layouts, complete keyboard/focus traversal, 200% zoom, screen reader, real devices, OS motion/contrast preference rendering and a full automated accessibility scan remain **unverified**. These are manual/blocked checks, not skipped pytest cases. Source/contrast checks do not establish full WCAG conformance. No “1 Insight” project component was found.

Existing docs/sql_output files are prior repository artifacts, not new execution evidence from this task. ER diagram generation/comparison was excluded and was not rerun. Contribution ownership/originality and external PR/review participation remain unverified.
