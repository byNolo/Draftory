# Draftory

Draftory is an expandable sports drafting and simulation platform. The first
playable game drafts nine real 2024 MLB hitters within 90 fictional credits and
simulates a 162-game season in a Rust/WASM Web Worker. Review your record and
individual batting totals, replay a season or start another draft. Prices and
the simulation remain experimental; results are not real-world predictions.

The repository also includes a local Cloudflare Worker player API, a reproducible
offline Python pipeline and an independently testable native Rust simulator.
See [the playable game guide](docs/MLB_GAME.md) and
[M7C validation](data/validation/mlb-game-v1.md).
Scope and statistical decisions live in the [project plan](docs/PROJECT_PLAN.md),
[architecture](docs/ARCHITECTURE.md), [data specification](docs/DATA_SPEC.md), and
[simulation specification](docs/SIMULATION_SPEC.md).

See [CONTRIBUTING.md](CONTRIBUTING.md) for the branch, validation and pull-request workflow.

## Layout and boundaries

```text
apps/web/                React + TypeScript + Vite presentation
services/api/            Cloudflare Worker HTTP boundary and local D1 config
crates/baseball-sim/     Portable scripted/sampled baseball engine and native examples
crates/sim-wasm/         Thin JSON/wasm-bindgen adapter; no baseball rules
data/pipeline/           Lahman acquisition, normalization, profiles and preparation
data/fixtures/           Small synthetic and verified historical test excerpts
data/validation/         Measured source quality reports
contracts/              Language-neutral schemas and version conventions
infra/d1/migrations/    Versioned local player-data schema
docs/                   Planning documents and foundation/data-source reports
.github/workflows/      Independent JavaScript, Rust, and Python checks
```

Python prepares data offline; the Worker serves published profiles; Rust
processes preloaded inputs; React displays results. Rust remains independent
of all host services. WASM runs through a thin adapter in a dedicated browser Web Worker.

## Prerequisites

- Node.js 22.13+ on the 22 LTS line, or Node.js 24+; npm 10+.
- Rust 1.85+ with Cargo, rustfmt and Clippy (`rustup component add rustfmt clippy`).
  Native Windows builds require the appropriate MSVC linker and Windows SDK.
