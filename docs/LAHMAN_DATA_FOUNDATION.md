# Lahman data foundation

This milestone implements acquisition, inspection, normalized facts and preliminary
descriptive profiles. It follows the existing Python / Rust / API boundaries;
there is no simulator, frontend integration, Retrosheet import or database schema.
The request's Milestone 2 includes the plan's M1 import and the explicitly requested
preliminary aggregation work from M2. No later milestone has started.

## Source and reproducibility

The source is SABR's official [2025 Lahman CSV release](https://sabr.org/lahman-database/),
covering 1871–2025. SABR links a **Box folder**, not a fixed ZIP archive. The packaged
[source lock](../data/pipeline/src/draftory_data/resources/lahman-2025.lock.json)
pins eight individual official file URLs, byte sizes, SHA-256 values and CSV headers.
Its canonical content SHA-256 is
`8f4cfb56f0726ebe7c900f8d8748232a3c8b326b2fc0d44a387512442e58a22c`.

These are project-observed hashes of official HTTPS downloads, not independently
published SABR checksums. An independent second download reproduced all eight.
Acquisition never substitutes mirrors or silently accepts a changed release.
An unavailable URL or mismatch fails explicitly; future source revisions require
a reviewed lock update and regenerated reports/artifacts.

`fetch` reuses verified cached files, downloads missing files through temporary
files and verifies bytes before publishing them. Changed cached files fail rather
than being overwritten. An interruption can leave verified files that a subsequent
fetch safely resumes. `acquisition.json` records the lock hash, file list and UTC
verification time. A verification time is not a claimed original retrieval time
for cached files. The receipt is version 1.0.0 and describes a folder snapshot;
the foundation's archive-oriented v0.1 source-manifest example is not reused.

CSV parsing uses UTF-8 with optional BOM. Exact field casing matters, notably
`Fielding.POS`, `Teams.Ghome` and `Teams.IPouts`. `NA` is a valid league ID, never
a missing marker. Empty fields, literal `NULL` and `\N` parse as null; zero stays
zero. Counts must be integers; finite floating-point fields are limited to the
documented ERA, FP and ZR columns. No pandas or runtime dependencies are needed.

See [data attribution](DATA_ATTRIBUTION.md) and the
[measured quality report](../data/validation/lahman-2025-data-quality-report.md).

## CLI

From `data/pipeline`:

```sh
uv sync --locked
uv run draftory-data fetch --source-dir ../raw/lahman-2025
uv run draftory-data verify --source-dir ../raw/lahman-2025
uv run draftory-data inspect --source-dir ../raw/lahman-2025 --output-dir ../processed/lahman-2025-inspection
uv run draftory-data normalize --source-dir ../raw/lahman-2025 --output-dir ../processed/lahman-2025
```

All transforms verify source hashes first. Inspection writes `inspection.json`
(complete fields/types, per-year nulls, coverage and diagnostics) and
`data-quality-report.md`. Normalize writes eight JSONL files and a checksum manifest.
Raw files, acquisition receipts and generated datasets remain ignored by Git.

```sh
# A specific complete player-season
uv run draftory-data profile --source-dir ../raw/lahman-2025 --player judgeaa01 --leagues AL NL --start-year 2025 --end-year 2025 --output ../processed/examples/judge-2025.json

# Career counts pooled before dividing by opportunities
uv run draftory-data profile --source-dir ../raw/lahman-2025 --player judgeaa01 --leagues AL NL --method aggregate

# Arithmetic mean or component median of complete season-level rates
uv run draftory-data profile --source-dir ../raw/lahman-2025 --player judgeaa01 --leagues AL NL --method season_rate_mean
uv run draftory-data profile --source-dir ../raw/lahman-2025 --player judgeaa01 --leagues AL NL --method season_rate_median

# Team filter applies before season aggregation; all three methods are supported
uv run draftory-data profile --source-dir ../raw/lahman-2025 --player sotoju01 --leagues AL NL --team WAS --method aggregate

# Franchise scope and inclusive year bounds are independent filters
uv run draftory-data profile --source-dir ../raw/lahman-2025 --player judgeaa01 --leagues AL NL --franchise NYY --start-year 2020 --end-year 2025 --method season_rate_median --min-season-pa 100 --min-seasons 2

# Pretty-print a generated artifact without changing it
uv run python -m json.tool ../processed/examples/judge-2025.json
```

