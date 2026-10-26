# M6B published profiles → browser simulation

Validated 2026-10-26 on Windows ARM64, Snapdragon X Plus, Node 22.21.0,
Rust 1.88.0, Playwright 1.58.2 and pinned wasm-bindgen 0.2.105. No cloud deployment,
production import, pricing, gameplay rules, statistical fitting or RNG changes.
See [architecture and reproduction](../../docs/PLAYER_DATA_BROWSER.md).

## Implemented path and identities

The developer panel selects a published dataset, resolves nine known 2024 NYA
players through local D1/Worker metadata, batch-loads their prepared profiles,
assembles an existing versioned season input and sends it to the existing WASM
worker. React renders record, runs, differential and phase timings. Offline bundled
simulation remains available without API access. Cache/error handling and MLB
assembly are separate modules; no Rust, Python or SQL migration changed.

The real run imports the unchanged verified M6A 2024 publication:

- Dataset: `dataset:1fba260824fe05abec3c5950cd184caa0d314b41f1253bc782f97b678bb28add`.
- Official SABR Lahman 2025 CSV release, observed 2026-10-25, including February
  2026 BOM revisions; the existing locked source and attribution are retained.
- Import SQL SHA-256: `4dab2562d2b4344cd7499bb6ea54f899b4ba3fe95f1f859c3772d6d7f695828d`.
- 526 available profiles; only nine are retrieved for the user lineup. Their
  published season-aggregate IDs differ from M4's team-scoped IDs, but the selected
  NYA players' prepared weights match. IDs are preserved, never rewritten.
- Static artifact: `pilot:0ff787c4ee807cd681cc296a5429f254cdabfc057ee40433f32789c92121d848`.
- Original M4 fixture SHA-256:
  `d02959d2673eeeec2951644cf327434babefeddeb1cb5b516d809d3aa8a562a4`.

The static artifact carries the exact nine CHA opponent profiles, original
Retrosheet transition model, rules and configuration. The assembled input contains
18 referenced profiles and 162 games. The Lahman preparation baseline is verified
separately from the Retrosheet model. Source/policy/context/model/schema mismatches,
bad seeds, malformed profiles and content-digest failures are rejected before WASM.
Seeds are unsigned 64-bit decimal strings, including `18446744073709551615`.

The fixture-derived CI publication uses unchanged M4 prepared profiles and
explicitly test-only identity metadata. It is a separate dataset, not a claimed
526-player source import. Both modes run actual Wrangler, SQLite/D1 migrations,
HTTP API and browser WASM; they do not mock successful integration requests.

## Correctness

For seed `20261025`, the real and fixture-derived paths reproduce **105 wins,
57 losses, 759 runs scored, 580 allowed, +179 differential**. Full parsed WASM
results equal native release Rust results, including all per-game totals and
player statistics. Six identical runs preserve identical input strings and
outputs. The maximum u64 seed also reaches the worker losslessly and matches the
native record. Existing detailed event parity tests remain intact.

Each browser integration scenario verifies no requests during the actual
simulation interval, cache hits and explicit invalidation, retry after API errors,
pre-WASM invalid-seed rejection, incompatible dataset rejection and missing static
artifact recovery. Unit checks additionally cover missing/wrong/reordered batch
members, request deduplication, 20-item chunking, concurrent cache work, immutable
snapshot clones, cache clearing during an in-flight load and malformed profiles.

## Network and asset costs

The real publication requires **12 API requests** (one catalog, one compact dataset,
nine selected-player metadata responses and one nine-profile batch) plus **one
shared static artifact request**. Total decoded data response bodies: **81,416
bytes**. This excludes application JS, WASM, HTTP headers and request bodies.
The initial catalog is explicit; refreshing or paginating it adds requests.

The compact `?view=simulation` representation avoids transferring the full baseline
audit while preserving its opaque ID and the existing full-detail endpoint.
Published data and profile bytes are unchanged. Repeat simulation transfers zero
additional bytes and makes zero requests. Explicit cache clear causes twelve new
data requests (the selected catalog entry remains in the UI). Browser HTTP caching
may satisfy immutable GETs; the session-cache tests count actual fetch calls.

