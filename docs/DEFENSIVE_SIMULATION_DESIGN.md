# Defensive simulation research and proposed M8C.4

M8C.4 now implements a narrower [error-avoidance model](DEFENSIVE_SIMULATION.md).
The following remains the original research proposal; its whole-complement
odds formula was replaced by transfers limited to eligible errors/ordinary outs.

M8C.3, reviewed 2026-10-28. **Design only.** The live game, prices, batting
profiles, source locks, D1, Rust rules/RNG and goldens are unchanged.
[Measured findings](../data/validation/defense-research-v1.md) and
[compact measurements](../data/validation/defense-research-v1.json) distinguish
source facts from experiments. Python remains responsible for offline preparation;
Rust will own any approved event changes. No architectural change is needed.

## Recommendation and scope

Start with a small, explicitly labeled **error-avoidance model**, using nullable,
position-specific Lahman facts and Retrosheet-supported legal joint transitions.
Keep range, arm strength, framing, catcher running control and player-specific
double-play skill neutral initially. This can change actual outs/reaches/runs,
but is **not a complete defensive ability rating**. An excellent range shortstop
cannot yet receive defensible range credit from our current season totals.
Do not promise that error avoidance makes defense as valuable as elite hitting.

Range needs opportunity/difficulty information. Neither fielding percentage nor
putouts+assists per inning identifies balls a fielder failed to reach. The latter
also rewards a pitcher's ground-ball mix and teammates' throws. Publishing it as
range would give precise-looking but unjustified talent rankings. A later
Retrosheet opportunity estimator is feasible research; it is not approved or
fitted here. Advanced external metrics need a permitted, pinned redistribution
source before becoming a dependency.

Before shipping defense, instrument the baseline GDP opportunity decomposition
in a separately versioned diagnostic and validate the error mapping on development
data. If meaningful range-driven offensive/defensive trade-offs are required for
M8C.4 acceptance, that is a **data/model blocker**, not permission to invent range.

## Facts, experimental estimator and missing data

Join by official player/year/team/league/stint/position. Sum each contributing
stint once within the same position. Never join batting counts onto every fielding
row. Use `Fielding` for infield/C and `FieldingOFsplit` for LF/CF/RF; generic OF
is not a ninth fielding slot and never adds to its three splits. Preserve source
rows. Specific-position copies across tables must agree and are counted once.

For player-position `i` and same-season AL/NL position reference `p`:

```text
TC_i = PO_i + A_i + E_i                  # recorded chances, not balls reachable
mu_p = sum(E_j) / sum(TC_j)              # same position and compatible source era
e_hat_i = (E_i + K * mu_p) / (TC_i + K)
experimental_avoidance_i = 1000 * (mu_p - e_hat_i)
```

The research uses all 2024 AL/NL player-position lines with complete core facts,
positive chances and >=300 defensive innings for the reference, including players
outside the batting pilot. `K=100` prior chances and the 300-inning observation
floor are **sensitivity settings, not fitted reliability thresholds**. Measured
coverage at 50/100/300/600 innings is retained. Below the floor or with any unknown
core/innings contribution, experimental rating is null. Known zero errors with
positive chances is a real observation and shrinks toward the baseline. Zero
chances never yields perfect defense. `InnOuts/3` is innings; 1002 outs are 334
innings, not baseball decimal notation `1002.0` innings.

Production must keep separate `status` (`observed`, `insufficient`, `unknown`,
`notApplicable`), games/outs/chances, baseline ID, estimator ID and effect. Missing
or insufficient data gets **neutral effect**, with its reason exposed. Eligibility
remains the existing games rule; neutral fallback must not silently remove a
draft-eligible player. A DH has not-applicable defense regardless of his other
positions. Do not substitute career reputation, batting PA or another position.

M8C.4 should compare candidate floors/prior strengths by predicting next-year
position error rates from 2022 into 2023, then report locked-policy sensitivity on
2024 development. This is reliability work, not fitting runs to inspected 2025.
Rare errors, scorer judgment and heterogeneous receiving/throwing chances remain
limitations even after shrinkage. Catcher and first-base TC are especially unlike
SS TC. No common 0–100 overall-defense scale is justified.

