# M5B browser compatibility, performance and static delivery

Measured 2026-10-26 on Windows ARM64, Snapdragon X Plus X1P42100 / Qualcomm
Oryon, Rust 1.88.0 native ARM64, Node 22.21.0, Playwright 1.58.2 and Wrangler
4.152.0. Engine 0.4.0 and all core contracts/rules/models/RNG are unchanged;
adapter 0.2.0 adds transport projection and host-side measurement only.
[Reproduction, scope and phone instructions](../../docs/BROWSER_VALIDATION.md).

## Implemented changes and compatibility

Added Firefox/WebKit and mobile-emulation parity projects, separate Edge projects,
a 29-opponent/270-profile capacity test, native/WASM phase benchmarks, linear
memory and scoped worker-heap snapshots, Cloudflare static headers, and a local
redeployment test. The summary now projects computed fields in Rust before JSON
serialization; the complete detailed result remains available and unchanged.

| Environment                   | Version / descriptor             | Parity and lifecycle        | Delivery/CSP                    |
| ----------------------------- | -------------------------------- | --------------------------- | ------------------------------- |
| Chromium x64/emulated         | 145.0.7632.6                     | 10/10 exact/lifecycle cases | 2/2 cases                       |
| Edge ARM64                    | 156.0.4314.42                    | 10/10 exact/lifecycle cases | 2/2 cases                       |
| Firefox x64/emulated          | 146.0.1                          | 10/10 exact/lifecycle cases | 2/2 cases                       |
| WebKit Windows x64/emulated   | 26.0                             | 10/10 exact/lifecycle cases | 2/2 cases                       |
| Mobile Chromium emulation     | Pixel 7 / desktop Chromium       | 10/10 cases                 | Covered by desktop engine tests |
| Mobile WebKit emulation       | iPhone 13 / desktop WebKit       | 10/10 cases                 | Covered by desktop engine tests |
| Local new-deployment scenario | Production A → rebuilt B         | 1/1 case                    | HTML/assets/stale-tab recovery  |
| Physical Android / iOS        | No connected device              | NOT TESTED                  | NOT TESTED                      |
| Shipping macOS/iOS Safari     | Not the Windows WebKit test port | NOT TESTED                  | NOT TESTED                      |

All three existing seeds (`0`, `9007199254740993`, maximum u64), 162-game summary
and detailed results retain full native/parsed-JSON equality, including scores,
individual/team stats, game seeds, contextual events and snapshots. No equality
criteria or goldens were relaxed. Compact responses equal the full result's
projection. The larger case repeats verified parameter templates with distinct
profile/instance IDs and explicitly synthetic opponents; it is capacity evidence,
not 30 real historical rosters. Existing fixture outputs remain 105–57, R759/RA580,
RD+179. Main-thread frames are counted only while a worker request is outstanding.

The initial final-matrix run detected a Firefox-only CSP violation: its automatic
favicon request was blocked by `default-src 'none'`. The final policy explicitly
allows only same-origin images. The zero-policy-violations assertion is unchanged;
no violation is filtered and no generic `unsafe-eval` was added. Final tests use
that policy. The timing snapshots below preceded this image-policy-only fix;
JS/WASM/input bytes and the simulation paths are identical to the final build.

Mobile emulation runs this computer's CPU and desktop browser engines with
viewport/touch/user-agent settings. It proves neither physical-phone speed,
thermal/memory behavior, cellular transfer nor shipping Safari compatibility.

## HTTP-cache-cold versus reload startup

Three fresh browser contexts and their three same-context reloads per engine.
Values are median [min–max] milliseconds from navigation start. Ready includes
frontend and worker startup; result includes immediate first simulation/render.
No route interception or synthetic network throttle is used. These are localhost
HTTP-cache context measurements: browser-process/JIT, OS and server caches are
not cleared, so they are **not genuine first-visit WAN/cellular timings**.

