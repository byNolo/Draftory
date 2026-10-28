# M8C.4 error-avoidance simulation v1

2026-10-28. Implemented locally, **opt-in**, without changing batting profiles,
prices, the 65-credit budget, pitching, opponents, schedules or legacy goldens.
No deployment or M8C.4 commit. M8C.3 was committed separately as `89081bf` without
pushing. [Methodology/reproduction](../../docs/DEFENSIVE_SIMULATION.md),
[data/reliability results](defense-v1-data.json),
[paired outcomes](defense-v1-outcomes.json),
[performance measurements](defense-v1-performance.json),
[evaluation plan](defense-v1-evaluation-plan.md).

## Implemented mechanics

Python publishes separate, content-addressed player-position error profiles and
a training-derived shared model. Rust transfers probability between supported
error reaches and existing ordinary-out/runners-hold choices while the opponent
bats. Batting weights, GDP/choice weights, destinations and zero support are
preserved. There is no final-score adjustment or independent second error roll.
The neutral pitcher and existing opponent defense remain neutral; DH does not
field. The fielding assignment follows draft positions independently of batting
order, including reordered-lineup native/WASM integration.

Only **1B/2B/3B/SS** have sufficient unambiguous mapping observations for this v1.
Catcher and each OF position are neutral rather than forced into a weakly
supported model. Range, hit-to-out conversion, individual GDP, framing, stealing,
blocking and arms are not implemented. This is not overall defensive ability.

The UI's **Experimental error avoidance** option is off by default for comparison
and legacy play. Enabling it loads the static supplement, displays exposure and
neutral/insufficient statuses, and assembles explicit defensive input. It fails
visibly on incompatible data rather than quietly downgrading. Full results and
local diagnostics retain new-mode versions and defensive references for replay.

## Data and reliability

All original Lahman/M4 locks and source/profile/catalog bytes remain unchanged.
The supplement uses the official Lahman 2025 release and unchanged 526-player
2024 publication, dataset
`dataset:1fba260824fe05abec3c5950cd184caa0d314b41f1253bc782f97b678bb28add`.
It has **788 eligible player-position profiles** and ID
`defense-supplement:bc23560d196fa7f10a7424906a6460d3c4a546f018fb356287b64526eba24611`.
No D1 schema/import or full batting-profile duplication.

Source aggregation preserves nulls, sums each team/stint once within a position,
and never adds generic OF to LF/CF/RF. The relative-rate estimator uses complete
`E/(PO+A+E)` facts, **100 defensive innings** minimum and **1,000 prior chances**,
shrunk to same-position 2024 AL/NL rates. References require complete positive
chances and >=300 innings. Minimum/prior choices were compared on 2022→2023
prediction, with disclosed 2023→2024 development sensitivity. All twelve settings
are retained; no reputation, desired wins or 2025 holdout selected the effects.
The pooled log-loss improvements are small and do not establish difficulty-
adjusted defensive talent or per-player confidence intervals.

| Position | Eligible | Observed active | Insufficient | Mapping neutral | Reference E / chances |
| -------- | -------: | --------------: | -----------: | --------------: | --------------------- |
| C        |       77 |               0 |            0 |              77 | 282 / 38,759          |
| 1B       |       93 |              75 |           18 |               0 | 184 / 32,888          |
| 2B       |      100 |              83 |           17 |               0 | 213 / 14,928          |
| 3B       |      104 |              87 |           17 |               0 | 337 / 9,484           |
| SS       |       77 |              66 |           11 |               0 | 439 / 16,034          |
| LF       |      121 |               0 |           27 |              94 | 87 / 6,691            |
| CF       |       92 |               0 |           15 |              77 | 96 / 10,695           |
| RF       |      124 |               0 |           23 |             101 | 106 / 7,378           |

Totals: **311 active, 128 insufficient, 349 mapping-neutral, zero unknown** in
this particular pool. Unknown/incomplete future records receive neutral effect
with their reason retained; tests exercise that path. Eligibility is unchanged.

