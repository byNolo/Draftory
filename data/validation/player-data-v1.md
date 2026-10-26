# M6A player data: local publication and retrieval

Measured 2026-10-26 on Windows ARM64, Node 22.21.0, Wrangler 4.152.0 and Python
3.12.14. SQLite tooling reports 3.53.1. This is a local implementation/measurement
report; no Cloudflare database or deployment was provisioned. See
[reproduction and API contracts](../../docs/PLAYER_DATA_API.md).

## Source and publication

Official SABR Lahman 2025 CSV folder snapshot, including the pinned February 2026
BOM revisions; lock SHA-256:
`8f4cfb56f0726ebe7c900f8d8748232a3c8b326b2fc0d44a387512442e58a22c`.
Original source file hashes are verified before transformation. Attribution and
CC-BY-SA-3.0 notices remain with the source and dataset metadata.

Publication selects **2024 AL/NL season aggregates**, with the existing policy:
minimum 50 PA, prior 200 PA, recorded-season window 2000–2025 and explicit contact
approximation. It applies exactly M4's contact relabeling, not a new model.
The exported Judge weights match the existing M4 season fixture. Profiles require
input 1.2.0 and its separately resolved contextual transition model. No context
refitting, historical recalibration, pricing or draft eligibility decision occurs.

Dataset ID:
`dataset:1fba260824fe05abec3c5950cd184caa0d314b41f1253bc782f97b678bb28add`.

| Entity                                                         | Imported count |
| -------------------------------------------------------------- | -------------: |
| Source / publication / dataset                                 |         1 each |
| Players / player-seasons / prepared profiles / dataset members |       526 each |
| Batting stints                                                 |            592 |
| Team-seasons / franchises                                      |        30 each |
| Team-position observations (including zero/null)               |          6,512 |
| Positive complete player-position pool entries                 |          1,827 |
| Total application rows                                         |         11,098 |

928 candidate player-seasons are excluded by incomplete/insufficient data or the
50-PA preparation minimum, including zero-PA pitchers. Exclusions and the full
league-context audit remain in the generated manifest. This is a preparation
subset, not a claim that 928 historical identities are invalid. No raw dataset or
generated import/database is committed.

Position pool counts: C 79, 1B 146, 2B 146, 3B 144, SS 111, LF 194, CF 138,
RF 180, DH 382, OF 263 and P 44. These overlap across players. Positive recorded
appearances are metadata, not gameplay qualification; no DH fallback is applied.

Luis Arraez (`lahman:arraelu01`) has two 2024 batting stints, MIA and SDN, with
41 + 159 = 200 hits. The database retains both stints and exactly one season
profile/member. Synthetic cross-league trade tests additionally verify that
appearance rows cannot multiply batting totals and unknown position counts do
not become zero or a fabricated filter match.

## Storage and repeatability

| Measurement                                                  |     Bytes |
| ------------------------------------------------------------ | --------: |
| SQL import artifact                                          | 6,839,740 |
| Sum of prepared JSON payloads                                |   508,843 |
| Fresh offline SQLite schema + publication page estimate      | 4,722,688 |
| Actual imported local D1 backing database logical page bytes | 4,739,072 |

Local D1 logical storage is approximately **4.52 MiB**, including indexes and
Wrangler migration metadata. It is not cloud billable storage, WAL/process
memory, or the size of the verbose SQL export. D1 rejected `PRAGMA page_count`
through its SQL interface (`SQLITE_AUTH`); measurement instead used a read-only
SQLite connection to the actual local backing file and `page_count * page_size`.
Foreign-key validation returned no violations.

SQL SHA-256:
`4dab2562d2b4344cd7499bb6ea54f899b4ba3fe95f1f859c3772d6d7f695828d`.
The full artifact imported **twice** through local Wrangler without duplication.
Native SQLite tests also verify the second import changes **zero** rows and a
changed conflict row fails instead of silently overwriting the existing version.
Completion-marker checks reject missing/inconsistent membership or position pools.

A real API-served Judge profile was also substituted into the existing native
season fixture by updating its profile reference. Rust accepted the complete input
and retained the golden **105–57, R759/RA580** result. No fixture or engine source
was edited for that smoke test.

