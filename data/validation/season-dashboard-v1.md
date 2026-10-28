# M8C.5 season dashboard and expanded opponents

Final-review update: the historical pricing regression below is resolved by an
explicitly pinned research engine; see [investigation and final checks](season-dashboard-final-review-v1.md).

Implemented locally on 2026-10-28. **No commit, push, deployment or next milestone.**
[Methodology and reproduction](../../docs/SEASON_DASHBOARD.md),
[measured JSON](season-dashboard-v1.json),
[opponent publication](../publications/opponents-2024-v1.json),
[compact golden](../fixtures/dashboard-season-2024-v1.golden.json).

## Data, schedule and functionality

Nine verified representative 2024 clubs: Arizona, Baltimore, Boston, Chicago
White Sox, Houston, Los Angeles Dodgers, Milwaukee, New York Yankees and
Philadelphia. The official pinned Lahman source, 526-player publication and
prepared batting profiles are unchanged. Eighty-one unique profiles are stored
once; source, policy, year, context, transition model, selection version, SQL
hash and canonical publication ID are retained. No new source, fitted model,
player prices, D1 table or runtime roster endpoint.

For each club, sum distinct batting stints once, rank published hitters by
team PA, tie by stable player ID, take nine and retain that order. These are
**representative PA-ranked orders**, not authentic starting lineups. Prepared
ability remains each player's original full-season aggregate; membership PA
does not become a new probability distribution. Traded identities, missing
counts and source mismatches are checked rather than imputed. All six divisions
are represented. Selection is not tuned to wins or the inspected 2025 holdout.

The unchanged Rust scheduler sorts IDs, cycles away/home pairs, and repeats the
nine-club round nine times: **162 games, 18/opponent, nine home and nine away
per opponent**. Input array permutations do not change results. This synthetic
Draftory schedule has no calendar dates; it is fixed across seeds. The existing
indexed game-seed derivation remains unchanged. No fatigue/availability effects
give early/late opponents a different playing context.

The UI preserves the 65-credit draft, three free rerolls, independent batting
order/fielding assignments, retry/cancellation and new-seed reruns. Results add:

- Final W–L, win percentage, runs/differential, team AVG/OBP/SLG and tied leaders.
- All supported requested player columns: PA, AB, H, 2B, 3B, HR, BB, SO, RBI,
  R, AVG, OBP, SLG and OPS, with explicit denominator notes and zero handling.
- Cumulative-wins chart, .500 guide and full cumulative records in a table.
- All 162 games in simulation order, opponent/result filters, venue and scores.
- Per-opponent W–L and runs/differential; selectable inning lines and existing
  team game counters (H, HR, BB, SO, LOB), not invented individual boxes.
- Result-bound defensive mode and opponent-publication snapshots in exports.

Pitching remains standardized and opponent defense neutral. Optional user
error avoidance remains incomplete and explicitly identified. Historical
player cards and simulated results remain labeled separately.

## Reproducible examples

Legal current-catalog draft seed `20261027`, the existing fixture's first-choice
picks (no rerolls), season seed `20261025`, neutral defense:
**64–98**, 588 runs scored, 780 allowed, **−192** differential. All 162 scores,
player totals and opponent summaries reconcile to native Rust. The prior CHA-
only fixture still reproduces its original results under the legacy adapter;
different opponent ability legitimately changes the new game's results.

The new nine-star diagnostic fixture is synthetic and **not claimed affordable**
under the 65-credit budget. Seed `20261025`, neutral mode: **92–70**, 973 scored,
785 allowed, **+188**. With its real experimental error-avoidance assignments:
**92–70**, 975 scored, 784 allowed. This single seed is a reproducibility example,
not evidence for general runs saved or improved calibration. M8C.4's multi-seed
defensive experiment remains the relevant impact study. Both neutral and active
defense receive full native/WASM parity checks, including maximum-u64 seeds.

## Payloads and native performance

Same host, release JSON boundary, 21 calls/mode (first plus 20 repeats); file
reading is outside timing. Decode, validation, simulation, projection and encode
are included in boundary time. These are first calls after process startup,
not cold OS-cache or network measurements. The legacy control uses the same
offensive diagnostic roster and single CHA opponent. Full outputs include input;
compact outputs do not include input or event traces.

| Mode                      | Input bytes | Compact bytes | Full summary bytes | Full traces bytes | First boundary ms | Warm boundary median [min–max] ms | Warm core median ms |
| ------------------------- | ----------: | ------------: | -----------------: | ----------------: | ----------------: | --------------------------------- | ------------------: |
| Legacy batting projection |      64,627 |         3,307 |            908,652 |         5,928,346 |             11.77 | 8.34 [8.13–9.77]                  |                8.11 |
| Nine opponents, neutral   |     141,900 |        59,593 |          1,014,754 |         6,383,519 |             12.99 | 10.57 [9.75–11.41]                |                9.35 |
| Nine opponents, defense   |     156,788 |        59,669 |          1,029,633 |         6,398,619 |             13.45 | 10.55 [10.06–11.45]               |                9.31 |

