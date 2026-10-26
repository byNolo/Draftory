# MLB player data foundation (M6A)

Python publishes a selected, immutable player dataset; the Worker performs bounded
read-only retrieval from D1. Rust and React are unchanged. This follows the existing
[architecture](ARCHITECTURE.md), [Lahman workflow](LAHMAN_DATA_FOUNDATION.md) and
[simulation contracts](SIMULATION_FOUNDATION.md). It introduces no draft rules,
prices, authentication, cloud resources, new statistical model or recalibration.
[Measured local results](../data/validation/player-data-v1.md).

## Storage decisions

The [first migration](../infra/d1/migrations/0001_mlb_player_data.sql) uses SQLite
STRICT tables, composite foreign keys, nullable facts and explicit indexes:

| Table                                | Grain / purpose                                                                                      |
| ------------------------------------ | ---------------------------------------------------------------------------------------------------- |
| `mlb_sources`                        | Source release/lock identity and attribution, stored once                                            |
| `mlb_players`                        | Source-scoped identity revision, original Lahman ID, name, bats/throws, birth year and external IDs  |
| `mlb_franchises`, `mlb_team_seasons` | Source franchise and year/team/league relationships                                                  |
| `mlb_player_seasons`                 | One source/player/year, independent of team trades                                                   |
| `mlb_batting_stints`                 | Original batting stint and nullable count JSON; exact source row                                     |
| `mlb_position_appearances`           | Year/team/league/position appearances and source row; null differs from zero                         |
| `mlb_profiles`                       | Immutable prepared payload, historical profile ID, aggregation definition and compatibility versions |
| `mlb_datasets`                       | Content-addressed publication configuration, source, year, policy and league-context audit           |
| `mlb_dataset_profiles`               | One profile per player in this season dataset, dense zero-based ordinal                              |
| `mlb_dataset_positions`              | Dense ordinal per recorded-position pool, profile ID and summed games                                |
| `mlb_publications`                   | Completion marker, player count and position counts; inserted last                                   |

An identity is `lahman:<playerID>`, never a name. Source-scoped primary keys allow
a later source release to revise facts without changing old snapshots. Batting
stints are stored once; full-season counts derive by summing those stints, never
by joining appearances. Team membership comes from stints and does not create a
second player or full-season profile. Fielding and redundant season/career count
copies are not imported; modern `Appearances.csv` supplies the position metadata.
The full normalized historical source remains offline.

Prepared integer weights are **versioned JSON**, not eight/nine duplicated SQL
columns: the API retrieves the complete Rust-ready object and never filters or
calculates weights in SQL. Indexed relational columns carry IDs, source, model,
input schema, aggregation and membership. The payload reuses
`simulation-input.schema.json#/$defs/profile`, including provenance and flags.
Only one copy exists per prepared content ID; datasets reference it. JSON count
facts retain the existing source field vocabulary without inventing SQL columns
for every historical statistic.

The first exporter publishes **one season / aggregate method / AL+NL** at a time,
within 2000–2025 and the existing preparation window. The definition and aggregation
columns can represent the existing pipeline's `aggregate`, `season_rate_mean`,
and `season_rate_median` methods; career/team/range publication is deferred rather
than precomputing all combinations. Other sports should add sport-specific facts
and profiles when needed, not stretch MLB batting columns into generic ratings.

## Reproducible export and local import

From `data/pipeline`, with the verified pinned official 2025 release available:

```sh
uv sync --locked
uv run draftory-data verify --source-dir ../raw/lahman-2025
uv run draftory-data export-d1 --source-dir ../raw/lahman-2025 --year 2024 --contact-policy ordinary-out-proxy-v1 --output-dir ../processed/d1-2024 --migrations-dir ../../infra/d1/migrations
```

`--min-pa` defaults to the existing preparation minimum of 50; `--prior-pa`
defaults to 200. These are existing research-preparation settings, **not agreed
draft eligibility or pricing policy**. Contact approximation must be explicitly
acknowledged. Preparation reuses M3 smoothing/rounding and exactly M4's
`lahman-contact-adapter-v1` contact relabeling. It keeps zero `battedBallOut` and
nonzero `otherContact` where appropriate, requires input **1.2.0** with a separately
resolved contextual model, and does not refit transitions or package a schedule.
The existing calibration limitations still apply.