| Environment                 | Fresh-context ready  | Fresh-context first rendered result | Same-context reload ready | Reload first rendered result |
| --------------------------- | -------------------- | ----------------------------------- | ------------------------- | ---------------------------- |
| Chromium x64/emulated       | 296.7 [270.3–520.6]  | 503.3 [493.5–776.7]                 | 128.9 [113.4–207.1]       | 327.3 [308.8–415.7]          |
| Edge ARM64                  | 329.8 [316.1–726.5]  | 380.5 [369.1–780.7]                 | 95.1 [92.4–96.1]          | 145.6 [142.9–145.7]          |
| Firefox x64/emulated        | 939.0 [761.0–1276.0] | 1501.0 [1261.0–1763.0]              | 828.0 [753.0–1221.0]      | 1411.0 [1336.0–1700.0]       |
| WebKit Windows x64/emulated | 559.0 [433.0–584.0]  | 827.0 [715.0–863.0]                 | 320.0 [311.0–497.0]       | 578.0 [572.0–760.0]          |

Worker-instance initialization (fetch/compile/instantiate; asset/code caches may already be warm) across the twelve execution cases:

| Environment                 | First observed init ms | Subsequent init median [min–max] ms |
| --------------------------- | ---------------------- | ----------------------------------- |
| Chromium x64/emulated       | 116.0                  | 21.3 [15.6–40.1]                    |
| Edge ARM64                  | 109.5                  | 15.6 [10.3–18.8]                    |
| Firefox x64/emulated        | 105.0                  | 46.0 [24.0–74.0]                    |
| WebKit Windows x64/emulated | 151.0                  | 128.0 [93.0–163.0]                  |

Worker resource entries retain encoded/decoded/transfer sizes where the browser
supplies them. On the first measured Edge worker the WASM was 130,412 encoded /
384,123 decoded bytes; a resource's transfer size also contains overhead. No
CDN/phone inference is made from these local runtime values.

## 29-opponent execution, first versus repeated

One fresh worker per case, one first execution and ten subsequent runs. All
inputs/seeds are identical within a case. Native runs use the same JSON boundary;
file I/O/printing are outside timing. Warm figures are medians, with sample SD and
range retained. The first worker call can reuse compiled browser code and is not
a cold browser/OS. Summary/events below are engine detail modes; both request
only a compact summary over the worker boundary.

| Environment                 | Detail  | Native warm boundary ms | First worker round trip ms | Warm round trip median [range] ms | Warm SD ms |
| --------------------------- | ------- | ----------------------- | -------------------------- | --------------------------------- | ---------- |
| Chromium x64/emulated       | summary | 29.6                    | 606.9                      | 121.6 [78.8–148.9]                | 27.2       |
| Chromium x64/emulated       | events  | 24.9                    | 354.3                      | 130.1 [88.0–197.1]                | 35.5       |
| Edge ARM64                  | summary | 25.5                    | 196.1                      | 113.2 [89.1–225.8]                | 38.8       |
| Edge ARM64                  | events  | 35.5                    | 209.9                      | 83.5 [63.7–136.5]                 | 21.1       |
| Firefox x64/emulated        | summary | 23.0                    | 770.0                      | 458.0 [444.0–510.0]               | 20.4       |
| Firefox x64/emulated        | events  | 24.4                    | 754.0                      | 557.0 [471.0–738.0]               | 87.0       |
| WebKit Windows x64/emulated | summary | 22.4                    | 835.0                      | 400.5 [336.0–572.0]               | 70.0       |
| WebKit Windows x64/emulated | events  | 24.9                    | 1226.0                     | 289.0 [229.0–478.0]               | 94.9       |

Warm per-stage medians, milliseconds (zero can mean below browser timer resolution):

