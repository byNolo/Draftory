# M7A MLB valuation and eligibility research v1

Research over the existing **526-player 2024 AL/NL publication**, not final game
rules or validated MLB player values. No historical counts, prepared profiles,
Rust rules/RNG, calibration, frontend, Worker or D1 schema were changed.
[Reproduction and artifact guide](../../docs/PLAYER_VALUATION_RESEARCH.md).
[Compact machine-readable results](valuation-eligibility-v1.json).

## Snapshot and experimental context

Dataset `dataset:1fba260824fe05abec3c5950cd184caa0d314b41f1253bc782f97b678bb28add`;
SQL SHA-256 `4dab2562d2b4344cd7499bb6ea54f899b4ba3fe95f1f859c3772d6d7f695828d`.
Official SABR Lahman 2025 release, season-aggregate 2024 profiles, minimum 50 PA,
existing 200-PA prior and acknowledged contact approximation. See
[source attribution and license](../../docs/DATA_ATTRIBUTION.md) and
[M6A publication](../../docs/PLAYER_DATA_API.md). No new source or mirror is used.

Engine **0.4.0**, game input **1.2.0**, season **1.0.0**,
`round-robin-season-v1`, `splitmix64-v1`, contextual contact transitions. Pinned
M4 fixture SHA-256
`d02959d2673eeeec2951644cf327434babefeddeb1cb5b516d809d3aa8a562a4`.
All source, context, policy, transition-model, reference-profile and native-binary
identities are recorded in the compact JSON; per-player profiles/seeds and full
audits are in the generated results. These numbers depend on those versions.

## Eligibility alternatives

`Appearances` measures games appeared, not starts, innings or defensive ability.
Batting totals sum original stints before use; traded players occur once in the
526-player pool. Position games sum across teams independently of batting counts.
The 6,512 published position observations have **zero null cells** in this subset;
that does not establish completeness for all Lahman years. The loader retains
unknowns, and synthetic tests verify that one unknown team contribution keeps a
position unknown. Zero games never qualifies. No missing position is imputed.

| Policy                       |   C |  1B |  2B |  3B |  SS |  LF |  CF |  RF |  DH |
| ---------------------------- | --: | --: | --: | --: | --: | --: | --: | --: | --: |
| Recorded >=1 game            |  79 | 146 | 146 | 144 | 111 | 194 | 138 | 180 | 382 |
| Recorded >=5 games           |  77 | 105 | 117 | 121 |  95 | 146 | 103 | 146 | 200 |
| Recorded >=10 games          |  77 |  93 | 100 | 104 |  77 | 121 |  92 | 124 | 129 |
| >=10 games, all hitters DH   |  77 |  93 | 100 | 104 |  77 | 121 |  92 | 124 | 526 |
| >=20 games, all hitters DH   |  73 |  66 |  76 |  77 |  60 |  83 |  73 |  89 | 526 |
| >=10 games, broad OF, all DH |  77 |  93 | 100 | 104 |  77 | 221 | 221 | 221 | 526 |
| >=10 games, all DH, >=200 PA |  47 |  74 |  74 |  71 |  56 |  93 |  75 |  94 | 365 |
| >=10 games, all DH, >=400 PA |  17 |  47 |  38 |  34 |  34 |  45 |  41 |  48 | 207 |

One game admits incidental appearances. Five games retains a larger flexible pool;
ten removes more incidental entries; twenty makes SS the smallest pool at 60.
At ten games, **196 players qualify for multiple fielding positions**, excluding
DH, and 22 qualify for no fielding position. Universal DH gives those 22 a slot;
observed ten-game DH instead has 129 candidates. This is a policy choice about
allowing any qualified hitter to bat, not evidence of observed DH usage.

Generic OF has 263 positive-appearance players, but it overlaps the specific
outfield columns. Never add OF to LF/CF/RF games. The broad policy deliberately
lets >=10 generic OF games qualify all three slots: CF expands from 92 to 221,
including players without ten recorded CF games. That grants unsupported
specific-position experience and is only a sensitivity test. Strict specific
positions are preferable for an initial nine-position experiment.

Raising the PA floor to 400 leaves only **17 catchers**. This is a much greater
scarcity change than raising the fielding-games threshold. PA is historical
sample size, not an availability or injury forecast. Players below an extra PA
floor count as ineligible, not as records with missing positional data.

## Valuation methods and reference choice

