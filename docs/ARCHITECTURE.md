# Draftory — Technical Architecture

**Version:** 0.1 (2026-10-25)  
**Status:** Proposed implementation baseline; document deviations as decisions are tested.

## 1. Design goals

- Run ordinary baseball simulations in browsers (including mobile) without scaling per-user simulation CPU on the backend.
- Keep Rust simulation portable: native executable/test runner and `wasm32` build use the same sport rules.
- Separate historical ingestion, projection/profile creation, game-mode rules, simulation, storage and display.
- Download **only the player profiles and shared opponent/context data required** for the active game, not the raw historical database.
- Keep cloud hosting as close to free as practical; no assumption that free-tier quotas will always suffice.
- Make later sports and game modes possible without imposing an artificial universal simulation model.

## 2. High-level runtime flow

```text
Official free datasets (Lahman; optionally Retrosheet)
      |
      v
Python ETL: verify release -> normalize -> calculate/validate profiles
      |
      +--> versioned artifacts / test fixtures
      |
      v
Cloudflare D1: players, appearances, aggregates, profile versions, game configs
      ^
      |
Cloudflare Worker API: authorized profile lookup, random offers, versioned snapshots
      ^
      | HTTPS, small JSON payloads (or measured binary format later)
      v
React + TypeScript (Vite), Cloudflare static hosting
      |
      v
Browser Web Worker --> Rust/WASM simulation (deterministic, no runtime fetch)
      |
      v
Season summary, player lines, per-game scores, optional replay records -> React
```

**Ownership:** Python owns imports and projections; D1 stores normalized/queryable records; Worker owns API and draft state; Rust owns baseball rules and simulation; React owns presentation. None of the Rust simulation logic should depend on Cloudflare or the DOM.

**M7B developer-playtest adjustment:** ephemeral draft state lives locally in a
pure MLB TypeScript module, separate from React. A versioned static catalog
supplies metadata/prices; the Worker supplies selected simulation profiles.
Server-owned sessions remain a future option. This avoids premature session
endpoints/storage for a casual prototype with no verification requirement.
See [draft rules and replay](MLB_DRAFT.md).

**M8A hosting preparation:** one Workers Static Assets application serves the
Vite build, with `/api` and `/api/*` routed to the existing read-only Worker/D1
API. Matched assets bypass application code; unmatched routes use a strict 404
handler with non-cacheable errors. The separate alpha configuration has no public
route enabled by default. Hosted account/database selection, Access policy and
deployment require approval; see [alpha deployment](ALPHA_DEPLOYMENT.md).

## 3. Proposed repository layout

```text
draftory/
├── apps/
│   └── web/                       # React + TS + Vite
│       ├── src/features/          # gameplay, simulator harness, results
│       ├── src/workers/           # browser worker and WASM bridge
│       └── src/lib/api/           # typed API client
├── services/
│   └── api/                       # Cloudflare Worker HTTP API
├── crates/
│   ├── baseball-sim/              # portable Rust engine and tests
│   │   ├── src/{profile,pa,bases,inning,game,season,stats,rng}.rs
│   │   └── tests/
│   └── sim-wasm/                  # thin wasm-bindgen adapter (when needed)
├── data/
│   ├── pipeline/                  # Python ETL and projection generation
│   ├── validation/                # calibration and statistical reports
│   └── fixtures/                  # small, legal-to-ship example inputs
├── contracts/                     # JSON schemas / fixture schemas / versions
├── infra/
│   └── d1/migrations/             # schema + import scripts
├── docs/
│   ├── PROJECT_PLAN.md
│   ├── ARCHITECTURE.md
│   ├── DATA_SPEC.md
│   └── SIMULATION_SPEC.md
└── README.md
```

This is a **suggested shape**, not a requirement to create empty directories or excessive packages. Begin with the minimum to support M0/M1; split crates only when the WASM interface requires it.

## 4. Modules and contracts

### 4.1 Python data pipeline

- Read **pinned** official releases; verify checksum when available and record retrieval date.
- Parse exact schemas from the bundled official readme, not guessed field lists.
- Preserve original player/team/year/stint/source IDs and raw records or provenance reference.
- Normalize batting/fielding information; produce versioned statistical profiles and quality flags.
- Output compact, deterministic serialized profiles and schema-conformance test fixtures.
- Run offline/batch; never run Python in a user's gameplay request.

### 4.2 Rust baseball simulator

- Pure computation: `SimulationInput -> SimulationResult`.
- No SQL, HTTP, JS callbacks, wall-clock randomness, I/O or runtime profile fetching inside simulation loops.
- Own a stable seeded PRNG with portable, documented algorithm; don't rely on thread/platform defaults.
- Expose both one-game and season functions; optionally choose summary vs event log output.
- Produce a machine-readable engine version; store version and profile dataset version with each run.
- In WASM, run inside a **Web Worker** and return aggregated batches/progress rather than individual event callbacks.

Illustrative conceptual interface (subject to implementation):

```ts
interface SimulationInput {
  schemaVersion: string;
  engineVersion: string;
  profileSetVersion: string;
  rulesetId: string;
  seed: string;                 // encoded 64-bit seed, no JS number precision loss
  userLineup: BatterProfile[];   // nine selected players and batting order
  opponentSchedule: OpponentGameContext[];
  pitchingContext: PitchingContext;
  detail: "summary" | "events";
}

interface SimulationResult {
  schemaVersion: string;
  engineVersion: string;
  seed: string;
  record: { wins: number; losses: number };
  games: GameSummary[];
  batterTotals: BatterSeasonLine[];
  runTotals: { scored: number; allowed: number };
  eventLog?: GameEvent[];
}
```