| Environment                 | Detail  | Rust input decode | Simulation incl. validation | Rust serialization | WASM call incl. copies/cleanup | Worker JSON processing |
| --------------------------- | ------- | ----------------- | --------------------------- | ------------------ | ------------------------------ | ---------------------- |
| Chromium x64/emulated       | summary | 6.25              | 99.75                       | 0.25               | 120.00                         | 0.05                   |
| Chromium x64/emulated       | events  | 6.00              | 112.50                      | 0.25               | 128.80                         | 0.10                   |
| Edge ARM64                  | summary | 3.40              | 104.45                      | 0.00               | 112.55                         | 0.05                   |
| Edge ARM64                  | events  | 1.70              | 76.70                       | 0.00               | 82.20                          | 0.00                   |
| Firefox x64/emulated        | summary | 11.50             | 430.50                      | 0.50               | 456.00                         | 0.00                   |
| Firefox x64/emulated        | events  | 12.00             | 522.00                      | 0.00               | 556.00                         | 0.00                   |
| WebKit Windows x64/emulated | summary | 18.00             | 183.50                      | 1.00               | 396.50                         | 0.00                   |
| WebKit Windows x64/emulated | events  | 16.00             | 128.00                      | 1.00               | 286.50                         | 0.00                   |

The phase sum does not include all result destruction, generated binding string
copies and host work; do not call the residual isolated transfer time. Browser
privacy timers/JIT/allocator/CPU load affect these short samples. No GC is forced.

## Optimization evidence and remaining performance finding

The `summaryBaseline` control serializes and parses the full result, then sends
only its projection, reproducing M5A's worker path. Compact summary and baseline
are measured in separate fresh worker instances, in sequential cases; these are
observations, not randomized/paired causal estimates or universal speed claims.

| Environment                 | Summary detail: baseline → compact RTT ms | Events detail: baseline → compact RTT ms |
| --------------------------- | ----------------------------------------- | ---------------------------------------- |
| Chromium x64/emulated       | 148.8 → 121.6                             | 325.1 → 130.1                            |
| Edge ARM64                  | 133.6 → 113.2                             | 172.3 → 83.5                             |
| Firefox x64/emulated        | 589.5 → 458.0                             | 805.5 → 557.0                            |
| WebKit Windows x64/emulated | 171.5 → 400.5                             | 708.5 → 289.0                            |

The compact path removes measured full-JSON serialization/parsing and consistently
reduces allocated WASM capacity. **It is not faster in every case:** WebKit's warm
summary median was 400.5 ms compact versus 171.5 ms baseline. Its simulation and
unmeasured boundary/cleanup costs also differed substantially across the separate
instances, so a sole serialization cause cannot explain that result. Keep this
as an open performance finding; investigate on native macOS/iOS and with paired
steady-state sampling before making a cross-browser speed guarantee. No user-agent
workaround, engine/model change or correctness relaxation was introduced. The
first large events/compact WebKit call also exceeded one second (1,226 ms) on this
emulated Windows port. Physical device performance remains a launch gate.

## Memory

All four engines observed the same capacity for the large input after execution:

| Engine detail | Compact linear capacity MiB | Full/baseline linear capacity MiB |
| ------------- | --------------------------- | --------------------------------- |
| summary       | 2.125                       | 6.375                             |
| events        | 4.000                       | 20.375                            |

These are `WebAssembly.Memory.buffer.byteLength` capacities, not live allocated
Rust bytes or process RSS. They remain at their high-water capacity after results
are freed and can be released by terminating the worker. Repeated samples retain
capacity rather than retaining every result/history. This is not a proof of no
leaks or a production memory ceiling.

Edge dedicated-worker DevTools snapshots after eleven runs, no forced GC:

| Detail/output   | JS used heap MiB | JS total heap MiB | Backing storage MiB |
| --------------- | ---------------- | ----------------- | ------------------- |
| summary/summary | 3.731            | 5.352             | 0.006               |
| summary/full    | 3.743            | 8.352             | 1.118               |
| events/summary  | 3.731            | 5.352             | 0.006               |
| events/full     | 10.893           | 38.102            | 5.859               |

Snapshots are scoped worker JS observations, not peaks or the whole browser. Do
not add them blindly to WASM capacity. Firefox/WebKit worker JS snapshots are
unavailable via Chromium CDP. `measureUserAgentSpecificMemory` is unavailable in
this non-isolated environment; no COOP/COEP or SharedArrayBuffer was added solely
for measurement. Total browser/process RSS is not reliably measured here.

