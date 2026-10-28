# Season dashboard and representative opponents (M8C.5)

The playable game now uses nine representative 2024 opponents and a **synthetic
Draftory schedule**. The original single-CHA pilot, fixtures, diagnostic harness
and goldens remain available. No baseball probabilities, pricing, draft budget,
pitching model, RNG or scheduler algorithm changed. This milestone is local;
it does not provision, commit or deploy anything.

## Opponent preparation and authenticity

`draftory_data.opponents` verifies the existing official Lahman release lock,
the unchanged 526-player publication SQL/manifest, prepared-profile hashes and
the pinned M4 context fixture. It does not fetch a new source or fit a model.
The immutable `data/publications/opponents-2024-v1.json` publication contains
ARI, BAL, BOS, CHA, HOU, LAN, MIL, NYA and PHI. These are a small, fixed pool
covering all six divisions, including both strong and weak historical offenses;
the selection is not optimized against simulated wins or the 2025 holdout.
Display abbreviations come from Lahman's `teamIDBR`, e.g. LAD, NYY and CHW.

Within each club, sum distinct 2024 batting stints once and rank published
players by team PA (`AB+BB+HBP+SH+SF`), descending, ties by stable player ID.
Take the first nine. Each must have a positive source-team PA and an existing
verified full-season prepared profile. Missing counts, duplicate stints or too
few candidates fail preparation. This selection/order is versioned as
`team-pa-ranked-nine-full-season-profiles-v1`.

These are **PA-ranked representative batting orders**, not observed starting
lineups or complete historical rosters. A traded player uses the unchanged
full-season aggregate profile, not invented team-split rates. No defensive
positions, pitching staff, bench, fatigue or substitutions are assigned to these
opponents. All nine bat throughout the season. Membership, names, source season,
selection PA and IDs remain inspectable. Opponent defense is neutral.

There are 81 distinct prepared profiles, stored once in the artifact. Batting
profiles, historical facts, source locks and price catalogs are unchanged.
The publication binds dataset/source/policy/context/transition/engine/selection
versions, its source SQL hash and attribution. Its canonical content ID is
`opponents:29182146a03008ee33def9b5474956da826163debf4c1b2b97baab43a9c12ce8`.
Python refuses different bytes at an existing publication path. The browser
checks both this compiled pin and the canonical hash, validates identity links
and compatibility, and rejects incomplete, stale or mismatched data.

The artifact is lazily fetched at simulation start, cached for the page session,
and evicted on failure for retry. Only the drafted nine use the existing API;
the entire 526-profile database is never downloaded. Identical player-profile
IDs shared with the user are deduplicated in simulation input. Draft lineups
are explicitly synthetic, so a historical identity may occur on both sides;
distinct batter-instance IDs preserve scorekeeping. Historical pilot identity
guards are unchanged. No D1 migration or new HTTP endpoint is needed.

## Schedule and seeds

Reuse Rust `round-robin-season-v1`: sort opponent IDs in ASCII order, then play
one away/home pair per opponent, repeating that order nine times. Every opponent
gets exactly 18 games, nine home and nine away: **162 games, 81 home/81 away**.
No team gets extra games from array ordering or a partial final cycle. Input
opponent/profile array permutations cannot change the actual games.

The schedule itself is fixed across season seeds. Each game's independent seed
still uses `splitmix64-index-v1` from the season seed and zero-based game index;
there is no new random draw or seed conversion through a JS number. Changing
the season seed changes outcomes, not opponent frequency. Ordering determines
the seed/opponent pairing and the displayed season progression. With no fatigue
or inter-game state, early/late opponents have no availability advantage. This
is not an official MLB calendar, travel model or shared-league standings system.

## Compact projection and dashboard

The new `dashboard` Worker output and `simulate_season_dashboard_json` WASM
export reuse the existing engine result. The separately versioned
`season-dashboard-summary.schema.json` contract includes existing summary and
batting objects plus dashboard **1.0.0**:

- Every game's number, opponent ID, home/away, seed, score, W/L, cumulative
  record, innings, combined PA, hits, HR, BB, SO and LOB.
- Inning run pairs and game metric pairs always use **user/opponent** order,
  independent of home/away. Null means an unplayed half-inning, not a played zero.
- Per-opponent game counts, W/L, runs scored/allowed and differential.
- Schedule/seed-derivation versions, selected defensive model ID (or null) and
  explicit neutral opponent defense.