The dashboard is larger than M8C.4's roughly 3.3 KB batting-only projection
because it carries 162 inspectable games, yet remains about **94% smaller** than
the new full summary and **99% smaller** than full traces. JSON pairs avoid
repeating large per-game batter boxes. Native core cost grows by about 1.2 ms
in this same-run comparison: more referenced profiles/opponents and different
opponent-driven game/PA lengths. Decode/projection/encoding add further boundary
cost. This is a measured modest increase, not a claim of zero overhead. M8C.4's
older 11.5 ms core measurements used another timing window; do not treat timing
differences across sessions as an engine-speed improvement.

Only the structured summary, batting object, dashboard and timings cross from
Worker to React. Full-detail capability remains available for diagnostics; no
full season trace or repeated large input is sent to React by default.

## Browser timing and delivery

An isolated parity/measurement run used a fresh Worker per mode, first call then
five repeats, local production assets. Browser/OS caches can be warm; the second
mode can reuse compiled/cache state. No first-visit WAN claim. Native expected
output comparison occurs outside the measured browser request interval.
Neutral-mode values; full raw distributions and defense mode are in JSON:

| Browser/project           | WASM init ms | First core ms | Warm core median [min–max] ms | Warm Worker round trip median ms | Active-defense warm core median ms |
| ------------------------- | -----------: | ------------: | ----------------------------- | -------------------------------: | ---------------------------------: |
| Chromium                  |         29.2 |          78.5 | 23.0 [20.8–25.4]              |                             31.4 |                               24.3 |
| Firefox                   |           72 |           278 | 132 [124–238]                 |                              153 |                                131 |
| WebKit                    |           43 |           131 | 30 [22–51]                    |                               47 |                                 30 |
| Edge                      |         33.2 |          21.8 | 12.8 [12.1–13.2]              |                             15.9 |                               11.5 |
| Mobile Chromium emulation |         26.2 |          85.1 | 23.7 [22–31.5]                |                             32.3 |                               24.3 |
| Mobile WebKit emulation   |           38 |           112 | 27 [24–44]                    |                               48 |                                 29 |

Allocated WASM linear-memory high-water is **2,752,512 bytes (2.625 MiB)** in
these summary/dashboard samples, versus M8C.4's roughly 1.69 MiB. This is not
the JS heap or total browser process memory. Full traces have higher costs.
No physical Android/iOS hardware or actual Safari installation was tested.

Current static opponent artifact is **97,295 bytes raw**, about **17 KB gzip**.
It is lazy, hashed and cached once per page session. Only the selected user
profiles come from D1/API. Local real-publication tests observe one opponent
request and no new HTTP requests on exact replay. Initial selective-data loads
in the six-project sample used 29 requests / 149,233 decoded response bytes
(API plus opponent asset), excluding page bootstrap, shared pilot and WASM.
The final Chromium capture additionally records all observed HTTP responses;
see JSON for that separately labeled scope. Decoded body bytes are not compressed
WAN transfer. Production asset raw/gzip sizes are recorded alongside measurements;
Python gzip level 6 differs slightly from Vite's compressor.

The final full-startup captures each observed **36 HTTP responses totaling
1,135,201 decoded body bytes**, including page bootstrap, Worker/WASM, catalog,
pilot, opponent artifact and selected API data. Exact replay added no requests.
This is local uncached page-session activity, not a cold CDN or compressed-wire
measurement. Current production assets (Python gzip level 6):

| Asset             | Raw bytes | Gzip bytes |
| ----------------- | --------: | ---------: |
| Opponent artifact |    97,295 |     17,553 |
| Main frontend JS  |   280,406 |     86,911 |
| Main CSS          |    11,625 |      3,250 |
| Web Worker JS     |     6,206 |      2,295 |
| WASM              |   484,855 |    158,157 |

Worker-to-React messages are about 60 KB in JSON-equivalent size (exact sample
distributions in JSON). Structured-clone heap/copy byte counts are not directly
measured; these sizes must not be interpreted as whole-process memory use.

