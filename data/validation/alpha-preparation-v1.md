# M8A · Cloudflare alpha deployment preparation

Checked 2026-10-27. **Local preparation only:** no live Cloudflare account/resource
inspection, provisioning, import, Access configuration or deployment was executed.
CLI help, local Wrangler and dry-run bundling were used. No commit or M8B work.
See [the deployment runbook and exact reviewed command sequence](../../docs/ALPHA_DEPLOYMENT.md)
and [machine-readable local measurements/estimates](alpha-preparation-v1.json).

## Proposed arrangement and changed files

One Workers Static Assets app, `draftory-alpha`, serves HTTPS HTML, hashed
JS/CSS/WASM and the existing versioned catalog/pilot artifacts. `/api` and
`/api/*` use the existing bounded read-only API and a separate alpha D1 binding.
Matched static assets do not invoke application code. Simulation stays entirely
inside the browser's Rust/WASM Web Worker.

Workers Static Assets reuses this repository's Worker/D1 implementation without
a Pages Functions adapter or another project. Pages remains viable, but adds no
benefit here. See [Cloudflare's routing documentation](https://developers.cloudflare.com/workers/static-assets/routing/worker-script/)
and [Pages/Workers differences](https://developers.cloudflare.com/workers/static-assets/migration-guides/migrate-from-pages/).

- `services/api/wrangler.alpha.json`: separate unrouted alpha template, sentinel
  account/database IDs, static binding, API-first paths, explicit preview disablement
  and native Workers observability. The existing local API configuration is unchanged.
- `services/api/src/alpha.ts`: thin API/static boundary, alpha no-index headers
  and non-cacheable missing-asset responses. No data queries/models were rewritten.
- `scripts/prepare-alpha.mjs`: local build/data/version audit and optional ignored
  hosted-config rendering. Rejects missing/placeholder/conflicting target IDs,
  changed SQL/catalog/pilot and unexpected public files; records migration and
  asset SHA-256 values. It never executes a cloud operation.
- Alpha Playwright configs/tests plus the reused local fixture/import runner:
  real production output and D1 on one origin, no Vite proxy. CI adds local alpha
  checks only, with no deployment secrets or provisioning step.
- Client recovery messages now apply to hosted network/Access-session failures.
  A failed season can explicitly reload the newest app, with a warning that this
  clears the ephemeral draft. Static `noindex` is indexing advice, not authentication.
- README, architecture and browser-validation links, this report and the new
  runbook; generated dry-run output remains under ignored build directories.

No historical records, prices, draft rules, simulation mechanics, RNG, native/WASM
goldens or D1 migrations were changed. No dependency or authentication system was added.

## Cache finding and fix

The real local Static Assets runtime returned a **404 with
`public, max-age=31536000, immutable`** for a nonexistent `/assets/*.wasm`,
because `_headers` matches request paths. Returning its normal `404-page` asset
also bypassed the application handler, so a response-only wrapper was insufficient.

The alpha config now uses `not_found_handling: none`: valid assets still serve
directly, while misses reach the Worker. It serves the existing 404 HTML with
status 404 and `no-store`. Successful hashed assets remain immutable; HTML
revalidates. Tests require the error status, no-store and a usable return link,
along with WASM/JS MIME and the existing CSP. The established redeployment test
still checks changed hashes, a running worker surviving updates and stale-tab reload.
The new gameplay case checks reload recovery from a missing WASM asset.

## Measured locally versus estimated cloud usage

The unchanged 2024 publication was applied twice to real SQLite with the existing
ordered migration and foreign-key checks:

| Local measurement                                |                       Result |
| ------------------------------------------------ | ---------------------------: |
| Published player profiles                        |                          526 |
| SQL bytes                                        |                    6,839,740 |
| Initial base rows inserted                       |                       11,098 |
| Row changes on exact repeat                      |                            0 |
| Foreign-key violations                           |                            0 |
| SQLite allocated pages × page size               |              4,722,688 bytes |
| Static files audited, including HTML and headers |                           12 |
| Total static bytes                               |                      998,358 |
| Alpha Worker dry-run bundle                      | About 16.6 KiB, 4.8 KiB gzip |

The SQL SHA-256 matches the frontend catalog's pinned source publication. Only
the selected 2024 SQL is imported; no raw Lahman/Retrosheet release is an asset.
Existing tests verify completion-marker visibility, immutable conflicts and
repeat imports. The marker is written last, so partial publications remain hidden.

**Planning example, not hosted measurements:** 25 allowlisted testers, each
drafting 10 new teams/day, over 30 days. Budget 30 API calls and 2,000 D1 rows
read per draft; these are estimates, not hard bounds. Repeat season simulations
with an already loaded lineup need no new API data.

| Resource            | Estimated use                                                       | Current Free allowance                      |
| ------------------- | ------------------------------------------------------------------- | ------------------------------------------- |
| Worker invocations  | 7,500/day; 225,000/month                                            | 100,000/day                                 |
| D1 rows read        | 500,000/day; 15 million/month                                       | 5 million/day                               |
| Gameplay D1 writes  | 0                                                                   | 100,000/day                                 |
| Initial data import | Plan for 50,000 writes including index overhead                     | Same daily write allowance                  |
| D1 storage          | Reserve 10 MB; local measurement 4.72 MB                            | 500 MB/database; 5 GB/account               |
| Static delivery     | Approximately 1 MB of application/artifact bytes before compression | Static requests/storage currently unmetered |
| Access seats        | 25 planned                                                          | Free plan intended for teams under 50 users |

Local table-plus-index insertion counting suggests about **26,129** initial
insertions. That is an approximation, not D1 billable-write telemetry; the larger
planning budget leaves headroom. Migration/service metadata and other account
workloads still count. The local repeat's zero base-row changes do not prove a
hosted retry has no read cost. Actual D1 storage and billing must be measured.

The expected cost under these assumptions and selected **Free** plans is **$0/month**.
No domain purchase or paid monitoring is required. Quotas are shared across the
account; abuse, reloads, retries, other apps and schema/query growth can exceed
these assumptions. Free Worker CPU is limited to **10 ms/invocation** and has
not been validated remotely. Browser simulation time is not Worker CPU time.
Access does not make quota monitoring unnecessary.

Sources checked 2026-10-27: [static billing](https://developers.cloudflare.com/workers/static-assets/billing-and-limitations/),
[Workers limits](https://developers.cloudflare.com/workers/platform/limits/),
[D1 pricing](https://developers.cloudflare.com/d1/platform/pricing/),
[D1 limits](https://developers.cloudflare.com/d1/platform/limits/),
[Access Free plan](https://www.cloudflare.com/sase/products/access/).
Workers Logs currently includes 200,000 logs/day and three-day Free retention;
its documentation announces a pricing transition on December 1, 2026. Recheck
[logging limits](https://developers.cloudflare.com/workers/observability/logs/workers-logs/)
before deployment. The runbook identifies Worker CPU/request/error, D1 row/storage
and static delivery metrics; no user-level analytics or external monitor was added.

## Access, credentials and remaining hosted gates

The actual account, Free plan, Workers subdomain, database UUID and target ownership
are not selected or verified. The committed template is deliberately unusable for
a real account. Config rendering was exercised locally with clearly fictional
IDs and dry-run bundled, then retained only as an ignored `.example.json` file.
The normal `wrangler.hosted.json` does not exist until real target preparation.

After approval: verify account/membership and target names, create only the alpha
D1, render/review its configuration, migrate/import, deploy with no public route,
configure Access for this Worker, then separately enable its Workers URL.
OAuth or an account-scoped Workers/D1 admin token is needed for deployment;
Access administration needs its corresponding permissions. No application secret
or credential belongs in the frontend, WASM, Git or current CI workflow.

[Worker-level Access](https://developers.cloudflare.com/workers/configuration/cloudflare-access/)
can protect the app and its static assets without custom account code. Use a
specific email allowlist, not obscurity or a path-only policy; keep alternate
preview/version URLs disabled. Test signed-out/denied identities on HTML,
JS/WASM, API GET and POST, as well as session expiry and reauthentication.
Already downloaded data/local exports cannot be revoked by an Access policy.

Remaining hosted-only tests: actual HTTPS/TLS, Access policy coverage, deployed
cache/MIME/CSP behavior across a redeploy, CPU under the Free cap, D1 read/write
telemetry and storage, quota behavior, and approved rollback. Worker versions do
not roll back D1 or Access state. Preserve immutable data and review destructive
recovery separately; no delete/restore operation is automated.

Physical Android/iPhone and screen-reader testing have not occurred. Desktop
mobile emulation checks viewport/touch behavior on this computer, not phone CPU,
memory, radio or shipping Safari. The runbook supplies a short real-phone checklist.

## Local validation

Completed locally on Windows:

| Check                                                                           | Result                                                                          |
| ------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| `npm run typecheck`, `npm run lint`, `npm run format:check`, `git diff --check` | Passed                                                                          |
| `npm run build`, `npm run check:api`, `npm run check:alpha`                     | Production build and local dry-run bundles passed                               |
| `npm run test:alpha:tools`                                                      | 6 passed; target guards, stale catalog/pilot rejection and build audit          |
| `npm run test:data-client`                                                      | 27 passed                                                                       |
| `npm run test:api`                                                              | 8 passed                                                                        |
| `npm run test:browser`, `npm run test:edge`                                     | Passed, including unchanged native/WASM goldens and deployment regression       |
| `npm run test:integration`                                                      | 30 passed; 3 optional full-publication cases skipped in the default fixture run |
| Local D1 check                                                                  | `SELECT 1` passed                                                               |
| Rust formatting, Clippy, workspace tests and WASM build                         | Passed; 52 tests                                                                |
| Python Ruff lint/format and pytest                                              | Passed; 145 tests, 8 optional integration skips                                 |

`npm run test:alpha` passed **27/27** with the CI fixture, then **27/27** with
`M6B_IMPORT_SQL=data/processed/d1-2024/import.sql`. Both runs covered Chromium,
Firefox, WebKit, Pixel 7 emulation and iPhone 13 emulation. The full publication
run used real D1 data for gameplay, except explicit failure injections.
The production alpha checks verify API routing, immutable asset/MIME/CSP headers,
strict non-cacheable misses, browser-worker initialization, complete draft/season
parity, retry/cancellation, version mismatches and missing-WASM reload recovery.

`npx playwright test --config apps/web/playwright.alpha.config.ts --project edge`
with the full-publication variable also passed **7/7**.
GitHub Actions has been extended but has not executed these uncommitted changes.
No physical phone, hosted performance, live Access or cloud deployment result is claimed.
