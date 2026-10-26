# M4 season simulation and historical calibration v1

The season layer works, and contextual mechanics improve run averages. **The model is not fully calibrated:** hits and PA fail the frozen diagnostic bands, GDP is too frequent, and score variance remains low. A close mean run total does not cancel these failures.

Engine **0.4.0**; game input **1.2.0**; season input/result **1.0.0**; `round-robin-season-v1`, `splitmix64-index-v1`, `splitmix64-v1`, `contextual-nine-inning-v1`, `retrosheet-contextual-v1`, `retrosheet-contact-transitions-v1`, `lahman-contact-adapter-v1`. The [implementation guide](../../docs/SIMULATION_FOUNDATION.md#season-simulation-and-calibration-m4) documents contracts, mechanics, workflow and limits.

## Sources and target availability

The information used here was obtained free of charge from and is copyrighted by Retrosheet. Interested parties may contact Retrosheet at [www.retrosheet.org](https://www.retrosheet.org/).

Official [Retrosheet game logs](https://www.retrosheet.org/gamelogs/index.html), [field guide](https://www.retrosheet.org/gamelogs/glfields.txt) and [parsed plays](https://www.retrosheet.org/downloads/plays.html) supply the narrow supplement. The packaged `retrosheet-m4.lock.json` pins four season game-log archives, two parsed-play archives and two documentation files. Only 2022/2023 plays are downloaded. Project-observed SHA-256 values identify exact official HTTPS snapshots; they are not upstream-published authenticity signatures.

Retrosheet lock: `1f725399cff54a7c924f4d71cd1dedbdc393f025b4a6ef3b3dded2ea3fe7a017`. Lahman is the official SABR 2025 CSV snapshot, lock `8f4cfb56f0726ebe7c900f8d8748232a3c8b326b2fc0d44a387512442e58a22c`. [Attribution and license notices](../../docs/DATA_ATTRIBUTION.md) remain separate: Retrosheet data-use notice and Lahman CC BY-SA 3.0. Raw releases, detailed preparation audits, full targets and batch outputs stay under ignored `data/raw`/`data/processed`.

| Target                                             | Lahman season data                                            | Retrosheet supplement                                    |
| -------------------------------------------------- | ------------------------------------------------------------- | -------------------------------------------------------- |
| R, H, BB, SO, HR per team-game                     | Teams totals / G; independently reconciled                    | Game-log batting totals / actual games                   |
| PA per team-game                                   | Sum complete team-season batting stints; interference omitted | AB + BB + HBP + SH + SF + interference                   |
| Team W–L, runs allowed/differential                | Teams W/L/R/RA                                                | Recomputed from individual final scores                  |
| Run histogram, shutouts, 10+ run games             | Not recoverable from season sums                              | Both team scores in each game                            |
| Inning scoring and unplayed home halves            | Unavailable                                                   | Parsed line scores; double-digit innings and x supported |
| Joint runner transitions, GDP/error/choice context | GIDP counts only; no base/out opportunities                   | Parsed pre/post runner IDs, outs, event and RBI flags    |
| Historical starting orders                         | Membership/stints and People.retroID crosswalk                | Nine starter IDs in batting order per game               |

## Split, uncertainty and frozen diagnostics

The final integrity check excluded matchups where a traded player appeared in both fixed orders from different dates. Both models were rerun with the same corrected sets (27–29 opponents per club), preserving all fitted probabilities and thresholds. This amendment followed the initial 2025 evaluation and is disclosed in the evaluation plan; the corrected figures are not pristine preregistered confirmation. No 2025 event data was fitted. The lineup audit lists each excluded pair and shared IDs.

2022–2023 regular-season full plays, innings 1–8, fit the transition model. 2024 is **development validation** because early diagnostics were inspected during development. **2025 is the final holdout**, evaluated after fixing the estimator/taxonomy and [evaluation plan](m4-evaluation-plan.md). No holdout plays or outcome-driven scoring multipliers are used. Known same-year Lahman profiles are conditioning inputs; this is not a future-player forecasting test. Later revisions informed by these holdout results need a new version/evaluation set.

All thirty clubs per year are evaluated, each with twenty seeded 162-game seasons under each model: **4,800 seasons / 777,600 completed games**, plus separate benchmarks. Team experiments are independent synthetic schedules, not a shared thirty-team standings simulation. Seeds come from base `20261025` using indexed SplitMix64, then the season schedule derives each game seed; rows record engine/RNG/model versions and the actual season seed. Team/repetition uniqueness is validated before aggregation.

Mean ± values below are **95% Monte Carlo half-widths across twenty league-level repetitions**. They quantify simulation sampling, not source accuracy, model uncertainty or twenty independent historical years. Historical means are exact for the source sample; paired-game cluster SEs describe hypothetical game-to-game sampling. No confidence interval for a single first-call timing is asserted.

Frozen per-metric bands are the larger of the absolute 2022–2023 historical mean difference and 1.96 times the combined paired-game cluster SE. Score-distribution tolerance is training-year empirical total variation. These broad prototype bands are data-derived diagnostics, not proof of historical equivalence. All failed bands are shown.

## Historical baseline and run comparisons

| Season | Role          | Actual games | Historical R/team-game | M3 baseline | M4 contextual ± MC95 | M4 bias |
| ------ | ------------- | ------------ | ---------------------- | ----------- | -------------------- | ------- |
| 2022   | training      | 2,430        | 4.2833                 | 4.1255      | 4.2778 ± 0.0146      | -0.0055 |
| 2023   | training      | 2,430        | 4.6156                 | 4.5184      | 4.6391 ± 0.0110      | +0.0234 |
| 2024   | development   | 2,429        | 4.3934                 | 4.1854      | 4.3274 ± 0.0127      | -0.0659 |
| 2025   | final holdout | 2,430        | 4.4473                 | 4.2711      | 4.4191 ± 0.0145      | -0.0283 |

Season targets contain every team’s actual W–L, runs scored/allowed and all batting counts. Across all **120 team-seasons**, Lahman and Retrosheet agree on G, W, L, R, RA, H, BB, SO and HR; no source totals were repaired. The archives contain one home-bats-first game (2022), 22 shortened games across the four seasons, and modern extra innings. All remain in historical targets; the simulator uses ordinary nine-inning starts and empty extras, so this is an explicit rules mismatch rather than exact historical replay.

## Final 2025 holdout: batting and distributions

| Per team-game | Historical | M3      | M4 ± MC95        | M4 bias | Frozen band | Result   |
| ------------- | ---------- | ------- | ---------------- | ------- | ----------- | -------- |
| runs          | 4.4473     | 4.2711  | 4.4191 ± 0.0145  | -0.0283 | ±0.3323     | pass     |
| hits          | 8.2588     | 8.9093  | 8.7272 ± 0.0198  | +0.4683 | ±0.2395     | **FAIL** |
| walks         | 3.1644     | 3.4348  | 3.3590 ± 0.0082  | +0.1946 | ±0.1988     | pass     |
| strikeouts    | 8.3632     | 8.7578  | 8.5591 ± 0.0196  | +0.1960 | ±0.2121     | pass     |
| homeRuns      | 1.1626     | 1.2841  | 1.2604 ± 0.0077  | +0.0978 | ±0.1344     | pass     |
| pa            | 37.6391    | 39.8155 | 38.9282 ± 0.0287 | +1.2891 | ±0.4222     | **FAIL** |

| 2025 score summary              | Historical | M3      | M4      |
| ------------------------------- | ---------- | ------- | ------- |
| Shutout frequency               | 6.811%     | 7.496%  | 6.335%  |
| 10+ runs                        | 7.922%     | 5.983%  | 6.448%  |
| Runs standard deviation         | 3.2468     | 3.0177  | 3.0326  |
| Total variation from historical | —          | 0.02916 | 0.03091 |

Training score-TV band is 0.05761; both models pass that broad band. M4 improves the run mean but does **not** improve every histogram measure. In particular, high-scoring tails and variance remain too small. Source and simulated score frequencies follow (97,200 simulated user-team games; 4,860 historical team-games).

| Runs | Historical frequency | M4 frequency |
| ---- | -------------------- | ------------ |
| 0    | 6.811%               | 6.335%       |
| 1    | 11.523%              | 10.385%      |
| 2    | 12.716%              | 12.984%      |
| 3    | 13.827%              | 14.006%      |
| 4    | 13.333%              | 13.381%      |
| 5    | 10.535%              | 11.346%      |
| 6    | 8.477%               | 9.395%       |
| 7    | 6.564%               | 7.030%       |
| 8    | 4.877%               | 5.105%       |
| 9    | 3.416%               | 3.586%       |
| 10+  | 7.922%               | 6.448%       |

| 2025 inning | Historical runs / played half | M4 runs / played half |
| ----------- | ----------------------------- | --------------------- |
| 1           | 0.5321                        | 0.5250                |
| 2           | 0.4473                        | 0.4721                |
| 3           | 0.5097                        | 0.5026                |
| 4           | 0.5047                        | 0.4901                |
| 5           | 0.5078                        | 0.4837                |
| 6           | 0.5065                        | 0.4901                |
| 7           | 0.4922                        | 0.4900                |
| 8           | 0.4856                        | 0.4931                |
| 9           | 0.4541                        | 0.4700                |

GDP is a material residual: historical 0.6424/team-game versus simulated 0.8913 (+38.8%). Simulated error reaches are 0.2281/game and choices 0.7592; holdout game logs do not separately identify batter ROE/choice rates, so no invented validation targets are supplied. Extra-inning frequency is 9.85% versus 8.60% historical; empty simulated extras are not the modern automatic-runner rule.

## Lineups, strength and win/loss behavior

All 120 selected orders are **observed starting orders**, not PA-ranked fallbacks. The most frequent eligible nine-player pattern is selected, ties by IDs; each complete team-specific player profile requires 50 PA. Raw stints and year/team membership are verified first, and players are unique within each lineup. These orders are held fixed all year, with no substitutions or fatigue, and thus are not historical 162-game rosters.

- **2024.NYA fixture:** Anthony Volpe, Juan Soto, Aaron Judge, Alex Verdugo, Giancarlo Stanton, Anthony Rizzo, Gleyber Torres, Austin Wells, Oswaldo Cabrera. Example source date 20240427, row 399; the order occurs 9 times. It is a verified starting order, not a claim about every game.
- **2024.CHA fixture:** Corey Julks, Luis Robert, Andrew Benintendi, Andrew Vaughn, Gavin Sheets, Korey Lee, Lenyn Sosa, Miguel Vargas, Jacob Amaya. Example source date 20240831, row 2037; the order occurs 2 times. It is a verified starting order, not a claim about every game.

| Season | Selected players’ share of actual PA |
| ------ | -----------------------------------: |
| 2022   |                               66.50% |
| 2023   |                               68.10% |
| 2024   |                               67.76% |
| 2025   |                               67.96% |

The fixed nine replace roughly one third of historical PA taken by other players. This gives a concrete selection-bias mechanism: the selected hitters now receive 100% of simulated PA. Missing running outs and non-PA events also change base occupancy, opportunities and GDP exposure. These are plausible causes, not a fitted causal decomposition. Do not hide them with scoring multipliers. The 200-PA prior can additionally compress lineup extremes.

| Season | Offensive tercile | Historical RPG | M4 RPG |
| ------ | ----------------- | -------------- | ------ |
| 2022   | average           | 4.3037         | 4.1898 |
| 2022   | strong            | 4.7568         | 4.6174 |
| 2022   | weak              | 3.7895         | 4.0262 |
| 2023   | average           | 4.5667         | 4.6318 |
| 2023   | strong            | 5.1877         | 4.9391 |
| 2023   | weak              | 4.0926         | 4.3464 |
| 2024   | average           | 4.3632         | 4.2899 |
| 2024   | strong            | 4.8849         | 4.6411 |
| 2024   | weak              | 3.9321         | 4.0513 |
| 2025   | average           | 4.4056         | 4.2887 |
| 2025   | strong            | 4.9123         | 4.8073 |
| 2025   | weak              | 4.0241         | 4.1612 |

The relationship between simulated run differential/game and win rate across 600 holdout team-seasons is positive (Pearson r=0.8708). The following compares actual records to simulated mean wins ± **season SD**, not a prediction interval. Pitching/defense is standardized, schedules are synthetic, and historical team pitching strength is absent; exact actual W–L recovery is not a supported objective.

| 2025 team | Actual W–L | Actual RD | Simulated wins ± SD | Simulated RD/game |
| --------- | ---------- | --------- | ------------------- | ----------------- |
| 2025.ANA  | 72–90      | -164      | 75.85 ± 5.05        | -0.252            |
| 2025.ARI  | 80–82      | +6        | 89.05 ± 5.92        | +0.514            |
| 2025.ATH  | 76–86      | -84       | 85.60 ± 7.36        | +0.289            |
| 2025.ATL  | 76–86      | -10       | 72.20 ± 7.60        | -0.436            |
| 2025.BAL  | 75–87      | -111      | 79.55 ± 9.38        | -0.092            |
| 2025.BOS  | 89–73      | +110      | 82.75 ± 5.96        | +0.106            |
| 2025.CHA  | 60–102     | -95       | 72.95 ± 6.03        | -0.497            |
| 2025.CHN  | 92–70      | +144      | 85.30 ± 6.33        | +0.242            |
| 2025.CIN  | 83–79      | +35       | 82.05 ± 4.58        | -0.004            |
| 2025.CLE  | 88–74      | -6        | 71.25 ± 5.42        | -0.610            |
| 2025.COL  | 43–119     | -424      | 78.85 ± 6.88        | -0.205            |
| 2025.DET  | 87–75      | +67       | 82.05 ± 4.88        | +0.044            |
| 2025.HOU  | 87–75      | +21       | 79.15 ± 4.99        | -0.062            |
| 2025.KCA  | 82–80      | +14       | 79.35 ± 4.78        | -0.060            |
| 2025.LAN  | 93–69      | +142      | 89.95 ± 5.92        | +0.685            |
| 2025.MIA  | 79–83      | -89       | 77.25 ± 5.21        | -0.304            |
| 2025.MIL  | 97–65      | +172      | 83.90 ± 7.52        | +0.192            |
| 2025.MIN  | 70–92      | -95       | 82.45 ± 5.82        | +0.065            |
| 2025.NYA  | 94–68      | +164      | 90.00 ± 5.22        | +0.644            |
| 2025.NYN  | 83–79      | +51       | 88.20 ± 4.66        | +0.471            |
| 2025.PHI  | 96–66      | +130      | 87.65 ± 6.28        | +0.445            |
| 2025.PIT  | 71–91      | -62       | 72.25 ± 5.47        | -0.539            |
| 2025.SDN  | 90–72      | +81       | 82.85 ± 5.42        | +0.185            |
| 2025.SEA  | 90–72      | +72       | 88.70 ± 5.69        | +0.512            |
| 2025.SFN  | 81–81      | +21       | 76.50 ± 5.49        | -0.282            |
| 2025.SLN  | 78–84      | -65       | 76.35 ± 5.40        | -0.240            |
| 2025.TBA  | 77–85      | +31       | 76.65 ± 6.30        | -0.246            |
| 2025.TEX  | 81–81      | +79       | 74.70 ± 6.44        | -0.276            |
| 2025.TOR  | 94–68      | +77       | 82.25 ± 4.44        | +0.102            |
| 2025.WAS  | 66–96      | -212      | 76.50 ± 6.21        | -0.333            |

## Model assumptions and measured limitations

The fit contains 211,000 eligible single/double/residual-contact plays. Of 72 base/out/event cells, one sparse cell (double, zero outs, runner only on third; 35 observations) falls back to the old policy under the 50-observation rule. Source classifications are retained in the ignored audit:

| Fit classification                     |   Plays |
| -------------------------------------- | ------: |
| batter-extra-advance-proxy             |   1,338 |
| ground-double-play                     |   6,250 |
| observed-error                         |   1,968 |
| observed-fieldersChoice                |   5,320 |
| observed-safe-transition               | 147,021 |
| running-out-on-hit-proxy               |   1,086 |
| third-out-or-unsupported-contact-proxy |  48,016 |
| unsupported-contact-reach-proxy        |       1 |

Terminal contact proxies primarily represent ordinary third outs: holding then stranding runners preserves the supported outcome. The remaining proxies explicitly cover unsupported running outs, extra batter advances on hits, compound plays and ambiguous reaches. They are not dropped from denominators. GDP holds other runners and suppresses all runs/RBI, including occasional legal zero-out advances. Error/choice frequencies are pooled conditional estimates, not measured individual batter facts. Per-runner RBI credit is source-derived; model runs need not equal RBI.

Sacrifices are still explicitly conditioned out. Generic walks include IBB but do not model intentional decisions. Non-PA steals/caught stealing, pickoffs, wild pitches/passed balls/balks, complex tag/force timing, dropped-third-strike reaches, substitutions, parks and individual pitching are absent. Retrosheet contains evidence for some deferred events; they are unimplemented scope, not nonexistent data. Neutral pitching reduces real-world heterogeneity; fixed orders and missing running events alter PA/base-state distributions. These facts explain why valid conditional tables and close RPG can coexist with excessive GDP/PA and low run variance. Further calibration needs targeted ablations and a newly reserved evaluation set, not retuning against the already-used 2025 holdout.

## Native performance and memory

Snapdragon X Plus X1P42100 / Qualcomm Oryon, Windows ARM64, rustc 1.88.0, `aarch64-pc-windows-msvc`, Cargo release defaults. Final benchmarks were rerun after calibration and build jobs completed. No affinity/allocator instrumentation or timing confidence intervals; first-call timings vary. The fixture for timing uses one user lineup and all 29 season opponents (270 prepared profiles).

| Measurement                       | Summary         | Events          |
| --------------------------------- | --------------- | --------------- |
| One game, first call              | 0.1977 ms       | 0.4177 ms       |
| One 162-game season, first call   | 23.9454 ms      | 43.3151 ms      |
| 1,000 seasons (162,000 games)     | 42.9225 s       | 48.9016 s       |
| Mean repeated season              | 42.9225 ms      | 48.9016 ms      |
| Serialized result size            | 1,189,265 bytes | 6,238,536 bytes |
| Observed process peak working set | 11.12 MiB       | 20.09 MiB       |

Both modes accumulate 6,254,108 user PA across the same 1,000 seeds. Timings include validation, setup, input clones, state transitions and result allocation/destruction; parsing, historical preparation, JSON serialization and file/database I/O are outside those loops. Results are dropped between seasons, rather than retaining 1,000 detailed histories. Windows process peaks are polled every 10 ms and may miss the last interval; they include runtime/input/result memory, not engine-only heap. Traces grow with games/PA; summary omits them. The <1-second season goal is met on this native device. Browser/WASM runtime and mobile speed remain untested.

## Validation, reproduction and next steps

- Rust fmt/Clippy (`-D warnings`) and **48 tests** pass, including original scripted goldens, per-game replay, schedule/seed order stability, complete-game/season aggregation, every fitted transition choice, force-third-out run suppression, error/choice identities and contextual walk-offs. Walk-off outs are excluded from stranded-runner counts, including scoring outs and fielder's choices.
- Python Ruff and **132 tests** pass with both verified source directories. Seven source integrations skip without downloaded data. Sources, malformed/duplicate logs, probability mass, aliases/fixtures, repeated-season uncertainty and duplicate native rows are tested.
- Native release examples and `wasm32-unknown-unknown` library compilation pass. Actual WASM execution parity was not tested. The complete native season JSON validates against shared schemas.
- Web/API TypeScript, ESLint, web build, Wrangler dry run and local D1 `SELECT 1` checks pass. These components receive no feature changes; no resources are provisioned. Prettier and Git whitespace checks pass.

Run the fetch/prepare/run commands and release benchmark examples in the [workflow guide](../../docs/SIMULATION_FOUNDATION.md#season-simulation-and-calibration-m4). Machine-readable artifacts are `targets.json`, `lineups.json`, `transitions{,-audit}.json`, per-year `inputs-YYYY.json`, `manifest.json`, per-model `rows-YYYY-MODE.json` and `results/calibration.json`. Statistical counts are deterministic; elapsed timings and hashes including timings naturally vary. The small committed NYA/CHA fixture and compact golden are regression artifacts; raw/large outputs are ignored.

Before treating M4 as an accuracy gate, investigate the failed hit/PA bands, GDP/base occupancy and roster-exposure bias with isolated ablations. Do not expand full-roster gameplay or add arbitrary multipliers. For M5, the next technical work is a thin WASM adapter in a Web Worker, golden native/WASM execution parity, bounded payload/detail handling, and real desktop/mobile cold/warm benchmarks. Keep the documented realism limits visible. M5 and automatic Git commits are not part of this implementation.