## Minimum event model: a replacement conditional resolver

The current sampler already selects direct hits and residual `otherContact` from
prepared batting weights. The contextual model already contains ROE and GDP.
Do **not** independently roll an error or double play afterward. Do not call
`otherContact` all contact or equate it to ground balls.

For each existing `otherContact × outs × bases` cell `s`, let `T_s(t)` be its
validated joint destination probabilities. Let `E_s` be its error-reach choices,
and `p_s = sum(T_s(t), t in E_s)`. Estimate primary-fielder involvement weights
`w_s,p` from eligible 2022/23 `firstf` observations, with counted unknowns and
explicit sparse-cell fallback to a broader compatible position distribution.
Pool LF/CF/RF only to estimate a fallback **involvement mix**, never player skill.
Pitcher involvement has ratio 1. Keep catcher-specific running events outside it.

An initial, testable mapping is:

```text
r_i = e_hat_i / mu_position             # lower = fewer recorded errors
# Explicit neutral/unknown/pitcher r = 1; absent reference -> neutral
R_s = sum_p(w_s,p * r_assigned_fielder(p))
p'_s = (p_s * R_s) / (1 - p_s + p_s * R_s)
T'_s(t) = T_s(t) * p'_s/p_s             if t is an error reach
T'_s(t) = T_s(t) * (1-p'_s)/(1-p_s)     otherwise
```

This is a **proposed error-odds proxy**, not an estimated causal relationship
between TC errors and batter ROE. Many errors advance runners rather than create
ROE; TC includes receiving chances. Validate that mapping before publication.
The numerical amplitude/prior must be selected from development evidence, not
from desired wins or player reputations. Record neutral reference-population
centering if shrunk ratios' exposure-weighted mean differs from 1; quantify any
residual league drift instead of assuming it cancels.

For `p_s=0`, leave the cell unchanged. For `p_s=1`, retain its supported choices
and flag no alternate support; do not invent an out transition. For supported
mixed cells, reweight existing legal choices, using exact rational arithmetic
offline and integer largest-remainder tickets to total 1,000,000 in a fixed
documented choice order. Reject nonfinite/negative effects. Specify and validate
any effect limits before publication; this research has not selected arbitrary
caps. Keep original zero-support transitions at zero.

The team-specific tables can be precomputed once per matchup in Rust using fixed
integer/rational rules and bounded intermediates, after input validation. Sample
one choice using the existing conditional-ticket pattern. No per-PA allocations,
network, Python, SQL or independent post-result coins. If primary-fielder credit
is displayed later, a versioned joint choice can carry it; do not make summary
and replay use different draws to assign credit.

Reweighting the whole non-error complement also changes GDP probability slightly
through normalization. That is an explicit limitation: inspect error, ordinary
out, choice and GDP shares together. It is not a GDP repair. If that coupling is
unacceptable, M8C.4 must instead define and validate compatible error↔ordinary-out
transition pairs and preserve all unrelated mass; do not quietly swap models.
Defer player-specific GDP modifiers until opportunity-specific evidence exists.

Better error avoidance reduces safe reaches and advances; the state machine then
produces fewer scoring opportunities. Measure runs allowed through paired
replacement experiments after implementation, not by applying a final-score
bonus or asserting a fixed runs/error conversion. Runs and wins can vary
nonlinearly by base/out state, lineup and seed.

## Hits, contact and future range

Essential v1 leaves 1B/2B/3B/HR/BB/HBP/K batting weights unchanged. It changes only
the outcome of supported residual contact. This avoids applying defense twice
to hits already in those weights; it also means a range-only defender gets no
benefit yet. Home runs are outside fieldable-contact conversion.

A future range extension must **replace**, rather than follow, the affected
categorical sampling stage. Reserve total fieldable mass
`C = P(1B)+P(2B)+P(3B)+P(otherContact)` and conserve it when exchanging hits and
outs. For example a supported, bounded single↔ordinary-out transfer `d` would
use `P'(1B)=P(1B)-d`, `P'(otherContact)=P(otherContact)+d`; both must stay >=0.
`d` must come from opportunity-adjusted fielding evidence, not RF/9 or offensive
price. Multi-base hit/arm effects need their own evidence and legal advancement.