Measured UI assembly includes validation and data loading, separately from
Worker startup/execution. A frozen private snapshot caches successful opponent
validation without trusting caller-mutated data or bypassing source checks.
Tests verify mutation, stale copies and conflicting shared profiles still fail.
Representative repeated assembly samples are about 8–33 ms in Edge/Chromium/
Firefox and about 284–302 ms in WebKit emulations; full end-to-end replay samples
are about 25–382 ms. These are one first/one replay per project, not latency
confidence intervals. WebKit's remaining common assembler/profile validation
cost remains visible; no negligible-assembly-cost claim is made.

For comparison, a sizing-only preview of 29 clubs (excluding CHA) contains 261
distinct existing profiles, **310,757 bytes raw / 55,480 gzip**. Delivery is
practical. With the unchanged scheduler, 23 clubs would receive six games and
six clubs four, determined by sorted IDs. Nine exactly balanced opponents are
therefore the deliberate v1 choice. This preview is not published as a v1 pool
or used by the game.

## Validation and remaining issue

| Check                                                                                                | Result                                                                           |
| ---------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| Rust workspace, including new dashboard/schedule/projection tests                                    | **63 passed**                                                                    |
| Rust fmt, Clippy `-D warnings`, native release examples, WASM build                                  | Pass                                                                             |
| TypeScript/data-client/draft/pricing regression suite                                                | **36 passed**, plus three focused opponent/cache tests after optimization        |
| Production build, TypeScript, ESLint, Ruff                                                           | Pass                                                                             |
| Browser parity/delivery/regression suite                                                             | **72 passed**                                                                    |
| Edge parity/delivery/regression suite                                                                | **15 passed**                                                                    |
| Isolated final dashboard full native/WASM parity, neutral/defense and summary/events                 | **6 passed**                                                                     |
| Default API/game integration                                                                         | **50 passed**, eight optional full-publication skips                             |
| Genuine 526-player local D1 tests, including skipped publication/reroll paths, defense and dashboard | **22 passed**                                                                    |
| Final frozen-cache dashboard integration across all six projects                                     | **6 passed**                                                                     |
| API tests; API/alpha dry-runs; alpha tools                                                           | **8 passed**; dry-runs pass; **6 tools tests passed**                            |
| Local single-origin alpha hosting/game regression                                                    | **47 passed**, five optional full-publication skips; local D1 SELECT also passed |
| Full source-backed Python suite                                                                      | **178 passed, one pre-existing local-cache failure**                             |
| Focused final opponent/data/dashboard-contract tests                                                 | **4 passed**, including official-source byte reproduction                        |

The Python failure is
`test_verified_producer_reproduces_both_catalog_versions_when_local_research_is_available`:
the optional ignored `data/processed/m8c2/draft-budgets.json` binds the old
draft-engine source hash, while the previously committed reroll change modified
that file. The old pricing report also intentionally freezes that historical
hash. M8C.5 does not change the draft engine or either price catalog. The test
correctly refuses the stale research combination. Both catalog reproduction
assertions pass before that diagnostic-summary failure. This is **not** a fully
green Python-suite claim. Resolving the historical research-cache/test lifecycle
should be separate from rewriting frozen pricing evidence; no integrity check,
source lock, catalog, legacy golden or research report was weakened to hide it.

CI's existing Rust-to-JavaScript build-artifact handoff now includes and marks
executable the new native `project_season` comparator. Local Windows tests use
the same boundary; hosted GitHub Actions has not been run because this work is
uncommitted/unpushed.

The dashboard game tests cover all 162 scores/totals, filters, keyboard focus to
selected details, mobile document overflow, replay caching, independent batting
order/fielding, optional error avoidance, source mismatches and new draft/reset.
Native tests additionally reconcile every batter counter across all games,
inning scores, per-opponent records, schedule permutations, missing profiles,
duplicate rosters and explicit-neutral identity. New contracts reject unexpected
event logs and unsupported projection versions. Existing full-result goldens
remain unchanged. Desktop/mobile screenshots were inspected; human screen-reader
and physical-device usability remain untested.

## Limits and recommended next steps

This small pool is not calibrated to represent average MLB opponent strength;
its PA-ranked full-season regulars can differ materially from real team offense.
The nine-club choice balances game counts, not competitive strength or player
prices. Win-rate balance needs human playtests, not hidden scoring changes.

The known hit/PA/GDP excess, including the historical **+38.8% GDP discrepancy**,
compressed scoring variance, standardized pitching, fixed nine hitters, empty
extra innings, no substitutes and incomplete defense remain. No new statistical
adjustments, opponent defense or authentic roster/schedule claims are introduced.

Next: human desktop/phone/dashboard playtests; separately resolve the stale
pricing-research cache test; profile remaining WebKit assembly cost if needed;
then explicitly review larger-pool frequency/order policy and evaluation needs.
Expanded mechanics or recalibration need separate authorization/evidence.
