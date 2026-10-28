# Shared contracts

M7B adds `mlb-draft-catalog.schema.json` v1.0.0 for the compact static offer
publication: source/dataset/policy identities, fixed experimental prices,
nullable position games and default eligibility. It contains no simulation
probabilities. See [draft workflow](../docs/MLB_DRAFT.md).

M4 extends game input with **v1.2.0**, retaining v1.0/v1.1 behavior. It adds
`contextual-nine-inning-v1`, `retrosheet-contextual-v1`, and an explicit
`otherContact` weight/event. v1.2 requires zero legacy `battedBallOut` mass and
an immutable `contextual-model.schema.json` snapshot. The residual contact category
is no longer named as a guaranteed out. Conditional choices preserve runner
destinations and per-runner RBI credit; result traces add `transitionIndex`.
Optional GDP/error/choice counters appear only when nonzero, preserving legacy
golden JSON. Rules, preparation and source versions remain separate.

`season-input.schema.json` and `season-result.schema.json` v1.0 reuse game/team/
profile/stat definitions. Season bounds, seed derivation, opponent order, home/away
schedule and failure semantics are documented in the
[simulation guide](../docs/SIMULATION_FOUNDATION.md#season-simulation-and-calibration-m4).
Season scores/boxes are ordered **user, opponent**; inning lines and event halves
retain away/home meanings. A root input is stored once, rather than copied into
every game's result. Structural schemas do not replace engine validation of
transition legality, weight sums, version combinations or aggregate consistency.

Language-neutral JSON Schema is the source of truth for exchanged artifacts.
M6A adds `player-data-api.schema.json` v1.0.0 for profile, bounded batch,
player-page and error envelopes. It references the existing prepared profile
definition instead of changing Rust inputs. The committed synthetic SQL/JSON pair
is checked by Python and consumed by local Worker/D1 tests. Dataset configuration,
SQL import manifests and remaining route envelopes are documented in the
[player data guide](../docs/PLAYER_DATA_API.md).

`source-manifest.schema.json` v0.1.0 defines acquisition provenance: original
archive URL, UTC retrieval timestamp, release label, archive SHA-256 and extracted
file SHA-256 values. Retain upstream readme and license files alongside raw inputs
and include them in the file list. A checksum identifies bytes; it does not prove
upstream authenticity unless independently published and verified.

The synthetic fixture under `data/fixtures/` uses deliberately fake checksums and
an invalid example domain; it is not evidence of an acquired Lahman release.
Python tests validate the schema and reject missing/invalid provenance.

The data foundation adds:

- `normalized-lahman-record.schema.json`: definitions for eight JSONL fact files,
  including player, stint, season, team-season, appearance and fielding records.
- `normalized-lahman-manifest.schema.json`: source lock identity, output row counts
  and SHA-256 values for normalized artifacts.
- `batting-profile.schema.json`: preliminary descriptive profiles, explicit
  aggregation/filter requests, sample lineage and insufficient-data results.

The Rust foundation adds `simulation-input.schema.json`,
`simulation-script.schema.json`, and `simulation-result.schema.json` v1.0.0.
Shared event/profile definitions live in the input schema and are referenced by
the script/result schemas. The example-domain `$id` values are identifiers;
validators register these local files and never need to fetch that domain.
Rust enforces semantic constraints JSON Schema cannot express, including weight
sums, u64 seed range, unique identities and profile references. Synthetic input,
event script and golden result are validated by Python and consumed by Rust.
See [simulation foundation](../docs/SIMULATION_FOUNDATION.md) for rules, advancement
policy and API usage.

Statistical integration adds input **v1.1.0**, requiring `sampling.rngVersion`,
`leagueAverage` pitching context and per-profile opaque provenance. Scripted v1.0
inputs remain accepted unchanged; they cannot opt into sampling. The same eight
events and result v1.0 envelope remain in use. A result echoes its complete input,
including the v1.1 metadata needed to replay sampling. Scripted replay can also
apply an event trace to a v1.1 input without consuming randomness.

`simulation-preparation.schema.json` v1.0 describes the offline companion audit:
original descriptive profiles, source release/lock, configurable policy, league
context, excluded sacrifice mass, contact approximation, smoothing and rounding.
It references the existing historical/prepared schemas rather than duplicating
those definitions. Rust never consumes the Lahman-specific audit. Content IDs
link prepared profiles to that audit. See the
[statistical integration policy](../docs/SIMULATION_FOUNDATION.md#statistical-integration-m3).

See [the data workflow](../docs/LAHMAN_DATA_FOUNDATION.md) for field semantics,
canonical profile hashes, examples and restrictions on simulation use. The source
is an official folder, so the pipeline uses its own v1 acquisition receipt and
per-file lock, rather than claiming the archive-oriented v0.1 example is a real
import manifest.

Do not turn the illustrative PA vector or TypeScript interface in the planning
documents into a final simulation contract yet. Add sport-specific schemas and
cross-language fixtures when consumers exist. Breaking artifact changes require
a schema version bump and coordinated fixture/consumer updates; producer, source,
model and rules versions remain separate concepts.

M7C adds `season-batting-summary.schema.json` v1.0.0, a compact projection
of the existing Rust season result. Its `batting` field carries only team ID,
team totals and the nine batter boxes, reusing existing counter definitions.
Full result and summary transports remain supported; input, game events and
opponent boxes are omitted from this projection. The projection has its own
version and does not change engine, rules, RNG or season-result versions.

## M8C.4 defensive contracts

The `defense.schema.json` definitions specify separate defensive profiles,
environment and eight fielding assignments (all 1.0.0). The supplement schema
binds the unchanged 2024 batting publication. Opt-in `defense-game-input` is
1.3.0, `defense-season-input` 1.1.0, and their result schemas 1.1.0. Existing
schemas are unchanged and reject opt-in fields/versions. Runtime validation
additionally checks ID/source/year/model/position links and probability mass.
See [methodology and compatibility](../docs/DEFENSIVE_SIMULATION.md).
