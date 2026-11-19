# Teammate handoff

Use branch **polish/viva-eight-phases** for the updated project. It contains eight separate polishing phase commits plus this handoff documentation. The pull request targets main; this handoff does not merge or deploy the changes.

## Get the updated code

Fresh checkout:

```bash
git clone --branch polish/viva-eight-phases https://github.com/vasishtcoffee/medicine-substitution-shortage-finder.git
cd medicine-substitution-shortage-finder
git switch -c feat/teammate-task
```

Existing clean checkout, if the shared branch is not yet local:

```bash
git fetch origin
git switch --track origin/polish/viva-eight-phases
git switch -c feat/teammate-task
```

If it is already local, use `git switch polish/viva-eight-phases` and `git pull --ff-only` before creating your own feature branch. Keep personal work on a separate branch. Until the parent pull request is merged, base follow-up work on this shared branch so it includes the current UI and fixes.

## Run it

Follow [README setup](../README.md#setup-and-reliable-startup-windows-powershell). Create your own local virtual environment, install requirements and run `npm ci` in frontend. Copy `.env.example` to `.env` and configure your local database credentials/ports. The synthetic login emails are in README; passwords come from your local DEMO_*_PASSWORD values.

Use dedicated app databases. Bootstrap configures server accounts/roles, and seed resets stock in the selected database; review the README mutation scope first. Routine startup uses the explicit API/frontend commands and does not require reseeding. This checkout does not include another developer's `.env`, database files, virtual environment or node_modules.

## What changed

- Dark navy/coral UI, responsive navigation, dashboard hierarchy, medicine/candidate presentation and accessible shared controls.
- Removed Feed Lab, SQL Demo and visible disclaimer boxes; native viva tools are under [viva/](../viva/README.md). Operational feed/sync APIs remain.
- Invalid/expired-session recovery preserves authenticated 403 responses and database RBAC.
- Exact public OpenAPI/documentation comparison; Next.js patched to 16.4.5.
- Isolated real MySQL/MongoDB testing, physical Mongo outage/recovery coverage and test explanations.

## Verification and remaining work

The recorded full command `python scripts/check_all.py` ran **130 individual tests: 110 real backend, 3 separate fault-injection stubs, 17 frontend; 0 failed/skipped**. It requires V: and MySQL/MongoDB server binaries and uses its own disposable servers/databases. It reports blocked services explicitly. See [actual results](TESTING.md) and [test explanations](../tests/TESTS_EXPLAINED.md).

The command returned **exit 1** because dependency audit still reported **8 moderate and 2 critical affected development-tool packages**. See [dependency review](DEPENDENCY_REVIEW.md); do not describe all checks as green.

Browser verification is **partial**. Patient login/dashboard/search/candidates and two stale-state fixes were exercised; browser control stopped at an order confirmation. Full patient-to-pharmacist browser workflow, actual 200% zoom, complete keyboard traversal, screen-reader/device checks and other-role browser layouts remain unverified. See [browser record](BROWSER_VERIFICATION.md) and [accessibility checklist](ACCESSIBILITY.md).

Native mysql scripts ran; mongosh was unavailable. Individual contributions/originality require confirmation beyond git author metadata; see [contributions](TEAM_CONTRIBUTIONS.md). ER diagram work was excluded from this polish.

The earlier local report describes its cleanup at that time. A later UI-preview request recreated a dedicated synthetic demo database and started local preview servers; this is workstation-local state, not something supplied by GitHub. Use your own setup rather than relying on another machine's running services.