`python -m draftory_data` provides the same commands. Exit codes: 0 success,
2 invalid input/source/I/O error, 3 a valid `insufficient_data` profile (still
written/printed). Explicit `--leagues` is mandatory. There is no implicit "all
historical major leagues" career pool. Team IDs mean the exact source code across
selected years; `--franchise` follows `Teams.franchID`. They are mutually exclusive.
Minimum PA and season counts are configurable; defaults of one are mathematical
minimums, not proposed gameplay eligibility thresholds.

## Normalized records and contracts

The versioned [manifest](../contracts/normalized-lahman-manifest.schema.json) binds
every output file to its row count and byte checksum. Each line conforms to a
definition in [normalized-lahman-record.schema.json](../contracts/normalized-lahman-record.schema.json):

| File                         | Definition          | Grain                                                                         |
| ---------------------------- | ------------------- | ----------------------------------------------------------------------------- |
| `players.jsonl`              | `player`            | One `lahman:<playerID>` identity; original ID/name/external mappings in facts |
| `teams.jsonl`                | `team`              | Source year/team/league plus franchise and original facts                     |
| `franchises.jsonl`           | `franchise`         | Source franchise identity                                                     |
| `batting-stints.jsonl`       | `battingStint`      | Player/year/stint/team/league with original nullable counts                   |
| `player-seasons.jsonl`       | `seasonBatting`     | Player/year, with all contributing teams/leagues listed                       |
| `player-team-seasons.jsonl`  | `teamSeasonBatting` | Player/year/team/league, collapsing repeated stints with that team            |
| `position-appearances.jsonl` | `appearance`        | Player/year/team/league, counts including LF/CF/RF/DH                         |
| `fielding.jsonl`             | `fielding`          | Player/year/stint/team/league/position/source table                           |

Duplicate candidate keys and orphan identity/team/franchise references fail
normalization. The two observed inconsistent batting rows are preserved with
quality flags. Source row numbers count the header as row 1. Facts retain source
field names; normalized keys use snake_case. Batting row references always refer
to pinned `Batting.csv`. Other records identify their source through the file
mapping above; fielding includes its source table explicitly.

Full player-year records sum each stint once and retain all source-row references.
No appearance join participates in these sums. Unknown components propagate to
null in the aggregate. Player-year records can list multiple historical leagues;
they are facts, not an eligible gameplay pool. Profile requests independently
filter explicit leagues before aggregation. No position threshold or DH fallback
is applied. FieldingOFsplit is retained separately, never added to Fielding totals.

JSONL uses UTF-8, LF and sorted JSON keys; counts remain integers. Consumers must
verify the manifest and select the matching record definition. Output schema
version is 1.0.0; incompatible changes require a version bump. Producer, model
and source versions remain separate.

## Profile semantics and limitations

[batting-profile.schema.json](../contracts/batting-profile.schema.json) defines the
preliminary profile, version 1.0.0. Source identity/lock hash, canonical request,
included seasons/rows, exclusions, historical totals, included totals, sample
opportunities and quality flags are retained. `profileId` is `sha256:` plus the
SHA-256 of the sorted, compact UTF-8 JSON object before adding `profileId`.
Integer-valued floats serialize as JSON integers; other JSON numbers use Python's
deterministic finite float serialization. This is not
yet a cross-language canonicalization or simulation replay contract.

| Method               | Calculation                                                                                     |
| -------------------- | ----------------------------------------------------------------------------------------------- |
| `aggregate`          | Sum eligible season event counts, then divide by summed PA; opportunity-weighted                |
| `season_rate_mean`   | Arithmetic mean of each eligible season's unrounded event rate; each season gets equal weight   |
| `season_rate_median` | Component-wise median of eligible unrounded season event rates, then divide by the vector's sum |

