# M9A — Baseball simulation accuracy audit

Reviewed October 29, 2026. **The current model reproduces its earlier calibration
failures; the audit finds no reason to reduce season randomness or tune a global
GDP multiplier.** Prioritize supported out/advancement and sacrifice accounting,
then explicit contact opportunities and running events. Matching mean runs has
hidden errors in exposure, hit rates and scoring distributions.

This is investigation and an M9B proposal, not M9B implementation. Only a native
observation example, offline diagnostic, tests and reports were added. Baseball
rules, probabilities, prepared profiles, defensive ratings, prices/budgets,
opponent publication, contracts, D1 and gameplay UI are unchanged. Historical
reports and source locks remain intact. No commit, push or deployment was made.

The information used here was obtained free of charge from and is copyrighted by
Retrosheet. Interested parties may contact Retrosheet at
[www.retrosheet.org](https://www.retrosheet.org/).
Lahman attribution and license remain in [DATA_ATTRIBUTION](../../docs/DATA_ATTRIBUTION.md).

## 1. Evidence, versions and uncertainty

Base checkout: `6f6b63a3bad2bac71bfaab1d794dcfcd78cec8fc`. Engine 0.4.0;
`lahman-contact-adapter-v1`, `modern-neutral-v1`,
`retrosheet-contact-transitions-v1`, `contextual-nine-inning-v1`,
`round-robin-season-v1`, `splitmix64-index-v1`, `splitmix64-v1`. Native Windows
ARM64, rustc 1.88.0; Python 3.12.14; Node 22.21.0; Ruff 0.14.14.
Binary/input/output hashes and exact counters are in
[simulation-accuracy-v1.json](simulation-accuracy-v1.json).

Read the project plan, architecture, data/simulation specifications, simulation
foundation, Lahman foundation, M4 calibration, M8C.3 opportunity research,
implemented error avoidance and season-dashboard documentation before editing.
Reviewed the Rust sampler, joint transition validation/resolution, game endings,
scorekeeping and scheduler; Python profile adapter, fitter and source verification;
and the immutable opponent publication and dashboard projection.

Experiments:

- Reverified the existing Lahman, M4 Retrosheet and separate 2024 development-play
  locks. Regenerated the full M4 preparation into a new ignored directory.
- Repeated the original **4,800 seasons / 777,600 games**: 30 clubs × 20 seeds ×
  four years × two models. Every compact row in both baseline and contextual
  batches equals its archived row after removing elapsed-time measurements.
- Ran **600 additional seasons / 97,200 games**: 200 seed roots each for the
  published PA-ranked CHA, HOU and NYA nines against the current nine-opponent
  pool. These intentionally cover weak, middle and stronger offenses, not
  budget-legal draft samples or complete historical teams. Neutral defense and
  unchanged full-season profiles; opponents include a synthetic mirror of the
  user club, as permitted by the current synthetic gameplay identity policy.
- Captured events for the first **20 seeds per roster / 9,720 games**. Trace
  comparisons use only user PAs in innings 1–8, matching the fitter's window.
  Source fit counts exclude SH/SF; separate omitted-event counts retain them.
- Repeated six traced seasons byte-for-byte and matched their summary-mode
  results. Checked runner conservation in all 97,200 new games.

2022–2023 are **training/in-sample**, 2024 is **development**, and 2025 is
**previously inspected diagnostic evidence**. The old report's “final holdout”
label describes its original use, not an untouched set today. No probabilities
were fitted or selected here. There is **no genuinely new confirmation sample**;
new seeds are Monte Carlo replication, not new historical validation. Do not
claim these exploratory measurements were preregistered acceptance tests.

Baseline ± values below are 95% Monte Carlo half-widths across 20 league-level
repetitions. New season mean intervals use 200 season repetitions. These quantify
simulation sampling only. Historical totals are exact for the pinned sample.
Rare-tail percentages and source conversion estimates still have sampling/model
uncertainty; the experiment does not identify a causal percentage for each missing
mechanic. At 200 seasons, a 5% tail probability has roughly 1.5 percentage points
standard error, and SD estimation has roughly 5% relative sampling error under a
normal approximation.

## 2. Updated baseline accuracy

Per user team-game, original all-club contextual experiment. Preparation, seeds,
rosters and schedules reproduce the M4 measurement design, not the newer
nine-opponent gameplay pool.

| Year / role      | Runs: historical → simulated | Hits: historical → simulated | PA: historical → simulated |
| ---------------- | ---------------------------- | ---------------------------- | -------------------------- |
| 2022 training    | 4.2833 → 4.2778 ± 0.0146     | 8.1636 → 8.6811 ± 0.0151     | 37.4593 → 38.7813 ± 0.0274 |
| 2023 training    | 4.6156 → 4.6391 ± 0.0110     | 8.4031 → 8.9123 ± 0.0204     | 37.8815 → 39.1874 ± 0.0303 |
| 2024 development | 4.3934 → 4.3274 ± 0.0127     | 8.1974 → 8.6674 ± 0.0189     | 37.5564 → 38.8289 ± 0.0288 |
| 2025 inspected   | 4.4473 → 4.4191 ± 0.0145     | 8.2588 → 8.7272 ± 0.0198     | 37.6391 → 38.9282 ± 0.0287 |

Expanded 2024 development measurements:

| Per team-game |                            Historical |  Current ± MC95 |
| ------------- | ------------------------------------: | --------------: |
| BB            |                                3.0731 | 3.2536 ± 0.0092 |
| SO            |                                8.4802 | 8.6840 ± 0.0144 |
| 2B            |                                1.5996 | 1.6929 ± 0.0056 |
| 3B            |                                0.1435 | 0.1517 ± 0.0019 |
| HR            |                                1.1225 | 1.2097 ± 0.0068 |
| HBP           |                                0.4158 | 0.4401 ± 0.0052 |
| GDP           |                                0.6643 | 0.8757 ± 0.0044 |
| Batter ROE    | Not available separately in game logs |          0.2309 |
| Modeled FC    |         No equivalent game-log target |          0.7461 |

2024 GDP excess is **31.8%**. The reproduced, already inspected 2025 excess is
**38.8%** (0.6424 → 0.8913). Training-year GDP excess is already present:
0.6981 → 0.8842 in 2022; 0.7132 → 0.8775 in 2023.

| Distribution          | 2024 historical → current | 2025 inspected historical → current |
| --------------------- | ------------------------- | ----------------------------------- |
| Runs SD               | 3.0865 → 2.9847           | 3.2468 → 3.0325                     |
| Shutouts              | 6.608% → 6.524%           | 6.811% → 6.335%                     |
| 10+ runs              | 6.608% → 5.925%           | 7.922% → 6.448%                     |
| Games reaching extras | 8.893% → 9.948%           | 8.601% → 9.854%                     |

Full score histograms and original frozen-band results remain reproducible in
`data/processed/m9a/calibration/calibration.json`; do not replace the existing
bands with thresholds chosen to pass this audit. The earlier PA/hit failures
remain. Near-correct RPG does not establish correct innings or tails.

## 3. PA, hits, runner states and inning length

The exact descriptive identity `H/game = PA/game × H/PA` separates volume from
rate without changing the simulator. Using the historical hit rate as reference,
the 2024 **+0.4700 hits/game** comprises **+0.2777 from PA volume** and
**+0.1922 from the remaining rate difference**. About 59% is the volume term.
For inspected 2025 the corresponding terms are +0.2829 and +0.1855. These are
algebraic allocations, not independently identified causal effects.

The adapter and roster construction both affect the rate term. For the 270
selected historical 2024 batting slots:

| Equal-slot H/PA diagnostic                        |    Rate |
| ------------------------------------------------- | ------: |
| Raw official-denominator rate of selected hitters | 0.21914 |
| Same selected rates, conditioned on no SH/SF      | 0.22123 |
| After the unchanged 200-PA prior                  | 0.22282 |
| Actual simulated all-club H/PA                    | 0.22322 |
| Historical all-roster H/PA                        | 0.21827 |

Equal-slot weighting differs from actual batting-order exposure; these rows must
not be interpreted as a fitted additive causal decomposition. They show that
“the fixed nine are better hitters” is insufficient as the sole explanation.
Removing sacrifice mass and smoothing also matter. The selected hitters supplied
only 67.76% of historical 2024 PA, but take every simulated PA, without bench
players, injuries, substitutions or pitcher batting. Their average excluded
sacrifice mass is 0.958%. The prior compresses individual strengths and can raise
this selected cohort's mean rate. A hit/PA correction must preserve this distinction
between a historical aggregate and the intended fixed-roster experiment.

The Rust sampler uses cumulative million-ticket distributions and unbiased
rejection sampling, not independent AVG rolls. Measured BB/SO/HBP/HR totals in
the 200-seed cohorts agree with exposure-weighted input expectations within their
reported Monte Carlo intervals. Doubles use credited events, so comparison with
sampled weights also includes legal walk-off hit downgrades. There is no evidence
here for repairing the PRNG or imposing a run multiplier.

Missing/simplified baseball events are measurable, not merely speculative:

| Source events, full regular plays in innings 1–8 |              2022 |              2023 |  2024 development |
| ------------------------------------------------ | ----------------: | ----------------: | ----------------: |
| Non-PA outs (actual outs delta)                  |               842 |               934 |             1,018 |
| Recorded running outs of existing runners on PAs |               883 |               869 |               808 |
| SH / SF                                          |       311 / 1,070 |       335 / 1,099 |       353 / 1,096 |
| SB flags, all destinations                       |             2,219 |             3,132 |             3,276 |
| CS flags, all destinations                       |               759 |               804 |               898 |
| Pickoff flags                                    |               256 |               277 |               320 |
| WP / PB / balk flags                             | 1,399 / 200 / 106 | 1,405 / 202 / 183 | 1,250 / 217 / 175 |

These event flags overlap; **do not sum them into an estimated PA correction**.
For example CS/pickoffs may overlap, and GDP is a batting out rather than an
additional running-out flag. Non-PA outs alone are about 0.210 per historical
2024 team-game within innings 1–8, much smaller than +1.2725 simulated PA/game.
They are consequential but cannot alone explain the entire discrepancy.

The fitter conservatively replaces 1,086 training running-out-on-hit plays and
1,338 extra-batter-advance plays. Its 48,016 third-out/unsupported-contact proxies
are mostly ordinary third outs; treating that whole count as erroneous discarded
running outs would grossly overstate the defect. Sacrifices are conditioned out;
steals/CS, pickoffs and WP/PB/balk transitions are absent. Successful steals can
remove a GDP opportunity without recording an out. Missing running outs preserve
runners; simplified safe advancement changes both scoring efficiency and later
base-state exposure. Errors/FC are already inside residual contact, so adding an
independent error or choice roll would double-count them.

2024 source innings 1–8 average **4.2292 PA/played half**, with 0.510% reaching
10+ PA. New fixed CHA/HOU/NYA traces average **4.1883 / 4.3742 / 4.4066**, with
10+ PA frequencies **0.463% / 0.806% / 0.748%**. Source PA here include sacrifices;
the engine cannot. Weak and strong fixed offenses should not be forced to have
identical inning lengths. The game code advances the batting cursor on third
outs, clears/strands runners, skips unplayed home halves and truncates walk-offs;
existing edge-case tests pass. No inning-reset bug was identified.

## 4. GDP opportunity decomposition

Use the M8C.3 factorization:

`GDP/PA = residual contact/PA × eligible residual/residual × GDP/eligible residual`.

Eligibility means runner on first and fewer than two outs. Residual contact is
`AB − H − SO`, not a true ground-ball opportunity. The eight eligible base/out
cells have different conversion shares; changes in their mix matter too.

| Innings 1–8, no sacrifices |      PA | Residual/PA | Eligible/residual | GDP/eligible | GDP/PA |
| -------------------------- | ------: | ----------: | ----------------: | -----------: | -----: |
| 2022–23 training, pooled   | 327,116 |     45.647% |           18.154% |      23.057% | 1.911% |
| 2024 observed development  | 162,877 |     45.906% |           17.724% |      21.989% | 1.789% |
| Current CHA, 20 seeds      | 108,560 |     46.972% |           20.058% |      23.416% | 2.206% |
| Current HOU, 20 seeds      | 113,380 |     47.919% |           21.918% |      23.329% | 2.450% |
| Current NYA, 20 seeds      | 114,220 |     45.061% |           22.454% |      23.328% | 2.360% |

The frozen table applied to observed training cells predicts **6,250.004798 GDP**
against 6,250 observed, reproducing M8C.3. This is an in-sample reconciliation,
not validation. Applied to actual **2024 development** contact/state counts it
predicts **3,050.136342** against **2,914** observed: **+4.67%**. There is thus a
development conversion/model-transfer discrepancy even before simulation changes
the opportunity mix. Sampling and year/contact composition can contribute; this
does not identify a universal 4.67% probability correction.

In the new traces, actual GDP versus table expectation on simulated states is
CHA **2,395 vs 2,370.08**, HOU **2,778 vs 2,783.06**, NYA **2,696 vs 2,698.98**.
Exposure is materially elevated, while realized conversion is close to the
table's own prediction. The cohorts have different profiles from the historical
population, so this is evidence about the mechanism, not a numerical attribution
of the entire original 2025 excess.

Ground opportunity denominators also differ. Training has 58,942 state-eligible
PAs, 18,075 state-eligible grounds, 27,107 eligible residuals, and 13,497 eligible
residual grounds. Dividing 6,250 GDP by all eligible grounds gives 34.58%; dividing
by eligible residual grounds gives 46.31%. Neither is the 23.06% residual-contact
conditional rate. Applying another ground fraction to today's marginalized table
would double-condition the model.

The new source cross-tab narrows the `dpopp` ambiguity: training flags match
explicitly eligible **residual ground contacts**, plus 45 eligible residual line
drives (24 in 2022, 21 in 2023). In 2024 there are 21 analogous line flags and one
eligible residual ground without the flag. This explains why the flags nearly
match fieldable-contact opportunities but badly disagree with all eligible PAs
or all eligible grounds. It is an observed property of pinned bytes, not a claim
that the short official definition guarantees those semantics. Preserve flags
and compute explicit denominators.

Do not lower GDP globally or use defender ratings to cancel baseline exposure.
Audit state frequencies, contact composition and conditional conversion separately
after each future mechanics change.

## 5. Season variability

All three rosters play the same fixed nine-opponent policy: 18 games per opponent,
nine home/nine away; 81 home/81 away overall. Seeds change outcomes, not opponent
frequency. Games derive their RNG roots independently of prior game length.
No fatigue or other inter-game state is present.

| Fixed roster, 200 seasons | Wins mean ± MC95 | Season win SD | Schedule baseline SD | Observed range | Empirical central 95% |
| ------------------------- | ---------------: | ------------: | -------------------: | -------------- | --------------------- |
| CHA                       |     65.70 ± 0.78 |          5.64 |                 6.23 | 50–86          | 56–77                 |
| HOU                       |     82.56 ± 0.86 |          6.18 |                 6.34 | 68–107         | 72–94                 |
| NYA                       |     84.33 ± 0.83 |          6.02 |                 6.34 | 66–104         | 75–96                 |

The comparison is Poisson-binomial: estimate each fixed game's win probability
across season roots and sum `p_j(1−p_j)`, with the finite-sample correction
`n/(n−1)`. It accommodates unequal opponents and home/away probabilities. The
familiar equal-strength binomial SD is `sqrt(162×0.5×0.5)=6.36`.
Observed/baseline win variance ratios are **0.819 / 0.948 / 0.903**. These do not
show excess season randomness; CHA is somewhat underdispersed in this sample,
which merits replication if it persists, not a PRNG intervention from a single
exploratory cohort. With 200 seasons the approximate 95% sampling span for a
variance ratio around one is roughly 0.8–1.2.

| Fixed roster | RS mean / season SD | RA mean / season SD | RD mean / season SD | Per-game runs SD |
| ------------ | ------------------: | ------------------: | ------------------: | ---------------: |
| CHA          |      603.88 / 33.51 |      752.68 / 34.98 |     -148.80 / 47.79 |            2.731 |
| HOU          |      765.17 / 39.47 |      751.00 / 39.85 |      +14.17 / 52.69 |            3.117 |
| NYA          |      787.72 / 39.49 |      753.45 / 42.66 |      +34.27 / 56.14 |            3.181 |

Seasons with ≤70 wins occur **83% / 2.5% / 1%**; ≥93 wins occur
**0% / 5.5% / 9%**, respectively. Frequencies more than two schedule-baseline
SD from each roster mean are 4% / 2.5% / 2.5%. Tail estimates are coarse;
zero occurrences is not zero underlying probability.

**A 70–93 spread is plausible for a roughly 81–84-win roster**: its endpoints
are around two season SD from that strength. A range alone, without seed count
and roster strength, is not evidence of a structural problem. Actual historical
club wins are not interchangeable replications: pitching, injuries, schedule and
talent change. Comparing their cross-team spread with repeated fixed-roster SD
would confound strength variation with luck. The historical per-game scoring
variance/tails in section 2 are the more useful observed comparison here.

Empty extras are a genuine rules mismatch. The new cohorts reach extras in
10.16% / 9.49% / 9.34% of games and go beyond ten innings in
5.88% / 5.28% / 5.28%, versus 2.223% beyond ten in historical 2024. Modern MLB
regular-season extras start with a runner at second; see the
[official rule definition](https://www.mlb.com/glossary/rules/designated-runner).
That change can shorten **already tied** games and alter extra-inning scoring.
It cannot directly repair excess games tied after nine; investigate regulation
scoring/strength compression separately.

## 6. Batted-ball model limitations and defensive prerequisites

The current engine samples hits before contextual contact. It never samples a
true GB/FB/LD/pop-up class, contact location or fielding opportunity. Ordinary
outs, safe force choices, ROE and GDP share `otherContact`; safe choices replace
the runner actually forced out. Errors are not hits. The separate opt-in
error-avoidance model transfers only supported error/ordinary-out mass; it does
not change conditional GDP weights and cannot fix this baseline.

The verified training BIP types are G 95,768; F 47,735; L 52,123; P 15,383;
BG 1,084; BP 148; BL 19. The pinned 2024 development counterpart has G 46,913;
F 24,418; L 25,978; P 7,854; BG 580; BP 81; BL 5. The
[Retrosheet dictionary](https://www.retrosheet.org/downloads/plays.html) separates
these types, identifies runner states and first fielders, and distinguishes GDP
from other double plays. Its fly flag includes pop-ups, so using it alone loses
that distinction. Current artifacts contain the relevant evidence; no new source
was needed for this audit.

An explicit contact model would permit coherent GB-only GDP eligibility, tag-ups,
air outs and later hit↔out range effects. It must jointly reconcile hit type,
fieldable contact and legal runner outcomes. Splitting residual outs into GB/FB
while leaving hits entirely upstream is insufficient for a credible range model.
Use typed categories, unknown handling, sparse-cell backoff and retained proxy
mass. Location/final-fielder observations do not establish difficulty-adjusted
individual talent, especially across older/deduced records.

OF **arms** need legal on-hit running outs and tag-ups; OF **range** additionally
needs contact opportunities including hits and difficulty/coverage evidence.
Catcher **throwing** needs attempt/non-PA SB/CS/pickoff opportunities and separation
of pitcher/runner effects. **Blocking** needs WP/PB advancement and attribution.
**Framing** needs suitable pitch/count evidence and a separate validated model.
The current error proxy supplies none of these prerequisites by itself.

## 7. Prioritized corrections and proposed M9B scope

### Priority 1 — Restore supported contact out/advancement accounting (M9B)

**Problem/evidence:** 1,086 training on-hit running-out proxies plus extra advances,
808 recorded existing-runner PA running outs in the 2024 window, elevated occupancy
and excess PA. **Expected impact:** fewer artificially surviving runners, corrected
inning/LOB/GDP exposure and some run/hit-volume reduction; magnitude is unproven.
Some advances increase runs, so do not require every metric to decrease.
**Data:** classify supported joint single/double and ordinary-contact runner-outs,
retain unsupported reasons, resolve third-out timing and source identity carefully;
fit 2022–23 and inspect 2024 without dropping difficult mass.
**Rust:** allow versioned joint hit transitions with runner retirements and extra
batter destinations; distinguish force/timing third outs, score/RBI/LOB and walk-offs.
**Compatibility:** new transition/rules IDs and corresponding accepted contracts;
retain v1 resolver/artifacts and goldens for replay. No silent replacement of old
weights. **Calibration/tests:** source-state replay, per-cell out/run conservation,
timing third outs, walk-offs and native/WASM parity; paired development cohorts
with full PA/hit/GDP/score reports. **Complexity/risk:** medium-high; third-out
legality is the principal risk. Begin with source-proven supported cases.

### Priority 2 — Restore explicit sacrifice denominator/accounting (M9B)

**Problem/evidence:** SH/SF are conditioned out; selected 2024 hit rate rises
0.21914 → 0.22123 before smoothing. Existing out advancement can score runs but
cannot receive sacrifice/official AB credit. **Expected impact:** coherent PA/AB,
SF RBI/tag-ups and SH advancement; removes a known source-rate distortion, without
promising an exact PA/game target. **Data:** retain full PA denominators, estimate
situation-dependent SF/SH frequencies and legal joint outcomes; distinguish bunt
attempts from successfully credited SH. Do not paste unconditional sacrifice
probabilities into impossible base states or create a generic scoring out.
**Rust:** separately identify/credit SH/SF and resolve supported transitions.
**Compatibility:** new preparation/policy/profile IDs, outcome/scorekeeping schema
and rules version; old profiles remain unchanged and accepted only by their old
semantics. **Calibration/tests:** full-vs-conditioned source reconciliation,
no-sacrifice states, two-out restrictions, PA/AB/OBP/RBI, force/timing and walk-offs;
training fit and frozen 2024 development comparison alongside priority 1.
**Complexity/risk:** medium-high; selective sacrifice decisions and double-counted
fly-out mass are key risks.

**Smallest meaningful M9B:** priorities 1 and 2 as a bounded, separately versioned
**out and sacrifice accounting correction**, with the new diagnostics as acceptance
evidence. Complete its source classifications/design before writing the new rules.
Keep unsupported cases counted and explicitly proxied. If source reconciliation
shows the two cannot be separated safely, revise the design rather than inserting
probability patches. Measure residuals honestly: missing non-PA events and contact
composition mean this scope is not a promise to eliminate the entire GDP excess.

### Priority 3 — Introduce explicit contact opportunities (following M9B)

**Problem/evidence:** pooled GDP fits training but overpredicts observed 2024 cells
4.67%; no simulated grounds exist and defender range cannot affect upstream hits.
**Expected impact:** separates ground/contact mix from conversion and establishes
an OF-range foundation; improvement must be measured, not assumed.
**Data:** type/unknown/location/first-fielder coverage, hits plus outs/FC/ROE,
GDP versus other DP, batter/pitching mix and shrinkage/backoff; preserve the
`dpopp` cross-tab. **Rust:** a versioned contact stage and coherent joint hit/out
resolution; never apply a second ground fraction to the v1 GDP table.
**Compatibility:** new contact/preparation/transition/rules versions and fixtures;
error-avoidance supplement must be rebuilt/validated or stay v1-only.
**Calibration/tests:** component-rate and state-standardized GDP checks, within-cell
conversion, score tails, unknown/sparse classes, range-neutral parity and later
new confirmation data. **Complexity/risk:** high; sparse stratification and
hit/contact double counting. Do not add player range ratings to compensate first.

### Priority 4 — Add non-PA running and supported loose-ball advances

**Problem/evidence:** the source contains CS/pickoffs, thousands of steals and
WP/PB/balk events; engine contains none. **Expected impact:** changes opportunity
and scoring distributions, reduces some runner retention, enables catcher
throwing/blocking and additional arm evaluation. Successful running can increase
runs while also reducing GDP exposure. **Data:** attempt opportunities conditioned
on runner/state/out context, outcomes and source attribution; flags must not be
summed as disjoint events. **Rust:** a distinct non-PA event stage that does not
advance the batter cursor, legal runner identity/third outs and revised conservation.
**Compatibility:** new event-log/rules/result versions and separate running profiles
or priors; preserve legacy RNG draw order in legacy mode. **Calibration/tests:**
attempt/success/out denominators, inning-ending CS, compound events, cursor and
conservation tests, no double-counted pickoffs, game/season distributions and
native/WASM parity. **Complexity/risk:** high; attempted-running selection and
pitcher/runner/catcher confounding. Defer individual talent until baseline works.

### Priority 5 — Modern extras, then matched validation and heterogeneity research

**Problem/evidence:** long empty extras; low historical score variance; fixed nines
and neutral pitching differ from MLB. **Expected impact:** an automatic runner
corrects post-nine rules and duration. Better matched validation separates roster
effects; evidence-based pitching/park heterogeneity could improve tails, but an
arbitrary noise multiplier is unjustified. **Data:** use pinned historical extra
and lineup/roster observations for development; research permitted pitching/park
inputs separately. **Rust:** automatic runner initialization with the preceding
batter identity, runs/LOB attribution and conservation including introduced runners;
later environment models only after design approval. **Compatibility:** distinct
regular-season ruleset, unchanged old empty-extras mode; environment/profile and
schedule versions if later models change. **Calibration/tests:** paired regulation
versus extra metrics, previous-batter/cursor tests, walk-offs, introduced-runner
conservation, duration tails; compare fixed-roster expected event rates separately
from historical full-roster targets. **Complexity/risk:** medium for extras, high
for heterogeneity; automatic runners do not explain entry into extras or cure
regulation scoring. This can be a small separate rules change after M9B.

For every behavior-changing milestone, publish all metrics and opportunity
decompositions, preserve old reproducibility, freeze the estimator and acceptance
plan before any genuinely new confirmation evidence is inspected. 2025 cannot be
reused as that confirmation set. No new eligible set is asserted or acquired here.

## 8. Testing and reproduction

From the repository root, with existing installed dependencies and local verified
sources (no downloads):

```powershell
$py = '.\data\pipeline\.venv\Scripts\python.exe'
cargo build --locked --release --examples
& $py -m draftory_data.calibration prepare --source-dir data/raw/lahman-2025 --retrosheet-dir data/raw/retrosheet-m4 --output-dir data/processed/m9a/prepared
& $py -m draftory_data.calibration run --input-dir data/processed/m4 --runner target/release/examples/calibrate.exe --repetitions 20 --output-dir data/processed/m9a/calibration
& $py -m draftory_data.accuracy_audit --run-native
& $py -m pytest data/pipeline/tests -q --lahman-source data/raw/lahman-2025 --retrosheet-source data/raw/retrosheet-m4
```

`accuracy_audit` without `--run-native` recollects the saved season rows, source
audits and reproducibility probes. Season root indices are `repeat*3+rosterIndex`,
base seed 20261029; user order is CHA,HOU,NYA. Each game then uses the unchanged
indexed seed derivation. Complete generated inputs, results and historical batch
output remain ignored under `data/processed/m9a`; only compact audit measurements
are versioned. Exact source lock hashes and runner/input/output hashes are in JSON.

All regenerated simulation inputs, transitions, targets, contexts and manifest
match archived bytes. `lineups.json` has **16 diagnostic display-name differences**:
regeneration restores the verified UTF-8 names where the archive contains
reversible double Windows-1252 mojibake. The diagnostic accepts only proven
reversible name differences, records them individually, and rejects any other
preparation difference. The archive is preserved. These names do not affect
prepared profiles or Rust results.

Completed checks:

| Check                                                      | Result                                                                        |
| ---------------------------------------------------------- | ----------------------------------------------------------------------------- |
| Full Python suite with both verified source options        | **185 passed**, including four audit tests                                    |
| Final focused audit tests after diagnostic refinements     | **4 passed**                                                                  |
| Ruff check and format check                                | Pass                                                                          |
| Rust workspace tests                                       | Pass, including legacy/defense/dashboard goldens and deterministic invariants |
| Rust fmt and all-target Clippy with warnings denied        | Pass                                                                          |
| Release native examples; workspace WASM target compilation | Pass                                                                          |
| TypeScript typecheck, ESLint, production build             | Pass                                                                          |
| API build dry-run; D1 `SELECT 1 --local`                   | Pass; no remote operation                                                     |
| Prettier and whitespace check                              | Pass                                                                          |
| Historical batch replay                                    | All 4,800 rows match archived results, excluding timings                      |
| New native deterministic probes                            | Six traced seasons repeat byte-identically; summary/events outcomes match     |
| New game accounting                                        | Runner conservation passes in all 97,200 games                                |

Browser suites were not rerun for this diagnostic/docs-only change. No browser
runtime or performance claim follows from native tests or WASM compilation. Final
status contains only the new audit example, offline module/tests, two reports and
README links;
no tracked production or historical artifact changed.

## 9. Known limitations

- No new historical confirmation sample; results remain retrospective and
  conditional on known same-year batting profiles.
- Fixed nines, source-team versus full-season trade profiles and PA-ranked versus
  observed starting orders are distinct experiments. Exact actual team wins are
  unsupported with neutral pitching; mirror-club synthetic games are deliberate.
- Twenty trace seeds per roster support targeted exposure diagnostics, not an
  exhaustive causal ablation. Changes in runner events, lineup exposure and
  contact types interact; their isolated contributions are not identified here.
- Source inning-length summaries retain sacrifices; fitter-matched contact
  summaries exclude them. Modern completeness does not establish older coverage.
- ROE is batter reaches, not all errors. Game logs do not provide a separate
  comparable ROE/FC target. Source ROE evidence is limited to the selected window.
- New root seeds have indexed uniqueness and deterministic replay; this is not
  a mathematical proof of independent PRNG streams. There is no observed excess
  season variance warranting reduced randomness.
- No new contact model, defender talent model, price calibration, roster mode,
  actual MLB schedule, cloud operation or UI change was implemented.
