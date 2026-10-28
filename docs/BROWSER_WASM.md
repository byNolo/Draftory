# Browser season integration (M5A)

M8C.5: the playable game now uses nine verified representative opponents and a
compact season dashboard. The single-opponent descriptions below retain the
legacy pilot/history. See [current selection, contracts and gameplay](SEASON_DASHBOARD.md).

M7C: the playable game is now at `/`; the diagnostic harness described below
is at `/dev`. See [the game guide](MLB_GAME.md) for current gameplay and result
projection behavior.

M5B extends this foundation with a compact Rust summary path, phase/memory
instrumentation, additional browsers and local Pages delivery tests. See
[current M5B commands and measurement definitions](BROWSER_VALIDATION.md).

React now runs the existing 162-game simulator in a dedicated module Web Worker.
The original path is a developer harness using the bundled fixture. M6B adds
optional [published profile loading](PLAYER_DATA_BROWSER.md), without drafting or final game UI.
The [M4 calibration limitations](../data/validation/season-calibration-v1.md) still
apply: excessive hits/PA/GDP, compressed scoring variance, fixed orders, neutral
pitching, and no automatic extra-inning runner. Browser parity does not establish
historical accuracy. No simulation rules, statistical policies or RNG versions change.

## Boundaries and versions

`crates/sim-wasm` is a separate, small adapter because it isolates wasm-bindgen
and runtime JSON serialization from the portable engine. This follows the optional
adapter layout in [architecture](ARCHITECTURE.md); the core remains unchanged.
The initial adapter was 0.1.0 (M5B is 0.2.0), the engine is 0.4.0, season input/result 1.0.0 and contextual
game input 1.2.0. Existing contracts, source fixtures and goldens are reused.
Actual browser parity, measurements and compatibility limits are recorded in the
[M5A execution report](../data/validation/browser-wasm-v1.md).

The full-result WASM export is `simulate_season_json(string) -> string`, throwing a JSON
error string on failure. Native `simulate_json` exercises the identical
parse/validate/simulate/serialize path. Errors distinguish `invalidJson`
(including wrong JSON types), `invalidInput`, `gameFailed` (with game number),
and `serializationFailed`. No partial results or invented winners are returned.
Rust is responsible for validating input and computing every statistic.

Seeds remain canonical decimal strings at every boundary; do not call `Number`
or parse them into JavaScript numbers. Derived game seeds also remain strings.
JSON counts are bounded by existing engine limits and safe as JS integers.

`apps/web/src/workers/season.worker.ts` owns one cached WASM initialization promise.
The module uses wasm-bindgen `--target web`, a Vite asset URL, and no WASI,
SharedArrayBuffer, threads, runtime fetches within simulation, or external imports.
Loading the bundled WASM and fixture is ordinary static asset loading, not backend
simulation. Generated bindings/WASM are ignored and rebuilt from Cargo.lock.

## Worker protocol and lifecycle

`protocol.ts` defines discriminated request/response envelopes with request IDs:

- `initialize` → `ready` with initialization duration, or structured error.
- `simulate` with versioned `inputJson` and `output: summary | full` → result/error.
- A summary response projects engine/schema/seed, games, W–L and run totals only.
  No arithmetic/statistical model is implemented in React or the worker.
- Full output additionally returns the original result JSON for parity/replay
  diagnostics. The React harness always requests summary, avoiding large event
  histories and repeated root-input snapshots on the main thread.

`SeasonClient` allows one outstanding request, rejects overlap with `busy`, and
matches responses by ID. The worker also rejects requests arriving during async
initialization; once synchronous WASM starts, its event loop cannot process a
second message until completion. The client prevents such hidden queued work.
This is intentionally not a job queue. Errors/message decoding failures settle
pending client requests. Termination rejects pending work and frees the worker;
restart creates a fresh module instance. There is no cooperative cancellation or
per-game progress callback in this milestone. React cleans up on unmount and
handles StrictMode's setup/cleanup cycle.

## Build and run

From the repository root, with Node/npm and Rust installed:

```sh
npm ci
rustup target add wasm32-unknown-unknown
cargo install wasm-bindgen-cli --version 0.2.105 --locked --root target/wasm-tools
npm run build:wasm
npm run dev:web
```