If using ground/fly/line/pop-up subtypes, fit a joint type/primary-fielder/outcome
model conditional on situation, reconcile its neutral marginals with prepared
batting mass and existing baserunning, and distinguish pitcher-induced contact
from fielder conversion. A ball's eventual fielder/location is not automatically
the player responsible for every hit. Retrosheet lacks tracked starting position,
trajectory and difficulty; even this extension would remain a proxy. Never turn
DRS runs into an added score bonus or apply complete DRS alongside separately
modeled errors/GDP/range that it already includes.

## Roster, pitching and base/out invariants

Each team needs an explicit position→player defensive assignment independent of
batting order: C,1B,2B,3B,SS,LF,CF,RF; neutral pitcher supplied by environment; DH
omitted. Validate unique identities, eligible assigned positions, matching
profile year/source and effect versions. Batting-order edits cannot move a player
to a different fielding position. Apply user defense while the **opponent bats**;
opponent defense while the user bats. Initially opposing defense is explicitly
neutral, since existing opponent templates do not publish defensive assignments.
Standardized pitching remains unchanged; catcher stats cannot secretly introduce
pitcher quality. One defender plays every relevant inning; no fatigue, bench,
substitution, injuries, pitcher batting or positioning tactics are modeled.

Existing joint-transition validation must still enforce no duplicate runners,
passing, backward movement, invented runners, illegal outs or RBI on suppressed
third-out runs. Reach errors must not be scored as hits. GDP requires first
occupied/<2 outs; errors are not a license to violate force or walk-off rules.
Keep current supported scorer simplifications explicit; no earned-run claim.
Neutral defense should bypass the new resolver in legacy mode with **no extra
RNG draw**, preserving old saved runs and all current golden bytes.

## Historical/career compatibility

Coverage is by field, position and league-season, not a global cutoff. An early
record with innings filled is not proof that every historical inning was measured
with modern precision. Preserve completeness flags, documented source practices,
and original counts. Generic OF games cannot justify a CF skill estimate.
Unknown legacy `FieldingOF` stint-to-team linkage cannot be guessed.

Use position/league/year baselines. Never compare raw 19th-century error rates to 2024. For career/year-range pooled estimates, form expected errors
`sum(TC_season * mu_position,league,season)` over complete compatible exposure,
then shrink the observed/expected ratio with an explicit prior and missing-season
audit. Do not average already shrunk or rounded ratings. Equal-season mean/median
must remain explicit alternatives with season exposure thresholds; a median is
not an opportunity-weighted career aggregate. Different positions stay separate.
Mapping a historical relative rate into a modern environment is an assumption
requiring its own model ID/evaluation. Sparse/incompatible eras use neutral with
a visible warning; do not manufacture innings from games or import guessed range.

## Concrete M8C.4 work and compatibility proposal

1. **Freeze a new evaluation plan first.** Reproduce GDP opportunity counters on
   training/development, including PA mix, runner-first/<2outs, residual contacts,
   eligible ground balls and conversion. Retain the inspected 2025 results only
   as regression diagnostics. Select a new untouched season/source split before
   confirmatory evaluation; 2026 is not in these locks. Do not acquire or label
   a new holdout as untouched after inspecting it. Baseline defects remain
   reported independently of defense. Do not bundle unapproved recalibration.
2. Python: promote tested nullable fielding facts into a separate defense producer;
   verify source/joins, estimate error baselines/reliability and involvement on
   2022/23; inspect 2024 development; gate unsupported fields. Produce immutable
   defense model/profile artifacts with provenance and quality flags. Never
   overwrite current batting profiles or currency catalogs.
3. Contracts (proposed names/versions, not created): defense profile **1.0.0**
   keyed by player/year/position and estimator/source IDs; defense environment
   **1.0.0** with baselines/involvement and transition-model dependency; opt-in
   game input **1.3.0**, season input **1.1.0** and explicit defensive rules/model
   versions. Result/replay schema needs a new version if adding defensive choices
   or attribution. Strict old parsers reject new fields, so deploy adapter/API
   support together. Keep legacy parsing and execution separately available.