Training uses only full regular-season, no-sacrifice PAs in innings 1–8 of
2022/23. Exactly one error must match the primary fielder, the batter must reach,
and a supported out alternative must exist. Advancing-only errors, unsupported
compound/ambiguous plays and pitcher errors remain unchanged. There are 1,754 attributable
paired ROE before the position floor, **1,600** at enabled positions. The existing
50-observation sparse-evidence safeguard is applied per primary position over
training, not an assertion that fifty plays validate every fielder.

A separately pinned official **2024 development** archive confirms category/
attribution availability: 880 attributable pairs before the position floor,
812 at enabled positions. Its SHA-256 is
`a3e8c08876ddf70e1ffb0b20486c2873cf4aae19e0acc8002096e9056107615b`.
It is not fitted or used as an untouched holdout. No new 2025 plays or model
retuning. Source integrity hashes are project observations, not upstream signatures.
See [attribution/licensing](../../docs/DATA_ATTRIBUTION.md) for Lahman CC BY-SA
3.0 and the required Retrosheet notice.

## Example profiles

Values below are ratios of **estimated recorded error rate** to the position
reference. Lower is better only for the supported error subset, not total defense.
Active ratios in the whole publication span 0.660573–1.481654.

| Player / position   | Innings | E / chances | Error ratio | Status                          |
| ------------------- | ------: | ----------- | ----------: | ------------------------------- |
| Paul Goldschmidt 1B |   1,313 | 5 / 1,323   |    0.815194 | Observed                        |
| Francisco Lindor SS | 1,311.7 | 12 / 564    |    0.919621 | Observed                        |
| Bobby Witt SS       | 1,393.7 | 15 / 583    |    0.977801 | Observed                        |
| Matt Chapman 3B     |   1,338 | 15 / 405    |    1.012197 | Observed; range not represented |
| Mookie Betts 2B     |     105 | 0 / 33      |    0.968054 | Observed, heavily shrunk        |
| Mookie Betts SS     |   531.3 | 9 / 245     |    1.067241 | Separate position               |
| Aaron Judge CF      |     903 | 0 / 252     |    1.000000 | Mapping neutral                 |
| Mike Trout CF       |     203 | 0 / 67      |    1.000000 | Mapping neutral                 |

Zero errors never becomes perfect defense. Core facts, source/model IDs,
compatible batting profile, year/position, policy/reference context and quality
status remain inspectable independently of fictional prices.

## Game impact: paired 64-seed development experiment

Five modes × seeds 0–63 × 162 games = **320 seasons / 51,840 games**. The same
nine published batting profiles, CHA opponent, pitching and schedule are used
throughout. This diagnostic lineup is synthetic and is not claimed to fit the
65-credit budget; legal draft-to-season gameplay is tested separately. Controls
replace supported-position ratios with 0.5 or 1.5 and are
explicitly synthetic; they are never published player ratings. All neutral
**game/event/counter** outputs equal legacy exactly; only new-mode metadata differs.

Per-season means; change columns are paired differences from legacy ± 95% Monte
Carlo half-width across 64 seeds. These are simulation uncertainty for this fixed
fixture, not real-world defensive forecast intervals.

| Mode             | Opponent ROE | Runs allowed | Paired RA change   |    Wins | Paired wins change |
| ---------------- | -----------: | -----------: | ------------------ | ------: | ------------------ |
| Legacy           |       36.391 |      575.844 | —                  | 113.625 | —                  |
| Explicit neutral |       36.391 |      575.844 | 0 exactly          | 113.625 | 0 exactly          |
| Real assignments |       35.438 |      574.969 | **-0.875 ± 0.613** | 113.766 | +0.141 ± 0.163     |
| Strong control   |       22.453 |      567.672 | **-8.172 ± 2.326** | 114.312 | +0.688 ± 0.564     |
| Weak control     |       50.625 |      582.469 | **+6.625 ± 1.639** | 113.266 | -0.359 ± 0.457     |

