# Draftory — Baseball Simulation Specification

**Version:** 0.1 (2026-10-25)  
**Status:** Implementable behavioral baseline plus explicit unresolved statistical modeling questions.

## 1. Purpose and non-goals

Build a **fast, deterministic, plate-appearance-level MLB simulator** that consumes precomputed player probability profiles, produces game and 162-game season results, and records meaningful player statistics. The first playable game drafts **nine hitters**, not a full roster. The pitching/defensive environment is standardized initially to keep the focus on hitters.

**Not MVP:** pitch-by-pitch sequencing, ball physics, full defense/fielding logic, pitcher fatigue, rotation/bullpen management, substitutions, injuries, competitive anti-cheat or server simulation.

The simulator must **simulate actual outs, runners, innings and scoring**, not simply generate a W–L record from an overall team strength rating.

## 2. Architecture and responsibility

- **Python data pipeline** generates outcome profiles, opponent parameters, baserunning transition priors and versioned test fixtures.
- **Rust simulation core** owns game state transitions, random sampling, outcome resolution, scorekeeping, statistics and season aggregation.
- **Rust native runner** executes tests, calibrations and benchmarks.
- **Browser WASM Web Worker** runs exactly the same Rust core with preloaded data and returns compact results to React.
- **Frontend** presents season outcomes and optional game replay; it does not compute official simulation statistics from ad hoc UI rules.

The core must be pure with respect to network and persistent state. No real-time Lahman/Retrosheet lookups while simulating.

## 3. Initial game model

- Nine user-selected hitters in a defined **batting order**; roster validation is performed before simulation.
- Both teams are represented by a lineup plus an explicit pitching/defensive **context**. MVP can represent opponent lineups using calibrated opponent profile templates rather than individual roster fidelity.
- User team pitching/defense is held at a standardized league-average baseline, independent of hitter selection.
- Play full nine-inning baseball games with home/away rules, early termination of the bottom ninth when home already leads, walk-offs, and extra innings where applicable.
- Handle official ruleset variations (such as automatic runner in extra innings) through a **versioned ruleset**, not embedded assumptions. Choose a single modern ruleset for the first benchmark.
- Full regular season target is **162 user-team games**. Opponent distribution, home/away assignments, park/environment and schedule structure are configurable and versioned; do not claim to mirror an exact MLB schedule until implemented.
- A simulated batting appearance may be called PA even though official AB differs; correctly account for walks/HBP/sacrifices where modeled.

## 4. Game state

At minimum:

```text
GameState:
  inning: positive integer
  half: top | bottom
  outs: 0..2 (transition at 3 ends half-inning)
  bases: [runner? at first, second, third]
  awayScore, homeScore: nonnegative integers
  awayNextBatterIndex, homeNextBatterIndex: 0..8
  optional current batter / pending outcome
  team/individual cumulative scorekeeping
  ruleset, RNG state, event index
```

Every runner must carry a batter/player ID sufficient to attribute runs and event outcomes. Don't model bases as only three booleans if run attribution will be required.

## 5. Plate-appearance resolution

### 5.1 Stage A — Determine context

Read current batter, opposing pitching context and any modeled situational factors. The initial model may use **league-average opponent pitching** and batter-specific PA probabilities. Introduce pitcher-batter interaction only after calibration, with a documented formula (e.g. odds-ratio/log5-style approach) rather than naive multiplication of percentages.

### 5.2 Stage B — Sample outcome

For the first coherent taxonomy, consider:

- 1B / 2B / 3B / HR
- BB / HBP
- SO
- non-strikeout out in play

