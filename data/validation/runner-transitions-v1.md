# M9B.1 — Runner outs and advancement corrections

**Implemented as an explicit experimental mode.** Supported hit-related runner
outs, extra batter advances and a narrow terminal force-choice class now resolve
jointly in Rust. Credited hit type remains distinct from final batter destination.
Source-proven timing third outs can score; force third outs cannot; a winning
timing run cancels a later tag retirement. Default gameplay and every legacy
golden retain their old rules.

This is a supported event-accounting correction, **not full calibration**. The
2024 development experiment reduces PA/hit excess modestly, while runs and score
variance move slightly farther from historical targets. No probabilities were
adjusted to hide those outcomes. M9B.2 sacrifice accounting is not implemented.

The information used here was obtained free of charge from and is copyrighted by
Retrosheet. Interested parties may contact Retrosheet at
[www.retrosheet.org](https://www.retrosheet.org/).
Lahman attribution/license remain in [DATA_ATTRIBUTION](../../docs/DATA_ATTRIBUTION.md).

See [rules, contracts and reproduction](../../docs/RUNNER_TRANSITIONS.md),
[machine-readable measurements](runner-transitions-v1.json), and the unchanged
[M9A audit](simulation-accuracy-v1.md).

## Source evidence and coverage

Verified the existing Lahman/M4 source provenance and separate 2024 development
play lock; no lock or upstream byte was replaced. Fit selection is full
regular-season PAs in innings 1–8, no SH/SF, single/double/residual contacts.
2022–2023 fit the model; 2024 is development. No 2025 plays are read, and the
previously inspected 2025 data is not an untouched confirmation sample.

| Classification                                       | 2022 training | 2023 training | 2024 development |
| ---------------------------------------------------- | ------------: | ------------: | ---------------: |
| Selected single/double/residual observations         |       105,846 |       105,154 |          105,195 |
| Newly represented hit running outs without runs      |           353 |           334 |              329 |
| Newly represented proven timing third outs with runs |            90 |           114 |               94 |
| Newly represented extra batter advances              |           666 |           668 |              668 |
| Newly represented force choices                      |         1,199 |         1,122 |            1,057 |
| Already supported v1 GDP                             |         3,112 |         3,138 |            2,914 |
| Already supported v1 ROE                             |         1,025 |           943 |            1,014 |
| Already supported v1 FC                              |         2,736 |         2,584 |            2,582 |
| Already supported v1 safe transitions                |        73,604 |        73,417 |           73,387 |

Training promotions total **4,546 of 211,000 selected observations** (2.15%).
They represent **891 of 1,086** earlier hit-running-out proxies (82.0%),
**1,334 of 1,338** extra-batter-advance proxies (99.7%), and 2,321 terminal force
choices previously treated as ordinary batter outs. Terminal force correction
usually changes FC/runner identity rather than the total number of outs.

Training running-out attempts recovered: single to second **401**, single to
third **129**, single to home **202**, double to third **61**, double to home
**98**. Counts include batter and existing-runner attempts. The 2024 counterparts
are **203 / 62 / 71 / 33 / 54**. Every promoted out has an explicit raw attempted
base plus parsed out evidence and identity/out-count reconciliation.

Remaining training proxies total **45,895**, including 44,811 ordinary-terminal
or unsupported-contact cases, 703 compound/other-DP cases, 183 unresolved
destinations, 173 unresolved non-terminal run/out order cases, 14 unproven running
outs and 11 error/appeal-out cases. Their complete reason/event cross-tabs are
retained in the new audit. These counts are a source classification, not an
assertion that ordinary third outs are all erroneous or missing running outs.

The new estimator keeps all observations in their original 72 cell denominators.
The unchanged 50-observation rule still falls back for double/zero outs/third-only
(35 training observations). Maximum choices are 27, below the existing 128 bound.
Integer Hamilton rounding preserves exactly one million tickets per cell. Sparse
and unsupported mass is counted and conservatively represented, never dropped.
The observation floor applies to each complete cell, not each rare choice; rare
outcomes retain substantial estimation uncertainty and are not player-skill claims.

## Implemented semantics and exclusions

The fitter reconciles batter/pre-runner IDs with post bases, credited scorer IDs,
RBI, outs delta, restricted raw advance syntax, and terminal LOB IDs. LOB IDs
prove survival after post-base columns clear; their terminal bookkeeping bases
use explicit advances or the conservative hit/start base. Movement after the
third out is not reconstructed or carried into another inning.

Promoted transitions carry fixed arrays of out kinds and attempted bases plus a
proven run-before-out flag. They retain per-runner destinations, RBI and reach
classification. Rust rejects absent identities, collisions, passing/backward
movement, invalid force chains, invalid hit/out combinations and unproven timing.
No separate runner-out random roll, extra PA or extra batting-order advance occurs.

The source's credited runs establish order for a sole non-force third out. They
do not establish order for non-terminal runs plus an out; those cases remain
proxied rather than using semicolon order as a clock. Complex/uncertain events,
appeals, apparent outs involving errors, multiple new running outs, other DP/TP,
triples' running outs and unresolved identities remain unsupported. V1 ordinary
contact advancement, ROE and GDP keep their supported semantics.

Third-out and game-ending rules were checked against
[Official Baseball Rules 5.08 and 9.06](https://mktg.mlbstatic.com/mlb/official-information/2026-official-baseball-rules.pdf):
force/batter-before-first third outs cannot score; a legal timing run can count;
non-HR walk-offs stop at the winning run and limit credited hit bases. New timing
metadata allows canceling a later tag out once the winning run ends the game.
The game attributes runs and RBI only to retained scorers and counts all terminal
stranded runners by conservation. New tests exercise suppression, timing, hit
credit, RBI, cursor advancement and walk-off LOB independently of any golden.

Sacrifices, between-PA SB/CS/pickoffs, WP/PB/balks, new contact classes, pitching,
defender abilities, prices and schedules remain outside this change.

## Versions, defaults and defense

New game input **1.4.0**, season input/result **1.2.0**, game result **1.2.0**;
rules `runner-outs-nine-inning-v1`; policy `retrosheet-runner-outs-v1`; model
`retrosheet-runner-transitions-v1`. The model content ID is
`runner-transitions:b12dc1d0dac044cc6896735f88d1e63f31dc59ff288c9e63054c5d710f86255e`.
The source identifier stays linked to the unchanged Retrosheet lock.

New schemas are separate from the old input/result/model schemas. The compact
dashboard accepts result version 1.2.0 while keeping its existing computed layout.
Old profiles, defensive/opponent publications, source locks, scheduler and seed
versions are unchanged. Engine metadata stays 0.4.0 to preserve legacy serialized
goldens; the new rules/schema/model tuple identifies the experimental semantics.

Default gameplay remains legacy. Opt-in uses generated versioned input or the
new explicit `assembleRunnerSeason` diagnostic function, which verifies model
identity/source and preserves the supplied lineup/profile/schedule snapshot.
No gameplay toggle, default publication swap or new endpoint is added.
The existing Worker accepts the JSON and returns compact dashboard/batting data;
full traces are requested only for diagnostic parity/replay.

Existing error-avoidance artifacts are **incompatible with this new mode** and
are rejected. Old/defensive rules reject the new model; new rules reject old
models and defensive configuration. This avoids silently changing error/out
mapping or applying defensive effects twice. Old neutral and experimental
defensive modes retain their original outputs and assignments.

## Direct accounting versus season effects

On **the observed training states**, replacing only the promoted proxies adds
**891 retirements**, **214 credited runs** and **34 RBI** compared with the old
proxy resolutions. Extra advances and source RBI exceptions explain why adding
runner outs need not reduce immediate runs or make runs equal RBI. The 2024
development counterparts are +423 outs, +121 runs and +31 RBI. These are direct
source-state accounting differences, not season projections.

All GDP choice weights are **exactly unchanged in every cell**, including integer
rounding. Applying either table to observed training states gives the same expected
GDP, **6,250.004798**, against 6,250 observed. Actual season GDP differences arise
through future opportunities, conditional-cell mix and Monte Carlo variation,
not a GDP probability reduction.

Season experiments use the same root seeds and unchanged batting distributions;
the additional joint choices can change later ticket consumption and paths. A
paired seed is therefore a reproducible comparison, not a guarantee of a matched
play stream. Report aggregate uncertainty and source-state effects separately.

## Old/new accuracy measurements

Historical fixed-order calibration: **30 clubs × 10 seasons × three years × two
models = 1,800 seasons / 291,600 games**. Same-year profiles and synthetic opposing
lineups follow the established experiment; standardized pitching and fixed nines
remain conditioning assumptions. All metrics and Monte Carlo intervals are in JSON.

| Window           | Metric per user team-game |     Old |     New | Historical |
| ---------------- | ------------------------- | ------: | ------: | ---------: |
| 2022 training    | PA                        | 38.7680 | 38.6193 |    37.4593 |
|                  | Hits                      |  8.6648 |  8.6341 |     8.1636 |
|                  | Runs                      |  4.2748 |  4.2441 |     4.2833 |
|                  | GDP                       |  0.8836 |  0.8710 |     0.6981 |
| 2023 training    | PA                        | 39.1781 | 39.0114 |    37.8815 |
|                  | Hits                      |  8.9060 |  8.8688 |     8.4031 |
|                  | Runs                      |  4.6322 |  4.5932 |     4.6156 |
|                  | GDP                       |  0.8798 |  0.8609 |     0.7132 |
| 2024 development | PA                        | 38.8512 | 38.6792 |    37.5564 |
|                  | Hits                      |  8.6685 |  8.6380 |     8.1974 |
|                  | Runs                      |  4.3196 |  4.2856 |     4.3934 |
|                  | GDP                       |  0.8768 |  0.8698 |     0.6643 |

The development PA excess falls by about 13%, hit excess by about 6%, while GDP
still exceeds history by about 31%. These changes do not justify a global
multiplier or player-defense adjustment. In 2024, RBI/game is 4.2523 → 4.1964,
ROE 0.2322 → 0.2274, and modeled FC 0.7509 → 1.0556; the FC increase includes the
explicit restoration of terminal forced-runner/batter identity and credit.
ROE is not all fielding errors; no separate full-game historical ROE/FC target
is invented from game logs.

2024 runs SD is **2.9802 → 2.9731** (historical 3.0865), 10+ runs
**5.984% → 5.825%** (6.608%), shutouts **6.576% → 6.761%** (6.608%), and extra
innings **9.977% → 9.963%** (8.893%). Thus mean runs, dispersion and high-score
frequency are not improved by this isolated scope. Missing sacrifices, running
events, fixed-roster selection and neutral pitching still matter. Parameters
were not changed in response to these measurements.

## Current nine-opponent seasons and opportunities

Additional **600 seasons / 97,200 games**: CHA/HOU/NYA PA-ranked full-season
profile nines, 100 root seeds each under both modes, base seed 20261029. The
same nine published opponents, including synthetic mirror-club matchups, get
18 games each, nine home/nine away. These are fixed computation cohorts, not
claimed budget-legal draft samples or authentic historical full rosters.

| Roster | PA old → new      | H old → new     | R old → new     | GDP old → new   | LOB old → new   |
| ------ | ----------------- | --------------- | --------------- | --------------- | --------------- |
| CHA    | 38.0128 → 37.8186 | 8.3128 → 8.3082 | 3.7283 → 3.7263 | 0.8287 → 0.8203 | 7.0664 → 6.9490 |
| HOU    | 39.2294 → 39.1264 | 9.4468 → 9.4409 | 4.7478 → 4.7232 | 0.9728 → 0.9503 | 7.5562 → 7.4623 |
| NYA    | 39.4961 → 39.3270 | 8.8304 → 8.7879 | 4.8720 → 4.8296 | 0.9283 → 0.9084 | 7.7286 → 7.6157 |

Paired PA differences/game with MC95 half-widths are **-0.1943 ± 0.0967**,
**-0.1030 ± 0.0955**, **-0.1691 ± 0.0945**. Corresponding hit and run intervals
include zero in these individual cohorts. Avoid claiming a precise per-roster
hit/run improvement from their point estimates alone.

First 20 seeds per roster/mode capture events: **19,440 games**. User innings
1–8 trace metrics are comparable across modes; terminal/walk-off destinations
are excluded from realized safe-advance measurements.

| Roster | Residual GDP-eligible share old → new | GDP/eligible old → new | PA/played half old → new | New tag outs per traced season | New extra batter bases per traced season |
| ------ | ------------------------------------- | ---------------------- | ------------------------ | -----------------------------: | ---------------------------------------: |
| CHA    | 20.058% → 19.764%                     | 23.416% → 23.603%      | 4.1883 → 4.1707          |                          15.90 |                                    21.90 |
| HOU    | 21.918% → 21.715%                     | 23.329% → 23.263%      | 4.3742 → 4.3660          |                          18.55 |                                    29.55 |
| NYA    | 22.454% → 22.276%                     | 23.328% → 22.872%      | 4.4066 → 4.4069          |                          17.55 |                                    27.25 |

The joint single/double/residual-contact runner advance-base summaries and all
24 base/out cells remain in the
measurement JSON/ignored row files. GDP opportunity factorization is retained;
state exposure and conditional conversion must continue to be examined separately.

| Roster | Wins mean ± MC95, old → new | Season win SD, old → new | Central empirical 95%, old → new |
| ------ | --------------------------- | ------------------------ | -------------------------------- |
| CHA    | 66.06 ± 1.14 → 67.31 ± 1.26 | 5.80 → 6.41              | 54–77 → 54–80                    |
| HOU    | 82.86 ± 1.20 → 83.26 ± 1.13 | 6.11 → 5.74              | 72–93 → 72–94                    |
| NYA    | 84.46 ± 1.23 → 84.92 ± 1.24 | 6.28 → 6.31              | 75–97 → 72–96                    |

No randomness reduction is indicated. Differences of a win or so in mean strength
have Monte Carlo uncertainty and do not establish an improvement in historical
team-win prediction with standardized pitching. Score/RA/RD variability and tail
frequencies are recorded for each mode and roster in JSON.

## Reproducibility, parity, performance and tests

Windows ARM64; rustc 1.88.0; Python 3.12.14; Node 22.21.0. Engine 0.4.0 and
existing SplitMix64/indexed-seed versions. Historical experiment root seeds use
the original base 20261025; roster roots use 20261029 and `repeat*3+rosterIndex`.
No host randomness is used by the core. MC95 values describe simulated repetition
uncertainty, not source quality, model uncertainty or untouched historical years.

Input, model and row hashes, complete source reason counts, seeds and measured
results are retained in the new report artifacts. Exact native season probes
repeat six seasons per mode and match summary/events outcomes. The Rust tests
replay the new source-backed full season choice-by-choice and validate every
source-model choice. Existing legacy/defense/dashboard goldens remain unchanged.

Transition model compact JSON is **44,315 → 79,516 bytes**, gzip
**3,532 → 5,129 bytes**. The shared single-opponent input is
**64,656 → 99,859 bytes**, gzip **7,203 → 8,849 bytes**. No new model asset is
automatically loaded by default gameplay. Full source rows and experiment inputs
remain ignored rather than being transferred to React.

Final isolated native measurements, 100 seeded summary seasons per mode/fixture:

| Fixture                                  | Old mean / first measured season | New mean / first measured season |
| ---------------------------------------- | -------------------------------- | -------------------------------- |
| Single opponent, observed NYA/CHA orders | 12.19 / 15.34 ms                 | 12.64 / 15.39 ms                 |
| Current nine-opponent dashboard fixture  | 13.48 / 15.57 ms                 | 14.52 / 16.80 ms                 |

Native timing includes input cloning, validation, simulation and result creation;
JSON parsing/serialization is outside the season timer. The first measured season
follows a standalone game, so is not a cold-process claim. An earlier isolated
single-opponent pass measured 11.94 → 14.29 ms and another 13.19 → 12.79 ms. These reversals show
why these small timing differences should not be treated as a precise speed effect.
No timing confidence interval or physical-phone performance guarantee is asserted.

Browser/WASM core simulation warm medians (five subsequent calls after one fresh
Worker's first call), measured sequentially without concurrent builds/test batches:

| Target                    | Single-opponent old → new | Nine-opponent old → new | Nine-opponent total WASM call old → new |
| ------------------------- | ------------------------- | ----------------------- | --------------------------------------- |
| Chromium                  | 30.8 → 31.4 ms            | 33.6 → 34.1 ms          | 40.8 → 43.1 ms                          |
| Firefox                   | 214 → 166 ms              | 193 → 200 ms            | 220 → 229 ms                            |
| WebKit                    | 35 → 37 ms                | 41 → 41 ms              | 61 → 57 ms                              |
| Edge                      | 16.0 → 16.1 ms            | 18.0 → 18.5 ms          | 21.1 → 21.9 ms                          |
| Mobile Chromium emulation | 31.7 → 30.8 ms            | 31.7 → 36.6 ms          | 40.5 → 44.6 ms                          |
| Mobile WebKit emulation   | 34 → 37 ms                | 42 → 46 ms              | 60 → 59 ms                              |

The total WASM call includes input/result string copies, parsing and serialization;
it can vary differently from core simulation. First-call core timings, all six
samples, initialization/parse/serialization times and memory samples are in JSON.
Fresh Workers may still benefit from browser/OS caches and compiled-code reuse.
Both fixtures are computation controls; the nine-opponent fixture's synthetic star
user roster is not claimed budget-legal. The separate 100-root cohorts above use
the published PA-ranked CHA/HOU/NYA nines.

The nine-opponent input is **141,900 → 177,103 bytes**, gzip
**20,211 → 21,923 bytes**. Gzip sizes use Python level 9 with `mtime=0`;
input/model sizes are compact UTF-8 JSON rather than pretty-printed file size.
Compact dashboard/batting JSON is **56,071 → 56,127 bytes** for the single-opponent
fixture and **59,593 → 59,568 bytes** for nine opponents. Full summary-season
serialization, not sent to React's compact path, is **912,183 → 951,187 bytes**
and **1,014,754 → 1,052,751 bytes**, respectively. No full event traces enter the
compact response; the browser tests assert this explicitly.

Maximum allocated WASM linear memory during the six compact calls is
**2,555,904 → 2,621,440 bytes** (single opponent) and
**2,752,512 → 2,818,048 bytes** (nine opponents): one extra 64-KiB page in each
case. This is not whole-browser/JS heap, native peak RSS, full-trace peak memory,
physical-phone or WAN memory/transfer measurement. New metadata consists of fixed
arrays and adds no per-PA heap allocation or separate retirement roll.

| Validation                                                         | Final result                                                                                                    |
| ------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------- |
| Rust workspace                                                     | Pass, including all legacy/defense/dashboard goldens and six new runner tests                                   |
| Final focused Rust runner tests / all-target Clippy / fmt          | Pass                                                                                                            |
| Source-backed Python full run                                      | 189 passed; one new source round-trip assertion initially compared tuples with JSON lists                       |
| Corrected Python runner tests with both verified sources           | **5 passed**; canonical serialized bytes match exactly, including the unknown-RBI and timing-passing safeguards |
| Ruff check/format                                                  | Pass                                                                                                            |
| TypeScript typecheck / ESLint / production build / WASM build      | Pass                                                                                                            |
| Data/client/draft tests                                            | **38 passed**                                                                                                   |
| API suite                                                          | **8 passed** on isolated rerun after an initial 30-second timeout during concurrent jobs                        |
| Main browser suite                                                 | **76 passed**; its deployment case passed unchanged on isolated rerun                                           |
| Edge browser suite                                                 | **16 passed**                                                                                                   |
| Final focused old/new single- and nine-opponent parity/cost checks | **6 browser targets passed**, repeated full traces at zero/max-u64 and compact native parity                    |
| Real-publication local-D1 gameplay integration                     | **58 passed**, plus **14 Edge tests passed**                                                                    |
| API build dry-run / local D1 SELECT                                | Pass; no remote operation                                                                                       |

The five legacy audit regression tests also pass, including a real native summary/events probe that ignores the additional trace observations when comparing outcomes.

The source round-trip assertion was corrected to compare exact canonical bytes,
not to relax any source/model field. The deployment case initially saw a stale
deleted asset return HTTP 500 during concurrent load, then passed its original
404/reload assertions in isolation. API and deployment tests were not weakened.
No known failing assertion remains. Exact native probes, every source-model
choice, complete-season accounting, deterministic replay, summary/events and
native/WASM parity are all covered. Historical artifacts/goldens are unchanged.

## Limitations and M9B.2 recommendation

The promoted classes leave unproven chronology and multi-out/compound plays as
explicit proxies; this is not a full event-file interpreter. Already-supported
v1 choices retain their existing walk-off ordering assumptions rather than gaining
invented source chronology from this extension. Additional batter
advancement can arise on throws/errors without changing hit credit, and the model
does not claim individual speed/arm or defensive attribution. The new mode rejects
the old error-avoidance artifacts until their mapping is separately validated.

V1 GDP still holds the other runners and suppresses all runs, including on zero-out
GDP. Recovering those advances safely would require ordering multiple retirements
relative to scoring/walk-offs beyond this single-retirement promotion. Those
conservative resolutions remain counted; no GDP weight was changed to offset them.

PA/hit/GDP discrepancies and low score variance remain. Automatic-runner extras,
between-PA running, pitching/park heterogeneity and explicit contact classes are
not implemented. Repeated seeds constitute new Monte Carlo evidence, not a new
historical confirmation set. The 2024 development sample remains development;
2025 remains previously inspected diagnostic evidence.

M9B.2 should add contextually supported SH/SF and official denominator/AB/RBI/OBP
accounting with new immutable profile/rules/transition IDs. Keep the 200-PA prior
unless separately authorized, retain old weights and replay modes, validate
impossible sacrifice states/two-out restrictions and runner timing, and publish
all metrics without tuning to a target run average. Do not disguise ordinary
advancing outs as officially credited sacrifices. This report recommends that
scope; no M9B.2 implementation, commit, push or deployment is performed.