Strong/weak controls have measurable, correctly directed effects on runs allowed.
Real assignments have a small effect here; their win change is unresolved. Do
not turn these results into a fixed runs-saved bonus or a general player value.

Relative to legacy, strong control changes opponent ordinary contact outs by
+11.375 ± 2.945, PA -13.828 ± 5.728, hits -3.062 ± 2.332 and GDP -1.500 ± 0.683.
Weak control gives ordinary outs -10.594 ± 3.403, PA +15.203 ± 5.649, hits
+2.922 ± 1.925 and GDP +1.844 ± 0.746. **Hit and GDP probabilities were not
changed**: opportunities, game length and subsequent shared-RNG paths change.
User runs scored changes are unresolved (+0.156 ± 3.141 strong; -0.312 ± 2.317
weak), consistent with identical offensive inputs rather than fixed offensive
outcomes. The complete JSON includes all requested counters; ignored observations
retain every seed/input hash and 24 base/out state counts per mode/season.

The known **M4 2025 GDP excess (+38.8%) remains unresolved**. This experiment
does not recalibrate that baseline; its fixed 2024/CHA comparison is not the
historical league sample. Conditional GDP weights are unchanged by construction.

## Compatibility, payload and performance

Legacy game 1.0/1.1/1.2 and season 1.0 inputs retain original behavior and goldens.
New opt-in game 1.3, season 1.1, rules `error-avoidance-nine-inning-v1`, model
`error-avoidance-v1` and result 1.1 schemas are separate. Engine metadata remains
0.4.0 for legacy compatibility. Full results echo complete input; compact gameplay
diagnostics retain supplement/model/profile references. Wrong player/position/
year/source/model links and forbidden legacy opt-in fields fail before execution.

The prototype showed significant repeat-copy/validation overhead in browsers.
Immutable configuration now shares through Rust Arc; defensive transitions compile
once per season. Season entry validates **all** matchups, including unused ones,
then uses a private validated-game constructor. Public entry points still validate;
no correctness check or golden was weakened. No per-PA defense allocations or
extra random draws. A new defensive golden and exact trace replay are covered.

Native release, Windows host: compiler setup **0.0086 ms** mean over 1,000 calls.
First-season timings are first calls within the benchmark after setup, **not**
cold OS-cache/startup/network timings. Twenty repeated runs/row:

| Mode    | First season ms | Warm median ms | Warm min–max ms | Full summary JSON bytes |
| ------- | --------------: | -------------: | --------------- | ----------------------: |
| Legacy  |           12.72 |          11.46 | 11.13–12.83     |                 908,652 |
| Neutral |           11.36 |          11.41 | 11.21–11.80     |                 923,543 |
| Real    |           11.63 |          11.51 | 11.22–11.92     |                 923,370 |

Native steady overhead is within observed variation. Parsing/JSON I/O are outside
these loops; input cloning, validation, simulation and result allocation are in
the loop. Each browser mode uses a fresh worker; five repeated simulations after
the first call. Local production assets and browser/OS caches may be warm. Real
assignments, milliseconds:

| Project                   | WASM init | First simulation | Warm median | Warm min–max | Parity |
| ------------------------- | --------: | ---------------: | ----------: | ------------ | ------ |
| Chromium                  |      16.1 |            265.1 |        52.1 | 40.7–206.7   | Exact  |
| Firefox                   |        45 |              297 |         193 | 184–238      | Exact  |
| WebKit                    |       146 |              353 |          95 | 33–124       | Exact  |
| Edge                      |         6 |             27.8 |        15.9 | 14.9–19.2    | Exact  |
| Mobile Chromium emulation |       9.7 |            122.4 |        32.7 | 27.7–39.1    | Exact  |
| Mobile WebKit emulation   |        67 |              165 |          37 | 27–60        | Exact  |