## Input, output and asset sizes

UTF-8 application data, for the exact benchmark seeds (sizes can change with
seed/outcomes). Capacity inputs are generated, not committed historical data.

| Input                 | Opponents/profiles | Input bytes (summary/events) | Full result bytes (summary/events) | Compact bytes |
| --------------------- | ------------------ | ---------------------------- | ---------------------------------- | ------------- |
| Small observed orders | 1/18               | 64,656/64,655                | 912,183/5,880,585                  | 159           |
| Synthetic capacity    | 29/270             | 316,034/316,033              | 1,166,639/6,138,247                | 159           |

The compact response reaching React is approximately 0.44–0.54 KB including
transport diagnostics (UTF-8 JSON-representation estimate). Full large-input
responses additionally carry approximately 1.17 MB summary / 6.14 MB events.
Structured-clone's private wire representation and JS internal string storage
are not measured. Input parsing/copying remains at the request boundary; a
persistent input cache or new binary format was not justified/introduced.

| Production asset          | Raw bytes | gzip bytes (Node zlib estimate) |
| ------------------------- | --------- | ------------------------------- |
| index-B5SUWd_s.js         | 341,911   | 78,829                          |
| index-BFW8mo15.css        | 415       | 290                             |
| season.worker-DpqoMdPx.js | 5,328     | 2,183                           |
| sim_wasm_bg-BWh7ETki.wasm | 384,123   | 130,412                         |

The WASM grew from M5A's 366,194 to 384,123 bytes due to the compact adapter and
instrumentation. No new application runtime dependency was added. Raw benchmark
samples, ranges, SD, initialization resources and memory snapshots are retained
locally in ignored `target/browser-parity/m5b-performance-{chromium,edge,firefox,webkit}.json`.
The committed report is a measured snapshot, not a generated raw dataset.

## Deployment/cache findings

Tests use actual local Wrangler Pages serving copied production build artifacts.
WASM is `application/wasm`; JS/worker URLs are hashed and have correct MIME types.
HTML revalidates (`no-cache`), assets are immutable for a year, and a top-level
404 prevents missing hashes becoming SPA HTML. CSP is applied to both document
and worker, permits same-origin assets and narrow `wasm-unsafe-eval`, and has no
broad `unsafe-eval`. No development-server URLs, COOP/COEP or shared memory are
required. Cloudflare does not expose `_headers` as a served asset.

A second actual Vite build with identical source/no minification changes JS/worker
hashes without changing rules. Tests replace only generated served files, verify
new HTML, old asset 404s, active-worker continuity, then recover a delayed stale
old-worker URL through the new Reload app action. This validates local behavior,
not a live CDN/atomic release, custom domain, TLS or production cache purge.

## Validation and remaining gates

- 51 Rust tests; formatting; host and WASM Clippy with warnings denied; native
  release examples; release WASM/binding generation: pass.
- Browser correctness: 12 each Chromium/Firefox/WebKit/Edge, 10 each mobile
  emulation, one deployment case (69 distinct project cases). Four separate
  performance cases completed. Exact equality/goldens remain intact.
- TypeScript, ESLint, Prettier, production Vite build, Worker dry-run and local
  D1 `SELECT 1`: pass. No resources were provisioned or deployed.
- Python is unchanged; Ruff/format and 125 tests pass, with 7 optional source-data
  integrations skipped without source-directory options. Hosted CI
  is configured for Chromium/Firefox/WebKit/mobile/deployment, but hosted CI itself
  was not executed locally. Edge is tested only where installed.

No local correctness/CSP blocker remains. Before shipping/integrating on an actual
host, verify its live headers, compression, HTML revalidation and asset retention;
choose the API origin/CSP deliberately when a later data-integration milestone is
authorized. Physical mid/low-range Android and iOS memory/performance checks and
the WebKit summary timing anomaly remain open validation gates. There is no
physical-device performance claim, cloud data integration, game feature, new
statistical model or automatic Git commit in M5B. Existing M4 calibration biases
remain visible and unchanged.