**Don't implement this TypeScript sketch as the canonical schema.** Define a language-neutral contract under `contracts/`, write fixtures for Python/Rust/TS, then generate or validate bindings where practical. Avoid silently changing fields after clients exist.

### 4.3 Cloudflare Worker API

Potential endpoints (future, not all required in M0–M4):

- `GET /api/config/:id` — versioned mode/ruleset/pool metadata.
- `POST /api/draft/:id/offer` — eligible randomized player offers with server-side constraints when the game UI exists.
- `POST /api/profiles/batch` — return requested authorized profiles in a bounded batch.
- `GET /api/simulation-context/:id` — small opponent schedule / pitching environment package, cached by version.
- `POST /api/results` — optional saved casual run; **do not represent client-submitted results as verified**.

All API routes must validate input, cap batch sizes and response sizes, use parameterized D1 queries, and avoid full-table random sorting. Return immutable version IDs and appropriate cache headers for public historical profiles. For MVP no paid compute service or server-sim endpoint is needed.

### 4.4 D1 persistence

Suggested logical areas (not final migration):

- `players` and `source_player_ids`
- `teams` / `franchises`, `team_seasons`
- `player_season_stints` and normalized batting / position appearance facts
- `profile_definitions` and `compiled_profiles` with producer, source and schema versions
- `game_configs` and eligible pool snapshots
- optional `draft_sessions`, `saved_runs`

Follow physical schema design only after inspecting source field coverage and testing queries. Avoid storing millions of redundant profile combinations by default; compute/select useful configurations offline or on demand through controlled pipelines.

## 5. Cache and payload strategy

1. Static React JS/CSS and WASM: CDN cached with content hashes.
2. Profile API: compact numerical probability arrays plus IDs and metadata. Transport JSON for the first implementation; consider binary only after measuring.
3. Download just the draft's visible players as offered. At simulation start fetch selected profiles not already cached.
4. Load a **versioned opponent/schedule context** once per ruleset/season and cache it separately across games.
5. Cache fetched profiles in memory during the session; optional browser cache/IndexedDB only if it demonstrably improves repeat play. Internet is required; **offline operation is not a requirement**.
6. Explicitly define how old cached profiles are invalidated when versions change.

## 6. Simulation execution strategy

- Default: browser Web Worker loads WASM and accepts a bounded, fully resolved simulation input.
- UI displays load/simulation progress and offers cancellation via worker termination or cooperative cancellation.
- No UI blocking loops, per-PA JS/WASM calls or string-heavy logs in the hot path.
- Mobile support is a launch constraint; test actual mid/low-tier Android devices, desktop browsers and memory ceilings.
- Keep a **native Rust CLI benchmark/test harness**; do not create server compute as an MVP dependency.
- Future verification: replay selected competitive runs on a separate self-hosted Rust service using identical versioned inputs and seeds. No implementation now.

## 7. Multi-sport and multi-game design

Keep platform-level concepts abstract but small:

- `GameMode` defines the offering/roster/pricing constraints and how it asks a sport for an eligible player pool and simulator result.
- `SportModule` owns player profiles, eligible positions, ratings, simulation rules, and output schema.
- `SimulationResult` has shared top-level metadata, plus sport-specific statistics and game details.
- UI uses sport-specific result components when necessary; don't force MLB `HR/OPS` into a universal sports stat interface.

Introduce a second sport or game mode only after MLB workflows demonstrate where abstraction is genuinely useful.

## 8. Versions, reproducibility and compatibility

Every saved or shareable run should contain:

- input schema version, game mode/ruleset version
- player profile IDs + immutable profile snapshot/version
- opponent/schedule/pitching context version
- Rust engine version + random generator version
- seed, ordered lineup and simulation settings
- checksum/hash of canonicalized input for diagnostics (not anti-cheat proof)

Use integer/defined rounding logic or documented floating-point operations with cross-target regression tests. *Reproducibility is a tested property*, not an assumption merely because a seed exists.

## 9. Security, cost and operations

- Assume the browser client and results are untrusted; casual saved outcomes may be forged.
- Do not place secrets in WASM, JS bundles or client-accessible payloads.
- Deploy small Worker functions for API and input validation; revisit current Cloudflare quota/pricing before deployment.
- Account and authentication are optional initially; protect write endpoints from abuse if added.
- Log request failures, import versions, aggregate timings and schema errors without recording sensitive personal information unnecessarily.
- Back up the normalized DB/artifacts and retain deterministic import scripts; D1 is not the original source of truth for public historical data.

## 10. Developer workflow and gates

- Format/lint/test Python, Rust and TS in CI as they are introduced.
- Fixtures are the bridge between languages: identical sample profile decodes and simulates in native Rust/WASM.
- Keep small commits by milestone; review schema changes before bulk importing data.
- Do not add premature microservices, AI analysis dependencies, queueing systems or production user accounts.

## 11. References

- Cloudflare Workers: https://developers.cloudflare.com/workers/
- D1: https://developers.cloudflare.com/d1/
- Rust/WASM wasm-bindgen: https://rustwasm.github.io/wasm-bindgen/
- Web Workers: https://developer.mozilla.org/en-US/docs/Web/API/Web_Workers_API
- See [DATA_SPEC.md](DATA_SPEC.md) and [SIMULATION_SPEC.md](SIMULATION_SPEC.md).


M8C.5 reuses the Rust scheduler and adds a Python-produced, immutable static
opponent pool plus a compact Rust dashboard projection. React owns filtering,
charts and presentation; no D1/API schema changes. See [season dashboard](SEASON_DASHBOARD.md).
