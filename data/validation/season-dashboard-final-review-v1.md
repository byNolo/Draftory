# M8C.5 final review and pricing regression resolution

2026-10-28. No commit, push, deployment or next milestone.
[Machine-readable comparison](season-dashboard-pricing-review-v1.json).

## Root cause

The original failure was reproduced in
`test_verified_producer_reproduces_both_catalog_versions_when_local_research_is_available`.
Both immutable catalogs reproduced successfully; the failure occurred when
`compact_summary` compared the historical draft cache's engine hash with the
moving application source file.

The ignored cache `data/processed/m8c2/draft-budgets.json` correctly records
SHA-256 `38c8a68ba2c1bc9876b69107ddf44e25ad22781d5c1d8b4bdb792cf5792f082a`,
exactly the bytes from commit `fe02cbda273cc4db9339539592284eb4b7026a84`.
Commit `a6f7bca03f60302872f9d5a19f2bef388b179665` added optional rerolls and
changed the live source hash to
`2ff3e2ccf280d3ddfa5206ad6f4cdf67a6dbd9206fefcd0868bde69831d4bd4a`.
M8C.5 did not change that engine. The cache was valid historical evidence,
not corrupt observations; the bug was binding its validator/runner to HEAD.

## Fix and numerical verification

The original TypeScript source is preserved verbatim at
`data/research/pricing-draft-engine-v1.ts`. Both the Node experiment runner and
Python summary validator verify its fixed historical SHA-256 before use.
The live game still uses the current engine. No expected historical hash,
source lock, pricing formula, PA assumptions, statistical measurement, catalog,
frozen numerical report or legacy simulation golden was changed.

Fresh experiments were generated in separate ignored output directories:

```sh
node scripts/study-draft-pricing.mjs 100 historical target/m8c5/pricing-historical
node scripts/study-draft-pricing.mjs 100 current target/m8c5/pricing-current
```

Each ran four price policies × four budgets × four agents × 100 seeds:
**64 cases, 6,400 complete drafts, 171,458 safe offers checked**. Recursively
comparing every field except wall-clock timings and the expected current/historical
source-hash difference gives exact equality between the original cache, the
fresh historical run and the fresh current-engine run. This includes provenance,
study/PA measurement identifiers, completion counts, cost/remaining distributions,
choice counts by round, value-index summaries, elite/low-PA frequencies,
selected-tier counts and distinct-player/roster counts.

The experiment never invokes rerolls, so current-engine execution retains the
legacy draw stream and selection behavior. No simulation rule or probability
changed. Newly measured performance times naturally differ; original cached
timings/report bytes remain intact. The runner refuses to overwrite existing
measurement files, and a current-engine comparison requires a separate output
directory. A new Python regression verifies the frozen report's engine binding
and rejects a modified snapshot. Existing assertions, including exact complete
report equality and mismatched-input rejection, remain enforced.

## Dashboard review

The implementation review and executable checks confirm:

- All 162 opponent references resolve; nine opponents each receive 18 games,
  with nine home and nine away. Sorting/permutation and same-seed determinism
  are covered without a scheduler rewrite.
- Game scores, inning lines, per-opponent W/L and runs reconcile with season
  totals. Player counters remain keyed to the correct batter IDs, and every
  player's aggregate reconciles to their per-game counters in Rust.
- Custom batting order is separate from fielding assignments. Experimental
  error avoidance remains opt-in and labeled; opponents remain neutral.
- Legacy single-opponent fixtures/goldens are unchanged. Full and compact
  projections agree exactly with native Rust, including maximum-u64 seeds.
- Compact results contain supported counters and inning summaries, without
  full inputs, duplicated prepared profiles or season event logs.

No additional dashboard correctness bug was found. Existing historical calibration,
representative-roster and physical-device limitations remain as documented.

## Final validation

All requested final checks passed:

| Check                                                                                                    | Result     |
| -------------------------------------------------------------------------------------------------------- | ---------- |
| Full source-backed Python suite, including the original regression and new pin test                      | 181 passed |
| Focused pricing tests                                                                                    | 8 passed   |
| Rust workspace tests                                                                                     | 63 passed  |
| Native/WASM parity, dashboard and legacy summary/events, six browser projects                            | 24 passed  |
| Real-D1 single-origin alpha: hosting, dashboard, custom order, rerolls and defense                       | 23 passed  |
| TypeScript data-client/draft/pricing tests                                                               | 37 passed  |
| API tests                                                                                                | 8 passed   |
| WASM build, production build, TypeScript, Clippy, Rust fmt, ESLint, Prettier, Ruff and whitespace checks | Passed     |

The full Python command was:

```sh
data/pipeline/.venv/Scripts/python.exe -m pytest data/pipeline/tests -q --lahman-source data/raw/lahman-2025 --retrosheet-source data/raw/retrosheet-m4
```

Browser parity used `dashboard v1 multiple|native/browser full-season parity`
across Chromium, Firefox, WebKit, Edge and both mobile emulations. Real-D1 alpha
used the existing alpha Playwright config with `M6B_IMPORT_SQL` set, selecting
single-origin hosting, dashboard reconciliation, error avoidance, custom batting
order and reroll flows. These tests preserve exact native equality, legacy goldens
and reconciliation assertions. No assertions were relaxed or failures suppressed.

**M8C.5 is ready to commit.** No blocking issues remain from this review; existing
simulation calibration and physical-device validation limitations remain documented.
No commit, push, deployment or another milestone was performed.
