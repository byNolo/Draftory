# Draftory development instructions

- Read [project plan](docs/PROJECT_PLAN.md), [architecture](docs/ARCHITECTURE.md),
  [data specification](docs/DATA_SPEC.md), and [simulation specification](docs/SIMULATION_SPEC.md)
  before changing behavior. Preserve unresolved decisions; do not invent models.
- React owns presentation; Workers owns HTTP/storage access; Python owns offline
  imports/profiles; Rust owns portable baseball computation. Rust must not depend
  on React, Cloudflare, SQL, network access, or host-clock randomness.
- Keep sport rules specific to baseball. Add shared abstractions only when a
  second real consumer needs them. Defer WASM bindings until the adapter is needed.
- Use strict TypeScript, ESLint/Prettier, Rust fmt/Clippy, and Python Ruff/pytest.
  Keep dependencies small; commit npm, Cargo and uv lockfiles when updated.
- Exchange versioned artifacts through `contracts/`; use small synthetic fixtures
  in `data/fixtures/`. Never commit raw releases, generated datasets, local DBs,
  secrets, or copyrighted media. Preserve null values, source IDs and provenance.
- Run affected checks from [README](README.md); run all foundation checks before
  milestone handoff. Add meaningful behavioral tests when functionality exists.
  Simulation changes need deterministic and invariant tests, eventually across
  native/WASM targets. Report unavailable checks honestly.
- Use local Wrangler/D1 commands with `--local`; no resource provisioning,
  deployment or production tables during foundation work. No paid services.
- Keep work within the requested milestone. Foundation does not authorize Lahman
  ingestion, drafting/pricing/authentication, or simulation implementation.
- Review diffs and report architectural decisions. Do not create commits unless
  the user asks.
