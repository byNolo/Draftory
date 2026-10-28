# Cloudflare alpha preparation · M8A

**Preparation only. No account, database, Access policy or live deployment has been
created or changed. Every cloud mutation below requires explicit approval first.**
Account IDs, database IDs, membership, plan and target ownership remain unverified.
Do not run the cloud command examples as part of routine local validation.

## Arrangement and environment separation

Use one **Workers Static Assets** application named `draftory-alpha`: HTTPS static
React/Vite, hashed browser Worker/WASM and the existing pilot/context JSON, with
`/api` and `/api/*` handled by the existing read-only D1 API. Matched static assets
bypass application code. Rust still executes entirely in the visitor's browser.
No simulation server, new database schema, CORS, Pages project or Vite hosting
plugin is needed.

Pages could serve the frontend and Pages Functions could adapt the API, but that
adds a second API entry convention/project without improving this repository.
Workers Static Assets keeps the existing Worker entry and D1 binding together
with its static version. This is a project-specific choice, not a claim that
Pages is unavailable. See [routing](https://developers.cloudflare.com/workers/static-assets/routing/worker-script/)
and [Pages migration differences](https://developers.cloudflare.com/workers/static-assets/migration-guides/migrate-from-pages/).

| Use                          | Configuration                                 | Database/state                                                  |
| ---------------------------- | --------------------------------------------- | --------------------------------------------------------------- |
| Existing Vite + local API    | `services/api/wrangler.jsonc`                 | `draftory-local`, existing local state                          |
| Production-build alpha tests | `services/api/wrangler.alpha.json`            | Sentinel IDs, isolated `target/m8a-api`                         |
| Future hosted alpha          | Generated `target/alpha/wrangler.hosted.json` | Explicit approved account and separate `draftory-alpha` D1 UUID |

The committed alpha template has an all-zero account/database ID, no routes,
`workers_dev: false` and `preview_urls: false`. It is for local tests/dry runs;
**never use it for a remote operation**. The preparation tool accepts both real
IDs together, rejects placeholders and conflicting account environment variables,
and writes only ignored local review files. It does not authenticate or verify
Cloudflare ownership, and never invokes a cloud command. The Worker/database names
stay fixed to `draftory-alpha`; there is no production environment or deploy script.

## Local validation and release preparation

From the repository root, using the prerequisites already in the README:

```sh
npm ci
npm run build:wasm
npm run build
npm run typecheck
npm run lint
npm run format:check
npm run check:alpha
npm run test:alpha:tools
npm run test:alpha
npm run test:browser
npm run test:api
npm run test:data-client
```

`check:alpha` audits the built files and runs `wrangler deploy --dry-run`, which
bundles locally without deploying. No credentials are required. CI runs these
checks, not deployments. `test:alpha` serves the real production build and API/D1
through **one local Wrangler origin**, with no Vite proxy. Ordinary CI uses the
existing nine-profile M4 test publication for genuine D1/API checks and the small
verified M7C HTTP excerpts for draft cards. This is not a full 526-player CI import.

For the complete dataset, first follow the existing
[official-source export instructions](PLAYER_DATA_API.md#reproducible-export-and-local-import).
Only the selected 2024 publication is needed; keep raw Lahman/Retrosheet data offline.

```powershell
npm run prepare:alpha
$env:M6B_IMPORT_SQL = 'data/processed/d1-2024/import.sql'
npm run test:alpha
Remove-Item Env:M6B_IMPORT_SQL
```

The reused import variable selects a real publication. The alpha test server
verifies its manifest, SQL hash and frontend compatibility before importing it
**locally**. All gameplay then uses genuine D1 responses except deliberate error
injections. Optional installed Edge: `npx playwright test --config apps/web/playwright.alpha.config.ts --project edge`.

Preparation writes `target/alpha/release.json`, containing SHA-256/byte sizes for
the static files, migration hashes, catalog/pilot/dataset IDs and publication
details. It rejects stale catalog/pilot assets or unexpected public files. The
existing exporter and immutable conflict checks remain authoritative; manifests
are never edited to make a mismatch pass. Inspect the release after the final
build. Re-run preparation if code, migrations, assets or data change.

## Account and access setup, after approval

Use a Cloudflare account on **Workers Free**, with D1 enabled, and choose a
Workers subdomain. A `workers.dev` hostname supplies HTTPS without buying a domain.
Use a separate alpha D1 database; never bind an existing production database.
Keep the local API configuration unchanged.

Administrator access can use Wrangler OAuth (`npx wrangler login`) or a locally
provided `CLOUDFLARE_API_TOKEN` scoped to the approved account with Workers Scripts
Edit and D1 Edit permissions. Access-policy administration additionally needs
the relevant Zero Trust permissions. Confirm the actual granted permissions in
the account. No runtime API key or app secret is required: D1 is an internal
binding. Never put tokens in Git, a `VITE_*` variable, frontend JS or WASM.
If deployment automation is approved later, use protected CI secrets/environments;
the current workflow has no deployment job or Cloudflare credentials.

Read-only preflight commands, for the selected account:

```powershell
$env:CLOUDFLARE_ACCOUNT_ID = '<approved-32-character-account-id>'
npx wrangler whoami --account $env:CLOUDFLARE_ACCOUNT_ID --json
npx wrangler d1 list --json
npx wrangler deployments list --name draftory-alpha
```

Compare the account ID with the dashboard, confirm the Free plan and membership,
and inspect both names before creating or replacing anything. An existing
`draftory-alpha` Worker or database is **not automatically safe to overwrite**:
stop unless ownership and its alpha role have been confirmed. Initial “not found”
is expected for a new Worker; authentication/permission errors are not that result.

## Exact cloud mutation sequence for review

**None of these commands has been executed. Obtain approval for the selected
account and alpha targets before proceeding.** The examples assume PowerShell
from the repository root; replace placeholders with reviewed values.

1. Create only the new alpha database. Disable automatic config editing:

   ```powershell
   npx wrangler d1 create draftory-alpha --update-config=false
   $alphaDatabaseId = '<UUID-returned-for-the-approved-alpha-database>'
   npm run prepare:alpha -- --account-id $env:CLOUDFLARE_ACCOUNT_ID --database-id $alphaDatabaseId
   ```

   Inspect `target/alpha/wrangler.hosted.json`: correct account, correct UUID,
   names `draftory-alpha`, absolute paths resolving inside this checkout,
   public and preview URLs disabled. The preparation script itself is local.

2. Apply ordered, versioned migrations, then import the exact verified 2024 SQL:

   ```powershell
   npx wrangler d1 migrations list DB --remote --config target/alpha/wrangler.hosted.json
   npx wrangler d1 migrations apply DB --remote --config target/alpha/wrangler.hosted.json
   npx wrangler d1 execute DB --remote --config target/alpha/wrangler.hosted.json --file data/processed/d1-2024/import.sql
   npx wrangler d1 execute DB --remote --config target/alpha/wrangler.hosted.json --command "SELECT dataset_id, player_count FROM mlb_publications"
   ```

   Expected publication: `dataset:1fba260824fe05abec3c5950cd184caa0d314b41f1253bc782f97b678bb28add`,
   526 players. Source SQL SHA-256 is
   `4dab2562d2b4344cd7499bb6ea54f899b4ba3fe95f1f859c3772d6d7f695828d`.
   Import parents precede children; the completion marker is last. A partial
   publication stays hidden. A retry of the exact same file is idempotent;
   conflicting immutable rows fail rather than being overwritten. Do not drop
   tables, delete records or import another season to repair a failure.

3. Deploy an unrouted version so the Worker exists for Access setup:

   ```powershell
   npx wrangler deploy --dry-run --config target/alpha/wrangler.hosted.json
   npx wrangler deploy --config target/alpha/wrangler.hosted.json
   ```

   This creates/updates cloud resources even though the app has no public route;
   it still requires approval. Keep `workers_dev` and previews disabled.

4. Configure **Cloudflare Access for this Worker only**, with **All traffic**
   protection and a small explicit email allowlist. Zero Trust's Free plan is
   intended for small teams (currently under 50 users); confirm plan/seats during
   signup. Email one-time PIN or an existing identity provider avoids custom app
   accounts. Avoid “Allow everyone”, public bypass rules and account-wide policy
   changes that could affect other Workers.

   [Worker-level Access](https://developers.cloudflare.com/workers/configuration/cloudflare-access/)
   protects its associated hostnames, API and static assets. For a legacy account
   without that control, a self-hosted hostname policy must cover the whole alpha
   hostname before exposure, not just `/` or `/api`. Version/preview URLs remain
   disabled. This app needs no WebSockets or `ctx.access` identity data.
   [Access plan information](https://www.cloudflare.com/sase/products/access/).

5. Only after reviewing the effective Access policy, approve enabling the URL:

   ```powershell
   npm run prepare:alpha -- --account-id $env:CLOUDFLARE_ACCOUNT_ID --database-id $alphaDatabaseId --enable-workers-dev
   npx wrangler deploy --dry-run --config target/alpha/wrangler.hosted.json
   npx wrangler deploy --config target/alpha/wrangler.hosted.json
   ```

   Record the actual HTTPS URL printed by Wrangler; the application contains no
   hardcoded hostname. Authenticate in a browser, then do the verification below.
   An obscure URL and `noindex` headers are **not** access control.

Access controls future requests, not copies already downloaded by an allowed
tester. Local playtest exports and cached historical data cannot be revoked.
Confirm that the main hostname and any aliases are protected using a signed-out
browser. Access-session expiry may require signing in again before retrying data
loads. Do not paste Access cookies, service tokens or logs into Git.

## Hosted verification and physical phones

Before sharing the URL, use signed-out/private browsing to check that HTML,
`/dev/`, JS, WASM and both API GET and POST requests are gated. A non-allowlisted
identity must be rejected. Check disabled preview/version/alternate hostnames;
test a session expiring and signing back in. These are hosted-only gates.

Then, authenticated on desktop and each physical Android/iPhone:

- Record model, OS/browser, URL and app version. Check HTTPS and a narrow viewport.
- Draft nine hitters with readable historical stats, visible budget, 44px targets,
  usable scrolling and no document-wide horizontal overflow.
- Simulate 162 games; verify the record and nine batting lines. Repeat a seed,
  try a new season and start another draft. Confirm the UI stays responsive.
- Briefly disconnect during card/profile loading; reconnect and retry. Try an
  expired Access session. If an old asset was removed, the reload option warns
  that it clears the ephemeral draft.
- Inspect actual WASM MIME/CSP, worker startup and API errors via remote browser
  debugging where available. Log first/warm observations without claiming a
  fresh radio/OS cache. Test Wi-Fi and mobile data if available.
- After an approved redeploy, test an already-open tab, a fresh navigation,
  HTML revalidation, unchanged hashed URLs and a deliberately missing asset.

Local browser emulation is not physical-device testing. No phones were tested in M8A.
No cross-origin isolation, SharedArrayBuffer or server simulation is required.

## Updates, failure recovery and rollback

Keep static JS/CSS/JSON/WASM immutable under hashed URLs, with HTML revalidation.
Known routes are `/` and `/dev/`; unknown deep links and missing assets return 404,
not SPA HTML. Failed asset downloads use `no-store`, so a missing version is not
cached for a year. API POST/errors also use `no-store`. Access is separate from
these cache rules. The deployment contains both the Worker and static assets.

For an app update, build, validate, prepare and review again, then use the explicit
hosted config. Do not enable automatic Git-based deployments during preparation.
Keep the release manifest and previous version ID for each approved deployment.
Check the new deployment while retaining old immutable D1 rows. An already loaded
WASM worker can finish; a tab that had not fetched removed assets may need reload,
which discards its unsaved draft. No service-worker/PWA cache is introduced.

Read-only version inspection and an **approval-required** Worker rollback:

```powershell
npx wrangler deployments list --config target/alpha/wrangler.hosted.json
npx wrangler versions list --config target/alpha/wrangler.hosted.json
# Mutates the hosted deployment; use a reviewed version ID:
npx wrangler rollback '<previous-version-id>' --config target/alpha/wrangler.hosted.json
```

Worker rollback does not undo D1 or Access-policy changes. Preserve old dataset
versions and backward-compatible schema changes. A new dataset must be generated
and reviewed separately, with updated catalog/frontend pins; publish it fully
before deploying clients that request its IDs. Do not overwrite an existing ID or
silently switch this alpha to another year/model. Re-test the older frontend too.

D1 Free currently provides seven days of Time Travel; record a bookmark/export
before approved changes. Restores are destructive cloud mutations requiring a
separate impact review and approval; they are not routine retry steps. Prefer
resuming an interrupted immutable import or rolling back the app. No deletion or
restore command is automated here. See [D1 recovery](https://developers.cloudflare.com/d1/reference/time-travel/)
and [Worker versions/storage boundaries](https://developers.cloudflare.com/workers/versions-and-deployments/).

## Usage, costs and observability

See [the M8A report](../data/validation/alpha-preparation-v1.md) for measured local
sizes and estimated usage. Quotas are account-wide, not dedicated to this alpha.
Static requests are currently free/unlimited; only API and unmatched-route Worker
invocations use the Workers allowance. Simulations and repeat runs happen locally.

In Workers & Pages → `draftory-alpha` → Metrics inspect request volume, CPU,
exceptions/errors and status distribution. Observability is enabled for native
Workers Logs; inspect the existing API failure messages without recording new
request bodies, cookies, emails or user-level gameplay analytics. Check asset
analytics/browser Resource Timing for delivery/cache behavior; asset-first hits
are not application-Worker invocations. Inspect the effective deployed headers.

In D1 → `draftory-alpha` → Metrics/Row Metrics inspect rows read/written and storage.
Use hosted D1 query `meta.rows_read`/`rows_written` for a sample of the exact API
queries, not returned-player counts. No telemetry endpoint or paid monitor is added.
Successful and failed gameplay performs reads only; investigate unexpected writes.
Watch the account usage as a whole and stop/limit the playtest before caps are hit.
Free-tier CPU and D1 quota failures must be validated on the actual host.

Official references, checked 2026-10-27:

- [Workers/static billing](https://developers.cloudflare.com/workers/static-assets/billing-and-limitations/),
  [Workers limits](https://developers.cloudflare.com/workers/platform/limits/).
- [D1 pricing/metrics](https://developers.cloudflare.com/d1/platform/pricing/),
  [D1 limits](https://developers.cloudflare.com/d1/platform/limits/),
  [remote import/export](https://developers.cloudflare.com/d1/best-practices/import-export-data/).
- [Workers Logs](https://developers.cloudflare.com/workers/observability/logs/workers-logs/),
  [static headers](https://developers.cloudflare.com/workers/static-assets/headers/).

Recheck the plans before real deployment. Workers Logs documents a pricing change
starting December 1, 2026; do not assume today's log allowance applies indefinitely.