| Production asset                                            |   Bytes |
| ----------------------------------------------------------- | ------: |
| Main application JS (includes the existing offline fixture) | 356,900 |
| WASM, unchanged                                             | 384,123 |
| Worker JS, unchanged                                        |   5,328 |
| Shared opponent/configuration JSON                          |  55,591 |
| CSS                                                         |     415 |
| Assembled SeasonInput, main thread → worker                 |  64,656 |
| Nine-profile API batch response                             |   8,841 |
| Compact dataset response                                    |   1,466 |

The static JSON is 6,455 bytes with Node gzip level 9; decoded sizes above do not
claim actual production wire compression. The existing offline fixture in the JS
contains overlapping opponent/model data, so using the API path also downloads a
separate shared artifact. This preserves the requested offline fallback; a future
production game can separate the developer fixture route after measuring that
tradeoff. No full historical database is transferred.

Repeated assembly validates hashes and serializes one input string per call;
it does not repeat network transfers. The worker retains the existing summary
output path instead of sending full event traces to React. Full traces remain
available via the existing protocol. Further caching of verified assembly work
should be considered only with immutable snapshot guarantees and measured need.

## Timing measurements

One initial load and first run, followed by five same-page repeats per browser,
using the real publication and the final production build. Services were already
running and WASM was initialized before the data panel was used. Loading time is
wall time from **Load pilot data** through profile retrieval, including response
parsing and shared-artifact verification; it excludes the earlier catalog request
and final input validation. Assembly includes validation, hashes and input JSON
serialization. The WASM call includes Rust JSON parsing/simulation/serialization;
worker round trip includes messaging and result processing. These are loopback
observations with host/runtime variability, not first-visit WAN benchmarks or a
controlled browser speed ranking. OS/browser caches may already be warm.

| Browser           | Data loading ms | First assembly ms | First WASM call ms | First worker round trip ms |
| ----------------- | --------------: | ----------------: | -----------------: | -------------------------: |
| Chromium          |           260.0 |              21.0 |              219.3 |                      220.6 |
| Firefox           |           391.0 |              50.0 |              464.0 |                      465.0 |
| Playwright WebKit |           265.0 |             274.0 |              253.0 |                      256.0 |
| Installed Edge    |           181.8 |               4.4 |               48.8 |                       49.5 |

Warm values are **median (min–max)** across five runs, in milliseconds.
WASM time is contained within round trip; do not add those two columns.
Preparation-to-result is each run's assembly plus worker round trip, excluding
React rendering. No additional fetch occurs in this phase.

| Browser           |            Assembly |           WASM call |   Worker round trip | Preparation to result |
| ----------------- | ------------------: | ------------------: | ------------------: | --------------------: |
| Chromium          |     10.1 (8.7–20.2) |    48.7 (48.4–68.5) |    49.4 (49.2–69.3) |      59.4 (57.9–89.5) |
| Firefox           |    36.0 (32.0–58.0) | 394.0 (380.0–409.0) | 395.0 (382.0–409.0) |   431.0 (427.0–451.0) |
| Playwright WebKit | 229.0 (225.0–252.0) |   92.0 (64.0–114.0) |   94.0 (66.0–117.0) |   322.0 (291.0–360.0) |
| Installed Edge    |       4.1 (3.7–4.5) |    32.3 (28.5–33.5) |    32.9 (29.0–34.4) |      37.4 (32.7–38.2) |

WebKit's repeated validation/assembly cost is visible and larger than its WASM
call here. It is not hidden inside a claimed simulation speed. Per-run source
measurements, request sizes, sample counts, ranges and standard deviations remain
in ignored `target/m6b/real-<browser>.json`; fixture-derived runs are separate files.
No new reliable memory claim is made in this integration milestone.

## Validation results

| Browser           | Fixture-derived local D1 integration | Real M6A local D1 integration | Existing parity/delivery |
| ----------------- | ------------------------------------ | ----------------------------- | ------------------------ |
| Chromium          | 3 passed                             | 3 passed                      | Passed                   |
| Firefox           | 3 passed                             | 3 passed                      | Passed                   |
| Playwright WebKit | 3 passed                             | 3 passed                      | Passed                   |
| Installed Edge    | 3 passed                             | 3 passed                      | Passed                   |