Run expectancy and context-dependent event values motivate offense measurement;
fixed weights need a compatible run environment. See FanGraphs' primary
[linear-weights explanation](https://library.fangraphs.com/principles/linear-weights/).
We evaluated two native experiments instead of importing real-MLB event weights
or duplicating the transition engine in Python:

| Method                        | Measurement                                                                                                     | Interpretation and cost                                                                                                                     |
| ----------------------------- | --------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| Homogeneous nine-copy offense | Mean team runs/game with nine candidate profile templates                                                       | Nonlinear offensive shape and self-synergy; large signal, but not individual contribution or a legal roster                                 |
| Paired single-slot marginal   | Candidate in slot five minus reference in slot five; other eight slots reference; team run difference/162 games | Context-specific substitution effect, directly comparable within the experiment; more sampling noise, batting-order and teammate dependence |

Both use unique synthetic batter-instance IDs, unchanged prepared profile
templates, neutral pitching and the fixture's fixed CHA opponent. No defense,
position-based run adjustment, baserunning skill, platoons, fatigue or roster
availability is added. Repeating parameter templates is an explicit experimental
control, not the Monte Carlo draft's identity policy.

The reference is **Jonathan Aranda**, selected mechanically as the eligible
published profile nearest the PA-weighted mean prepared probability vector
(L1 distance, opponent identities excluded). His 143 PA receive a 0.417 player
blend weight. This is a smoothed reference probability point, not a declaration
that Aranda is MLB average or replacement level. The unweighted pool mean can
therefore be negative relative to him. Actual wRAA compares to a specified league
baseline and scales by opportunities; this experiment does not implement wRAA.
[FanGraphs wRAA](https://library.fangraphs.com/offense/wraa/).

An empirical lower-quartile eligible hitter could be a draft-pool reference, but
calling that MLB replacement level would require evidence about freely available
talent and opportunity allocation. It is not estimated here. WAR also includes
components outside this offense-only experiment; no WAR conversion is proposed.
[FanGraphs position-player WAR](https://library.fangraphs.com/war/war-position-players/).
Pool scarcity is investigated separately as a currency adjustment, not as measured
defensive value or a calibrated replacement-level estimate.

Each of 526 candidates has **eight 162-game repetitions** for each of three
inputs (reference, homogeneous, marginal): **2,045,088 games**. Reference and
candidate comparisons use identical season seeds. The guide specifies sorting,
batching and seed derivation. Per-player standard errors describe simulation
sampling only; shared batch streams correlate player estimates.

## Value distributions and uncertainty

Across all players, homogeneous team offense spans **2.475–9.320 runs/game**,
median **3.946**, interquartile range **3.597–4.448**. Marginal team runs/162 span
**-43.375 to +65.750**, median **-5.875**, IQR **-13.375 to +4.500**.
Spearman-style midrank correlation between methods is **0.937**. Correlation
between marginal ranks from the first four versus last four repetitions is
**0.784**: broad tiers are more defensible than exact adjacent-player rankings.
The median marginal Monte Carlo SE is about **4.3 team runs/162**.

Ten-game specific positions with universal DH, unchanged 50-PA pool:

| Position |   N | Marginal P25 | Median |    P75 | Maximum |
| -------- | --: | -----------: | -----: | -----: | ------: |
| C        |  77 |      -16.875 | -7.875 |  2.000 |  32.125 |
| 1B       |  93 |       -9.375 | -3.125 |  5.125 |  37.500 |
| 2B       | 100 |      -14.375 | -9.000 | -1.000 |  31.125 |
| 3B       | 104 |      -14.375 | -8.188 |  1.500 |  37.375 |
| SS       |  77 |      -15.000 | -7.125 |  2.375 |  37.875 |
| LF       | 121 |      -12.375 | -5.625 |  5.500 |  50.750 |
| CF       |  92 |      -14.375 | -7.875 |  1.000 |  65.750 |
| RF       | 124 |      -12.000 | -5.688 |  5.500 |  59.500 |
| DH       | 526 |      -13.375 | -5.875 |  4.500 |  65.750 |

Positions overlap, so these are not independent groups. P25/P75 use ordered
sample indices floor((n-1)/4) and floor(3(n-1)/4); medians average the middle pair
for even samples. No defensive value is inferred from these distributions.

## Illustrative fictional currency

Let `v` be the marginal point estimate and
`z = (v - pool_min) / (pool_max - pool_min)` across all 526 players. Curves round
half up to integers. These constants are game-design experiments, not fitted
statistical parameters:

- **Linear:** `round_half_up(1 + 19*z)`; range 1–20.
- **Elite:** `round_half_up(1 + 29*z²)`; range 1–30. Higher elite ceiling but
  cheaper middle/lower players than the linear curve.
- **Scarcity:** `round_half_up(1 + 19*z + 2*log2(526 / eligible_slot_count))`.
  This is a slot-specific quote; universal DH has no premium. It is not yet a
  single immutable price for a multi-position player.

All three are monotonic in measured value within a position. Min/max scaling is
sensitive to outliers and sampling error; it must not become permanent pricing
without review. Scarcity is pool size only, not strength of alternatives or
defensive skill. It raises the cost of mandatory scarce slots and can worsen
budget feasibility rather than improve balance.

| Curve    | C median |  1B |  2B |  3B |  SS |  LF |  CF |  RF |  DH | Cheapest distinct nine |
| -------- | -------: | --: | --: | --: | --: | --: | --: | --: | --: | ---------------------: |
| Linear   |        7 |   8 |   7 |   7 |   7 |   8 |   7 |   8 |   8 |                     25 |
| Elite    |        4 |   5 |   4 |   4 |   4 |   4 |   4 |   4 |   4 |                     10 |
| Scarcity |       13 |  13 |  12 |  12 |  13 |  12 |  12 |  12 |   8 |                     63 |

Recognizable 2024 examples; slot is chosen only to display the scarcity quote.
Eligibility also includes universal DH and any other qualifying specific slots.
The +/- column is **one Monte Carlo SE**, not a real-world skill interval.

| Player            | Example slot | Marginal +/- SE | Linear | Elite | Scarcity at slot |
| ----------------- | ------------ | --------------: | -----: | ----: | ---------------: |
| Aaron Judge       | CF           | 65.75 +/- 14.52 |     20 |    30 |               25 |
| Shohei Ohtani     | DH           |  64.88 +/- 6.20 |     20 |    30 |               20 |
| Juan Soto         | RF           |  59.50 +/- 6.28 |     19 |    27 |               23 |
| Bobby Witt        | SS           |  37.88 +/- 5.75 |     15 |    17 |               21 |
| Mike Trout        | CF           |  26.00 +/- 4.83 |     13 |    13 |               18 |
| Jose Ramirez      | 3B           |  24.75 +/- 5.69 |     13 |    12 |               18 |
| William Contreras | C            |  19.75 +/- 5.79 |     12 |    11 |               18 |
| Mookie Betts      | SS           |  14.13 +/- 6.67 |     11 |     9 |               17 |
| Cal Raleigh       | C            |   2.63 +/- 3.80 |      9 |     6 |               15 |
| Adley Rutschman   | C            |   1.63 +/- 3.33 |      9 |     6 |               14 |
| Jonathan Aranda   | 1B           |   0.00 +/- 0.00 |      9 |     6 |               14 |
| Ronald Acuña      | RF           |  -5.88 +/- 5.73 |      8 |     4 |               12 |

Aranda's zero is exact by construction; others' differences need not be
statistically resolved. Betts qualifies at 2B/SS/RF/DH and gets scarcity quotes
16/17/15/11: a concrete unresolved choice between slot pricing and one price.
These are historical 2024 profile results, not career reputation or current skill.

## Outliers and current-model limitations

Judge leads the marginal point estimates, but his SE (14.52) is large and his
homogeneous 9.320 runs/game illustrates extreme self-synergy. Ohtani's 64.875 and
Soto's 59.500 are not meaningfully ordered against Judge by these eight runs.
Freddy Fermin has the largest rank disagreement: marginal percentile is about
0.379 higher than homogeneous percentile. Context and sampling can both cause
disagreement; no causal decomposition is claimed. Brandon Drury is the lowest
marginal estimate (-43.375); this is not a claim about permanent talent.

Small historical samples are already smoothed toward the existing league
context with `player_weight = PA/(PA+200)`: 50 PA yields 0.20, 200 yields 0.50,
400 yields 0.667. Rece Hinds has 51 PA and raw OPS 1.051 but only 0.203 player
weight; comparable direct on-base mass changes from 0.3333 raw to 0.3182 prepared,
and his marginal estimate is +10.25. Mike Trout's 126 PA and Acuña's 222 PA do
not limit their simulated availability. Prepared probability shape, raw OPS and
sample size describe different things. No smoothing parameter was retuned.

The [M4 calibration failures](season-calibration-v1.md) remain: excessive hits
and PA, GDP about 38.8% high in the 2025 holdout, compressed run variability,
fixed nine hitters and standardized neutral pitching. Additional limits include
contact approximation, omitted sacrifices in prepared outcome sampling, no
player-specific defense/speed and empty extra-inning starts. A single fixed
opponent/reference/order is narrower than a league-wide valuation context.
Paired RNG does not keep play sequences aligned after outcomes diverge. More
repetitions reduce Monte Carlo error, not these structural biases. Do not add
the single-slot deltas to predict an assembled team's season or claim WAR,
validated real-world run contribution, or calibrated final game balance.

## Random-offer and budget feasibility

Main grid: two eligibility policies (10/20 games, strict OF, all DH), three price
curves, budgets 60/90/120, five offer/agent combinations, **500 trials each**.
There are 90 main configurations plus four order sensitivities. Structurally
infeasible cases run zero trials and are identified separately in the JSON.
For feasible cases, completion rates have Wilson 95% binomial intervals (0/500
still allows up to about 0.76%; 500/500 has lower bound about 99.24%). These
intervals quantify the fixed experiment's random draws, not human strategy.

Default slot order C,1B,2B,3B,SS,LF,CF,RF,DH. Three offers sampled without
replacement within a round; already selected identities excluded globally;
unchosen players may reappear. All nine must be distinct. Uniform-global draws
from all 526 then filters eligibility; position draws from eligible players;
tier draws one each from that position's lower/middle/upper value thirds.
Greedy agents choose highest value affordable. Reserve agents choose highest
value that preserves an affordable complete distinct-player assignment.
Protected tier experiments insert one safe option when none is offered.

Completion percentages, ten-game/all-DH policy:

| Curve    | Budget | Global greedy | Position greedy | Position reserve | Tier reserve | Tier protected |
| -------- | -----: | ------------: | --------------: | ---------------: | -----------: | -------------: |
| Linear   |     60 |           0.0 |             0.0 |              0.0 |          0.0 |            100 |
| Linear   |     90 |           0.2 |            91.0 |             87.0 |         83.6 |            100 |
| Linear   |    120 |           0.2 |             100 |              100 |          100 |            100 |
| Elite    |     60 |           0.4 |            63.0 |             64.2 |         40.8 |            100 |
| Elite    |     90 |           0.2 |            98.8 |             99.8 |         99.6 |            100 |
| Elite    |    120 |           0.2 |             100 |              100 |          100 |            100 |
| Scarcity |     60 |    infeasible |      infeasible |       infeasible |   infeasible |     infeasible |
| Scarcity |     90 |           0.0 |             0.0 |              0.0 |          0.0 |            100 |
| Scarcity |    120 |           0.2 |            46.2 |             43.8 |         13.4 |            100 |

The cheapest linear lineup costs only 25, yet a 60 budget with ordinary offers
completed 0/500: structural affordability alone is insufficient. Global offers
usually contain no eligible choice at scarce slots; extra budget cannot fix
that. Reserve checks avoid deliberately destroying a possible completion but
cannot ensure future random offers contain it. The experiment configurations
use separate derived RNG streams; small rate differences between agents are not
paired causal comparisons. Three random choices rarely deliver the extreme
low-price lineup implied by the minimum.

Protected completion is **conditional on choosing only safe options** and
initial feasibility. It does not guarantee every human choice, three interesting
choices or a fair distribution. At linear budget 60 the protected tier case has
multiple safe choices in only 55.7% of observed rounds; at 90 this rises to 96.7%.
These round-weighted counts and the mean value spread are choice-diversity
proxies, subject to survival bias across failing drafts, not evidence of fun.
Tiers can overrepresent expensive players; the elite curve simultaneously makes
many ordinary players cheaper, so the three curve budgets are not equivalent
difficulty settings. Identity overlap and player counts alone do not capture
this. Exact matching, rather than adding independent position minima, verifies
budget feasibility.

The twenty-game policy's minimum lineup costs are 25/10/70 for linear/elite/
scarcity. At linear budget 90, position-reserve completion is 83.6%, versus 87.0%
for ten games. At scarcity budget 120 it falls from 43.8% to 6.0%. Eligibility
and prices interact: smaller pools also increase the count-based premium.
Across the main grid, 40,000 drafts were actually simulated; ten structurally
infeasible configurations account for the remaining 5,000 nominal trials.

Four additional ten-game/linear/budget-90 sensitivities each run 500 drafts.
With position-reserve offers, scarce-first order C,SS,CF,1B,2B,3B,LF,RF,DH
completes 91.4%, while DH-first completes 92.4%, versus 87.0% in the default
order. Tier-reserve completes 83.4%/83.2%, versus 83.6%. These separately seeded
results do not establish an optimal order. Reserve checks handle shared-player
constraints, and draw paths differ. Total actual Monte Carlo drafts: **42,000**.

## Validation

Executed locally on Windows, with the existing dependencies and official cached
source releases. No cloud resources were provisioned. The complete prototype
run and explicit native-cache reuse both completed. The formatted compact JSON
was compared as parsed UTF-8 JSON against `compact_summary(research.json)`;
all 526 player identities are unique and have eight native repetitions. Native
runner SHA-256 still matches the recorded executable after a release rebuild.
Publication SQL and the M4 fixture retain their original SHA-256 values.

Commands below are from the repository root; `uv` was invoked via the available
local tooling executable because it was not on PATH.

| Commands                                                                                                                                           | Result                                                                                    |
| -------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| `uv run --project data/pipeline ruff check data/pipeline`                                                                                          | Pass                                                                                      |
| `uv run --project data/pipeline ruff format --check data/pipeline`                                                                                 | Pass                                                                                      |
| `uv run --project data/pipeline pytest data/pipeline/tests -q`                                                                                     | 142 passed; 8 optional source tests skipped without source arguments                      |
| Same pytest command with `--lahman-source data/raw/lahman-2025 --retrosheet-source data/raw/retrosheet-m4`                                         | **150 passed**, including all source integrations and the new native research integration |
| `cargo fmt --all -- --check`; `cargo clippy --workspace --all-targets -- -D warnings`                                                              | Pass                                                                                      |
| `cargo test --workspace`                                                                                                                           | **51 passed**                                                                             |
| `cargo build --locked --workspace`; same with `--target wasm32-unknown-unknown`; `cargo build --locked --release --examples`; `npm run build:wasm` | Pass                                                                                      |
| `npm run typecheck`; `npm run lint`; `npm run format:check`; `npm run build`                                                                       | Pass                                                                                      |
| `npm run types:api`; generated declaration diff check                                                                                              | Pass, no declaration changes                                                              |
| `npm run check:api`; `npm run d1:check --workspace @draftory/api`                                                                                  | Pass, dry-run bundle and local SELECT only                                                |
| `npm run test:api`                                                                                                                                 | **8 passed**                                                                              |
| `npm run test:data-client`                                                                                                                         | **10 passed**                                                                             |
| `npm run test:browser`                                                                                                                             | **57 passed**, Chromium/Firefox/WebKit, mobile emulation and local deployment delivery    |
| `npm run test:integration`                                                                                                                         | **9 passed**, Chromium/Firefox/WebKit API-to-browser native parity and recovery           |
| `git diff --check`                                                                                                                                 | Pass                                                                                      |

The ten new research tests cover eligibility boundaries, generic OF/unknowns,
traded-player totals, publication/fixture integrity, exact assignment against
brute force, overlapping positions, exclusion bounds, currency curves, greedy
budget traps versus reserve/protected experiments, Wilson intervals, repeat
uncertainty and real native paired/cache checks. The default suite's eight
source skips were all exercised successfully with source arguments. Optional
Edge and browser performance suites were not rerun for this Python-only
research milestone; no new compatibility or performance claim is made.

## Provisional recommendation and decisions before M7B

Start further experiments with **ten observed games at each specific fielding
position, universal DH, and the unchanged 50-PA prepared pool**, while preserving
the alternatives for review. Avoid inferring CF from generic OF or requiring
400 PA without addressing the catcher bottleneck. Keep eligibility and offensive
value separate; there is no defensive simulation benefit for extra positions.

Use both valuation methods as diagnostics. Before publishing stable prices,
increase marginal repetitions or use broader tiers, evaluate reference/order/
opponent sensitivity, and decide how model uncertainty should be displayed.
Do not promote the existing noisy point estimates directly into permanent prices.
Linear budget 90 is a useful experimental comparison point, not a chosen game
budget. Position-filtered offers with an explicit safe-completion option deserve
further testing; reserve-aware choice alone did not eliminate dead ends.
Pool-count scarcity pricing should remain an optional experiment until its higher
mandatory-slot costs and multi-position quote behavior are accepted.

Review these decisions before M7B:

1. Specific-position threshold, treatment of unknowns/generic OF, universal versus
   observed DH, and any additional historical PA minimum.
2. Reference population, teammate/opponent/order context, precision target and
   whether calibrated model limitations permit player-facing value claims.
3. One player price versus slot-specific quotes; curve, currency scale, floor,
   elite ceiling, outlier handling and budget as a jointly balanced design.
4. Offer count, eligibility filtering, tier boundaries, slot order, recurrence of
   unchosen offers, selected-player uniqueness and what completion guarantee is
   promised for arbitrary user choices.
5. Whether failed drafts are allowed, whether unsafe options are unavailable or
   merely labeled, and what constitutes a meaningful choice beyond price spread.

M7B has not started. All findings are offline research, with final rules awaiting
review.