Some events are **context dependent** (double plays, sacrifice flies, fielders' choices, errors); do not treat them as independently sampled season-level batting outcomes without explicit rules. Expand the taxonomy with validated Retrosheet-derived priors and historical context.

Use one deterministic seeded PRNG and documented integer-to-probability conversion. Keep hot-loop sampling allocation-free where practical.

### 5.3 Stage C — Apply baserunning and out rules

- Bases and runs must update consistently: runner advancement can be forced, optional, or situation-dependent.
- Walk/HBP: batter to first; advance existing runners only if forced; bases-loaded award scores a run.
- HR: batter and all occupied runners score; bases clear.
- Hits: use a versioned advancement probability table conditioned on hit type, prior base state and outs. Start with conservative rules and improve against historical event data.
- Outs: SO makes one out; balls in play can produce fly/ground outs, and optionally double plays when calibrated.
- Caught stealing and sacrifices: **only** model and record if corresponding events are actually implemented.
- Transition to the next batter according to lineup order even when the preceding PA ended an inning, with the exception of modeled non-PA events as rules require.
- Resolve third-out timing and runs scored on plays correctly; do not award runs that rules disallow.

### 5.4 Stage D — Update scorekeeping

Accumulate actual simulated event counts and derived statistics, not independently sampled AVG/OPS/RBI. Explicitly define earned-vs-unearned runs when pitching statistics become relevant.

## 6. Inning and game rules

1. Initialize zero score, top of first, empty bases, zero outs, each team batting-order cursor at 0.
2. Simulate PAs until 3 outs; resolve any resulting runs and advance to the next half-inning; reset bases/outs.
3. Skip bottom ninth (or later) if home team already leads after top half.
4. End a bottom ninth/later half immediately once the winning home run is scored (walk-off), after resolving any applicable scoring exception.
5. Tied after regulation: proceed to extra innings using the selected ruleset (explicit handling of automatic runners if enabled).
6. Every game produces a winner for the chosen modern regular-season mode, subject to explicit safety limit for erroneous runaway games. **Never silently convert a runaway simulation into a random result.**
7. Preserve away/home identities and correct inning-by-inning line score. Account for extra innings and games where the home team takes fewer offensive turns.

**Implementation note:** fully accurate baseball scoring has edge cases. Favor an explicit, tested simplified ruleset over pretending full official-rule fidelity in v0.1; publish known limitations in the calibration report.

## 7. Player and team stats

### 7.1 MVP box-score fields, where underlying events are modeled

| Field | Derivation |
| --- | --- |
| PA | Actual plate appearances, including BB/HBP; adjust if sacrifices supported |
| AB | PA excluding walk, HBP, sacrifice and other official non-AB outcomes as modeled |
| H, 1B, 2B, 3B, HR | From simulated hits by type |
| BB, HBP, SO | From simulated outcomes |
| R | Runner identity crosses home legally |
| RBI | Credited under explicit baseball rules; begin with common hit/walk cases, document exclusions |
| AVG | H / AB (with zero-denominator handling) |
| OBP | (H + BB + HBP)/(AB + BB + HBP + SF), with SF only if supported |
| SLG | Total bases / AB |
| OPS | OBP + SLG |
| ISO | SLG − AVG |
| Team results | Game scores, W–L, runs scored/allowed, differential, winning percentage |

No fictional errors, stolen bases, double-play totals, fielding statistics, ERA or WHIP in the UI unless the relevant mechanics are implemented and validated. Differentiate simulated statistics from source historical stats.

### 7.2 Season outputs

- `record`: W/L from actual simulated games; `wins + losses = 162` under the proposed modern regular-season ruleset.
- Total team runs for/against and per-game run-scoring summary.
- Ordered per-game score/results; optional inning line scores.
- Cumulative season batter statistics for each drafted player.
- Optional notable events/records generated from underlying game statistics (not invented narratives).
- Optional full PA event log for a chosen game or replay mode, **not** necessarily all 162 games by default.

### 7.3 Presentation tiers

1. **Quick:** W–L, run differential, star performers.
2. **Season:** player batting lines, game-by-game scores, progression and aggregate context.
3. **Replay:** a complete event log for selected games or deterministic reconstruction from game seeds and immutable inputs.

## 8. Determinism and replay

- Seed is assigned **before** the simulation begins. Store it losslessly (e.g. encoded 64-bit integer string).
- Version the algorithm and use explicit ordering of sampled events; do not use unseeded OS/browser random calls.
- Given the same ordered lineup, source profiles, opponent schedule, ruleset, engine version and seed, native Rust and browser WASM should produce identical results, proven by fixtures.
- Decide whether each game gets a seed derived deterministically from the season seed; this simplifies reconstructing only one game without re-running 161 earlier games.
- Recording every PA is optional; reconstructing requires immutable profiles/contexts and engine versions to remain available.
- Later verification on a self-hosted service reuses the same engine, but **verification is out of scope for MVP**.

## 9. Speed, memory and transport

- Avoid crossing the WASM/JS boundary for every PA.
- Precompute any probability tables and cumulative distributions before entering the simulation loop.
- Use compact structs, arrays, fixed-width IDs and low-allocation event handling.
- Separate summary mode (low memory) from event capture mode (richer data), with identical outcome sampling.
- Preload user lineup and opponent contexts as a small payload; no mid-game Worker/D1/API fetch.
- Run in browser Web Worker and support cancellation and coarse progress notifications.
- **Provisional target, not a claim:** simulate 162 games in about a second or less on typical desktop after startup. Establish realistic mobile numbers through benchmarks; measure cold WASM load separately.

## 10. Calibration and model-quality program

Use known historical team/league season distributions (Lahman and/or Retrosheet). For each model version:

1. Run many simulated games using a controlled historical context.
2. Compare PA event shares (K/BB/1B/2B/3B/HR/HBP, where covered) to target distributions.
3. Compare hits, runs/game, run variance, low/high score tails, extra-inning frequency, home advantage and scoring by base/out state.
4. Compare realistic season W–L distributions under matched teams/environments; **do not** judge quality only by whether one random 162-game record equals a historical record.
5. Test multiple lineup constructions (on-base specialists, power hitters, weak lineups) for plausible run differentials.
6. Record model assumptions, mismatches and versioned calibration reports.
7. Define tolerances **after** exploratory baseline data analysis; don't invent arbitrary success thresholds.

A simplified league-average defense/pitching model will limit realism. Make limitations clear in results copy and technical reports.

## 11. Mandatory correctness tests

**Engine invariants**

- Every PA yields a valid event; probability distribution is valid.
- Outs never exceed 2 in active state; transition at third out resets half-inning correctly.
- Runner IDs occupy at most one base; no phantom runners or negative scores.
- Batter order advances and wraps correctly across innings.
- A bases-empty solo HR scores exactly one run; loaded HR scores exactly four.
- Bases-loaded walk scores exactly one and retains correctly forced runners.
- No runners advance on a routine strikeout (unless separately modeled non-PA events).
- Third-out situations don't incorrectly award runs.
- Walk-off and skip-bottom-ninth rules function correctly.
- Away/home runs sum to recorded scoring events; 162-game W + L = 162.
- Individual hit totals sum to team hits; player runs sum to team runs where all scoring runners are tracked.
- Fixed-seed golden tests match native and WASM outputs.

**Statistical tests**

- Observed event shares converge toward input probabilities over large samples.
- Run scoring and base-state advancement meet calibration expectations.
- No bias from shuffling or selecting outcomes with incorrectly normalized distributions.
- Changing batting order can affect run scoring, not just average player totals.
- Repeated seeds produce variation while the same seed is stable.

**Performance tests**

- 1 game, 162-game season, 1,000-season batch.
- Native vs desktop WASM vs mid-range Android; cold and warm timings.
- Peak memory, bundle transfer size, event logging overhead and Worker responsiveness.

## 12. Engineering milestones

### S0 — Pure fixtures / state machine

Create a synthetic batter outcome distribution, deterministic RNG, base-runner state and tests for forced advances, HR, hits and outs. No historical import is required for this step.

### S1 — Complete game

Simulate both halves of all innings, line scores, wins, walk-offs, extras, batting order and simplified box scores. Run fixed-seed regression fixtures.

### S2 — Real profiles and season

Read versioned profiles created by Python; 162 opponent contexts; accumulate game/season statistics; document simplified pitching model.

### S3 — Calibration

Use external historical evidence; improve baserunning and outcome models; measure biases and publish statistical report. This is a gate before claiming realistic results.

### S4 — Browser WASM

Compile with a thin adapter, run in a Web Worker, support summary/detail mode and measure actual desktop/mobile speed.

## 13. Outstanding questions / research tasks

- Exact mutually exclusive PA outcome taxonomy and formulas for source-rate estimation.
- How batting and opposing pitching/defense probabilities combine.
- Base advancement conditional probabilities and how they vary with outs, speed, event type, and era.
- Double plays, fielder's choice, errors, sacrifice flies and official RBI rules for the first credible version.
- Extra-inning ruleset, automatic runners, home/away/park adjustments.
- How a nine-hitter-only user team is compared to standardized opponents fairly.
- How much event data to keep in memory and whether game replay uses per-game derived seeds.
- Statistical confidence intervals and calibration acceptance thresholds.

## 14. References

- Lahman: https://sabr.org/lahman-database/
- Retrosheet: https://www.retrosheet.org/
- Related: [DATA_SPEC.md](DATA_SPEC.md), [ARCHITECTURE.md](ARCHITECTURE.md), [PROJECT_PLAN.md](PROJECT_PLAN.md).
