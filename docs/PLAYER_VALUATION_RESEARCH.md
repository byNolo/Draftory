# Offline MLB valuation and eligibility research (M7A)

M8C.2 reuses these frozen observations for provisional game currency; see
[pricing/PA findings](../data/validation/pricing-pa-v1.md) and the
[reproduction section below](#m8c2-pricing-and-pa-study). The original research
and its statistical limitations remain unchanged.

This is an analysis tool, not the draft game. Python reads the immutable M6A
publication and calls the existing native Rust calibration example. It neither
changes prepared profiles nor implements baseball transitions in Python. There
are no new dependencies, database schemas, API routes, browser features or
production prices. The existing architecture is retained.

Read the [measured report](../data/validation/valuation-eligibility-v1.md) and
[compact results](../data/validation/valuation-eligibility-v1.json) before using
the numbers. Statistical values and hypothetical currency quotes are separate.

## Reproduce

From the repository root, first prepare the pinned 2024 publication using the
[M6A export instructions](PLAYER_DATA_API.md#reproducible-export-and-local-import).
No D1 instance or Worker is needed: research loads the generated SQL into an
in-memory SQLite database using the existing migrations.

```sh
uv sync --locked --project data/pipeline
cargo build --locked --release -p baseball-sim --example calibrate
uv run --project data/pipeline python -m draftory_data.valuation --publication-dir data/processed/d1-2024 --output-dir data/processed/m7a --repetitions 8 --draft-trials 500
```

This performs 2,045,088 native games and 94 draft experiment configurations. It
can take several minutes. Generated inputs and observations stay in ignored
`data/processed/m7a/`; no raw datasets or complete publication are checked in.
Use the same command with `--reuse-native` to verify and reuse native observations
while recalculating eligibility, prices and draft experiments. A cache with a
different input, executable hash, repetition count or research version fails
explicitly; changed rows fail their checksum. Remove that output directory or
choose a new one to intentionally regenerate with a newly built executable.

The runner path defaults to `target/release/examples/calibrate[.exe]`;
`--runner` overrides it. Binary hashes differ across platforms/toolchains: compare
inputs, versions, seeds and deterministic run counts across builds, not binary
hashes. A different `--repetitions` changes the experiment size and uncertainty;
cache reuse requires the same count and does not append repetitions.

## Measurements and outputs

The loader verifies SQL SHA-256, the publication content ID, profile digests,
source/policy/context compatibility, complete sample opportunities and membership
counts. Original batting stints are aggregated once per player. Position games
are summed across teams; any unknown contribution keeps that position unknown.
Missing, zero and positive observations remain distinct. Generic OF never implies
LF/CF/RF unless the named broad-OF sensitivity policy explicitly requests it.

Two synthetic experiments reuse the unchanged M4 fixture and contextual model:

- **Homogeneous offense:** nine unique batter-instance IDs use the candidate's
  profile template. Measure team runs/game; this includes nonlinear lineup effects.
- **Single-slot marginal offense:** replace slot five of nine reference templates
  with the candidate; subtract the paired reference team's runs/162 games.

The reference is the actual published profile nearest the PA-weighted mean
prepared probability vector by L1 distance, excluding the opponent's identities.
It is not a validated league-average or replacement-level hitter. The fixture's
CHA opponent, neutral pitching, schedule, transitions and rules remain fixed.
Template reuse is labeled `userLineupKind: synthetic`, never a legal draft roster.

Inputs are batched in publication order, 30 candidates per batch. The unchanged
runner sorts team IDs, then generates season seeds with
`season_game_seed(20261025, repeat * batch_length + sorted_team_index)`. Separate
reference/homogeneous/marginal calls use matching seeds. Streams repeat across
batches; results across different players are therefore not independent samples.
Batch size/order and actual seeds are recorded. Error bars are sample standard
deviation / sqrt(repetitions) across paired season differences, not confidence
about real player skill or model accuracy. No individual simulated PA or outs
are available in this compact runner output: do not relabel the results per
600 candidate PA or per 27 outs.

Outputs (research schema `1.0.0`, `mlb-valuation-research-v1`):

| File                                   | Contents                                                                                                                                                               |
| -------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `research.json`                        | All 526 records, source/policy/context/model IDs, binary/fixture hashes, eight seeds and deltas per player, policy/price distributions and all draft experiments       |
| `rankings.csv`                         | Descending marginal point estimates, profile IDs, historical PA/OPS, smoothing weight, direct on-base probability mass, uncertainty, homogeneous value and eligibility |
| `summary.json`                         | Compact review subset: all policy counts, selected distributions, examples/outliers and tabular experiment results                                                     |
| `native/*.input.json`, `native/*.json` | Synthetic native inputs, checksummed deterministic observations and cache identity                                                                                     |

The checked-in compact JSON is `summary.json` formatted by Prettier. Its draft
table has explicit `columns` and `rows`. Full input/output audits remain available
locally. `preparedDirectOnBaseMass` sums direct single/double/triple/HR/BB/HBP
weights; it is not predicted official OBP because unresolved contact can produce
errors or force choices. `rawComparableDirectOnBaseMass` excludes SH/SF from its
denominator to match preparation; `raw.OBP` retains the historical display formula.

The offline offer analysis uses Python's MT19937, independently of Rust's RNG:
the integer seed is SHA-256 of canonical `[20261027, configuration]`. Each case
records its seed/version, offers, selection policy, order and trial count. Offers
contain up to three distinct identities; selected identities are excluded from
all subsequent slots. Unselected offers may recur. Tiers are per-position thirds
of the value-sorted eligible pool, frozen before selections. A reserve-aware agent
maximizes the marginal point estimate among choices that leave an affordable
distinct-player completion. Completion costs use exact minimum-cost matching,
including identity overlap, rather than independent slot minima. A protected
case inserts a cheapest-completion candidate when no safe offer exists; this is
an experimental rule, not implemented gameplay. Its guarantee assumes the agent
only chooses safe options. See the report for denominators and limitations.

## Validation

```sh
uv run --project data/pipeline ruff check data/pipeline
uv run --project data/pipeline ruff format --check data/pipeline
uv run --project data/pipeline pytest data/pipeline/tests
```

Tests use synthetic source/publication fixtures, brute-force assignment checks,
overlapping eligibility, budget traps, price monotonicity, null propagation,
tampering, and native cache/parity checks. The native integration test skips with
an explicit reason when the release `calibrate` executable has not been built.
Run it after building to exercise real paired native measurements. Existing
source integration tests also accept `--lahman-source data/raw/lahman-2025` and
`--retrosheet-source data/raw/retrosheet-m4` from the repository root.

## M8C.2 pricing and PA study

Use the existing verified 2024 SQL publication and reviewed
`data/processed/m7a/research.json`. The portable integer measurement digest must
match M7A; the historical source/profile context cannot be silently substituted.
If starting without that generated research, use the M7A workflow above first.
Do not rerun its two-million-game valuation merely to compare currency/budgets.

From the root:

```sh
cargo build --locked --release -p baseball-sim --example season
uv run --project data/pipeline python -m draftory_data.pricing_study --publication-dir data/processed/d1-2024 --research data/processed/m7a/research.json --output-dir data/processed/m8c2
node scripts/study-draft-pricing.mjs 100
uv run --project data/pipeline python -m draftory_data.draft_catalog --publication-dir data/processed/d1-2024 --research data/processed/m7a/research.json --pricing-policy m8c2-elite-1-30-smoothed-v1 --output data/publications/mlb-draft-2024-v2.json
uv run --project data/pipeline python -m draftory_data.pricing_study --publication-dir data/processed/d1-2024 --research data/processed/m7a/research.json --output-dir data/processed/m8c2 --reuse-native --draft-study data/processed/m8c2/draft-budgets.json --summary-output data/validation/pricing-pa-v1.json
```

`pricing.py` defines exact rational half-up currency formulas, broad pool-value
tiers, two comparison-only PA adjustments and the selected elite/no-extra-PA
policy. The measured report explains why the extra adjustments were rejected.
These functions never edit a prepared outcome vector or historical statistic.

`pricing_study` measures actual candidate PA in slot five of the existing reference
lineup for two fixed season seeds, over all 526 profiles. It retains versioned
input JSON and checksummed observations under ignored `data/processed/m8c2/native`.
`--reuse-native` rejects changed runner/input/observations; use a new directory or
explicitly rerun without that flag if the native binary changes. Binary hashes
are platform/toolchain dependent; prices depend only on the portable M7A integer
observations and explicit currency policy, not benchmark timings.

`study-draft-pricing.mjs` transpiles the actual pure TypeScript draft engine using
the already-installed compiler into ignored `target/m8c2/`. It does not recreate
the game in Python. Four price policies, budgets 65/70/75/90, four agents and 100
seeds produce 6,400 drafts, checking every displayed candidate's completion cost.
It writes cost/remaining distributions, per-round choices, selected value tiers,
elite frequencies, distinct rosters and fresh-cache timings to `draft-budgets.json`.
JS/JIT warmup is explicit; timings are not cold-network or phone measurements.

`--summary-output` combines these outputs with current catalog identity and checks
their provenance. Timing hashes naturally change across reruns; deterministic
catalog bytes do not. The publisher preserves v1, adds v2 with a new ID and schema,
and refuses to overwrite any existing catalog file with different bytes.
Only the compact currency catalog and compact report are committed; full native
inputs and large research audits remain generated. No D1 price table, migration,
probability adjustment or cloud deployment is part of this work.

### Historical pricing engine pin (M8C.5 final review)

M8C.2 executes `data/research/pricing-draft-engine-v1.ts`, the exact engine from
commit `fe02cbda273cc4db9339539592284eb4b7026a84`, SHA-256
`38c8a68ba2c1bc9876b69107ddf44e25ad22781d5c1d8b4bdb792cf5792f082a`.
Both the Node runner and Python summary validator verify these bytes. They do
not bind historical research to the evolving application engine. The snapshot
is executable evidence, excluded from formatting to preserve its exact hash.
The live game continues to use its current reroll-capable engine.

Use separate output directories to compare regenerated measurements without
replacing the original cache or frozen report:

```sh
node scripts/study-draft-pricing.mjs 100 historical target/m8c5/pricing-historical
node scripts/study-draft-pricing.mjs 100 current target/m8c5/pricing-current
```

`current` requires an explicit separate output directory. Existing measurement
files are never overwritten; use a fresh directory for another run. Compare all deterministic
fields; measured timings naturally differ. Regenerating a timing measurement is
not byte reproduction of an old wall-clock observation. Preserve the original
cache/report for that historical evidence. See the [final review](../data/validation/season-dashboard-final-review-v1.md).