Rust copies counters and computes cumulative/per-opponent sums before compact
serialization. It does not serialize the root input, 162 individual batter boxes
or play-by-play into this projection. The Worker passes the structured projection
once, without another result JSON string. Existing `summary`, `batting` and full
outputs retain their formats. Neutral result metadata stays 1.0.0; opt-in defense
retains 1.1.0. The nested dashboard version identifies its additional projection.
Full detailed output is still available through the diagnostic interface.

The dashboard preserves season record, runs/differential and tied leaders. It
adds team AVG/OBP/SLG, all supported player batting columns including AB, 2B, 3B,
BB, SO and OPS, cumulative wins with a .500 guide, opponent summaries and a
162-row scrollable result table. Opponent/result filters never reorder games
or change the full-season cumulative record. Selecting a game focuses its
details heading, showing inning runs and existing team counters. No individual
game stats, fielding-error attribution, standings or runs-saved values are invented.

Charts have descriptive text and complete cumulative records in the table.
Tables use captions, row/column headers and labeled keyboard-focusable scroll
regions. Filters have visible labels; native buttons remain at least 44px.
Wide statistics scroll inside their region on phones rather than overflowing
the document. Human screen-reader and physical-phone evaluation remains useful.

Fielding assignments, batting order, reroll history, 65-credit prices, cancellation,
retry and new-seed reruns keep their existing behavior. The defensive mode is
displayed with the result. Session exports retain opponent publication/name
snapshots, defense references, draft/order, seeds and compact dashboard, plus
assembly and browser execution timings. Timing metadata is not deterministic
simulation output or analytics; no upload/persistence is introduced.

## Reproduce and test

From the repository root, using the already verified local source/publication:

```sh
uv run --project data/pipeline python -m draftory_data.opponents
cargo build --locked --release --examples
cargo test --locked --workspace
npm run build:wasm
npm run build
npm run test:data-client
npm run test:browser
npm run test:edge
npm run test:integration
```

For genuine full local-D1 gameplay (including rerolls), set `M6B_IMPORT_SQL` to
`data/processed/d1-2024/import.sql` before the integration commands. Tests never
fetch raw releases or provision Cloudflare resources. Example diagnostic input
and compact golden are `data/fixtures/dashboard-season-2024-v1*.json`; their
synthetic nine-star roster is a computation fixture, not claimed budget-legal.
The game tests separately exercise legal drafted rosters.

For recorded browser measurements, run the dashboard parity test across all six
projects, then the dashboard integration test with the real publication:

```sh
npx playwright test --grep "dashboard v1 multiple" --project chromium --project firefox --project webkit --project edge --project mobile-chromium --project mobile-webkit
npx playwright test --config apps/web/playwright.integration.config.ts --grep "season dashboard reconciles" --project chromium --project firefox --project webkit --project edge --project mobile-chromium --project mobile-webkit
uv run --project data/pipeline python -m draftory_data.dashboard_validation --measure-native --evaluate-pool
npx prettier --write data/validation/season-dashboard-v1.json
```

The second command needs `M6B_IMPORT_SQL` set as above. Only real-publication
game runs feed the collector; fixture/alpha regressions cannot replace those
measurement files. Run native and browser benchmarks without concurrent heavy
jobs. Measurements and raw samples stay under ignored `target/m8c5`; the compact
handoff report is versioned separately.

See [the completion report](../data/validation/season-dashboard-v1.md) and its
machine-readable measurements for actual check results, sizes and timings.
Benchmarks distinguish a fresh Worker/first call from subsequent calls; local
assets/browser/OS caches may be warm. They are not physical phone or first-WAN-
visit measurements. Only allocated WASM linear memory is measured, not whole
browser/JS process memory.

## Limits and next priorities

Existing hit/PA/GDP excess and scoring-variance calibration failures remain;
adding opponents does not fix them. The previously inspected 2025 holdout was
not used to select new models. Pitching stays standardized and experimental
defense models only supported infield error avoidance. Opponents have no
fictional defensive quality. Known roster/overlap, fixed-order, no-substitution,
empty-extra-inning and neutral-pitching limitations remain visible.

Next: human dashboard/phone accessibility playtests, then separately review a
larger opponent pool and schedule policy. Twenty-nine opponents are technically
feasible, but 162 is not divisible by 58 paired games; balanced frequency and
representative ordering would need explicit policy/version decisions. Any new
baseball mechanics or historical recalibration needs its own evidence and a
new evaluation set. No next milestone or deployment is started here.
