# Error-avoidance simulation v1 (M8C.4)

This is an **opt-in experiment**, not an overall defensive ability model. At the
completed lineup screen select **Experimental error avoidance**. Unchecked is
the original neutral-defense simulation and remains the default/comparison mode.
The 65-credit budget, prices, batting weights, pitching, opponents and schedule
are unchanged. No cloud deployment or D1 migration is involved.

[Measured results](../data/validation/defense-v1.md),
[source/reliability measurements](../data/validation/defense-v1-data.json),
[paired outcomes](../data/validation/defense-v1-outcomes.json), and the
[development evaluation plan](../data/validation/defense-v1-evaluation-plan.md)
describe what was tested. The earlier [M8C.3 proposal](DEFENSIVE_SIMULATION_DESIGN.md)
is research history; the supported transfer model below supersedes its proposed
odds reweighting of the entire non-error complement.

## Supported behavior and evidence boundary

Only **1B, 2B, 3B and SS error avoidance** changes events in this model. Each
position has >=50 clearly attributed, supported batter-error reaches in the
2022/23 training sample. Catcher (13), LF (48), CF (45) and RF (48) do not meet
that conservative mapping floor and remain neutral; their Lahman facts are still
present. Fifty is a sparse-evidence safeguard consistent with the existing
transition fitter, not a proof of statistical reliability or a fitted optimum.
No pooling OF positions or importing reputation to fill the gap.

Eligible source plays must be full regular-season PAs in innings 1–8, without
SH/SF, and resolve to the existing supported `otherContact` error-reach
transition. There must be exactly one recorded error by exactly one position,
matching `firstf`, and a positive, existing ordinary-out/runners-hold alternative
in the same cell. Pitcher errors, ambiguous fielders, multiple errors, unsupported
compound/timing outcomes and errors that only advance an existing runner stay
unchanged. A batter ROE can also advance existing runners; its whole legal joint
transition is retained, rather than inventing independent advancement rolls.

Training inspection: 3,872 error plays, 1,986 batter ROE, 1,886 error plays without
batter ROE; 1,968 supported error reaches. Of these, 102 are ambiguous and 112
are pitcher-attributed. There are 1,754 unambiguous paired reaches before the
position floor, **1,600** at the four enabled positions. The independently pinned
2024 development plays have 880 unambiguous supported pairs before that floor,
812 at enabled positions; 11 other attributable plays lack a matching supported
pair and are left unchanged. These are the selected windows, not full-season MLB
error totals. The audit's `modifiableROE` counter is before the position floor;
its `position3`…`position6` counts give the enabled subset.

This supports a **relative error-rate proxy** on a restricted outcome subset.
It does not establish a causal conversion from every Lahman E to batter ROE,
nor difficulty-adjusted talent. Receiving/throwing chances, scorer judgment and
pitcher/batted-ball context remain confounders. Native experiments establish
implementation direction, not real-world predictive accuracy.

## Separate defensive profiles

Python verifies the original Lahman source lock and unchanged 526-player batting
publication. It reuses position-specific, null-preserving stint aggregation from
M8C.3. Traded players contribute each stint once; different positions stay
separate; generic OF never adds to LF/CF/RF. Unknown components stay unknown.
No batting profile or historical fact is rewritten.

For each position/season reference, pool complete AL/NL fielding records with
positive chances and >=300 defensive innings (including players outside the
batting pool). Let `mu = sum(E)/sum(PO+A+E)` at that position in 2024. For a
complete player-position with >=100 innings and positive chances:

```text
TC = PO + A + E
estimated_error_rate = (E + 1000*mu) / (TC + 1000)
errorRatio = round_half_up(1_000_000 * estimated_error_rate / mu)
```

All effect preparation uses exact rational arithmetic. Defensive time is InnOuts,
with innings=InnOuts/3. No innings are imputed from games. A recorded zero E is
not unknown and does not imply perfect defense; the prior keeps its estimate
above zero. An absent/zero reference denominator gives neutral fallback.

We compared floors 100/300/600 innings and prior strengths 100/300/1000/3000
chances using 2022 player-position rates to predict 2023 errors, scoring per-chance
binomial log loss over complete >=300-inning target records. Below-floor/missing
predictors use the previous-year position reference. The 100-inning/1000-chance
setting had the best pooled training score; 2023→2024 development sensitivity
also improves on the neutral reference. The 100-chance prior performed worse
than neutral. These small pooled score differences are not per-player confidence
intervals, and include positions whose event mappings remain disabled. The
settings stabilize a descriptive error proxy; they do not validate overall defense.