- For the web harness: `wasm32-unknown-unknown` and wasm-bindgen CLI **0.2.105**
  (matching the adapter's pinned dependency); setup commands below.
- [uv](https://docs.astral.sh/uv/getting-started/installation/); Python 3.12
  (uv can download it automatically).

No Cloudflare account, cloud resources or paid services are required. The
playable game needs the locally imported verified 2024 publication; diagnostic
fixture runs and ordinary CI do not need the raw historical datasets. Lockfiles pin dependencies; use the commands below
from the repository root unless another directory is shown.

## JavaScript and local API

```sh
npm ci
rustup target add wasm32-unknown-unknown
cargo install wasm-bindgen-cli --version 0.2.105 --locked --root target/wasm-tools
npm run build:wasm
npm run types:api
npm run build:pilot
npm run dev:web
```

Open the Vite URL printed in the terminal for the game. First import the verified
2024 publication following the API instructions below. Open `/dev` for the
diagnostic harness, whose bundled 162-game fixture works without that import. Rebuild WASM after Rust adapter/core changes.
See [browser integration](docs/BROWSER_WASM.md) for parity tests and instrumentation.
In a second terminal:

```sh
npm run dev:api
```

`GET http://127.0.0.1:8787/api/health` returns a JSON liveness response.
M6A adds read-only season/dataset catalogs, player/position metadata, and bounded
single/batch prepared-profile retrieval. Apply local migrations before data routes:

```sh
npm run d1:migrate --workspace @draftory/api
npm run test:api
```

The API tests populate an isolated synthetic database automatically. For the real
2024 subset, follow the [export/import and API guide](docs/PLAYER_DATA_API.md).
Measured counts, storage and query findings are in the
[M6A report](data/validation/player-data-v1.md). The harness also loads nine real
2024 profiles through the local API and simulates using the verified M4 opponent
and transition model. See the [M6B workflow](docs/PLAYER_DATA_BROWSER.md) for setup,
caching, compatibility and integration tests, and the
[M6B report](data/validation/player-data-browser-v1.md) for measurements.

```sh
npm run build
npm run typecheck
npm run lint
npm run format:check
npm run check:api
npm run d1:check --workspace @draftory/api
```

`check:api` bundles the Worker with `wrangler deploy --dry-run`; it does not deploy.
The D1 check executes `SELECT 1` locally. Its all-zero database ID is a local-only
sentinel. Wrangler persists local state under `services/api/.wrangler/`. There are
versioned player-data migrations. See [migration notes](infra/d1/migrations/README.md).
`worker-configuration.d.ts` is generated and checked in; regenerate it after config
or Wrangler updates with `npm run types:api`.

The root `undici` override keeps Wrangler's transitive HTTP client on a patched
7.x release. Remove it when Wrangler's dependency tree supplies that patch itself.

## Rust

```sh
cargo fmt --all -- --check
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace
```

The library validates prepared inputs and runs scripted or seeded sampled games.
Python prepares historical profiles with an explicit, uncalibrated research policy.
See the
[simulation foundation](docs/SIMULATION_FOUNDATION.md) for contract review,
supported mechanics and scoring limitations. Replay the shared synthetic game:

```sh
cargo run -p baseball-sim --example replay -- data/fixtures/simulation-input.synthetic.json data/fixtures/simulation-script.synthetic.json
cargo run -p baseball-sim --example simulate -- crates/baseball-sim/tests/fixtures/lahman-modern-game.json
cargo run --locked --release --example season -- crates/baseball-sim/tests/fixtures/season-modern-2024.json
```

The second command uses a small attributed Judge/Soto fixture with repeated players
to exercise the boundary, not authentic team rosters. See the
[statistical integration workflow](docs/SIMULATION_FOUNDATION.md#statistical-integration-m3)
for preparation commands, model limitations, RNG version and benchmark usage.

The native example owns file/terminal I/O; the core has none. To build both targets:

```sh
rustup target add wasm32-unknown-unknown
cargo build --locked --workspace
cargo build --locked --workspace --target wasm32-unknown-unknown
```

Compilation alone is not a WASM runtime execution test. M5A runs real-browser
parity against native release output, including complete event traces:

```sh
cargo build --locked --release --examples
npm run build:wasm
npm run build
npx playwright install chromium firefox webkit
npm run test:browser
npm run bench:browser
```

Browser tests use the production Vite build. Detailed measurement scope and browser
compatibility are documented in [the M5B guide](docs/BROWSER_VALIDATION.md).
`test:browser` covers Chromium, Firefox, WebKit, mobile emulation and a local
deployment-change test. Installed Edge is optional via `npm run test:edge`;
`npm run bench:edge` measures that browser. Tests use local Pages and the production
headers without provisioning resources. Phone LAN smoke-test instructions and
the limits of emulation are in the M5B guide.

M4 adds bounded, seeded 162-game seasons and an offline Python-driven historical
comparison workflow. The season fixture uses verified 2024 NYA/CHA starting
orders, held fixed for a synthetic schedule; it does not reproduce an MLB season.
See [season and calibration workflow](docs/SIMULATION_FOUNDATION.md#season-simulation-and-calibration-m4)
and the [calibration report](data/validation/season-calibration-v1.md) for source
splits, supported contextual mechanics, measured biases and benchmarks.

## Python

```sh
cd data/pipeline
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Use `uv add` / `uv add --dev` to change dependencies and review `uv.lock`. The
pipeline has no third-party runtime dependencies. Synthetic tests run without
downloads; optional integration tests verify the official pinned release locally.
See the [Lahman data workflow](docs/LAHMAN_DATA_FOUNDATION.md) for acquisition,
normalization, profile generation, contracts and statistical limitations.

M7A adds an offline [valuation and eligibility research workflow](docs/PLAYER_VALUATION_RESEARCH.md)
over the verified 2024 publication and unchanged native simulator. Its
[measured report](data/validation/valuation-eligibility-v1.md) compares eligibility,
offensive value, illustrative prices and random-offer feasibility. These are
research outputs; draft rules and prices remain provisional.

M7B adds a randomized MLB draft playtest below the existing harnesses: 90 credits,
nine positions and up to three safe choices per round. Drafting loads a compact
static catalog; simulating the finished roster requires the compatible local
player-data API/import. See [draft setup and replay](docs/MLB_DRAFT.md) and
[playtest results](data/validation/draft-engine-v1.md). Rules and prices remain
versioned experiments, without accounts or server sessions.

## Foundation and data milestones

Repository Foundation is **M0** in the plan. The requested **Milestone 2: Lahman
Data Foundation** covers the plan's M1 import and the explicitly requested
preliminary profile aggregation from M2. The original planning documents and
their numbering are preserved.

The proposed top-level layout is retained. npm workspaces handle JavaScript, a
Cargo workspace handles Rust, and uv manages the offline Python package. No
monorepo task orchestrator or universal sport interface is needed. Empty feature
and adapter packages are deferred. Versioned schemas now cover normalized facts,
output manifests, descriptive batting profiles and the prepared simulation boundary.

See [Lahman source findings](docs/LAHMAN_SOURCE_REVIEW.md) for the initial files,
fields and join hazards. The [data foundation](docs/LAHMAN_DATA_FOUNDATION.md)
documents measured coverage, working commands, profile semantics and remaining
questions. The [Rust foundation](docs/SIMULATION_FOUNDATION.md) now implements
scripted and sampled games plus season orchestration. Historical calibration is
an ongoing measured process; application tables beyond the M6A player publication remain deferred.