There is residual first/early-warm browser overhead and variability, especially
desktop WebKit/Chromium. These small samples do not isolate tiering/cache effects
from new-model setup; **no negligible-browser-overhead claim is made**. Legacy
warm medians are 33.2/168/39/15.2/31.1/33 ms respectively. All real-mode medians
are below 200 ms on this desktop. Do not extrapolate to physical phones or WAN
first visits. Broader steady-state profiling is warranted if tighter targets are
adopted. The performance JSON retains parsing, serialization, processing and
worker-total variation, not just the core number.

Summary-mode WASM linear-memory high-water was **1.6875 MiB** real versus
**1.625 MiB** legacy in these worker samples (see JSON for exact values). This
is allocated linear memory, not total browser/JS heap or process peak memory.
Physical Android/iOS hardware was not tested. Mobile projects are engine/device
emulation on the same computer.

Actual compact input is **79,515 bytes**, versus **64,627** legacy (+14,888).
Full summary results above include input; React instead receives the established
small summary/batting projection, without full input or event JSON. Detailed
results remain available and are verified exactly against native output.

Measured production assets (Python gzip level 6; Vite's compressor reports
slightly different sizes; neither establishes actual Cloudflare wire transfer):

| Asset                     | Raw bytes | Gzip bytes |
| ------------------------- | --------: | ---------: |
| Defensive supplement      |   427,821 |     73,944 |
| WASM                      |   457,265 |    149,987 |
| Main frontend JS          |   266,614 |     83,333 |
| Worker JS                 |     5,855 |      2,253 |
| Lazy developer harness JS |   129,967 |     12,651 |

The supplement is fetched once when selected; neutral play does not fetch it.
The new WASM/JS code is still part of the application build. Only eight profiles
and shared model enter Rust, no full batting publication or per-game HTTP calls.
The new assets use existing hashed immutable delivery, MIME and CSP rules. No
SharedArrayBuffer, cross-origin isolation, production route or resource required.

## Validation and next steps

Local checks:

| Check                                                                                                                                | Result                                                                      |
| ------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------- |
| Python Ruff lint/format; full pytest with both official source paths and the new development archive present                         | **176 passed**; no source skips                                             |
| Rust fmt/Clippy; workspace tests; release examples; native/WASM build                                                                | Pass; **59 tests** including original goldens and seven new defensive tests |
| TypeScript, ESLint, production Vite build                                                                                            | Pass                                                                        |
| Browser suite / Edge suite                                                                                                           | **67 / 14 passed**                                                          |
| Final optimized defensive full native/WASM parity and benchmark, all six projects                                                    | **6 passed**, including neutral identity and summary/events                 |
| Default API/game integration                                                                                                         | **45 passed**, 3 optional full-publication skips                            |
| Edge API/game integration                                                                                                            | **11 passed**, 1 optional full-publication skip                             |
| Genuine 526-player local D1 import: defensive gameplay all six projects plus full native/WASM publication parity on desktop projects | **10 passed**, exercising the skipped real-publication cases                |
| API tests / data-client and draft tests                                                                                              | **8 / 31 passed**                                                           |
| Worker dry-run and local D1 SELECT                                                                                                   | Pass; no remote operation                                                   |

The comprehensive source checks were rerun after preparation, and the 64-seed
experiment was repeated with the optimized binary without changing deterministic
metrics. Core version/source/catalog/golden files are preserved. Alpha tooling
tests also passed (six tests), along with repository Prettier and whitespace checks.

Remaining limits: all-error TC rates are proxies for a restricted ROE subset;
sample reliability is pooled, not difficulty adjusted; C/OF mapping remains
neutral; fixed full-season hitters and standardized pitching persist; historical
cross-era defense is unsupported; the GDP/hit/PA/variance baseline still fails
some M4 checks. This is a small error component, not a complete defense system.

Next work should make season-dashboard counters and model context inspectable,
without inventing per-fielder errors/runs saved. Expanded opponents need a
separately versioned roster/context and identity/payload tests. Further defensive
components require opportunity-specific evidence and a newly reserved historical
evaluation set. **M8C.5 has not started.**
