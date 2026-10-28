# Rust simulation foundation — contract decision and implementation scope

M8C.4 adds opt-in [position-specific error avoidance](DEFENSIVE_SIMULATION.md)
under new input/rules/model versions. Legacy inputs, RNG and golden behavior below
remain unchanged. Only error/ordinary-out mass transfers are supported; no range,
individual GDP, catcher specialties or pitcher ratings are added.

The original foundation review below records the scripted milestone. Statistical
integration is now implemented in [M3](#statistical-integration-m3); its explicit
research policies supersede the earlier deferred adapter/sampling gate. The
historical data contract remains unchanged. M4 below adds opt-in contextual
mechanics and seasons while preserving the legacy rules and replay behavior.
M5A adds a separate [browser/WASM adapter and developer harness](BROWSER_WASM.md);
the milestone records below retain their original scope and assumptions.

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

## Statistical integration (M3)

Python now owns `draftory_data.simulation`: validation and preparation of existing
descriptive profiles. Rust owns a separate `sampling` module and `simulate_game`.
No services, database, frontend, roster system or season orchestration were added.
The native `simulate` and `measure` examples own file/terminal/time measurement I/O;
the library still has no host services or floating-point sampling branches.

### Taxonomy and deliberate approximation

| Historical category        | Prepared event/policy                                                           |
| -------------------------- | ------------------------------------------------------------------------------- |
| Singles/doubles/triples/HR | Corresponding mutually exclusive hit type                                       |
| BB, including IBB          | One generic walk; sampled `intentional: false`; never add IBB again             |
| HBP, SO                    | Corresponding event; missing values reject preparation                          |
| `otherAtBat = AB - H - SO` | Unresolved contact; strict policy rejects it                                    |
| SH/SF                      | Condition on no sacrifice; report both excluded masses and retained denominator |

Lahman cannot separate errors, fielder choices, double plays and ordinary contact
outs from this residual. The adapter therefore **defaults to rejection**. The CLI
requires explicit `--contact-policy ordinary-out-proxy-v1` to use a lossy research
approximation: all retained residual contact receives the engine's single-out,
runners-hold event. This is not a claim that the historical residual counts outs.
Its conditional proxy mass is recorded separately from historical facts. No
unobserved error or double-play frequency is invented. This minimal policy avoids
expanding scoring mechanics around unidentifiable probabilities; a supported
error/choice/multiple-out taxonomy with defensible frequencies remains necessary
for calibration. A zero-prior vector can retain genuine zero probabilities.

SH/SF are removed **before** smoothing, separately for player and league. Every
remaining rate is divided by its retained mass; the companion records this
conditioning rather than silently dropping PA. Thus simulated PA and AB do not
reproduce original denominators, and sacrifice RBIs are absent. Historical
profiles/totals remain intact in the audit. Walk intent is not inferred from
context; moving observed IBB into generic BB creates another explicit bias.
IBB appear as zero in simulated box scores, not as an assertion about source data.

### Preparation, policy and pitching context

`lahman-pa-adapter-v1` accepts existing aggregate, arithmetic season-rate mean and
component-median profiles, including season, team, franchise and year filters.
It reproduces each input against the verified pinned release using the existing
profile producer, comparing the complete canonical object and its hash. A modified
field, missing category, unsupported version, null, inconsistent count or altered
probability cannot pass by merely recalculating a user-supplied hash. This offline
step intentionally requires the verified source directory. Python has no new
runtime dependencies; historical producer/schema semantics remain unchanged.

Initial `modern-neutral-v1` defaults (all included in its content-derived ID):

- AL/NL seasons in 2000..2025. The recorded-season window can be configured within
  1954..2025; actual required-field completeness is always checked. There is no
  assertion that all records in the wider window are usable.
- Any excluded selected season or insufficient profile rejects preparation. Select
  a complete year range rather than silently simulating a partial career.
- Minimum confidence proxy: 50 PA. Aggregate profiles use pooled PA; equal-season
  mean/median use the **smallest included season PA**, so a large season cannot
  conceal a tiny season carrying equal influence. This is conservative confidence
  weighting, not a statistical effective-sample-size estimate.
- Shrinkage: `N/(N+K) * player + K/(N+K) * league`, with `K=200` prior PA. `N`
  includes original SH/SF opportunities; it is the confidence proxy, not the
  conditional simulated denominator. Set `--prior-pa 0` to disable smoothing.
  The threshold and prior strength are provisional engineering choices, not fitted
  hyperparameters. Shrinkage stabilizes small samples but understates genuine
  extremes; minimum rejection alone would leave noisy accepted samples untouched.

The default league baseline pools verified, complete, positive-PA AL/NL
player-seasons in 2025, weighted by opportunities, with every stint included once.
Any bad/missing stint excludes the whole player-season. Exclusions list exact
missing fields, source rows, quality flags or zero PA. No minimum-player PA filter
is imposed on the league pool. Context years are configurable inside the policy
window; its source, years, counts and exclusions are hashed into `contextId`.

This `leagueAverage` environment means a common neutral opponent: prepared batter
rates apply directly, shrunk toward that reference pool. **Do not multiply by
league rates again.** It models neither an individual pitcher nor a log5 matchup.
Using a different year's baseline does not adjust the batter's era, park or league;
even same-year profiles are not park-neutral. The fixture contains elite hitters
repeated across batting slots, so its scores are not league scoring expectations.

### Contracts, determinism and sampling

Input v1.1 adds a required `sampling: {rngVersion: "splitmix64-v1"}` plus opaque
per-profile provenance (`playerId`, source-profile/source/policy/context IDs and
transformation version). Provenance context must match the game's context. Source
release text and checksum remain in the companion audit, linked by `sourceId`.
v1.0 scripted inputs remain unchanged. Result v1.0 still echoes the complete
input; package/engine version is now 0.3.0. Summary/events modes consume identical
random draws. A sampled event log can be replayed through the existing scripted
API to obtain the same result.

Prepared weights total exactly 1,000,000. Python interprets serialized decimal
rates as exact rational numbers, blends rationally, floors scaled weights and
distributes remainders by descending fraction, ties in this order: single,
double, triple, homeRun, walk, hitByPitch, strikeout, battedBallOut. Each conversion
error is less than one millionth; the audit records the maximum. True zeros do not
gain tickets from rounding (smoothing can intentionally supply prior mass).

Rust uses [Vigna's public-domain SplitMix64 reference](https://prng.di.unimi.it/splitmix64.c),
with state initially equal to the canonical decimal u64 seed; zero is valid.
Every draw increments state by `0x9e3779b97f4a7c15`, then uses the reference
xor-shifts and wrapping multiplications. Golden output tests freeze this sequence.
To select a ticket, reject raw draws below `(-1_000_000 mod 2^64) % 1_000_000`
and then take `% 1_000_000`. Cumulative half-open intervals in the fixed order
above select an event. This eliminates modulo bias and skips zero-weight events.
Rejection can consume extra raw draws; the algorithm/version and seed define that
behavior. No random base advancement was added. SplitMix64 is not cryptographic
and is not an anti-cheat or parallel-stream design. Future algorithm/mapping
changes require new version identifiers and goldens.

### Run preparation, games and measurements

Fetch/verify and produce profiles using [the data workflow](LAHMAN_DATA_FOUNDATION.md).
For example, from `data/pipeline`, in PowerShell:

```powershell
uv run draftory-data profile --source-dir ../raw/lahman-2025 --player judgeaa01 --leagues AL NL --start-year 2025 --end-year 2025 --output ../processed/judge2025.json
uv run draftory-data profile --source-dir ../raw/lahman-2025 --player sotoju01 --leagues AL NL --start-year 2025 --end-year 2025 --output ../processed/soto2025.json
$j = '../processed/judge2025.json'
$s = '../processed/soto2025.json'
$awayProfiles = @($j,$s,$j,$s,$j,$s,$j,$s,$j)
$homeProfiles = @($s,$j,$s,$j,$s,$j,$s,$j,$s)
uv run draftory-data prepare-game --source-dir ../raw/lahman-2025 --away-profiles $awayProfiles --home-profiles $homeProfiles --contact-policy ordinary-out-proxy-v1 --seed 2025 --detail events --output ../processed/modern-game.json
```

Each team requires exactly nine **ordered** profile paths. Repeated players are
allowed for boundary testing and receive distinct batter-instance IDs. This is
not roster validation. The output is standard input v1.1 plus a sibling
`modern-game.preparation.json` audit v1.0 (full historical profiles, source, policy,
context and per-profile mappings). `inputId` hashes the canonical game input;
prepared IDs hash prepared metadata/weights. Keep both artifacts together.

From the repository root, no raw data is needed to run the small verified fixture:

```sh
cargo run --locked --release --example simulate -- crates/baseball-sim/tests/fixtures/lahman-modern-game.json
cargo run --locked --release --example measure -- crates/baseball-sim/tests/fixtures/lahman-modern-game.json 10000000 5000
```

The benchmark parses once, samples the first profile, then times one complete
summary game and repeated games using seeds 0..4999. Timed games include input
cloning, validation, distribution setup, state transitions and result allocation;
JSON parsing/serialization, file I/O and statistical preparation are outside those
loops. Detailed tracing is excluded from the game benchmark. There is no claim of
steady-state latency from a single first-call timing. Measurements are descriptive,
not tests or performance gates. Reorder the profile array to measure another
profile without altering lineup references.

See [sampling validation and measurements](../data/validation/plate-appearance-sampling-v1.md)
for expected/observed frequencies, sample game, native timing, memory and checks.
Finite mechanics invariants remain covered by the scripted suite. Statistical
tests verify normalization and frequency convergence to prepared weights; they do
**not** establish historical scoring accuracy. WASM compilation passes; actual
WASM execution parity remains untested and no browser bindings are introduced.

## Season simulation and calibration (M4)

M4 adds `season.rs`, a bounded single-user season layer, and `contextual.rs`, a
small empirical transition resolver. Python owns the narrow Retrosheet import,
source/lineup joins, transition fitting and analysis. Rust remains pure portable
computation. No application/database or browser code is involved. Source choices,
target availability, uncertainty, biases and measurements are in the
[calibration report](../data/validation/season-calibration-v1.md), with the frozen
[evaluation plan](../data/validation/m4-evaluation-plan.md).

### New mechanics and compatibility

Game input **1.2.0**, `contextual-nine-inning-v1` rules and
`retrosheet-contextual-v1` advancement are an explicit opt-in combination. The
foundation game-end/walk-off/empty-extra-inning rules are retained. Inputs 1.0/1.1
and all scripted synthetic fixtures retain their prior event semantics and RNG
behavior. Results record engine version 0.4.0; legacy golden changes only update
that package version. New profile preparation is `lahman-contact-adapter-v1`.

v1.2 preserves the descriptive residual as **`otherContact`**, with zero legacy
`battedBallOut` weight. Singles/doubles/triples/HR/BB/HBP/SO retain their meanings.
The nine-field prepared vector includes the explicit zero legacy slot and sums
to 1,000,000. The M3 conditioning and rational smoothing/rounding math is reused;
historical totals remain unchanged. An independently versioned transition model
splits residual contact using source observations, not an invented player-level
error or choice statistic. Prepared IDs and transformation versions change.

`retrosheet-contact-transitions-v1` contains 72 ordered cells: single, double,
otherContact × outs 0..2 × base mask 0..7. Each cell stores observed sample count,
fallback status and integer-weighted joint destinations for batter/three runners.
Destinations are 0=out, 1..3=base, 4=run, 5=absent. Joint choices avoid independent
advancement coins placing runners on the same base or passing another runner.
Per-runner RBI flags preserve credit when a walk-off truncates would-be scorers.

The fitter uses only full regular-season parsed plays in innings 1–8 of 2022–2023.
It excludes SH/SF and non-PA events. Modern `othout` includes force outs where the
**batter reaches safely**; the fitter checks actual pre/post identities and outs,
not just the category name. Errors use `roe` plus safe batter destinations;
fielder choices include observed safe choices and force-out replacements. These
league conditional transitions are estimates for every player, not observed
individual batter frequencies. Walk/HBP, SO, triples and HR keep their existing
deterministic resolution. Strikeout reaches on dropped thirds remain unsupported.

Supported improvements are safe advancement on singles/doubles, single-out
advancement, safe error reaches, fielder choices and eligible first-base ground
double plays with fewer than two outs. Double plays remove the first-base runner
and batter, hold other runners and award no RBI or runs. This deliberately omits
occasional advances/runs on a zero-out double play, while forbidding runs on an
inning-ending force play. All supported third outs clear bases and strand the
remaining runners. `AB-H` is no longer a count of team outs.

Running outs on hits, extra batter advancement on a hit, complex contact plays,
third-out timing plays and uncertain records retain a counted conservative proxy.
Ordinary terminal contact outs use the established stranding behavior. No source
records are deleted to hide unsupported mass. Cells with fewer than 50 observations
fall back entirely to the conservative policy and are listed in the fit audit.
This is an explicit accuracy limitation, not a full Retrosheet rules interpreter.
SH/SF still require separate contextual models; steals, caught stealing, pickoffs,
wild pitches/passed balls/balks and automatic extra-inning runners remain absent.

Rust validates cell order, coverage, weight sums, presence masks, runner order,
collisions, legal retirements, reach classifications and RBI/scoring consistency.
The same SplitMix64 stream samples PA and contextual choice, with one additional
unbiased ticket only when that cell has multiple choices. Events/summary consume
identical draws. An event trace records the cell-local `transitionIndex`; replay
each play using `Game::apply_contextual_event(event, index)` or `apply_event` for
non-contextual plays. Direct `apply_event` cannot silently resolve ambiguous contact.
The legacy `replay_game` event-only API remains unchanged for legacy inputs.

Box scores add optional nonzero `groundedIntoDoublePlays`, `reachedOnError` and
`fieldersChoices`; they describe simulated choices, not complete official-source
category counts. Runs without RBI are possible. Runner conservation remains
`PA = outs + runs + LOB` after a completed game; hits, AB and RBI still derive from
the actual modeled appearances. Nothing samples independent batting averages.

### Season contract and schedule

`SeasonInput` v1.0 includes one user lineup, 1..30 opponents, prepared profile
pool (at most 279), common game configuration/context, source-kind labels,
summary/events detail, canonical u64 seed and a default length of 162 (1..1000).
Kinds distinguish observed fixed lineups, reconstructed fixed lineups and synthetic
opponents. These labels do not claim authentic complete rosters or schedules.

`round-robin-season-v1` sorts opponents by bytewise ID, then pairs away/home games
against each opponent in sequence, cycling to the configured length. The user is
away in zero-based game 0, home in game 1. Profile pools are resolved/sorted by ID;
batting order stays explicit. All opponents are validated even if a short season
does not reach them. Duplicate team/profile IDs, unresolved references, unsupported
versions and invalid matchups fail before play.

Season validation also compares canonical player IDs from profile provenance:
different batter-instance or team-stint profile IDs cannot put the same person on
both sides of one game. The historical calibration producer excludes such traded-
player matchups (`exclude-shared-player-identities-v1`), retaining 27..29 opponents
per user in this snapshot. The lineup audit lists exclusions and shared IDs. A
player may occur on different opponent teams in different games; the restriction
is matchup-local. Synthetic schedules still do not reproduce the MLB schedule.
Explicitly synthetic parameter templates may be reused for multiple distinct
batter instances; their provenance ID is not treated as a real person's identity.
Historical/reconstructed kinds retain the identity guard. Do not label a historical
lineup synthetic to imply an authentic roster with duplicate people.

`splitmix64-index-v1` derives zero-based game `i` directly as the first SplitMix64
output from state `seasonSeed + i * 0x9e3779b97f4a7c15`, modulo 2^64. Each game
then initializes its own SplitMix64 with that derived seed. Prior game length or
event logging cannot change later seeds; the first 1,000 derived seeds are unique.
This is a reproducible stream design, not a proof of statistical independence.
Any schedule/seed/transition algorithm change requires a new corresponding version.

`simulate_season` returns the immutable root input once, W–L, scored/allowed runs,
differential, team/user-batter totals, opponent totals and every game's seed,
score, boxes and inning lines. Scores and boxes use **user/opponent** ordering;
inning lines and event halves retain away/home. Summary omits event logs. Events
retains all traces and has higher bounded memory use. `SeasonInput::game_input(i)`
reconstructs a game for inspection. A failed or safety-aborted game propagates
`SeasonError::GameFailed { game_number, source }`; no incomplete season is returned
as a win/loss record. There are no standings, rotations, substitutions or playoffs.

### Reproduce data, calibration and benchmarks

From `data/pipeline` (raw/prepared outputs are ignored):

```sh
uv run python -m draftory_data.calibration fetch --retrosheet-dir ../raw/retrosheet-m4
uv run python -m draftory_data.calibration prepare --source-dir ../raw/lahman-2025 --retrosheet-dir ../raw/retrosheet-m4 --output-dir ../processed/m4
```

This verifies both source locks, writes targets, observed lineup selections and
their full source/profile audits, fits transitions, then writes thirty season
inputs for each of 2022–2025. Eligible starting orders are selected by descending
observed frequency, ties by IDs; every hitter must have a complete, team-specific
season profile with at least 50 PA. The first eligible pattern is used. A clearly
labeled PA-ranked reconstruction is only a fallback; insufficient teams fail.
`People.retroID` crosswalks are restricted to players active in that year, avoiding
ambiguous unrelated historical IDs. No lineup is assumed to start all real games.

From the repository root:

```sh
cargo build --locked --release --examples
cargo run --locked --release --example season -- crates/baseball-sim/tests/fixtures/season-modern-2024.json
cargo run --locked --release --example measure_season -- data/processed/m4/example-season-2024.json 1000 summary
cargo run --locked --release --example measure_season -- data/processed/m4/example-season-2024.json 1000 events
```

Then from `data/pipeline` (on Unix omit `.exe`):

```sh
uv run python -m draftory_data.calibration run --input-dir ../processed/m4 --runner ../../target/release/examples/calibrate.exe --repetitions 20 --output-dir ../processed/m4/results
uv run pytest tests --lahman-source=../raw/lahman-2025 --retrosheet-source=../raw/retrosheet-m4
```

`calibrate` reads JSON before timing and emits compact per-season analysis rows.
Its baseline mode explicitly maps unresolved contact back to the M3 out proxy
with a diagnostic model/ID/flag, preserving PA probabilities for a mechanics-only
comparison. Python reports historical targets, repeat variation, score histograms,
inning means, weak/average/strong terciles and W–L/run-differential relationships.
Source team-season batting counts are cross-checked against Lahman without repair.
Calibration fits 2022–2023; 2024 is development validation; 2025 is final holdout.
The test is retrospective and conditional on known season profiles, not a forecast.
The frozen plan defines training-derived diagnostic bands and requires reporting
failures. Passing a band cannot establish complete historical accuracy.
