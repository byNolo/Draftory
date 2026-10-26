# Browser compatibility and static delivery (M5B)

M6B adds [published profile loading](PLAYER_DATA_BROWSER.md) and an isolated
Wrangler/D1 integration suite. Its [measurements](../data/validation/player-data-browser-v1.md)
separate selective data loading from assembly and WASM execution. The tests below
continue to exercise the offline fixture and static delivery independently.

M5B extends the [M5A adapter](BROWSER_WASM.md) without changing the portable engine,
season/game contracts, historical data, rules, or RNG. The adapter is now 0.2.0;
the engine remains 0.4.0. Measured results and known limits are recorded in
[browser-validation-v2.md](../data/validation/browser-validation-v2.md).

## Reproduce

From the repository root, after the pinned setup in the README:

```sh
npm run build:wasm
cargo build --locked --release --examples
npm run build
npx playwright install chromium firefox webkit
npm run test:browser
npm run test:edge
npm run bench:browser
npm run bench:edge
```

Linux CI uses `playwright install --with-deps chromium firefox webkit`. Edge is a
separate opt-in command requiring installed Edge; an unavailable engine is a test
failure, never silently counted as compatible. Named Playwright projects are
`chromium`, `firefox`, `webkit`, `edge`, `mobile-chromium` (Pixel 7 descriptor),
`mobile-webkit` (iPhone 13 descriptor), and `deployment`. The default correctness
command excludes Edge and includes deployment. Benchmarks use four separate
`performance-*` projects, with Edge optional. No additional test framework is used.

Tests copy production artifacts into ignored `target/browser-site/current` and
serve them through **local Wrangler Workers Static Assets**, including the actual `_headers`
rules. The empty benchmark document exists only in that generated copy. No cloud
project, binding, account login, data integration or deployment is required.

The M6B review replaced legacy Pages dev after Linux CI returned 502 for
`/_headers` (`ENOTDIR` while checking `_headers/index.html`). The current asset
runtime excludes reserved configuration files and preserves strict 404 assertions.
Deployment tests replace files inside the watched directory and wait for the new
manifest, avoiding watcher invalidation on Windows. No production resources or
application routing changes are involved.

All established seed/detail parity comparisons remain exact. The compact response
is compared to the full result, including maximum-u64 seeds. A capacity fixture
constructs 29 explicitly **synthetic** opponents and 270 distinct profile records
from existing parameter templates; it is a reproducible resource-load test, not
30 historical teams or a new dataset. It does not change probabilities or models.

## Measurements and scope

Each browser benchmark records three fresh HTTP-cache context visits and three
reloads in their respective same contexts. A DOM observer measures navigation to
worker-ready and navigation to first rendered result, triggering an immediate
simulation without test-driver click latency. Routing/interception is not used
in these measurements because Playwright routing disables HTTP caches.

Fresh contexts do **not** clear browser-process JIT/WASM code caches, OS caches,
server caches, or create a physical first-visit WAN connection. These are local
HTTP-cache-cold/warm results, not cellular/production-CDN performance. Resource
Timing transfer/encoded/decoded sizes are retained where supplied by the engine;
missing/zero entries must not be interpreted as proof of network delivery.

For each small/large input, summary/events detail, and compact/full/old-summary
transport, one first worker execution is separated from ten subsequent samples.
Initialization creates a new instance per case but may reuse compiled browser
code/assets. First events-mode execution is not a fresh browser process. Reports
contain medians, sample SD, min/max and all raw samples. `M5B_REPETITIONS=3..100`
can change the number of warm samples; the default is ten. There is no timing gate.

The adapter, outside the deterministic core, measures input JSON decode,
`simulate_season` (including validation/allocation), and result serialization.
Host `performance.now()` calls are not made inside the simulation loop. The last
successful call's tiny phase vector is read by the single-request worker; it is
diagnostics, not game state. `wasmCallMs` additionally includes UTF-8 copies and
cleanup; do not interpret its difference from the phase sum as isolated IPC time.

Worker JSON parsing/projection and round-trip latency are measured separately.
The round-trip-minus-worker estimate includes scheduling and message copying.
Input/result UTF-8 sizes and a JSON-representation estimate of the worker response
are recorded. Structured-clone's private IPC wire format is not measured.

Memory reporting distinguishes:

- `WebAssembly.Memory.buffer.byteLength` before/after execution: allocated linear
  capacity/high-water growth, **not live Rust allocations or process RSS**. Pages
  do not shrink when Rust drops a result; terminate/recreate the worker to release
  its instance. This measurement works on every tested engine.
- Chromium/Edge DevTools `Runtime.getHeapUsage` on the dedicated worker: scoped
  JS heap/backing-store snapshots, not the whole browser, not a peak, and not a
  number to add blindly to WASM capacity. No forced GC occurs during the runs.