`dataset.context` is the Lahman league-baseline/smoothing audit referenced by
profile provenance. It is **not** the Retrosheet transition model expected in
Rust's `config.contextualModel`; a future input assembler must resolve both
compatible pieces explicitly.

The exporter verifies the source before transforming it. It excludes and reports
incomplete/insufficient player-seasons as whole units; it does not discard one
traded stint and call the remainder a season. Invalid vectors/configuration fail.
Before writing, it applies the migration and SQL twice to SQLite, checking foreign
keys and zero changes on the repeat. Output consists of:

- `import.sql`: deterministic UTF-8/LF SQL, parent rows first, one bounded statement
  per row (under 90 KB). No raw source download, database credentials or timestamps.
- `manifest.json` v1.0.0: dataset ID, policy/context/source versions, row counts,
  exclusions, prepared/SQL byte sizes, SQL SHA-256 and measured SQLite page estimate.
  Page estimates can vary by SQLite version; they do not participate in identity.

The CLI prints a compact count/size summary and manifest path; the complete
exclusion/context audit stays in the manifest rather than flooding the terminal.

SQL literals escape apostrophes and reject NUL; identifiers are fixed in code.
Identical conflict rows are no-ops. Different bytes at an existing key fail a
NOT NULL constraint instead of overwriting or silently ignoring a version collision.
An interrupted import remains hidden until its final publication marker; rerun the
same artifact to resume. The completion trigger verifies pool counts and ordinals.
Keep generated SQL/manifests/databases ignored. A small clearly synthetic SQL and
JSON pair is committed solely for cross-language tests.

From the repository root:

```sh
npm run d1:migrate --workspace @draftory/api
npx wrangler d1 execute DB --local --config services/api/wrangler.jsonc --file data/processed/d1-2024/import.sql
# Repeating that command must not duplicate or overwrite records.
npm run dev:api
```

The configured all-zero database ID remains a local sentinel. These commands use
`services/api/.wrangler/state`; API tests instead create isolated generated state
under `target/api-tests`. No remote import, provisioning or production deployment
is performed. Source notices and CC-BY-SA-3.0 attribution accompany dataset details.
Review redistribution/licensing requirements before an eventual public release.

## HTTP API v1.0.0

Default origin: `http://127.0.0.1:8787`. All successes include `schemaVersion`
except the existing health response; failures are
`{ "error": { "code": "...", "message": "...", "details": ...? } }`.
Core profile/batch/list envelopes are specified in
[player-data-api.schema.json](../contracts/player-data-api.schema.json).

| Route                               | Response / parameters                                                                                                                                        |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `GET /api/health`                   | Existing service health; no database query                                                                                                                   |
| `GET /api/seasons`                  | `{schemaVersion,seasons:number[],nextAfter}`; ascending years, `after` year, `limit`                                                                         |
| `GET /api/datasets`                 | `{schemaVersion,datasets:object[],nextAfter}`; optional `season`, `after` dataset ID, `limit`; omits bulky context audit                                     |
| `GET /api/datasets/:id`             | `{schemaVersion,dataset}`; full source, policy, context, counts, compatibility and attribution                                                               |
| `GET /api/players?dataset=:id`      | `{schemaVersion,datasetId,position,players,nextAfter}`; optional recorded `position`, `after` ordinal, `limit`                                               |
| `GET /api/players/:id?dataset=:id`  | `{schemaVersion,datasetId,player}`; identity, source metadata, year, profile ID, batting stints with team/franchise names and nullable position observations |
| `GET /api/profiles/:id?dataset=:id` | `{schemaVersion,datasetId,profile}`; exact prepared Rust profile                                                                                             |
| `POST /api/profiles/batch`          | Body `{datasetId,profileIds}`; response `{schemaVersion,datasetId,profiles}` in request order                                                                |

