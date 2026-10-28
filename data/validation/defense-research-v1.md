# M8C.3 defensive statistics research

2026-10-28. **Research and design complete; defensive simulation is not
implemented.** [M8C.4 design and reproduction](../../docs/DEFENSIVE_SIMULATION_DESIGN.md).
[Compact counts/provenance](defense-research-v1.json). Full experimental
player-position rows and era coverage remain generated, not published profiles.

Recommendation: begin with a limited **error-avoidance** effect on actual contact
transitions. Keep range, catcher specialties and individual GDP skill neutral
until opportunity evidence supports them. That limited v1 cannot yet reward all
the ways an excellent defensive shortstop helps a real team. Do not relabel
fielding percentage or RF/9 as complete defensive ability.

## Sources and integrity

The unchanged official SABR Lahman 2025 CSV snapshot is verified by all eight
file hashes, lock
`8f4cfb56f0726ebe7c900f8d8748232a3c8b326b2fc0d44a387512442e58a22c`.
The source readme, headers and bytes are authoritative for this analysis.
The [official release page](https://sabr.org/lahman-database/) identifies coverage
through 2025. [Attribution/license](../../docs/DATA_ATTRIBUTION.md): SABR Lahman,
Sean Lahman/Bryan Walko and contributors, CC BY-SA 3.0; retain attribution,
modifications and share-alike notices with derived datasets.

The unchanged 526-player 2024 pilot has dataset ID
`dataset:1fba260824fe05abec3c5950cd184caa0d314b41f1253bc782f97b678bb28add`,
SQL SHA-256 `4dab2562d2b4344cd7499bb6ea54f899b4ba3fe95f1f859c3772d6d7f695828d`.
The loader checks SQL, publication/profile identities and source compatibility.
Every published player/position count is reconciled to official Appearances.
All fielding identity/team joins are checked across the source tables.

Retrosheet source lock remains
`1f725399cff54a7c924f4d71cd1dedbdc393f025b4a6ef3b3dded2ea3fe7a017`.
Only pinned **2022/23 plays** are analyzed. No 2024/25 plays were downloaded;
2024 development game logs and the already inspected M4 2025 report are available.
No new fit, parameter change or holdout retuning occurred.

The information used here was obtained free of charge from and is copyrighted by
Retrosheet. Interested parties may contact Retrosheet at
[www.retrosheet.org](https://www.retrosheet.org/).

`FieldingOF.csv` is listed and defined in the pinned official readme (including a
release note removing erroneous 2023 rows; intended end 1955), but is **not in our
eight-file acquisition lock or local snapshot**. Its documented fields were
reviewed; its row coverage/missingness was not verified. The official Box folder
was unavailable to the web reader and its returned HTML did not expose file
metadata via a direct read. No mirror or guessed download was substituted and no
existing lock was changed. It does not block the current 2024 pool, which uses
verified specific outfield splits. Historical use needs a separately reviewed
official-file acquisition/checksum before claiming measured FieldingOF coverage.

## Available fields and historical coverage

The compact JSON contains **every column's** known/missing/zero counts and first/
last non-null year; full generated output also contains five era cohorts. Ranges
below are observations, not assertions that intervening years/leagues are complete.
All table rows/leagues are included in coverage; experimental ratings explicitly
filter AL/NL 2024. League codes remain categorical (`NA` is not null).

| Table           |         Rows | Observed year range  | Grain/use                                                                         |
| --------------- | -----------: | -------------------- | --------------------------------------------------------------------------------- |
| Fielding        |      174,332 | 1871–2025            | Player/year/stint/team/league/POS; P,C,1B,2B,3B,SS,OF plus PH/PR source anomalies |
| FieldingOFsplit |       45,147 | 1891–2025            | Same grain with LF/CF/RF; not additional team fielding on top of OF               |
| Appearances     |      128,512 | 1871–2025            | Player/year/team/league; position games/eligibility                               |
| Teams           |        3,614 | 1871–2025            | Team/league/season, fielding and pitching context                                 |
| FieldingOF      | Not acquired | Readme: through 1955 | playerID/yearID/stint + Glf/Gcf/Grf; no team/league column in documented schema   |

Fielding/OFsplit identity columns are strings except yearID/stint (integers).
All counts are nullable integers. `ZR` and Teams.`FP` are parsed as finite
numbers. Position is source `POS` (readme calls it `Pos`). Missing markers
empty/`NULL`/`\N` stay unknown, and known zero stays zero. Inapplicable columns
can be null or contain historical zero artifacts; a non-null cell is not proof
that a statistic is meaningful for that position.

| Field   | Definition, denominator and applicability          | Main Fielding known / missing; known-year bounds | Rating suitability                                                                  |
| ------- | -------------------------------------------------- | ------------------------------------------------ | ----------------------------------------------------------------------------------- |
| G       | Games at that position, not necessarily full games | 174,332 / 0; 1871–2025                           | Exposure/eligibility only; positions can overlap within a game                      |
| GS      | Starts at position                                 | 125,675 / 48,657; 1871–2025                      | Role/context, not skill or exact innings                                            |
| InnOuts | Defensive time measured in outs; innings=outs/3    | 144,395 / 29,937; 1871–2025                      | Preferred playing-time denominator where known; no games→innings imputation         |
| PO      | Putouts credited                                   | 173,716 / 616; 1871–2025                         | C dominated by strikeouts, 1B by receiving throws; not range alone                  |
| A       | Assists credited                                   | 173,716 / 616; 1871–2025                         | Throw/teammate/pitcher/context dependent; multiple fielders can assist              |
| E       | Official scored errors                             | 173,702 / 630; 1871–2025                         | E/(PO+A+E) gives recorded error rate, not all missed plays                          |
| DP      | Double-play participation                          | 173,703 / 629; 1871–2025                         | Not independent plays or conversion rate; needs actual eligible opportunities       |
| PB      | Catcher passed balls                               | 16,278 / 158,054; 1871–2025                      | Per catcher inning crude; actual blocking opportunities preferable; defer           |
| WP      | Wild pitches while catching, per readme            | 2,387 / 171,945; 1925–2025                       | Pitcher/catcher joint context; never equate to catcher mistakes                     |
| SB      | Opponent steals associated with catcher            | 12,288 / 162,044; 1871–2025                      | SB+CS is attempts, not times a runner could try; pitcher/runner biased              |
| CS      | Opponents caught stealing                          | 10,166 / 164,166; 1871–2025                      | CS/(SB+CS), if complete and >0; no attempts => unknown rate                         |
| ZR      | Readme labels Zone Rating                          | 1,169 / 173,163; **1954–1969 only**              | Values 0–15, not a usable modern range series; definition/units unresolved; exclude |

For OFsplit, G and InnOuts are complete across its 45,147 rows (including 327
recorded zero-out rows); GS is missing in 1,157, PO/A in 269, E in 271 and DP
in 273. Core known bounds begin 1891, but historical coverage is sparse. WP/ZR
are entirely null. PB has 1,114 historical zeros; SB has 244 known cells (243
zero); CS has one known zero. These are **not outfielder catching skills**.

Main-table era diagnostics show why a single cutoff is unsafe: 1871–1899 rows
have no missing InnOuts but mostly unknown starts; 1900–1953 has 29,917 missing
InnOuts of 54,995 rows. Some old exposure may be reconstructed; non-null does
not establish modern measurement quality. From 1954–1989 there are still 17
missing innings rows; 1990–2021 has three; 2022–2025 has none. Negro League
and other historical league records need their own context/completeness checks,
not aggregation into a modern AL/NL baseline. See the exact league lists in JSON.

Appearances: `G_all`, `GS`, `G_batting`, `G_defense`, `G_p`, `G_c`, `G_1b`,
`G_2b`, `G_3b`, `G_ss`, `G_lf`, `G_cf`, `G_rf`, `G_of`, `G_dh`, `G_ph`, `G_pr`.
They count games/roles, not defensive opportunities or talent. G_all is complete;
G_defense is missing in 19,154 rows, G_of in 11,457; each specific fielding-games
column has eight nulls. LF+CF+RF games can exceed unique OF games. Historical
DH zeros, pinch roles and positions are not interchangeable.

Teams: E/DP/FP describe team fielding; IPouts is team pitching/defensive outs;
HA/HRA/SOA/BBA/RA/ER give opponent/pitching context. G gives team-games. Team
SO is **batting** strikeouts; use SOA for opponent strikeouts. Team SB/CS are
**offense**, not catcher opponent steals. E and FP have 14 nulls, DP 394,
IPouts/HA/SOA each one across 3,614 rows. Exact team defensive efficiency needs
opponent balls-in-play, hits/HR, errors/choices and sacrifice treatment, which
these columns alone do not fully identify. Do not divide own batting AB into
opponent hits to invent DER.

For all thirty 2024 teams, main Fielding summed PO equals Teams.IPouts and
summed E equals Teams.E exactly. Generic OF is included once, split OF excluded
from that reconciliation. Summed individual DP participations are **9,968**,
versus **3,687 team DP**: summing player DP is not counting team double plays.

## 2024 pilot coverage

Eligible means the unchanged >=10 games at that **specific** position, in the
526-player >=50 batting-PA pilot. All eligible pairs have matching position
records, complete G/GS/InnOuts/PO/A/E/DP, and fielding G reconciles to published
appearances. There are **788 eligible player-position pairs**, not 788 players.

| Position | Any observed games | Eligible | Games median | Innings min / median / max | >=100 inn | >=300 inn | >=600 inn | Eligible multi-team |
| -------- | -----------------: | -------: | -----------: | -------------------------- | --------: | --------: | --------: | ------------------: |
| C        |                 79 |       77 |           66 | 115 / 544.3 / 1,122        |        77 |        56 |        34 |                   5 |
| 1B       |                146 |       93 |           41 | 22 / 300.7 / 1,443.3       |        75 |        47 |        27 |                  10 |
| 2B       |                146 |      100 |           37 | 37 / 251 / 1,382.7         |        83 |        43 |        25 |                   7 |
| 3B       |                144 |      104 |         36.5 | 55 / 261.7 / 1,361.7       |        87 |        47 |        23 |                  12 |
| SS       |                111 |       77 |           49 | 34.7 / 358.3 / 1,416.7     |        66 |        45 |        28 |                   5 |
| LF       |                194 |      121 |           30 | 19.3 / 186 / 1,248.3       |        94 |        44 |        24 |                  15 |
| CF       |                138 |       92 |           45 | 43 / 316.5 / 1,323.3       |        77 |        51 |        31 |                  10 |
| RF       |                180 |      124 |         35.5 | 27.7 / 224 / 1,363.7       |       101 |        52 |        22 |                  16 |

Only **385/788 pairs** meet the exploratory 300-inning floor; the other 403
would remain neutral under that setting. The floor is not an eligibility change
or a validated skill threshold. Source completeness and adequate exposure are
different questions. **196 players** qualify for multiple fielding positions;
49 distinct players have multiple teams contributing to at least one eligible
position. Position/team counts overlap and must not be summed as unique people.

22 players have no eligible fielding slot, but only **six have no recorded games
at any of the eight fielding positions**: Ohtani, Stanton, Ozuna, J. D. Martinez,
Joc Pederson and Dan Vogelbach. The other 16 have incidental/sub-threshold defense.
All 526 remain universal-DH eligible. DH assignment has no direct fielding effect.

Traded example: Luis Arraez's MIA+SDN 1B rows aggregate to 441 PO, 24 A, 5 E,
69 G and 533 innings; separate 2B rows give 67 PO, 103 A, 4 E, 42 G and 339
innings. Do not merge the positions or repeat his season batting line per row.
Betts's 2B/SS/RF exposure remains separate; Trout's 203 CF innings do not become
a full-season defensive sample just because his hitter is simulated all year.

## Measurement methods

| Approach                                 | What is measured / omitted                                                   | Confounding, sample and coverage                                                                                                     | Decision                                                            |
| ---------------------------------------- | ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------- |
| Position-adjusted FP=(PO+A)/TC           | Handling/throwing/receiving without a recorded error; omits unreachable hits | Scorer judgment, chance type and player selection; rare errors need shrinkage; broad history with gaps                               | Useful error-only input, not overall defense                        |
| E per TC, shrunk to position/season      | Same information with explicit error denominator and prior                   | TC includes receivers/C strikeouts; not difficulty adjusted or a direct ROE probability                                              | Best minimal experiment; validate event mapping                     |
| RF/9=27(PO+A)/InnOuts                    | Plays credited per nine defensive innings                                    | Pitcher K/GB/FB mix, teammates, shifts, park, runner mix; innings/position gaps; 1B/C particularly misleading                        | Diagnostic only; do not convert to range                            |
| Team defensive efficiency                | Team out conversion on balls in play                                         | Needs consistent BIP/ROE denominator; pitching/contact/park mix; cannot assign individual credit                                     | Retrosheet baseline diagnostic, not individual rating               |
| DP per inning/game or raw DP             | Participation frequency                                                      | Counts same DP for several fielders; actual ground/force opportunities, pivot, speed needed                                          | Reject as conversion rate; estimate opportunities first             |
| C CS/(SB+CS), PB/inning                  | Throwing outcomes on attempts, observed passed balls                         | Pitcher delivery/pickoffs, runner quality/selection, pitch difficulty; no framing signal; multiple seasons helpful                   | Descriptive only; defer until running/blocking events exist         |
| Retrosheet opportunity-relative fielding | Situational outcomes with ball type/location/fielders                        | No tracked starting position/velocity/hang time; location and final fielder are not unbiased difficulty; older games deduced/missing | Useful future estimator; not fitted here                            |
| DRS/UZR/OAA                              | Richer context-based defensive measures                                      | Components, opportunities and licensing differ; not interchangeable with raw rates or across eras                                    | Useful later with permitted pinned source; no dependency introduced |

[MLB's FP definition](https://www.mlb.com/glossary/standard-stats/fielding-percentage)
is about recorded chances. [Range-factor definition](https://www.mlb.com/glossary/advanced-stats/range-factor)
does not supply difficulty adjustment.
[FanGraphs UZR](https://library.fangraphs.com/defense/uzr/) accounts for fielding
components and context, remains noisy in short samples and uses proprietary
underlying observations; its published description favors multiple seasons.
[FanGraphs DRS](https://library.fangraphs.com/defense/drs/) and
[the metric publisher](https://www.fieldingbible.com/) describe broader defensive
components; the [publisher's archive](https://archive.fieldingbible.com/) offers
leaderboards back to 2003. Such run totals cannot independently identify each
simulation event component.

[MLB OAA](https://www.mlb.com/glossary/statcast/outs-above-average) uses tracked
opportunity difficulty; its definition covers infield and outfield range.
These sources materially improve opportunity adjustment, but public viewing is
not our verified bulk redistribution license. No advanced metrics were scraped,
purchased, imported or republished. Their exact per-position/year downloadable
coverage and reuse rights remain unresolved. They are unnecessary for error-only
v1 and cannot solve missing 19th-century tracking data.

## Experimental examples, not overall-defense rankings

Using the design's E/TC estimator with K=100 and >=300 innings; positive avoidance
means fewer errors per **1,000 recorded chances** than the position reference.
These are neither runs saved nor an OAA/DRS approximation.

| Player / position   | Innings | E / TC    | Avoidance | Interpretation                                                        |
| ------------------- | ------: | --------- | --------: | --------------------------------------------------------------------- |
| Francisco Lindor SS | 1,311.7 | 12 / 564  |     +5.18 | Error-only component                                                  |
| Bobby Witt SS       | 1,393.7 | 15 / 583  |     +1.41 | Range/arm value not measured                                          |
| Anthony Volpe SS    | 1,416.7 | 16 / 570  |     -0.59 | Near reference; not an overall skill verdict                          |
| Mookie Betts SS     |   531.3 | 9 / 245   |     -6.64 | Separate from RF/2B                                                   |
| Mookie Betts 2B     |     105 | 0 / 33    |   Unknown | Small sample, not perfect defense                                     |
| Matt Chapman 3B     |   1,338 | 15 / 405  |     -1.21 | A useful warning against interpreting errors as all defensive ability |
| Aaron Judge CF      |     903 | 0 / 252   |     +6.43 | Avoiding recorded errors says nothing about missed-hit range          |
| Juan Soto RF        | 1,277.7 | 2 / 300   |     +5.78 | Same limitation; not proof of elite range                             |
| Mike Trout CF       |     203 | 0 / 67    |   Unknown | Neutral fallback under experimental floor                             |
| Cal Raleigh C       |   1,122 | 6 / 1,195 |     +2.08 | Most PO are unrelated to range; no framing claim                      |

Raleigh's CS=32/SB=81 gives 28.32% on recorded attempts; Rutschman's 19/82 gives
18.81%; William Contreras's 21/72 gives 22.58%. Their PB/WP counts are 5/27,
3/21 and 6/30 respectively. The 2024 catcher rows have these counts populated,
but no pitcher/runner/pitch-difficulty adjustment. This is **not** evidence for
adding framing or stolen-base mechanics now.

## Retrosheet event findings

The verified CSV already contains the fields listed in its pinned `plays.html`;
the current [official field dictionary](https://www.retrosheet.org/downloads/plays.html)
also describes them. The reader exposes every column as a string; exposure in
the CSV is distinct from use by the existing fitter.

| Information                    | Already available                                                 | Current pipeline / additional work                                                                                                             |
| ------------------------------ | ----------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| Ground/fly/line/pop-up         | ground/fly/line, bunt, hittype G/F/L/P/BG/BP/BL, raw event        | Ignored by fitter; add typed categories and unknown handling; fly flag includes pop-ups                                                        |
| Ordinary outs, errors, choices | othout, roe, fc, e1…e9, outs before/after, batter destinations    | Fitter uses ROE/FC/othout + actual identities; per-position errors still unused; othout can include safe force choices                         |
| GDP/other DP/TP                | gdp, othdp, tp, dpopp, pivot                                      | Only supported GDP branch used; distinguish eligibility from conversion and other DP types                                                     |
| Fielders                       | firstf, f2…f9, pitcher, fseq, po1…po9, a1…a9, batout/brout fields | Available but unused for player skill; crosswalk People.retroID with active-year uniqueness and actual position                                |
| Advances and scoring           | br*\_pre/post, run*, rbi*, outs, raw event, SB/CS/PB/WP flags     | Supported joint transitions already extracted; compound/running/timing plays conservatively proxied; full interpretation requires more parsing |

Selection for every new source count is the exact M4 fit window: full regular
PAs, innings 1–8, no SH/SF in 2022/23. There are 327,116 PAs, 212,260 BIP and
149,319 residual contacts. BIP types: G 95,768; F 47,735; L 52,123; P 15,383;
BG 1,084; BP 148; BL 19. All selected BIP have firstf in 1…9 and f2…f9 filled;
32 have blank loc. This modern completeness does not establish historical
coverage or permission to use final fielder as causal responsibility.

**An important source-definition finding:** `dpopp` is not interchangeable with
runner-first/<2outs on every PA in these pinned bytes. The latter yields 58,942
PAs versus 13,542 reported dpopp flags; there are 45,400 disagreements. Even
ground-only eligibility (18,075) differs in 4,623 rows. The documentation's short
description does not fully characterize these observed flags. Compute explicit
base/out and contact denominators, retain the source flag and investigate the
remaining selection before using it in a conversion model. Do not repair raw
bytes or call every mismatch an invalid play.

Retrosheet permits reproducible estimates of contact/state/fielder involvement,
error reaches and eligible GDP frequencies with uncertainty/backoff. It does not
directly provide a difficulty-adjusted player range probability. Location/type
conditioning can improve a future baseline without claiming tracking precision.

## Double-play discrepancy diagnosis

The frozen M4 2025 report has historical GDP=0.6424/team-game versus 0.8913,
about **+38.8%**, while PA=37.6391 versus 38.9282 (+3.43%). PA volume alone
cannot explain it: dividing the GDP ratio by the PA ratio leaves about **+34.1%
GDP per PA**. This is arithmetic on the existing report, not a new holdout test.

The model has no individual fielders or actual ground-ball sampler. For residual
contact it selects a situation-specific joint outcome; the empirical GDP share
already marginalizes ground/non-ground frequencies. Thus “eligible opportunity”
must specify whether it means a PA in runner-first/<2outs state, a ground ball,
or a residual contact in that state. Applying another ground fraction to current
conditional GDP would double-condition it and is not an authorized fix.

Training decomposition:

- 58,942 state-eligible PAs; 18,075 state-eligible ground balls.
- 27,107 state-eligible residual contacts, of which 13,497 have ground=1.
- 6,250 supported GDP, equal to **all** selected source gdp flags.
- GDP / eligible residual contact = **23.06%**; GDP / eligible ground = **34.58%**.
  Different denominators, not contradictory conversion estimates.
- Applying the frozen table to the **observed training event/state counts** gives
  expected GDP **6,250.004798**, rounding within 0.005 of the actual numerator.
  All 72 cell observation counts reproduce M4. No missing-GDP or unnormalized-
  table explanation appears in this audit. This is an in-sample reconciliation,
  not independent calibration evidence.

A deliberately small additional diagnostic uses the unchanged 2024 NYA/CHA
fixture, one seed 20261025, 162 games, both batting teams. No new model or Monte
Carlo grid. Whole trace: 12,296 PAs, 5,581 residual contacts, 2,551 state-eligible
PAs, 1,152 eligible residual contacts and 275 GDP. Fit-window-only comparison:

| Quantity, innings 1–8        | Source 2022/23 fit | Native fixed 2024 fixture |
| ---------------------------- | -----------------: | ------------------------: |
| PA                           |            327,116 |                    11,051 |
| Residual contacts / PA       |            45.647% |                   45.290% |
| State-eligible PA / PA       |            18.019% |                   20.813% |
| Eligible residual / residual |            18.154% |                   20.679% |
| GDP / eligible residual      |            23.057% |                   24.058% |
| GDP / PA                     |             1.911% |                    2.253% |

The exact factorization is `(residual/PA) × (eligible/residual) ×
(GDP/eligible)`. In this narrow diagnostic residual-contact mass is similar,
eligible-state exposure is greater and conversion differs less. The engine
cannot report a simulated true ground fraction because it never sampled one.
Conversion also depends on the mix of the eight eligible base/out cells, not
just player skill. A single fixture/seed is not a league estimate or a numerical
decomposition of the 2025 residual.

**Likely primary cause is model/exposure structure**, supported by the exact
training reconciliation and this targeted diagnostic: fixed selected hitters
receive all PA; excess hits/PA, omitted steals/CS/pickoffs, sacrifices/running
outs and simplified advances change runner/out distributions. The original
calibration reports the selected hitters account for only about 68% of real PA.
Batter speed/handedness/contact mix, bunt policy, DP pivot/arm and pitching context
are also absent. Their separate causal contributions are not identified here.

Adding average-centered defensive skill does **not** repair excessive baseline
opportunities. Strong GDP fielders could increase an already excessive total;
weak fielders could reduce it by accident. Error-only changes may also alter
future baserunners and conditional GDP through normalization. Preserve separate
baseline and defense diagnostics; do not tune player ratings to match 2025.

## Design, limitations and next milestone

The [concrete design](../../docs/DEFENSIVE_SIMULATION_DESIGN.md) specifies error
formulas, floor/prior investigation, neutral fallbacks, primary-fielder weighting,
conditional-probability replacement, base/out invariants, opposing-side defense,
eight fielders/neutral pitcher/DH, historical/career baselines, proposed versioned
contracts/supplement, UI semantics, payload estimates, rollback and native/WASM
parity requirements. Error-only v1 changes actual game events, never final scores.
Range/hit↔out transfer is described as a separately evidence-gated extension.

Remaining decisions: reliability/amplitude validation, whether error-only scope
meets the desired gameplay trade-off, source dpopp semantics, historical ZR
meaning, official FieldingOF acquisition, advanced-metric reuse rights, and a
new untouched confirmation set. No source lock, published dataset, price or
production behavior changes in this milestone. M8C.4 has not started.

## Validation

Local checks completed with the existing installed dependencies:

| Command / check                                                                                                           | Result                                                                                     |
| ------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| `python -m draftory_data verify --source-dir data/raw/lahman-2025`                                                        | All eight official file checksums verified                                                 |
| `python -m draftory_data.defense_research ...` (see design for full command)                                              | Full audit and compact summary generated; both locks verified; no downloads                |
| `python -m pytest data/pipeline/tests -q --lahman-source data/raw/lahman-2025 --retrosheet-source data/raw/retrosheet-m4` | **170 passed**, including ten new research tests and both source-only reproducibility runs |
| `ruff check data/pipeline`; `ruff format --check data/pipeline`                                                           | Pass                                                                                       |
| `cargo fmt --all -- --check`; `cargo clippy --workspace --all-targets -- -D warnings`; `cargo test --workspace`           | Pass; **52 tests**, including existing goldens                                             |
| `cargo build --locked --workspace --target wasm32-unknown-unknown`                                                        | Pass                                                                                       |
| `npm run typecheck`; `npm run lint`; `npm run build`                                                                      | Pass; production asset hashes unchanged                                                    |
| `npm run check:api`; `npm run d1:check --workspace @draftory/api`                                                         | Pass; dry-run and **local** SELECT only                                                    |
| Prettier and `git diff --check`                                                                                           | Pass                                                                                       |

Browser suites were not rerun for this Python/docs-only milestone; no new
browser compatibility or performance claim is made. The optional native diagnostic
was executed twice byte-identically by its test, not merely skipped. FieldingOF
raw rows and external advanced-metric datasets were not available in the verified
snapshot and remain untested as described above.

The research is deterministic except platform-dependent native binary hashes;
its complete native JSON result repeats byte-for-byte with the same executable.
Synthetic tests cover trades, separate positions, duplicate/conflicting sources,
OF overlap, null/zero, zero denominator, shrinkage, sample floor, position-relative
baseline, source-flag distinction and contact taxonomy. Source integrations verify
all joins/counts, team PO/E reconciliation, frozen transition denominators and
two identical full source-only reruns. Raw and detailed generated data stay ignored.