- `npm run test:data-client`: **10 passed**, including native execution of assembled input.
- `npm run test:api`: **8 passed**, including compact-view/full-view equivalence and invalid-view rejection.
- `npm run test:integration` and `npm run test:integration:edge`: **12 passed** for the fixture-derived publication. The final real-export run used `M6B_IMPORT_SQL=data/processed/d1-2024/import.sql` with all four projects in one Playwright invocation: **12 passed**.
- `npm run test:browser`: **57 passed**, including existing Chromium/Firefox/WebKit, Pixel 7 and iPhone 13 emulation, exact native/event parity, 29 synthetic opponents, static headers and deployment replacement.
- `npm run test:edge`: **12 passed** against the final build.
- `npm run typecheck`, `npm run lint`, `npm run format:check`, `npm run build`: passed. No dependencies were added; existing locked installations were used.
- `npm run types:api` plus generated-types diff check: passed with no generated-type changes.
- `npm run check:api`: local Worker bundle/dry-run passed; no deployment.
- `npm run d1:check --workspace @draftory/api`: local `SELECT 1` passed. Integration tests applied the existing migration in isolated state and imported the real SQL successfully.
- `cargo fmt --all -- --check`, `cargo clippy --locked --workspace --all-targets -- -D warnings`: passed.
- `cargo test --locked --workspace`: **51 passed**; native workspace, release examples and `wasm32-unknown-unknown` workspace builds passed.
- `npm run build:wasm`: release bindings/WASM generated successfully with pinned CLI 0.2.105.
- In `data/pipeline`, `uv run ruff check .` and `uv run ruff format --check .`: passed; `uv run pytest`: **132 passed, 8 skipped**. Optional raw-source integrations were not enabled in this run; Python was unchanged. The real browser test imported the previously verified M6A publication, with its SQL checksum independently rechecked.
- All **12 JSON schemas** passed `Draft202012Validator.check_schema`; `git diff --check` passed.

Mobile emulation above covers the existing offline simulation path; this milestone
does not establish the API panel's performance on physical Android or iOS. No
physical Safari, phone or hosted Cloudflare tests were available/performed. There
are no failing required local checks. CI runs the API, client and browser
integration checks on Linux; remote results are recorded in GitHub pull-request checks.

The review traced the prior main-branch CI failure to legacy Pages dev returning
502 for `/_headers` on Linux (`ENOTDIR`), rather than a simulation mismatch. The
local delivery harness now uses Cloudflare Workers Static Assets, with the same
strict 404, MIME, cache, CSP and deployment-recovery assertions. Deployment tests
preserve the watched assets directory and wait for manifest updates. This changes
only local test infrastructure; historical measurements above used Pages dev.
CI saves test diagnostics on failure without uploading databases or raw datasets.
The initial review CI attempts timed out while APT downloaded browser system
libraries from the Azure Ubuntu mirror, before tests started. JavaScript CI now
uses the official Playwright 1.58.2 Noble image with preinstalled browsers and OS
libraries, matching the locked package; it does not skip browser execution.
Native release and WASM binaries/bindings are built once in the Rust job and
transferred as short-lived test artifacts to the browser container. Executable
permissions are restored explicitly after download; neither raw data nor local
databases enter those artifacts.

## Scope and remaining work

This remains a fixed 2024 NYA-versus-CHA synthetic schedule, not full-roster or
29-opponent gameplay. Existing calibration limitations, neutral pitching and
fixed-order assumptions apply. Loading player metadata does not imply positions
or draft eligibility are enforced. In-memory caching does not persist across tabs
or reloads. All validation runs use local tooling; no physical phone, hosted
Cloudflare route, WAN latency or competitive score verification is established.

Hashed static URLs inherit the existing immutable asset cache rules; HTML
revalidates. The actual local Pages regression suite checks MIME, CSP, cache and
deployment-change behavior. The integrated API tests use Vite preview's loopback
proxy, not a production Pages/Worker route. Eventual hosting must route same-origin
`/api` and retain compatible assets/publications across deployments. A stale
unloaded artifact produces a visible error; reloading obtains the new build.
Web Crypto digest verification requires HTTPS or localhost. No SharedArrayBuffer
or cross-origin isolation is introduced.

Before pricing and the first draft game, agree eligibility/position rules and an
explicit pricing policy using the existing calibration evidence. Expand opponent
configuration only with verified prepared inputs. Then implement the separately
authorized draft slice and production API/static routing with compatibility tests.
No pricing decisions or next-milestone implementation are included here.