Profiles include immutable ID, player/year/position, compatible batting-profile
ID, source/model IDs, games, outs, TC, E, status and integer errorRatio. Shared
reference counts and policy live once in the supplement, linked by model,
position and season. Statuses:

- `observed`: complete sufficient exposure, enabled event mapping.
- `insufficient`: known exposure below the floor or zero chances; neutral ratio.
- `unknown`: missing required facts/reference; neutral ratio.
- `modelNeutral`: sufficient Lahman data, but unsupported position mapping;
  neutral ratio. Missingness is not inferred to mean bad defense.

All non-observed effects equal 1,000,000. Current coverage is 788 eligible pairs:
311 observed at enabled infield positions, 128 insufficient and 349 model-neutral;
no unknown records in this particular 2024 subset. All eight fielding slots have
profiles; DH contributes none. This v1 deliberately rejects other years/models.
A historical extension needs versioned season/league references and measured
coverage, not raw cross-era error-rate comparisons.

## Probability transfer in Rust

The existing batting sampler is preserved. Hits are already classified before
contextual resolution; defense must not add a second error roll or change a hit
to an out. `otherContact` is residual AB contact, not all BIP or a ground-ball
class. Its existing joint destinations handle legal base/out and RBI outcomes.

Within each residual-contact/base/out cell, Python records the portion of each
error-reach choice attributable to an enabled primary position:

```text
a[choice, position] = floor(1_000_000 * attributed_observations / cell_observations)
delta[choice] = sum_position(floor(a * errorRatio / 1_000_000) - a)
new_error_choice_weight = original_weight + delta
new_ordinary_out_weight = original_weight - sum(delta)
```

Unknown/pitcher/unsupported portions of each error choice are unchanged. Only
paired ordinary batter-out/runners-hold and error-reach choices exchange mass.
**GDP, fielder-choice and hit-transition weights are not rescaled.** This avoids
the GDP coupling in the earlier whole-complement odds proposal. Aggregate GDP
counts can still change because earlier reaches/outs alter future opportunities.

Integer setup applies decreases before increases, processes choices in stable
order, and limits any transfer to leave at least one ticket in every existing
choice. No zero-support outcome appears or disappears. Unsupported/no-pair cells
are untouched. All cells still total exactly one million tickets and retain
their original choice order, destinations, RBI flags and reach classifications.
The upper accepted ratio bound is a numeric input-safety bound, not a selected
talent cap; observed ratios are heavily shrunk and much narrower.

The compiler runs **once per season** (or once for a standalone game). Immutable
defensive configuration uses Rust `Arc` to avoid deep copies for every game and
result. This uses Serde's existing `rc` feature, no new dependency or host service.
It introduces no browser threads, SharedArrayBuffer or cross-origin-isolation
requirement. The hot loop selects one precomputed distribution for the defending
side and consumes the same one conditional ticket as before. There are no
additional random draws or per-PA defense allocations.

Season entry validates every immutable matchup, including unused opponents,
before execution. The internal game constructor reuses that validated snapshot;
it does not repeat whole-model validation for each of 162 games. Public game and
season entry points still validate untrusted input, and invalid-matchup tests
remain enforced. This removed a measured browser slowdown without changing
sampling, event legality or golden outputs.

When the opponent bats, use the drafted team's eight position assignments and
a neutral/default pitcher. When the user bats, the existing opponent defense
is neutral. Season validation requires the defensive team to be the user team.
Assignments are bound to actual selected player/provenance/profile IDs and ordered
C,1B,2B,3B,SS,LF,CF,RF, separately from `userTeam.lineup` batting order. Wrong
identity, position, source, year, model or version fails before simulation.

Existing transition invariants remain authoritative: no passing/colliding or
phantom runners, legal outs, third-out and walk-off scoring, actual counter/RBI
credit and valid event replay. Reaches on error are not hits. Every supported
new-mode event can replay through the existing joint-choice API; its geometry
has not changed. No fielding error is retrospectively assigned to a named player
in the result, because the modifier marginalizes fielder involvement rather than
sampling a separate fielder event.

## Contracts, publication and delivery

New contracts are separate from legacy schemas:

- [Defense definitions](../contracts/defense.schema.json): profile, model,
  assignment/config definitions, version 1.0.0.
- [Supplement](../contracts/defense-supplement.schema.json), version 1.0.0.
- [Game input](../contracts/defense-game-input.schema.json), version 1.3.0,
  rules `error-avoidance-nine-inning-v1`.