Lists default to 20, maximum 50. `nextAfter: null` ends a page sequence; pass a
returned cursor back with the same dataset and position filter. Position ordinals
belong to that position pool, not the unfiltered pool. There are no offsets, name
wildcards or arbitrary searches. Unknown/repeated parameters fail. Profile and
dataset IDs require their prefix and 64 lowercase hex digits; player IDs are
bounded `lahman:` identifiers. Malformed inputs return 400, missing resources 404,
wrong methods 405, incompatible profile/input versions 409, oversized request 413,
wrong content type 415 and unsupported response size 422; internal failures are 500.

Batches contain 1–20 distinct IDs and at most 16 KiB of JSON. Any missing member
rejects the entire batch with its missing-ID list. A profile must belong to the
requested **published** dataset. Current compatibility is explicit:
`lahman-contact-adapter-v1` / input 1.2.0 / API 1.0.0. No conversion of future model
versions happens in the Worker. Responses are capped at 1 MiB. All SQL values are
bound parameters; the few SQL branches choose only hard-coded table/column names.

Catalogs use `public, max-age=60`. Successful dataset-scoped GETs use one-year
immutable caching; new versions require new IDs/URLs. POSTs and errors use
`no-store`. Cache headers are preparation for hosting, not proof of D1 reads being
avoided today: no Cache API, CDN rule, cross-origin CORS or authentication is added.
The future client should retain fetched versioned profiles and avoid refetching
them for each simulation. Public listing here is a development data-access API,
not a player-browsing gameplay UI.

## Positions, randomized selection and cost

Position filters mean **complete, positive recorded games**, summed across the
selected AL/NL season's teams. Unknown components remain unknown and are excluded
from positive pools. This does not establish a defensible gameplay minimum;
`OF` is not automatically split into LF/CF/RF, and DH has no universal fallback.
P and OF remain available as historical metadata, not extra lineup slots.

For a future random offer, sample a uniform integer in `[0, poolCount)` and seek
`(dataset_id, position, ordinal)` or `(dataset_id, ordinal)`. Counts and ordinals
are frozen in the publication. Selection exclusions, uniqueness/retries, offer
distribution, RNG and draft state are deliberately not implemented. Do not use
`ORDER BY RANDOM()` or a hash seek that biases uneven key gaps.

Each page fetches at most `limit+1` indexed members and performs indexed profile/
identity joins. A profile batch uses at most 21 bound parameters and two SQL
queries including dataset validation; player detail uses four including its two
batched metadata queries. Catalog size is currently tiny; many future versions
could require materialized season summaries because `DISTINCT` still reads matching
catalog entries. Query plans and local timings are recorded in the measured report.

As checked 2026-10-26, the D1 free plan documents 5 million rows read/day,
100,000 rows written/day and 5 GB account storage; its per-database limit is
500 MB. Index maintenance adds writes; returned rows alone are not billed reads.
See [official pricing](https://developers.cloudflare.com/d1/platform/pricing/),
[limits](https://developers.cloudflare.com/d1/platform/limits/) and
[index guidance](https://developers.cloudflare.com/d1/best-practices/use-indexes/).
Local Wrangler does not provide reliable hosted billing/CPU measurements. Inspect
hosted `meta.rows_read`/`rows_written` when deployment is separately authorized.

## Validation and next step

```sh
npm run test:api
npm run typecheck
npm run lint
npm run format:check
npm run check:api
# With the real subset imported and dev:api running, localhost only:
node scripts/measure-player-data.mjs
```

From `data/pipeline`, run `uv run pytest` for synthetic tests and add
`--lahman-source=../raw/lahman-2025` for verified release integration. Tests cover
real migrations, repeatability, foreign keys, partial publication, invalid vectors,
trades, missing facts, version changes and exact shared payloads. API tests use
real local Worker/D1, not a SQL mock, and need no browser download. CI runs them.

Next, add a small typed React loader and session cache for requested profile IDs;
assemble a fully versioned input with the separately selected compatible context,
then pass resolved JSON to the existing WASM worker. Keep backend fetches outside
Rust simulation. That integration, production hosting and draft mechanics are not
part of M6A.
