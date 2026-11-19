# Dependency review — 19 November 2026

Installed `next`, package manifest and lockfile were all **16.4.1**. Updated only Next.js and its matching `eslint-config-next` to **16.4.5** (same major/minor, smallest security patch identified). React remains 19.3.1.

Authoritative sources checked before updating:

- [Next.js 16.4.5 release](https://github.com/vercel/next.js/releases/tag/v16.4.5), 3 November 2026: seven moderate security fixes.
- [GHSA-mfr8-8qww-v76h](https://github.com/vercel/next.js/security/advisories/GHSA-mfr8-8qww-v76h) and [GHSA-vc7v-qv4w-wrv8](https://github.com/vercel/next.js/security/advisories/GHSA-vc7v-qv4w-wrv8): cache disclosure advisories returned by npm audit for the locked Next version.
- [GHSA-f3mh-rxg3-f5g2](https://github.com/vercel/next.js/security/advisories/GHSA-f3mh-rxg3-f5g2): HttpOnly cookie exposure on affected Edge routes, patched in 16.4.5.
- [GHSA-pc58-hwjq-p385](https://github.com/vercel/next.js/security/advisories/GHSA-pc58-hwjq-p385): response injection/disclosure under specified self-hosted proxy conditions, patched in 16.4.5.

These version ranges justify patching; they do not establish that every advisory's exploitation conditions occur in this app. The registry also offered 16.4.6, a later bug-fix patch; the selected 16.4.5 is the security release above.

Commands actually run:

```text
npm install --save-exact next@16.4.5 eslint-config-next@16.4.5 --fetch-retries=0 --fetch-timeout=30000 --no-audit
npm run lint
npm run typecheck
npm test
npm run build
npm audit --json --fetch-retries=0 --fetch-timeout=20000
```

Lint and TypeScript exited 0; frontend tests **14 passed, 0 failed, 0 skipped**; production build completed on Next 16.4.5. No browser or exploit test is implied by these checks.

Audit before patch: **12 affected packages (10 moderate, 2 critical)**. After patch: **10 (8 moderate, 2 critical)**, with no remaining `next` entry. Audit is **not passing**. Remaining affected development tooling: `@typescript-eslint/eslint-plugin`, `@typescript-eslint/parser`, `@typescript-eslint/type-utils`, `@typescript-eslint/typescript-estree`, `@typescript-eslint/utils`, `@vitest/mocker`, `minimatch`, `typescript-eslint` (moderate); `tinypool`, `vitest` (critical). These counts represent affected packages, not individual tests or necessarily distinct vulnerabilities. Initial install and later audit counts differed as registry advisory metadata changed; the saved pre/post JSON audits above are the comparison used here.

No broad `npm audit fix --force` was applied. The reported Vitest remediation requires a major-version upgrade, and npm suggested an ESLint config downgrade for part of the lint chain. Those changes are beyond the requested minimal Next patch and remain unresolved. Full evidence is in the delivered verification report and audit JSON files.