- [Season input](../contracts/defense-season-input.schema.json), version 1.1.0.
- [Game result](../contracts/defense-game-result.schema.json) and
  [season result](../contracts/defense-season-result.schema.json), version 1.1.0.

Core engine metadata stays 0.4.0 to preserve legacy goldens. New rules, schema,
defense-model and supplement IDs explicitly identify the opt-in semantics;
legacy inputs cannot enable defense. Full results echo the complete immutable
input. Compact results identify the new result schema; local gameplay diagnostics
also export the supplement/model and eight defensive profile references alongside
the independently saved batting order. Diagnostic exports are not a saved-game
import or a verification system.

The immutable [2024 supplement](../data/publications/defense-2024-v1.json) binds
the unchanged batting dataset to separate defensive facts, model, policy,
references and attribution. Its content ID is checked against the compiled ID
and canonical SHA-256 in the browser. Unknown/tampered/stale versions fail;
failed loads are evicted for retry. Python refuses to overwrite existing output
with different bytes. No prices or complete batting payloads are duplicated.

Vite serves one hashed JSON asset, loaded **only when the option is selected**,
cached for the page session. The compact 788-pair file costs about 74 KB using
Python gzip level 6 (Vite reports about 70 KB with its compressor);
this avoids hundreds of tiny requests/new API storage. Only the selected eight
profiles plus shared model enter simulation input. Consider shards only if a
larger multi-season pool makes this measured transfer inappropriate. Existing
asset MIME/cache/CSP behavior remains sufficient. There is no persistent browser
cache or new D1 publication; rollback is turning off the option or selecting the
legacy input/schema. Preserve immutable old artifacts for replay.

## Reproduce and validate

Use existing Lahman/M4 fetch and pilot-publication instructions first. The
additional official 2024 Retrosheet development plays have a **separate new lock**
`retrosheet-defense-dev.lock.json`; no existing source lock changes. Its observed
SHA-256 is `a3e8c08876ddf70e1ffb0b20486c2873cf4aae19e0acc8002096e9056107615b`.
These are project-observed integrity hashes, not upstream signatures. No mirror,
paid data or 2025 play archive is used.

From the repository root:

```sh
uv run --project data/pipeline python -m draftory_data.defense fetch-dev
uv run --project data/pipeline python -m draftory_data.defense prepare
uv run --project data/pipeline pytest data/pipeline/tests --lahman-source data/raw/lahman-2025 --retrosheet-source data/raw/retrosheet-m4
cargo test --workspace
cargo build --locked --release --examples
npm run build:wasm
npm run build
npm run test:browser
npm run test:edge
npm run test:integration
npm run test:integration:edge
uv run --project data/pipeline python -m draftory_data.defense_validation --runner target/release/examples/season.exe
target/release/examples/measure_defense.exe data/fixtures/defense-season-2024-v1.json
uv run --project data/pipeline python -m draftory_data.defense_validation --collect-performance
```

On Unix omit `.exe`. Default `prepare` checks source integrity without downloading;
use a new `--output` path to compare producer bytes with the immutable publication.
Source-backed tests skip explicitly if raw inputs/development archive/publication
are missing. Ordinary tests still validate contracts, content IDs, missing/zero
behavior, boundaries, immutable writes and real native behavior where built.
Research raw files, individual experiment inputs/results and browser timing
artifacts stay ignored; only compact reports/new shared fixtures are checked in.

For exact legacy comparison remove defense and select legacy game/season/rules
versions; setting all ratios neutral in the **new** input gives the same events,
but correctly retains new-mode metadata. Do not strip new metadata from saved
results or reinterpret legacy seeds using a future defensive resolver.

## Limitations and next steps

No range, hit↔out conversion, individual GDP skill, catcher framing/steals/
blocking, OF arm, pitcher roster, fatigue or availability is modeled. Neutral
fallback has visible reasons. The fixed nine hitters, CHA opponent and synthetic
schedule still limit realism; the known M4 hit/PA/GDP/variance failures remain.
Changing opportunities can change realized hits/GDP even when their probabilities
are untouched. Estimated errors alone may underrate excellent range defenders.

Next, keep the season dashboard tied to actual computed counters and visible
model limitations. Expanded opponents need a separately reviewed versioned
opponent context, identity handling and payload/performance measurements. Further
defensive skill needs opportunity-specific evidence and a new untouched evaluation
set. The inspected 2025 holdout is diagnostic only. No M8C.5 work is started here.
