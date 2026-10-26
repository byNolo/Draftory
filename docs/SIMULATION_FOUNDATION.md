# Rust simulation foundation — contract decision and implementation scope

## Statistical review and proposed contract (written before implementation)

The v1 Python descriptive profile remains unchanged. It separates raw totals,
calculated rates, excluded seasons and quality flags, which is appropriate for
data research. It cannot be passed directly to an event sampler:

- 1B/2B/3B/HR, BB, HBP and SO can be counted when required source facts are complete.
- IBB is included in BB. An eventual intentional-walk decision is contextual;
  never add IBB to BB a second time.
- `otherAtBat = AB - H - SO` includes reaches on error and fielder choices, not
  just outs. It cannot become `battedBallOut` through a field rename.
- SH/SF are observed season counts, but scoring them requires situational plays.
  They cannot be unconditional independent outs without a reviewed model.
- Nulls and inconsistent source facts are retained; excluded years are explicit.
  A future adapter must respect those exclusions and insufficient-data results.
- A mathematically valid one-PA distribution is not a credible projection.
  Shrinkage, minimum opportunities, missingness and era policies remain open.

Add a separate **simulation-input v1.0.0** contract under `contracts/`, rather
than modifying or duplicating the source-data contract. The input describes a
single game, opaque team/batter/profile IDs, two nine-batter orders, prepared
integer outcome weights, a pitching context, canonical decimal u64 seed, detail
level, and versioned rules/advancement policy. Integer weights total 1,000,000;
they describe the eight supported engine event types, not unresolved historical
categories. Only fabricated, explicitly labeled profiles are supplied this
milestone. No Lahman-to-simulation adapter or statistical sampler is authorized.

The engine will validate these prepared inputs, but consume directly supplied
events. Neither profile weights nor pitching context alter scripted events.
The seed is retained losslessly and unused; no RNG algorithm is chosen merely
to exercise it. Game mechanics, counters and advancement use integer operations.

Implement one named `foundation-nine-inning-v1` ruleset: nine innings, standard
top/bottom termination and walk-offs, and empty bases in extra innings. This is
explicitly not a claim to implement current MLB regular-season rules. Automatic
runners and configurable regulation lengths are deferred. Safety limits abort
without producing a winner. The deterministic `conservative-outs-v1` policy is
an illustrative test policy, not a calibrated historical model:

| Event                     | Advancement                                                                                     |
| ------------------------- | ----------------------------------------------------------------------------------------------- |
| Single                    | Third scores; second holds at third with 0/1 outs, scores with 2 outs; first advances to second |
| Double                    | Second/third score; first holds at third with 0/1 outs, scores with 2 outs                      |
| Triple                    | All existing runners score; batter reaches third                                                |
| Home run                  | Batter and all runners score; means an out-of-park HR with completed base touches               |
| Walk/HBP                  | Batter to first; advance only runners forced by occupied first/second/third                     |
| Strikeout/batted-ball out | Exactly one out, runners hold; no sacrifice or double play is implied                           |