4. Rust: validate roster assignment separately from order, build matchup tables,
   resolve contact once, record actual ROE/out/run effects. Keep neutral pitcher,
   neutral opponents and unknowns explicit. Error extremes, all base/out states,
   conservation, nonnegative exact mass, neutral identity, wrong source/version
   rejection, swapped home/away and DH invariance need tests.
5. Publication: **a new versioned defense supplement is required** for hosted
   use. Existing D1 batting publication need not be regenerated; choose a small
   immutable supplement first. If D1 publication/API integration is requested,
   add its reviewed storage/contract separately, preserve old dataset IDs and
   reject mismatched batting/defense years. No current D1 migration or import.
6. Frontend: show position-specific “error avoidance (experimental)”, defensive
   innings/chances and confidence/missing status, separate from offense and
   price. Do not label it OAA/DRS/WAR or overall defense. Preserve slot assignment
   through batting-order edits and result identity joins. No pricing adjustment
   until a later valuation/balance experiment.
7. Determinism: fixed integer quantization/order/overflow limits in Python/Rust,
   model/input/engine IDs, identical native/WASM fixtures/seeds; summary/events
   consume the same draws. New opt-in goldens, unchanged legacy goldens, browser
   parity on Chromium/Firefox/WebKit/Edge and mobile emulation. Pair comparisons
   by seeds but disclose path divergence after changed transitions.
8. Measure before publication: baseline vs neutral vs one-player replacement,
   both batting sides, confidence intervals across repetitions, ROE/GDP/PA/runs
   and state distributions, neutral league drift, payload bytes and browser
   timing. No fixed runs-saved or performance claim is established yet.

Estimated overhead: eight effect references per active lineup plus neutral
pitcher (roughly 1–3 KB compact JSON with IDs/flags), and a reusable model table
of 24×9 involvement weights (216 u32 = 864 bytes before metadata). These are
design estimates, not benchmark results. Cached reweighted transitions duplicate
part of the current 24 contact cells per matchup; exact size depends on choices.
CPU is bounded setup over those choices; PA sampling need not add a random draw.
Only selected defense profiles and shared context should reach the browser.

Rollback is selecting the existing catalog, batting publication and legacy
neutral rules/input; retain immutable artifacts and engine support needed for
old replays. New runs must record defensive assignment, supplement/model IDs and
seed. Do not reinterpret a saved old run using the new resolver. Error-only v1
is the smallest feasible step; range, GDP skill, catcher events, OF arm, advanced
tracking and cross-era talent projection remain future enhancements.

## Reproduce M8C.3

From the root, using the existing verified raw snapshot and generated M6A pilot:

```sh
uv run --project data/pipeline python -m draftory_data verify --source-dir data/raw/lahman-2025
cargo build --locked --release -p baseball-sim --example season
uv run --project data/pipeline python -m draftory_data.defense_research --source-dir data/raw/lahman-2025 --retrosheet-dir data/raw/retrosheet-m4 --publication-dir data/processed/d1-2024 --output-dir data/processed/m8c3 --runner target/release/examples/season.exe --summary-output data/validation/defense-research-v1.json
uv run --project data/pipeline ruff check data/pipeline
uv run --project data/pipeline ruff format --check data/pipeline
uv run --project data/pipeline pytest data/pipeline/tests --lahman-source data/raw/lahman-2025 --retrosheet-source data/raw/retrosheet-m4
```

On Unix omit `.exe`. Omit `--runner` to skip the optional 162-game event diagnostic;
it is not a defense experiment and never modifies Rust. Raw sources, complete
per-player experimental rows, era coverage, native input/output and research JSON
remain ignored in `data/processed/m8c3`. The summary retains source/model/fixture
IDs and content hashes; binary-dependent full research IDs can vary by build.
Counts and source-only output reproduce exactly. No source is fetched during
analysis/tests. Use existing source/publication acquisition instructions first
on a fresh checkout. The CLI does not replace or auto-upgrade source locks.