- Total browser memory is unavailable reliably here. `measureUserAgentSpecificMemory`
  is not usable in the non-isolated test environment; no COOP/COEP is introduced
  just to enable a measurement. Firefox/WebKit worker JS heap snapshots are not
  supplied through Chromium's protocol.

Raw reports and generated inputs remain ignored under
`target/browser-parity/m5b-performance-*.json` and `m5b-input-*.json`.

## Measured summary optimization

M5A returned a compact message but first serialized the full season in Rust and
parsed it in the worker: approximately 0.9–6 MB even for its small fixture. M5B
adds `simulate_season_summary_json` to project the already-computed fields in Rust
**before** serialization. Full `simulate_season_json` is preserved for parity and
replays. The worker's `summaryBaseline` diagnostic option preserves M5A's full-JSON
then-discard path for a controlled comparison; React never requests that option.

This does not skip season simulation or invent aggregate statistics. Detailed
events are still computed if the input requests them, even when only the compact
summary is transported. Avoiding event computation for a caller requesting events
would change semantics and is not done. The core's full result allocation remains;
this optimization addresses demonstrated boundary serialization/copy/parsing costs.

## Static assets and deployment behavior

`apps/web/dist` is the static upload directory. Vite emits hashed JS, worker JS,
CSS and WASM URLs; no `/src`, `@vite` or development-server dependency belongs in
production. `public/_headers` is copied into the output and understood by Pages
and Workers static assets; it is not application code. HTML at `/` and
`/index.html` uses `Cache-Control: no-cache` (store but revalidate); `/assets/*`
uses `public, max-age=31536000, immutable`. Never replace bytes behind a hash URL.
Production should use atomic deployments and preserve/cache old versioned assets
where the chosen hosting system supports it. HTML must not become year-cached.

All responses receive `nosniff` and a CSP allowing same-origin scripts, styles,
workers and fetches; only `'wasm-unsafe-eval'` permits WASM compilation. General
`'unsafe-eval'`, inline scripts, blob workers and cross-origin isolation are not
needed. The worker response also receives the CSP; the document's `worker-src`
alone does not govern WASM compilation inside the worker. MIME checks enforce
`application/wasm` and JavaScript types on the real local Cloudflare responses.

The top-level `404.html` prevents missing hashed assets from being returned as SPA
HTML. There is no client-side routing in this harness. If routing is added later,
design fallbacks that preserve real 404s for missing JS/WASM assets.

The deployment test builds the same source a second time without minification,
producing genuine new Vite JS/worker hashes in a generated directory. It replaces
only generated served assets, verifies revalidated HTML and old-asset 404s, proves
an active WASM instance keeps working, then reloads a stale tab to the new bundle.
Its artificially delayed old-worker request is an explicit uncached-resource
scenario, not a benchmark/cache hit. The UI offers **Reload app** on errors so an
old document does not endlessly retry an asset URL removed by a new deployment.
This is local delivery validation, not proof of production CDN behavior.

## Physical phone smoke test

No physical Android/iOS device is connected/tested. Mobile emulation checks engine
execution, viewport/touch/user-agent behavior and UI layout on this desktop CPU;
it does not establish phone CPU, thermal, memory, radio or actual Safari behavior.
Playwright WebKit is not the shipping iOS Safari application.

To test manually on a phone on the same private Wi-Fi/LAN:

```sh
npm run build:wasm
npm run build
npx wrangler pages dev apps/web/dist --ip 0.0.0.0 --port 4175 --compatibility-date 2026-10-26
```

Find the computer's LAN IPv4 address (`ipconfig` on Windows) and open
`http://<computer-LAN-IP>:4175/` on the phone; `localhost` on the phone points to
the phone. If Windows prompts, allow this local server on the private network.
The command is intentionally provided for manual use; automated tests bind only
127.0.0.1. No TLS/account/Cloudflare provisioning is needed for this harness's
Worker/WASM APIs. It does not use secure-context-only SharedArrayBuffer features.

Run twice, expect **105–57 / 759 scored / 580 allowed / +179**, stop/restart, and
record device model, OS/browser version, visible initialization/execution times
and any errors. Use a private/fresh browser session for a separate cache sample,
but do not label it a cold radio or OS measurement. Before launch, repeat on real
mid/low-range Android and iOS devices and verify the eventual hosted headers.

References: [Cloudflare Pages headers](https://developers.cloudflare.com/pages/configuration/headers/),
[static serving/cache behavior](https://developers.cloudflare.com/pages/configuration/serving-pages/),
[Workers static headers](https://developers.cloudflare.com/workers/static-assets/headers/),
[Playwright emulation](https://playwright.dev/docs/emulation), and
[WASM linear memory](https://developer.mozilla.org/en-US/docs/WebAssembly/Reference/JavaScript_interface/Memory/buffer).