Non-HR walk-offs stop at the winning run. Extra-base hit credit is limited by
the winning runner's advancement; HR walk-offs credit every legal run. All base
touches are assumed completed, with no appeals. These choices follow the basic
termination and hit-credit principles in MLB Rules 7.01 and 9.06, with the
unsupported scoring complexities below explicitly excluded. Reference:
[official baseball rules](https://mktg.mlbstatic.com/mlb/official-information/2026-official-baseball-rules.pdf).

## Boundaries

Rust owns only computation and serialization types. Filesystem/terminal I/O,
when used in examples or tests, stays outside the engine. No database, network,
OS clock, browser calls or WASM bindings belong in the library. No generic sport
interface or additional crate is needed. Serde supplies portable JSON-compatible
types; serde_json is a development dependency for fixtures and a native example.

## Deferred mechanics

Errors, fielder choices, sacrifices/tag-ups, double/triple plays, steals, runner
outs, dropped third strikes, interference, substitutions, automatic runners,
pitching statistics/earned runs, park/era adjustments and probabilistic runner
advancement are unsupported. The generic batted-ball out means only an ordinary
one-out play with holding runners. The engine must never silently substitute it
for an unresolved historical event.

This milestone has no real-player sampling, 162-game loop, calibration claim,
frontend/Cloudflare integration or browser adapter. Native/WASM compilation is
not proof of WASM runtime parity; execution parity remains a later validation gate.

## Implemented contracts and API

The three v1.0.0 contracts are
[input](../contracts/simulation-input.schema.json),
[script](../contracts/simulation-script.schema.json), and
[result](../contracts/simulation-result.schema.json). Result/script definitions
reference the input's shared event and identity definitions. Local validators
register their example-domain `$id` values; no schema server is required.

`GameInput` includes:

- `schemaVersion`, `rulesVersion`, a canonical decimal-string `seed` within u64
  range, `detail` (`summary` or `events`) and safety/advancement configuration.
- Named away/home teams with exactly nine ordered `{id, profileId}` batters.
  Opaque IDs use ASCII letters/digits plus `._:-`, start with a letter/digit and
  have at most 128 characters. Team IDs differ; batter IDs are globally unique.
- One to eighteen prepared profiles with unique IDs, a model version, positive
  sample-opportunity count, explicit quality flags and all eight integer weights.
  Profile references must resolve; weights must sum to 1,000,000. Zero or null
  weights cannot stand in for missing fields. Actual zeros are permitted.
- An explicit `scriptedNeutral` pitching context ID. It has no statistical
  effect, as events are externally supplied rather than sampled. Neither this
  context nor the synthetic weights assert league-average calibration.

JSON Schema handles structural constraints. `GameInput::validate` / `Game::new`
also check ID uniqueness, references, seed range and weight sum. Unknown JSON
fields and unsupported events are rejected. The seed is preserved, including
values beyond JavaScript's exact integer range, without conversion to a number.

`replay_game(input, events)` requires exactly one complete game: script exhaustion,
events following the final play, and safety aborts return typed errors. The
incremental API is `Game::new`, `apply_event`, `current_batter`, `snapshot`,
`box_score` and `result`. Mutable state is private; snapshots cannot be loaded
as unchecked resume states. Pure `resolve_bases` supports focused synthetic tests.

`apply_event` returns the supplied and credited event, scorer identities and the
post-transition snapshot. Event metadata names the half that just played;
`stateAfter` can already be in the next half. `outsOnPlay` preserves that play's
out count. Third outs clear bases and reset outs for the next active half. A
completed game's last half may show three outs. Both batting cursors advance on
every PA, including inning-ending and winning appearances.

The configured max inning is 9..65,535 and max PA is 1..1,000,000. A safety limit
reached on an unfinished game sets `aborted` with a reason; the last legal PA and
its counters remain observable. No successful final result or winner is produced.
A genuine game-ending play exactly at the limit still succeeds. Later events
against a final or aborted game return an error without changing state.

Results retain the complete prepared input, engine package version, winner,
away/home score and box scores, inning lines and final snapshot. A home inning
that never began is `null`, distinct from a played zero. Summary output omits
`eventLog`; events output contains the complete ordered PA trace. The mode cannot
change outcomes. There are no RNG draws, profile-rate multiplications, floats or
unordered hash-map iteration in game mechanics.

Counts include PA, AB, hits by type, BB, IBB (a BB subset), HBP, SO, R and RBI,
plus team batting outs and runners left on base. Every run in this supported
event subset has an explicit runner and RBI credit. Unsupported official-scoring
exceptions are not inferred. At a third out or final walk-off, unscored runners
are counted as left on base and terminal bases are cleared. A cut-short non-HR
walk-off includes uncredited would-be scorers in that accounting; it does not
pretend they crossed home before the winning run.

## Fixtures, execution and verification

The shared `data/fixtures/simulation-{input,script,result}.synthetic.json` files
describe an away solo HR followed by a bottom-ninth two-run walk-off double.
The result is home 2–1 after 56 PA, with 27 away/24 home batting outs and two
home runners left on base. All players/profiles are fabricated. Rust checks the
golden output plus independent expected counters; Python validates all schemas,
cross-file consistency, every batter/team total and rejected historical fields.

From the repository root:

```sh
cargo run -p baseball-sim --example replay -- data/fixtures/simulation-input.synthetic.json data/fixtures/simulation-script.synthetic.json
cargo fmt --all -- --check
cargo clippy --locked --workspace --all-targets -- -D warnings
cargo test --locked --workspace
cargo build --locked --workspace
cargo build --locked --workspace --target wasm32-unknown-unknown
```

The native example performs JSON and terminal I/O outside the library. Install
the WASM target with `rustup target add wasm32-unknown-unknown` if needed.
Run the ordinary Python suite from `data/pipeline` with `uv run pytest`, or add
`tests --lahman-source=../raw/lahman-2025` for the pinned-release integration cases.
No Python producer changes or historical imports are required for the new fixtures.

Unit tests exhaust all 8 occupancy masks × 3 out counts × 8 event kinds, checking
runner conservation and uniqueness. Integration tests cover innings, cursor
persistence, force plays, hit credit, RBI, walk-offs, extras, invalid contracts,
script errors, exact safety-limit boundaries, detail/seed independence and 64
generated event sequences with per-PA counter and runner invariants. No property
testing dependency is needed for these finite/enumerated cases.

## Next statistical integration gate

Choose and document the resolution of other AB outcomes and contextual sacrifices
before any adapter exports real prepared weights. Review small-sample and
missingness policies separately from source facts. Only then select a portable
versioned PRNG, integer sampling conversion and model/pitching interaction, with
native/WASM execution golden tests. Preserve the current scripted tests as the
mechanics oracle. No such adapter, sampler, season loop or next milestone is
implemented here.