Career, team, franchise, specific-season and inclusive year-range scopes all use
the same explicit methods. The plan's `career_mean` / `team_mean` terminology maps
to **aggregate**, not to the newly requested arithmetic season-rate mean.
`pooledDisplayStats` always derives AVG/OBP/SLG/OPS from included pooled counts;
it is not an average or median of rounded annual display statistics.

Required counts: AB, H, 2B, 3B, HR, BB, HBP, SO, SH, SF. An incomplete or inconsistent
stint excludes the entire affected season after scope filtering; valid seasons
may still form a partial career profile, with exclusions and a warning. Unknown
optional RBI/SB/CS/IBB/GIDP is retained and does not itself prevent basic rates.
No missing count is filled, and no incomplete stint is quietly dropped while
pretending its remaining season is complete.

The descriptive denominator is **AB + BB + HBP + SH + SF**, not a claim that every
official PA is represented. IBB is already in BB. Singles are H − 2B − 3B − HR.
The ten categories are 1B/2B/3B/HR/BB/HBP/SO/**otherAtBat**/SH/SF. The residual
`otherAtBat = AB − H − SO` includes reaches on error and fielder choices and must
not be treated as a guaranteed out. SH/SF require contextual rules before a
simulator can use them. Rare interference/awards are not separately available.

All successful vectors are finite, nonnegative and sum to one within floating
precision. `rawOutcomeRates` and `normalizationFactor` expose normalization;
median vectors can require a substantive adjustment. A zero-mass median returns
`insufficient_data`, with a flag, rather than inventing a distribution. Fewer
than the requested qualifying seasons also returns `insufficient_data` with
null probabilities. One-PA profiles are allowed when requested and prominently
carry sample counts and `no-small-sample-smoothing`; no shrinkage model is implied.

## Measured examples

These results come from the pinned source, using AL/NL only and no era adjustments.
Generated complete JSON examples are under ignored `data/processed/examples/`.

| Request                                               | Included PA components |         HR probability |
| ----------------------------------------------------- | ---------------------: | ---------------------: |
| Aaron Judge, 2025 season                              |                    679 | 53 / 679 = 0.078055965 |
| Juan Soto, 2022 season, both team stints              |                    663 | 27 / 663 = 0.040723982 |
| Aaron Judge, career aggregate through source end 2025 |                  4,995 |            0.073673674 |
| Aaron Judge, equal-season rate mean                   |    4,995 supporting PA |            0.070575473 |
| Aaron Judge, normalized component median              |    4,995 supporting PA |            0.077721589 |

For Soto 2022, WAS contributes AB 342/H 84/HR 21 and SDN contributes AB 182/H 43/HR 6.
The full-season result is AB 524/H 127/HR 27 with two source rows and one season.
Its PA figure is calculated from Lahman's supplied components; no external PA
total is substituted. Babe Ruth 1927 retains 60 historical HR but returns
`insufficient_data` because required historical components such as SF are unknown.

## Validation and next steps

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest
# Optional offline integration suite; never downloads during tests
uv run pytest tests --lahman-source=../raw/lahman-2025
```

Ordinary CI runs synthetic/source-contract tests and explicitly skips five
release integration tests. Integration verifies complete-file checksums, source
keys and joins, Judge 2025, Soto's two 2022 stints, known anomalies and incomplete
old records. Source tests also reject tampering, partial downloads, wrong headers,
missing fields, invalid counts and degenerate probability vectors.

Before the Rust PA engine consumes these profiles, review the event taxonomy,
missingness exclusions and minimum sample policy. Define a separate, approved
simulation-input contract, including opponent context, seeded RNG version and
contextual handling of sacrifices/other AB outcomes. Start Rust's state machine
with synthetic fixtures and conservation tests; these descriptive profiles are
not a calibrated opponent/era model. Retrosheet calibration and browser integration
remain later work.
