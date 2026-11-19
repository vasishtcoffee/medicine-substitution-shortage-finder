# Browser verification — 19 November 2026

**Partial.** Used a real Chrome tab at `http://127.0.0.1:3011`, production Next.js 16.4.5 and FastAPI at port 8011. Backend connections selected the dedicated V: MySQL/MongoDB servers (3311/27111) and `medsub_polish_demo_20261119`. No shared application server was stopped.

## Actually exercised

- Desktop login at a 1536px viewport; empty submission focused the required email field, with a visible focus outline. A wrong password showed “Invalid email or password”. Observed disabled “Signing in…” while the request was pending, then signed in as seeded patient 1.
- Patient dashboard: role-filtered navigation, medicine-search entry point, shortage KPI and semantic order-status breakdown. Inspected real rendered screenshots of login and dashboard.
- Search: entered Paracetamol, selected City Care Pharmacy, inspected real seeded medicine/brand/composition and availability bands; opened candidates for medicine 1, read eligibility and pending verification status, expanded six rejected near-matches. Patient exact quantities remained `hidden` in the candidate table.
- Set viewport to **320 × 800**. DOM measurement: `innerWidth=320`, document/body scroll widths **305px** (vertical scrollbar consumes space), candidate-table container **238px** with **808px** scrollable content. No page-wide horizontal overflow in that tested search state; inspected a mobile screenshot.
- Set viewport to **1280 × 900**. Opened the order form and filled quantity 115 plus the note “Browser verification 2026-11-19”. These were isolated synthetic test values, not real medical/patient data.

## Problems reproduced and fixed

| Problem | Reproduction before fix | Fix and verification |
|---|---|---|
| Previous order task survived an unrelated search | Search Paracetamol; open order for medicine 1; search `no-such-medicine-xyz`. “No medicines match” and the old order form appeared together. | A new search clears results, candidates and selected order. Reloaded the production app and repeated the steps: old order heading count **0**. Added a component regression test. |
| Candidate availability described the previous pharmacy | Open medicine 1 candidates at City Care: Pyrelief is Low. Select Green Cross: old table still said Low under “At chosen pharmacy”, although seeded Green Cross stock is In stock. | Pharmacy changes clear candidate state and invalidate pending responses. Reloaded and repeated: old candidate heading count **0**. Added a pending-response regression test. |
| Older responses could restore invalidated results | The above stale-state defects exposed unguarded asynchronous setters in search/candidate handlers. | Added request-generation checks. A component test resolves old/new searches out of order and verifies the latest result remains. This race was verified in jsdom, not reproduced with network throttling in Chrome. |

No endpoint, eligibility or ordering business rule changed. Request paths/payloads and DB RBAC are unchanged.

Source inspection also found that Admin declared ARIA tabs without tab panels or a tab keyboard implementation. The section switcher now uses a labeled group of native buttons with pressed state. It preserves the same sections/actions and native Tab/Enter/Space behavior; this source correction was not manually retested in Chrome after browser control stopped.

The existing Admin edit action also forced smooth scrolling. It now selects automatic scrolling when prefers-reduced-motion is enabled; this condition is source/typechecked, with OS preference rendering unverified.

## Browser stop and exact limit

Clicking “Request order” opened a native confirmation. The browser controller timed out; the dialog inspection returned `type=confirm`, but accepting it did not produce a verified outcome. A direct MySQL read found **zero** orders with the unique test note. Recovery attempts then ended with: **Computer Use could not determine the current browser URL on Windows confidently enough to enforce policy.** No further browser input was sent after that stop.

Therefore the browser patient-order → pharmacist-review/approval/completion → stock → alert → MongoDB workflow is **not completed or claimed**. The separately reported real integration suite does verify persisted workflow/outage effects, but it is not a substitute for this unfinished browser exercise. The intended 120 → 5 stock change was not observed or claimed.

The viewport override could not be reset after browser control stopped. The test tab may retain its confirmation/1280 × 900 override; dismiss/close it manually. The final database read confirmed **0** orders with the test note. Task-owned API/UI/database servers were then stopped and the named demo/viva databases removed; create a fresh dedicated environment before another demonstration. No task shutdown targeted a shared service; V: log/data folders remain for review. Final Windows inventory showed MySQL80 running and MongoDB service stopped. The cause of that service-state change was not established; the task's Mongo shutdown verified its own separate V: data directory first.

## Implemented, automated and manual are different

- Implemented/source-inspected: skip link first, semantic landmarks, active nav `aria-current`, visible offset focus, human-readable symbols/statuses, native controls, scrollable table regions, reduced-motion/contrast media queries.
- Automated/source calculations: 35 CSS-token contrast combinations passed; frontend component/session/search tests run in jsdom. DOM width measurements above were read from real Chrome. No axe scan was run.
- Manual browser actions/screenshots: only the states enumerated above. Seeing a focus outline after validation is not a complete keyboard navigation audit.
- **Unverified:** actual 200% browser zoom; full keyboard traversal/focus order; pharmacist/admin/inventory layouts in a browser; 320px on every screen; complete browser session-recovery/logout scenarios; full end-to-end browser workflow; screen reader; real mobile devices; reduced-motion/high-contrast OS preference rendering. Do not infer full WCAG conformance.

No floating “1 Insight” component exists in the inspected frontend source, and none appeared in the tested production views. No project component was invented to replace an external overlay.