A comparable additional modern season is an order-of-magnitude **4–5 MB** storage
estimate, not a guaranteed linear projection; shared source identities reduce
some duplication, while source revisions and combinations increase it. A single
subset is well below the current free 500 MB/database limit. Do not populate
all career/team/median/range combinations without measuring each selected set.
[Cloudflare limits](https://developers.cloudflare.com/d1/platform/limits/).

## Query and HTTP measurements

`EXPLAIN QUERY PLAN` on the actual local backing file showed:

- Player pages: indexed range seek on `(dataset_id, ordinal)`, then indexed profile
  and source/player joins.
- Position pages: indexed range seek on `(dataset_id, position, ordinal)`, then
  indexed profile and identity joins.
- Nine-profile batch: covering membership index `(dataset_id, profile_id)`, then
  primary-key profile lookups. No full historical-table scan or random sort.

100 repeated native read-only SQLite executions, using the same query shapes as
the API, yielded these medians [range], sample SD in milliseconds:

| Query                                    | Returned rows | Median [min–max] ms | SD ms |
| ---------------------------------------- | ------------: | ------------------- | ----: |
| First 20 players plus next-page sentinel |            21 | 0.122 [0.120–0.636] | 0.059 |
| First 20 catchers plus sentinel          |            21 | 0.157 [0.154–0.890] | 0.085 |
| Nine prepared profiles                   |             9 | 0.063 [0.061–0.454] | 0.042 |

These native SQLite timings exclude HTTP, Worker serialization and hosted D1.
Local HTTP measurements below use the actual Worker/D1 server on loopback with
five warmups and 30 repetitions. Timing spans Node fetch through complete response
text, without a CDN. Other validation ran on this shared development computer;
these are observations under that load, not isolated production performance or
Worker CPU measurements. Medians, range and sample SD are recorded.

| Request                          | Response bytes | Median [min–max] ms   | SD ms |
| -------------------------------- | -------------: | --------------------- | ----: |
| Dataset catalog for 2024         |          1,399 | 91.52 [74.85–162.07]  | 19.26 |
| 20 player summaries              |          3,264 | 126.47 [70.30–324.48] | 48.66 |
| 20 catcher summaries             |          3,684 | 110.26 [76.38–271.67] | 45.87 |
| Single prepared profile          |          1,091 | 85.75 [30.21–276.40]  | 52.81 |
| One player's historical metadata |          1,543 | 50.33 [36.63–133.43]  | 24.50 |
| Nine prepared profiles           |          8,844 | 50.78 [37.32–99.52]   | 15.19 |

Catalog/ordinary lookup queries omit the bulky context-exclusion audit; full
dataset detail retains it. Profile responses preserve the exact payload. Raw local
observations remain ignored in `target/m6a-*.json`; rerun the committed local-only
`scripts/measure-player-data.mjs` against an imported Worker to reproduce HTTP scope.
The response-size cap added during final review does not change successful bodies.

Row-read considerations: one dataset lookup plus indexed page/member retrieval;
no request-time `COUNT(*)` over players or historical facts. Batch size is capped
at 20, page size at 50, with keyset pagination. Future random selection can seek
frozen dense ordinals using precomputed counts. No offer generation exists.
Returned rows are not a reliable billable row-read count: indexes and joins also
matter. Local Wrangler returned statement durations but no reliable hosted
`rows_read`/`rows_written` counters; hosted quota/CPU validation remains pending.
Indexes also increase import writes. Current free allowances are 5 million reads
and 100,000 writes daily, with 5 GB total account storage; see
[official pricing](https://developers.cloudflare.com/d1/platform/pricing/).
No paid-service assumption or production throughput claim is made.

## Validation and remaining work

| Command / check                                                                      | Result                                                                      |
| ------------------------------------------------------------------------------------ | --------------------------------------------------------------------------- |
| `uv run pytest -q --lahman-source=../raw/lahman-2025`                                | 139 passed; one unrelated optional Retrosheet integration skipped           |
| `uv run pytest -q` without external source options                                   | 132 passed; eight optional integrations skipped                             |
| Ruff check / format check                                                            | Pass                                                                        |
| `npm run test:api`                                                                   | Eight local Worker/D1 integration groups pass                               |
| Rust fmt, workspace Clippy with warnings denied, workspace tests                     | Pass; 51 tests                                                              |
| Native workspace build, WASM workspace build, release WASM/bindings                  | Pass                                                                        |
| TypeScript, ESLint, Prettier, Vite production build                                  | Pass                                                                        |
| Worker type regeneration / unchanged generated types, dry-run bundle, local D1 check | Pass                                                                        |
| `npm run test:browser -- --max-failures=1`                                           | All 57 desktop/mobile-emulation/deployment cases pass with original timeout |
| Focused Chromium/Edge 29-opponent parity diagnostics                                 | Two cases pass                                                              |

An earlier broad browser run experienced a 60-second Chromium capacity timeout
and was stopped. A fresh-server diagnostic passed the unchanged case in Chromium
(7.2 seconds) and Edge (2.1 seconds), followed by a full standard-timeout suite pass.
No correctness assertion, golden output, simulator rule or browser test source was
changed to obtain those results. The transient slowdown's underlying cause was
not established. Hosted CI itself was not run locally.

The milestone checks migrations, constraints, repeat imports, partial-publication
visibility, missing/invalid data, trade aggregation, position filtering, keyset
pagination, ordered batches, missing resources and incompatible versions. Python
validates shared payloads against the existing Rust profile schema; local HTTP
tests compare responses to that same generated synthetic fixture. CI runs the
API suite without requiring external datasets or cloud resources.

Known limits: only modern single-season aggregate publication; other existing
profile methods remain offline until selected explicitly. Position thresholds,
DH eligibility, draft pools, pricing and full historical rollout remain unresolved.
The profile alone is not a complete season input: compatible context, opponent
profiles, schedule and rules still need assembly. M4 calibration biases and M5B's
physical-device/WebKit performance gates remain unchanged. No React fetch/client
cache or hosted cache/D1 billing validation exists yet.

The next authorized milestone can add typed selective loading and session caching
in React, verify the chosen dataset/model/context versions, and feed the resolved
profiles into the existing WASM worker. Production setup/deployment, accounts and
draft mechanics require their own scope and review. M6A creates no Git commit.
