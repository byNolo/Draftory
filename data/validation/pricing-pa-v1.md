# M8C.2 · Elite pricing and historical PA

Checked 2026-10-28. **Provisional human-playtest settings:** the previously
researched quadratic elite curve, **65 credits**, and **no additional PA price
adjustment**. Prices are fictional currency, not new talent estimates. No source
records, prepared weights, smoothing, Rust rules/RNG, opponents or goldens changed.

[Compact measurements](pricing-pa-v1.json) contain all 64 experiment rows, price
histograms, PA bands, outliers, hashes and selected catalog/policy identifiers.
[Reproduction](../../docs/PLAYER_VALUATION_RESEARCH.md#m8c2-pricing-and-pa-study)
uses the verified local publication and reviewed M7A measurements; no new source,
database table or dependency was introduced.

## Inputs, tiers and currency comparisons

All **526** 2024 profiles retain their identities and existing 200-PA smoothing.
M7A's eight integer marginal-run observations/player reproduce portable digest
`d450086adca34294ca61c6de5f3e06dca25b875545c5c8ea55c36993540431a6`.
Publication SQL SHA-256 remains
`4dab2562d2b4344cd7499bb6ea54f899b4ba3fe95f1f859c3772d6d7f695828d`.
See [source attribution](../../docs/DATA_ATTRIBUTION.md).

Let `v` be the mean of those eight marginal team-run differences and
`z = (v - pool_min)/(pool_max - pool_min)`. Every formula rounds half up once at
the end, with minimum price 1. Python uses exact rational arithmetic. The
existing values span -43.375 to +65.750. Four broad tiers use pool P25/P75/P95
thresholds -13.375 / +4.500 / +20.375; equal values stay together. Percentiles use
ordered index `floor((N-1)*q)`. These thresholds are descriptive, not confidence
intervals or validated talent classes. M7A's sampling errors make adjacent ranks
unreliable; no manual recognizable-player overrides were made.

| Comparison                      | Formula / interpretation                      |
| ------------------------------- | --------------------------------------------- |
| Existing linear                 | `1 + 19*z`, range 1–20                        |
| Researched elite, selected      | `B = 1 + 29*z²`, range 1–30                   |
| Confidence-discount sensitivity | `B * (1 - 0.15*clamp((200-PA)/150,0,1))`      |
| Tier-cap sensitivity            | Below 200 PA, `min(B, B_at_P95)`; otherwise B |

The last two affect **currency only**. Neither changes probabilities or limits
season participation. Historical PA never multiplies simulated ability or value.

| Value tier                  | Players | Linear median | Elite median |
| --------------------------- | ------: | ------------: | -----------: |
| Low                         |     130 |             5 |            3 |
| Middle                      |     262 |             8 |            4 |
| Above-average               |     106 |            10 |            8 |
| Elite (P95+, ties included) |      28 |          13.5 |         13.5 |

Whole-pool linear mean/median/range are 7.882 / 8 / 1–20; elite are
5.317 / 4 / 1–30. The new curve raises the extreme ceiling and makes ordinary
hitters cheaper; **not every elite-tier player gets more expensive**. Median
elite-to-middle price separation grows from 13.5 versus 8 to 13.5 versus 4.
Pool min/max scaling remains sensitive to noisy extremes and membership changes.

## Historical sample versus simulated usage

The new experiment runs each actual prepared profile in batting slot five of
the existing synthetic reference lineup, with eight reference templates and the
unchanged CHA opponent/context. Two full 162-game seasons use seeds 0 and 1:
**1,052 seasons / 170,424 games** through the existing native `season` example.
Candidate PA is read from that batter's actual season counters, not team PA/9.
Each generated input and cached observation is bound to its input/runner hashes.

| Historical PA band | Players | Historical PA median | Simulated PA median | Median player weight | Marginal value median |
| ------------------ | ------: | -------------------: | ------------------: | -------------------: | --------------------: |
| 50–99              |      71 |                   73 |                 687 |                0.267 |                -11.38 |
| 100–199            |      90 |                  150 |              686.25 |                0.429 |                -10.63 |
| 200–399            |     158 |                299.5 |                 687 |                0.600 |                 -8.38 |
| 400–599            |     130 |                482.5 |                 688 |                0.707 |                 -2.31 |
| 600+               |      77 |                  647 |               689.5 |                0.764 |                 +7.25 |

“Marginal value” is the M7A reference-lineup team-run-difference index, not the
player's runs or a forecast. Simulated PA entries are medians of each player's
two-seed mean. Median player-level simulated/historical exposure ratios are
9.37, 4.56, 2.30, 1.42 and 1.07 respectively; ratios are diagnostics, not pricing
multipliers. Fixed reference teammates/order keep usage similar across groups.
Two seeds characterize this particular experiment, not general lineup variance.

The existing prior uses `player_weight = PA/(PA+200)`. Thus small samples already
receive substantial league influence. For Rece Hinds, 51 historical PA become
689 simulated PA in this experiment; his raw comparable direct on-base mass is
0.3333 versus prepared 0.3182, and his player weight is 0.203. These masses are
not predicted official OBP: unresolved contact can produce errors/choices.
Mike Trout's 126 historical PA become 685.5 simulated PA with weight 0.387.
Those are examples of full-season exposure, not proof of poor underlying talent.

### Selected PA policy

Retain the already-smoothed ability-based price with **no extra PA adjustment**.
The discount changes 62 prices and the tier cap changes only one (Trout 13→11).
Discounting Trout gives 12 and Hinds 7 instead of 13 and 8; no new uncertainty or
availability downside is simulated in exchange. For the cheapest agent at 65,
the discount increases sub-200-PA selections from 3.08 to 3.38 per draft while
lowering average cost from 28.21 to 27.34. Shared seed paths diverge, so this is
a descriptive strategy comparison, not a fitted causal effect.

An extra confidence discount risks double-counting the existing prior and
subsidizing the exact full-season-usage concern. A cap also reduces price without
reducing simulated usage. Neither is adopted. This does **not** solve historical
availability: future exposure/availability rules need a separate reviewed
milestone, positional-coverage analysis and explicit gameplay behavior. No floor,
injury, bench, substitution or probability adjustment is implemented here.

## Budget and offer experiments

The actual deterministic TypeScript engine tests four prices × four budgets ×
four agents × seeds 0–99: **6,400/6,400 completed drafts**. All **171,458** displayed
offers are separately checked for an affordable distinct-player suffix. Eligibility
remains ten specific-position games, universal DH, nine unique identities, 50 PA,
three offers where possible, and the existing scarce-first draft order. The
matching invariant, not the observed completion percentage, preserves completion
after every allowed pick. Minimum distinct-roster costs are 25 linear and 10 for
all three elite-based comparisons.

Agents pick first offered, cheapest, highest price, or highest broad value tier
then cheapest within that tier. The last avoids ranking noisy adjacent estimates.
Full distributions, per-round one/two/three counts and timings stay in generated
`draft-budgets.json`; compact output includes every combination and tier selection.
“Elite/superstar frequency” here means the explicit 28-player P95+ model tier,
not career reputation or a precise skill ranking.

Elite curve, highest-price agent, 100 drafts per budget:

| Budget | Mean / median cost | Median credits left | Mean offers/round | One-choice rounds | Mean elite picks | Drafts with an elite |
| ------ | -----------------: | ------------------: | ----------------: | ----------------: | ---------------: | -------------------: |
| 65     |         62.02 / 64 |                   1 |            2.9911 |            0.222% |             0.87 |                  65% |
| 70     |         63.92 / 65 |                   5 |            2.9956 |                0% |             0.88 |                  67% |
| 75     |       65.22 / 66.5 |                 8.5 |                 3 |                0% |             0.86 |                  66% |
| 90     |         65.95 / 66 |                  24 |                 3 |                0% |             0.98 |                  70% |

At 65, highest-price roster mean value index is 3.68 versus 5.85 at 90. It is the
mean of individual marginal estimates, **not additive predicted roster runs**.
Every case yielded 100 distinct rosters; value-tier and selected-player counts
in the JSON describe construction differences, not proof of enjoyment.

Selected elite/65, four agents:

| Agent                      | Mean / median cost | Median credits left | Mean elite picks | Mean value index |
| -------------------------- | -----------------: | ------------------: | ---------------: | ---------------: |
| First offered              |       45.74 / 46.5 |                18.5 |             0.29 |            -4.59 |
| Cheapest                   |         28.21 / 28 |                  37 |                0 |           -14.77 |
| Highest price              |         62.02 / 64 |                   1 |             0.87 |            +3.68 |
| Highest tier, then cheaper |         58.17 / 60 |                   5 |             0.79 |            +2.16 |

**Design judgment:** choose 65 as the tightest requested budget with broad safe
choices. A 30-credit hitter consumes 46.2% of it, versus 22.2% for the previous
20-credit ceiling at 90. This creates a larger explicit elite commitment without
making forced single choices common. Ordinary hitters are cheaper, so conservative
drafts remain loose; the first/cheapest agents still leave substantial credits.
This is a practical experiment, not a claim that every draft is harder or balance
is solved. All four agents need human playtesting before further tuning.

## Publication, examples and performance

New policy: **`m8c2-elite-1-30-smoothed-v1`**, schema **2.0.0**, default budget 65.
Catalog **`draft-catalog:cbfacb05ccb10ad266e115074e56193a74e529355ce7ed2706b04aefef9e724c`**
is published separately as `mlb-draft-2024-v2.json`; v1 bytes and identifiers remain
unchanged. Regeneration is deterministic. The CLI refuses to replace an existing
catalog file with different bytes. Profile/dataset/source references remain the
same; no D1 migration or import is necessary for this currency-only update.

| Player          | Historical PA | Previous price | New price |
| --------------- | ------------: | -------------: | --------: |
| Aaron Judge     |           703 |             20 |        30 |
| Shohei Ohtani   |           728 |             20 |        30 |
| Juan Soto       |           713 |             19 |        27 |
| Mike Trout      |           126 |             13 |        13 |
| Rece Hinds      |            51 |             10 |         8 |
| Jonathan Aranda |           143 |              9 |         6 |

Prices are global per identity, not per position. Draft history keeps the actual
price paid. UI budget/remaining/spent/results use catalog/config values; cards
label historical PA and explain that it is not a simulated availability limit.
Custom orders still change only batting sequence, and results join by identity.
The matching algorithm and RNG are unchanged. Legacy 90-credit defaults remain
available with the legacy catalog for exact replay; the current catalog supplies 65. Its same historical first-choice example still yields the unchanged 81–81,
593-run native/WASM result, while its draft prices and catalog ID change.

Node v22.21.0, Windows ARM64: fresh engine/cache per draft after 20 JS/JIT warmup
drafts, not cold browser/network timing. Selected elite/65 first-offered median
whole computation is **9.71 ms**, P95 **10.47 ms**; median selection **0.73 ms**.
The same-run linear/90 first agent is about **10.2 ms** median. These descriptive
results do not establish a speedup or phone performance; no algorithm optimization
was introduced. New catalog build size is about 146.78 KB / 38.06 KB gzip versus
135.55 KB / 37.52 KB gzip for v1. The additional broad-tier labels cost about
0.54 KB gzip. No complete prepared-profile dataset enters the static catalog.

## Validation and limits

Local validation completed:

| Check                                                               | Result                                                               |
| ------------------------------------------------------------------- | -------------------------------------------------------------------- |
| Pricing/budget experiment                                           | 6,400 complete drafts; 171,458 displayed choices checked             |
| Native PA experiment                                                | 1,052 complete seasons, plus verified cache reproduction             |
| `npm run test:data-client`                                          | 31 passed; includes 400 new-budget and 1,200 legacy draft trials     |
| `npm run test:integration`                                          | 40 passed; 3 optional real-publication cases skipped in fixture mode |
| `npm run test:integration:edge`                                     | 10 passed; 1 optional real-publication skip                          |
| `npm run test:alpha` with real 526-player local publication         | 37 passed, Chromium/Firefox/WebKit and both mobile projects          |
| `npm run test:browser`; `npm run test:edge`                         | 62 and 13 passed; original full native/WASM goldens preserved        |
| `npm run test:api`; `npm run test:alpha:tools`                      | 8 and 6 passed                                                       |
| Python Ruff lint/format and pytest                                  | 152 passed, 8 optional source integrations skipped                   |
| Rust fmt, Clippy, workspace tests, WASM-target build                | Passed; 52 tests                                                     |
| TypeScript, ESLint, Prettier, Vite production build, Git whitespace | Passed                                                               |
| Worker dry-run checks and local D1 `SELECT 1`                       | Passed; no remote operation                                          |

The local Python run regenerates both immutable catalog versions from verified
research/publication bytes and reproduces the compact study. Fresh CI skips that
optional producer check when generated research is unavailable; pure formulas,
schema/digest checks, membership, immutable writes and compact-report consistency
still run. GitHub Actions has not executed these uncommitted M8C.2 changes.

New tests cover rational prices, monotonicity, PA-policy boundaries, tiers/ties,
immutable publication writes, both producer versions, cache integrity, digest
rejection, all requested budgets, every safe branch, deterministic replay,
budget/price displays and custom-order/native-WASM compatibility. Existing
historical/source/profile and simulation golden files are retained.

Remaining limitations: M7A's reference/order dependence and Monte Carlo noise,
pool min/max sensitivity, fixed CHA/neutral defense/pitching, existing scoring
calibration biases and full-season use of every hitter. No physical-phone or
human balance conclusions are claimed. M8C.3 should research defensive data field
coverage, identifiers, era gaps and measurement definitions before proposing
defensive values or touching the simulator. It has not started.

The completed M8A/M8C.1 work was committed as `0712131` before M8C.2. No M8C.2
commit, GitHub push or Cloudflare deployment was performed.