The build script checks the CLI version exactly, preferring `target/wasm-tools/bin`
and falling back to PATH. It builds the release adapter and emits JS/declarations/
WASM into ignored `apps/web/src/wasm`. The CLI and Rust dependency must change
together. No wasm-pack, Vite WASM plugin or application runtime dependency is needed.
Rerun `build:wasm` after editing Rust; Vite does not compile Rust or watch it.

Use the production build for parity and performance:

```sh
cargo build --locked --release --examples
npm run build:wasm
npm run typecheck
npm run lint
npm run build
npx playwright install chromium firefox webkit
npm run test:browser
npm run bench:browser
```

Playwright now starts local Pages on port 4173 and stops it afterward. Linux
hosts may need `npx playwright install --with-deps chromium firefox webkit`. To use an installed
Edge, run `npm run test:edge` / `npm run bench:edge`; no remote browser service
is required. Tests never need raw historical downloads or Cloudflare resources.

## Correctness and performance scope

The parity suite executes native release and real-browser WASM for seeds `0`,
`9007199254740993` and `18446744073709551615`, 162 games each, summary and events.
It compares parsed JSON recursively, independent of property order, including
every game score/seed, player/team statistic, version and contextual event outcome.
Removing event logs and changing only the echoed detail flag must make the two
detail modes identical. Timing lives outside the engine result and is not compared.
Tests also cover typed failures, safety aborts/recovery, one initialization per
worker, overlap rejection, animation-frame responsiveness, UI results/restart
and failed asset loading/recovery. Rust tests compare the adapter directly to core.

Measurements run separately with no speed threshold. Worker timers report:

- `initializationMs`: fetch/compile/instantiate after worker JS has loaded; cached
  and reported unchanged on later runs, not charged to each warm simulation.
- `wasmCallMs`: JSON decode, validation, core simulation, result JSON serialization
  and generated JS/WASM UTF-8 copies. It is not an isolated hot-loop measurement.
- `resultProcessingMs`: JSON parsing and compact summary projection in the worker.
- `workerTotalMs`: request handling, any initialization wait and worker processing.
- Client `roundTripMs`: posting input through receiving result. Subtracting worker
  total estimates combined messaging/scheduling overhead, not pure transfer cost.
- UI `endToEndMs`: click handler through resolved result before React's paint;
  fixture text is bundled and already loaded. Initialization is shown separately.

`measure_boundary` measures the identical native Rust JSON boundary, with file
reading/printing excluded. The browser benchmark stores raw samples and environment
metadata under ignored `target/browser-parity/performance.json`: one first call
and ten subsequent calls per detail mode, identical fixture/seed. Events are
retained and serialized inside WASM but only the compact summary crosses to the
main thread. Neither benchmark is comparable directly to M4's parse/serialization-
excluded loop with 29 opponents. Browser/OS caching may make startup warm; no
network throttling, production CDN or phone performance is inferred.

## Compatibility and next gate

The harness needs WebAssembly, module Workers, ES modules and modern Vite-supported
browsers. Serve over HTTP(S), not `file://`; allow same-origin worker/assets and
serve `.wasm` as `application/wasm` for streaming compilation. This deployment does
not require cross-origin isolation. No broad browser/device support is claimed
from a desktop Chromium test; Firefox, Safari/WebKit and physical mobile devices
need their own execution checks. WASM traps kill that request; restart if the
instance is unusable. There is no memory-budget or adversarial-payload guarantee.

For M5B, reserve work for browser/device coverage, cold/warm startup and memory
measurements, asset loading/cache/CSP behavior on the eventual static host, and
appropriate result payload bounds. Keep the calibration limitations visible and
investigate statistical biases separately; this adapter does not authorize new
game mechanics, backend integration or a draft interface.

Tool references: [wasm-bindgen CLI](https://wasm-bindgen.github.io/wasm-bindgen/reference/cli.html),
[Vite Web Workers](https://vite.dev/guide/features.html#web-workers), and
[Playwright browsers](https://playwright.dev/docs/browsers).

## Published player inputs

The M6B [browser data workflow](PLAYER_DATA_BROWSER.md) adds selective API loading
and compatibility-checked MLB season assembly before the existing worker boundary.
The bundled fixture and native/WASM parity path remain available.
