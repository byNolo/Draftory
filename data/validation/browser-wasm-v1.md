# M5A browser/WASM execution and parity

Validated 2026-10-26 on Windows ARM64, Snapdragon X Plus X1P42100 / Qualcomm Oryon,
Rust 1.88.0 (`aarch64-pc-windows-msvc`), Node 22.21.0 and Playwright 1.58.2.
The release adapter uses wasm-bindgen/CLI 0.2.105. Engine **0.4.0**, adapter
**0.1.0**, season contracts **1.0.0** and all M4 rule/RNG/model versions are unchanged.
See the [integration guide](../../docs/BROWSER_WASM.md) for design and reproduction.

## Correctness

The production Vite build passed **9 tests in each browser**:

- Chromium headless shell 145.0.7632.6, x64 executable under Windows ARM64 emulation.
- Installed Microsoft Edge 156.0.4314.42, native ARM64 executable, headless.

Native release Rust and browser WASM outputs match exactly for 162-game seasons
with decimal-string seeds `0`, `9007199254740993` and `18446744073709551615`, in
both summary and events modes. Parsed deep comparisons include every game score,
derived seed, W–L total, batter/team statistic, contextual transition, credited event
and post-play snapshot. Summary and detailed results match after removing only
event logs and the echoed detail flag. Timings are outside the compared results.

The bundled NYA/CHA M4 fixture also renders its established **105–57**, **759 runs
scored**, **580 allowed**, **+179 differential** result in React. These are fixed
2024 historical starting orders in a synthetic schedule, not a reconstructed
historical season. Sources/attribution remain in the [M4 report](season-calibration-v1.md)
and [fixture notes](../../crates/baseball-sim/tests/fixtures/README.md).

Tests cover malformed JSON, numeric/overflowing seeds, safety-aborted games with
explicit game number, recovery, one initialization per worker, overlap rejection,
main-thread animation during a 1,000-game detailed run, UI restart, failed WASM
loading/recovery, stopping during initialization, and unavailable Worker support.
The responsiveness check counts animation frames only while a single worker
request is pending, excluding frames between separate test-driver calls.
An initial Chromium large-seed case timed out at 60 seconds without a reported
mismatch. Its traced rerun passed in 5.8 seconds; the complete subsequent suite
passed (9/9), as did Edge (9/9). This is disclosed rather than counted as parity
evidence from a failed run. No test retries or relaxed equality criteria were added.

## Performance (separate from correctness)

The exact same fixture/seed is run eleven times per detail mode: one first call,
then ten subsequent calls. Native and WASM both include JSON parsing, validation,
simulation and result serialization; native file reading/printing is excluded.
WASM also includes generated UTF-8 boundary copies. Native release is ARM64 in
both comparisons. Warm values below are medians of the ten subsequent calls,
not an extrapolation or confidence interval. Events-mode first calls occur after
the summary benchmark in the already initialized worker.

| Environment           | Detail  | Native first / warm JSON boundary | WASM first / warm JSON boundary | Warm worker result processing | Warm round trip |
| --------------------- | ------- | --------------------------------- | ------------------------------- | ----------------------------- | --------------- |
| Chromium x64/emulated | summary | 79.1 / 58.2 ms                    | 490.2 / 187.4 ms                | 11.1 ms                       | 200.1 ms        |
| Chromium x64/emulated | events  | 88.7 / 103.3 ms                   | 288.2 / 190.2 ms                | 74.8 ms                       | 272.5 ms        |
| Edge ARM64            | summary | 59.1 / 47.9 ms                    | 142.0 / 73.3 ms                 | 7.2 ms                        | 79.3 ms         |
| Edge ARM64            | events  | 100.5 / 106.0 ms                  | 303.0 / 136.6 ms                | 47.3 ms                       | 180.1 ms        |

WASM fetch/compile/instantiate measured **39.8 ms Chromium / 53.5 ms Edge**;
observed worker creation through ready response measured **119.3 / 104.3 ms**.
The latter includes worker script loading and test-driver scheduling; browser/OS
caches may already be warm. No cold network/cache claim is made. Warm combined
messaging/scheduling estimates were 0.8–1.2 ms Chromium and 0.55–0.65 ms Edge.
These are round-trip-minus-worker estimates, not isolated transfer measurements.

Full serialized results contain **912,183 bytes summary / 5,880,585 bytes events**.
The benchmark, like the UI, retains/serializes the complete requested result inside
WASM but sends only the compact summary to the main thread. Full event JSON is
transferred separately by the parity tests. No isolated Rust serialization timer
or full-trace transfer benchmark is claimed. The release WASM asset is **366,194
bytes** (Vite gzip estimate **125.27 kB**); worker JS is **4,294 bytes**. The app JS
is **341,817 bytes**, including React and the bundled fixture.

The fixture has one opponent and eighteen profiles; M4's 29-opponent loop excluded
JSON parsing/serialization, so its measurements are not directly comparable.
The x64 emulation, JIT/allocator warmup and short sample make cross-browser ratios
descriptive only. No optimization or browser speed gate was introduced.
Raw measurements are ignored under `target/browser-parity/performance.json`;
this run's two snapshots were retained locally as `performance-chromium.json`
and `performance-msedge.json`. Re-running the benchmark replaces performance.json.

## Build/check results and limits

- Rust formatting, host and WASM Clippy (`-D warnings`), **50 native Rust tests**,
  native release examples, release WASM compilation and binding generation pass.
- TypeScript (including browser tests), ESLint, Prettier and Vite production build
  pass. CI now builds the pinned bindings and runs Chromium parity against native
  release output; the hosted CI workflow itself was not executed locally.
- Existing Python Ruff/format and **125 tests** pass; **7 optional source-data
  integrations skip** without explicit source-directory options. Core contracts,
  historical data, Python transformations and statistical models are unchanged.
- Wrangler dry-run and local D1 `SELECT 1` pass; no resources or data integrations
  were added or provisioned.

Desktop headless Chromium/Edge execution does not validate Firefox, Safari/WebKit,
physical phones, memory ceilings, production CDN/cache/CSP behavior or hostile
payloads. Module Workers, modern WebAssembly and HTTP(S) asset serving are required;
no SharedArrayBuffer/cross-origin isolation is needed. A worker can be terminated
and recreated, but there is no mid-season cooperative pause/resume or progress API.

Historical accuracy remains limited exactly as documented in M4: excessive hits,
PA and GDP, low score variance, fixed lineups and standardized pitching. Exact
native/WASM agreement is an execution result, not a calibration improvement.

Recommended M5B work: physical mobile and Firefox/Safari parity, controlled cold/warm
startup and memory tests, static-host asset/cache/CSP verification, and measured
input/result size budgets. No M5B, backend integration or new baseball rules are
implemented here.
