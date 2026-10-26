# Published profiles in the browser (M6B)

The developer harness now exercises local **D1 → Worker API → React → WASM →
162-game result**. The bundled M4 fixture remains the default offline option.
Nothing loads from the player API until a dataset is requested. No cloud resources
are provisioned. See the [measured report](../data/validation/player-data-browser-v1.md).

## Loading and assembly

`apps/web/src/lib/api/player-data.ts` provides typed catalog, dataset, player,
single-profile and batch-profile requests, runtime response checks and structured
errors. The small `SessionCache` is independent of MLB and can serve another API
consumer. The current payload types describe the existing MLB API; they are not a
universal model for future sports. No statistical calculations run in TypeScript.

`apps/web/src/mlb/season-input.ts` owns MLB-specific assembly. The current pilot
selects the nine verified 2024 NYA identities in the M4 batting order. Player
metadata resolves each identity to its published prepared-profile ID. One batch
retrieves those nine profiles; the full database and player catalog are not loaded.
Only referenced profiles enter the assembled input, with duplicate IDs collapsed.

`scripts/build-pilot.mjs` checks the M4 fixture's pinned SHA-256 before extracting
its exact CHA opponent profiles, game/season rules, pitching environment and
Retrosheet transition model. It writes an ignored, compact static JSON artifact
and its content ID under `apps/web/src/generated/`. Vite gives the JSON a hashed
asset URL; it is fetched lazily rather than embedded again in the application JS.
Build and development commands generate it automatically; run `npm run build:pilot`
before a standalone typecheck on a fresh checkout. No raw Retrosheet files,
calibration datasets, profile generation or transition fitting enter this path.

Assembly requires source, policy, year, profile aggregation, model and schema
compatibility. It verifies prepared-profile content IDs, integer weight sums and
the compiled pilot digest. Unknown profile fields and malformed flags are rejected.
It retains the existing game schema **1.2.0**, season schema **1.0.0**, engine
**0.4.0**, RNG and rules. Seeds remain canonical decimal strings through the full
unsigned 64-bit range. Incompatible data fails before the simulation worker call.

The two contexts stay distinct:

- `dataset.contextId` / profile provenance / `pitchingEnvironment.contextId`
  identify the Lahman baseline and smoothing preparation context.
- `config.contextualModel` contains the separately verified M4 Retrosheet contact
  transition model, identified by `transitionModelId` in the static artifact.

This uses one fixed CHA opponent for a synthetic 162-game schedule. It does not
claim authentic season rosters, positional eligibility enforcement, pitching
rosters or a historical MLB schedule. The pilot intentionally rejects other years
and preparation contexts rather than synthesizing missing configuration.

## Session and delivery behavior

Immutable dataset/profile IDs scope cache entries; player metadata is additionally
dataset-scoped. Concurrent individual and overlapping batch requests share work.
Batch requests deduplicate and split at the API's existing limit of 20. Failed
loads are evicted for retry. Callers receive independent clones. Clearing replaces
the cache generation, so old requests cannot repopulate the new cache.

Changing the selected dataset or **Clear session cache** invalidates the loaded
snapshot and both caches. The shared artifact key includes engine/assembler
versions, content ID and asset URL. New builds/reloads create new client instances;
there is no persistent browser storage. Repeat simulation revalidates and assembles
the in-memory snapshot without any data fetch. Existing worker output remains a
compact summary; full output remains available through the existing worker protocol.

`GET /api/datasets/:id?view=simulation` omits the approximately 72 KB baseline audit
and returns its existing opaque `contextId`. Default dataset details keep the full
audit. This is an additional representation, with the same publication ID and
immutable response caching; published records are unchanged. The catalog remains
compact and omits the audit. A dedicated URL keeps representation caches separate.

Vite development and preview proxy `/api` to `http://127.0.0.1:8787` by default;
override with `DRAFTORY_API_TARGET`. Production requests remain same-origin `/api`:
eventual hosting must route that path to the Worker. Existing `_headers` policies
cover hashed assets (immutable), HTML (revalidate), WASM MIME and CSP. No new
cross-origin isolation, SharedArrayBuffer, CORS or external origin is required.
Digest verification requires a secure Web Crypto context (HTTPS or localhost).
For phone testing use trusted HTTPS or localhost forwarding; plain LAN HTTP is
insufficient for this API-integrated path. Existing offline LAN instructions are
in [browser validation](BROWSER_VALIDATION.md). Physical phones were not tested.

## Local use and tests

First follow [export/import instructions](PLAYER_DATA_API.md) for the verified
2024 dataset, apply local migrations, then start `npm run dev:api` and
`npm run dev:web` in separate terminals. In the page, load published datasets,
select the 2024 season aggregate, load pilot data, inspect the profiles, then
simulate or change the seed and repeat. API/context errors are visible; retry a
failed request or clear the session after correcting incompatible data.

From the repository root, after building WASM and the production web application:

```sh
cargo build --locked --release --examples
npm run build:wasm
npm run build
npm run test:data-client
npm run test:api
npm run test:integration
npm run test:integration:edge
```

The integration runner creates only isolated generated state under
`target/m6b-api`, applies real migrations and starts local Wrangler plus Vite
preview. CI uses the exact existing M4 prepared profiles with explicitly test-only
identity metadata, not an unofficial source download or a claimed full publication.
For validation against the real M6A export, set `M6B_IMPORT_SQL`:

```powershell
$env:M6B_IMPORT_SQL = 'data/processed/d1-2024/import.sql'
npm run test:integration
npm run test:integration:edge
Remove-Item Env:M6B_IMPORT_SQL
```

Tests cover full native/WASM result equality, deterministic repetitions, maximum
seed preservation, selective requests, cache reuse/clear, API recovery and
incompatible/unavailable context rejection. They record timings and decoded
response sizes under ignored `target/m6b/`. The existing browser suite separately
tests actual local Cloudflare Static Assets headers, deployment changes and the offline fixture.
The integration proxy does not establish hosted Cloudflare routing or WAN latency.
