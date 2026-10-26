# Draftory

Draftory is an expandable sports drafting and simulation platform. MLB comes
first: draft historical hitters and eventually simulate a 162-game season using
plate-appearance events. This repository currently contains the development
foundation and Lahman data preparation: a React shell, a local Worker health
endpoint, a deterministic Rust game-state engine, and a reproducible offline Python pipeline.

Scope and statistical decisions live in the [project plan](docs/PROJECT_PLAN.md),
[architecture](docs/ARCHITECTURE.md), [data specification](docs/DATA_SPEC.md), and
[simulation specification](docs/SIMULATION_SPEC.md).

See [CONTRIBUTING.md](CONTRIBUTING.md) for the branch, validation and pull-request workflow.

## Layout and boundaries

```text
apps/web/                React + TypeScript + Vite presentation
services/api/            Cloudflare Worker HTTP boundary and local D1 config
crates/baseball-sim/     Portable scripted baseball game engine and native example
data/pipeline/           uv-managed Lahman acquisition, normalization and profiles
data/fixtures/           Small synthetic shared fixtures
data/validation/         Measured source quality reports
contracts/              Language-neutral schemas and version conventions
infra/d1/migrations/    Migration location; no SQL tables yet
docs/                   Planning documents and foundation/data-source reports
.github/workflows/      Independent JavaScript, Rust, and Python checks
```

Python prepares data offline; the Worker will serve compact artifacts; Rust
processes preloaded inputs; React will display results. Rust remains independent
of all host services. WASM will use a thin adapter in a browser Web Worker later.

## Prerequisites

- Node.js 22.13+ on the 22 LTS line, or Node.js 24+; npm 10+.
- Rust 1.85+ with Cargo, rustfmt and Clippy (`rustup component add rustfmt clippy`).
  Native Windows builds require the appropriate MSVC linker and Windows SDK.
- [uv](https://docs.astral.sh/uv/getting-started/installation/); Python 3.12
  (uv can download it automatically).

No Cloudflare account, cloud resources, paid services or historical datasets are
required for local development. Lockfiles pin dependencies; use the commands below
from the repository root unless another directory is shown.

## JavaScript and local API

```sh
npm ci
npm run types:api
npm run dev:web
```

Open the Vite URL printed in the terminal. In a second terminal:

```sh
npm run dev:api
```

`GET http://127.0.0.1:8787/api/health` returns a JSON health response. This is a
liveness check, not database readiness. Other paths return 404, other methods on
the health route return 405. The web shell does not call the API yet.

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
no migrations to apply or application tables. See [migration notes](infra/d1/migrations/README.md).
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

The library validates prepared inputs and resolves scripted single-game events.
It does not sample historical profiles or simulate seasons. See the
[simulation foundation](docs/SIMULATION_FOUNDATION.md) for contract review,
supported mechanics and scoring limitations. Replay the shared synthetic game:

```sh
cargo run -p baseball-sim --example replay -- data/fixtures/simulation-input.synthetic.json data/fixtures/simulation-script.synthetic.json
```

The native example owns file/terminal I/O; the core has none. To build both targets
without adding browser bindings:

```sh
rustup target add wasm32-unknown-unknown
cargo build --locked --workspace
cargo build --locked --workspace --target wasm32-unknown-unknown
```

The WASM build is not a WASM runtime execution test.

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

## Foundation and data milestones

Repository Foundation is **M0** in the plan. The requested **Milestone 2: Lahman
Data Foundation** covers the plan's M1 import and the explicitly requested
preliminary profile aggregation from M2. The original planning documents and
their numbering are preserved.

The proposed top-level layout is retained. npm workspaces handle JavaScript, a
Cargo workspace handles Rust, and uv manages the offline Python package. No
monorepo task orchestrator or universal sport interface is needed. Empty feature
and adapter packages are deferred. Versioned schemas now cover normalized facts,
output manifests, descriptive batting profiles and the scripted simulation boundary.

See [Lahman source findings](docs/LAHMAN_SOURCE_REVIEW.md) for the initial files,
fields and join hazards. The [data foundation](docs/LAHMAN_DATA_FOUNDATION.md)
documents measured coverage, working commands, profile semantics and remaining
questions. The [Rust foundation](docs/SIMULATION_FOUNDATION.md) now implements
scripted single-game mechanics. Statistical sampling, season simulation and
permanent D1 tables remain deferred.
