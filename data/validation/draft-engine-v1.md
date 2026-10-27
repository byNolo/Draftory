# M7B randomized MLB draft engine v1

Implemented a pure local MLB draft engine, compact static offer publication,
minimal responsive developer UI, and completed-roster adapter to the existing
API/WASM season workflow. No simulation rules, RNG, historical profiles,
calibration, D1 schemas or production resources changed. Existing developer
harnesses remain available. [Rules/reproduction guide](../../docs/MLB_DRAFT.md).
[Measured summary](draft-engine-v1.json).

## Published inputs and experimental rules

Catalog `draft-catalog:95602e268bcd87ff6f5640525e3cfc1936eff28ae57a3d715a2f990ba689f9f8`;
526 published 2024 AL/NL players from unchanged dataset
`dataset:1fba260824fe05abec3c5950cd184caa0d314b41f1253bc782f97b678bb28add`.
Portable M7A observation digest:
`d450086adca34294ca61c6de5f3e06dca25b875545c5c8ea55c36993540431a6`.
Regeneration from the verified publication/research produced byte-identical
catalogs, SHA-256
`255c93ef554afb3add167c9b7b50d6c562701809f3ae1f7a54a774fbb7777c26`.

Defaults: 90 credits, three offers, ten observed games at each specific position,
all published hitters eligible DH, 50-PA publication floor, one fixed M7A linear
1–20 price per player and scarce-first order C,SS,CF,1B,2B,3B,LF,RF,DH. These are
`mlb-protected-draft-v1` playtest settings, not permanent balance decisions.
Specific pools remain C77, 1B93, 2B100, 3B104, SS77, LF121, CF92, RF124, DH526.
There are no scarcity price premiums, manually priced stars or new valuations.

The producer verifies source/publication membership and the reviewed integer
M7A observations. Versioned metadata includes sample PA/nullable games for
configurable eligibility, but no full outcome profiles. The static catalog is
**135,552 bytes**, approximately **37.52 KB gzip** in the Vite build. Hashed asset
delivery reuses existing immutable cache headers. Verification rejects a changed
catalog/policy; a new publication needs a new reviewed content pin.

## Guarantee and determinism

Minimum-cost distinct-player matching accounts for remaining slots, identities,
actual eligibility and budget. A selection is safe only if an affordable suffix
assignment remains. Uniform without-replacement sampling uses the complete safe
pool, returning three options whenever possible. Every displayed option is safe;
fewer options honestly reflect a smaller safe pool. Initial infeasibility throws
an explicit error. Induction over remaining slots establishes completion for
**every permitted sequence**, not merely an agent's observed success rate.

This conditions randomness on future feasibility. Offers are not uniform over
all catalog members, and completed rosters are not uniformly distributed. Prior
unchosen offers may recur; selected players never do. No retry loop, fabricated
candidate or separate fallback insertion is needed for a feasible state.

`mulberry32-rejection-v1` has frozen integer/rejection/offer golden tests, ASCII
ordering and canonical u32 draft seeds. Season seeds remain separate u64 strings
and use the unchanged Rust RNG. State JSON preserves catalog/rule/RNG versions,
config, seed, ordered picks, previous offers and prices; `replay` reconstructs a
history before simulation. Frozen states and a matching cache do not alter replay.
Review also verified that JSON object-key reordering preserves valid drafts and
simulation assembly. Regression tests cover reordered states/configuration while
continuing to reject changed budgets and invalid histories.

## Automated playtests

Main experiment: seeds 0–99, budgets 25/60/90/120, first-offered, most-expensive
and cheapest-offered agents: **1,200 completed drafts / 1,200 attempts**. Every
currently offered branch was separately exercised and checked for nonnegative
remaining budget. Additional tests exhaust every permitted path of small scarce/
flexible synthetic pools, compare matching against brute force on 100 rectangular
matrices, and test 60 drafts with changed eligibility, order and offer count.
The correctness guarantee comes from the invariant, with these as validation.

Rates below count observed rounds, not draft success; each main case has 900
rounds. The cheapest feasible distinct nine costs 25 credits.

| Budget | Agent            | Completion | Rounds with >=2 choices | Rounds with 3 choices | Distinct rosters /100 |
| ------ | ---------------- | ---------: | ----------------------: | --------------------: | --------------------: |
| 25     | First offered    |       100% |                  38.22% |                24.56% |                    39 |
| 25     | Most expensive   |       100% |                  33.33% |                22.22% |                    18 |
| 25     | Cheapest         |       100% |                  46.78% |                29.56% |                    41 |
| 60     | First offered    |       100% |                  92.89% |                89.00% |                   100 |
| 60     | Most expensive   |       100% |                  70.78% |                66.56% |                   100 |
| 60     | Cheapest         |       100% |                    100% |                  100% |                   100 |
| 90     | First offered    |       100% |                    100% |                  100% |                   100 |
| 90     | Most expensive   |       100% |                  99.89% |                99.78% |                   100 |
| 90     | Cheapest         |       100% |                    100% |                  100% |                   100 |
| 120    | All three agents |       100% |                    100% |                  100% |              100 each |

A feasible 25-credit game is often forced rather than interesting. At 90, choice
count is rarely constrained in these trials; that is not proof choices are
equally competitive or enjoyable. Picking expensive players at 60 visibly reduces
later flexibility. Do not lower the budget solely because completion is protected.
Keep 90 for further human playtests and compare strategy/value outcomes before
changing the curve or adding tiers. No optimal strategy or balanced difficulty
is claimed from these three simple agents.

## Runtime, network and browser findings

Fresh-engine timing tests run 100 drafts with parsed catalog already in memory,
constructing a new engine each time and choosing the first offer. They separately
record constructor/first-offer, whole nine-pick computation and 900 selections.
No alternate-branch warming, network, React rendering or assertions enter those
intervals. Medians, quartiles and P95 are retained in the measured JSON. The
larger correctness experiment also records explicitly branch-warmed timings;
those are not representative end-user latency. Measurements are local desktop
observations under concurrent validation load, not mobile hardware guarantees.

| Fresh-engine measurement              | Median ms |  P25–P75 ms | P95 ms |
| ------------------------------------- | --------: | ----------: | -----: |
| Construction + first offers (100)     |     15.32 | 12.09–20.51 |  44.75 |
| Entire nine-pick computation (100)    |     47.01 | 39.61–67.87 | 166.74 |
| Individual selection/next round (900) |      3.51 |   2.11–5.31 |  12.36 |

Memo caches start fresh; the JavaScript runtime/JIT is already warmed. These
numbers do not establish first-visit network/startup latency. A long desktop tail
and untested physical phones are reasons to measure devices before launch, not
to claim a mobile performance target has passed.

Chromium, Firefox and WebKit completed the responsive 390x844 layout/replay test;
no horizontal overflow was observed and screenshots were inspected. Browser
click-to-render wall intervals include Playwright action overhead, scrolling,
rendering and scheduling; they must not be compared to pure engine timings.
Physical Android/iOS devices, throttled phone CPUs and WAN delivery were not tested.

The genuine 526-player D1 → API → draft → WASM workflow passed complete native/
WASM equality in all three engines. No API request occurs during drafting.
Simulation needs one compact dataset envelope, one batch containing exactly nine
selected profile IDs, and the existing static pilot artifact. No `/api/players`
metadata calls or full-catalog profile fetch occurs. Repeating the same roster's
season makes no further data requests. The real test uses draft seed 20261027,
first-offered choices and season seed 20261025: **81–81, 593 runs scored** across
all three engines. These are deterministic fixture-context results, not a forecast.

The roster is fictional and uses the existing `synthetic` user-lineup contract;
a hitter can also occur in the preserved CHA opponent template. Selected user
identities are still unique. This is explicitly disclosed rather than dropping
eligible players, relabeling provenance or adding new opponents. Batting order
is C,1B,2B,3B,SS,LF,CF,RF,DH, not the scarce-first drafting order. The historical
M6B pilot keeps its strict original identity/order/overlap checks and golden result.

An initial real-publication test hit the existing two-minute startup cap. Direct
inspection confirmed a successful local import of 11,098 SQL commands, with a
very large per-statement Wrangler stdout response. The integration server now
writes import stdout to ignored `target/m6b-api/import.log` and prints a compact
completion message; stderr remains visible. Only the explicit real-source mode
gets a five-minute startup cap; default fixture CI remains at two minutes. This
changes test infrastructure, not runtime import semantics or correctness checks.
Parallel validation also exposed a native test-helper race: unit and browser
processes wrote the same temporary `input.json`, producing one empty-input parse
failure. Each native call now uses a process/ordinal-specific path. The parity
assertions and established golden outputs were preserved; the regression suite
was rerun after isolating those artifacts.

## Validation and remaining limits

Run commands from the repository root; `uv` used the available local executable.
Catalog schema/digest, identical producer bytes, M7A example prices, source/sample
membership, nulls, multistints, eligibility boundaries, duplicates, budget errors,
extremely tight budgets, replay, restart and full selected-profile simulation are
covered. No required source download or new dependency was added to CI.

| Validation command                                                                                                         | Result                                                                               |
| -------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| `npm run test:data-client`                                                                                                 | 21 passed, including 1,200 seeded playtests and 100 fresh-engine timing drafts       |
| `uv run --project data/pipeline pytest data/pipeline/tests -q`                                                             | 144 passed, 8 optional source skips                                                  |
| Same pytest with `--lahman-source data/raw/lahman-2025 --retrosheet-source data/raw/retrosheet-m4`                         | 152 passed, no skips                                                                 |
| `uv run --project data/pipeline ruff check data/pipeline`; `ruff format --check data/pipeline` through the same uv project | Pass                                                                                 |
| `cargo fmt --all -- --check`; `cargo clippy --workspace --all-targets -- -D warnings`; `cargo test --workspace`            | Pass, 51 Rust tests                                                                  |
| `cargo build --locked --workspace`; same with `--target wasm32-unknown-unknown`; `npm run build:wasm`                      | Pass                                                                                 |
| `npm run typecheck`; `npm run lint`; `npm run build`; `npm run format:check`                                               | Pass                                                                                 |
| `npm run types:api` and generated declaration diff check                                                                   | Pass, no declaration changes                                                         |
| `npm run check:api`; `npm run d1:check --workspace @draftory/api`                                                          | Pass; dry-run and local SELECT only                                                  |
| `npm run test:api`                                                                                                         | 8 passed                                                                             |
| `npm run test:browser`                                                                                                     | 57 passed after test-input isolation                                                 |
| `npm run test:integration` with verified real publication                                                                  | 18 passed; all three browser engines                                                 |
| Default fixture integration and final real-draft rerun                                                                     | Fixture CI: 15 passed / 3 explicit real-source skips; final real-draft run: 9 passed |
| Catalog republish, SHA-256 comparison, schema/digest validation; `git diff --check`                                        | Pass                                                                                 |

CI's synthetic nine-player M4 publication cannot supply arbitrary real drafts:
real-publication browser tests explicitly skip without `M6B_IMPORT_SQL`. Local
real-source runs exercised them. Existing worker/profile tests still use synthetic
fixtures and immutable verified prepared profiles as documented. Optional Edge
and physical-device performance remain separate checks, not claimed here.

## Decisions and next steps for M7C

The architecture adjustment is local ephemeral draft state in an MLB TypeScript
module, with a static catalog, instead of introducing server sessions now. React
still owns presentation; Python prepares data/prices, the API retrieves published
profiles, and Rust owns baseball. The catalog is the requested small publication
exception to the general no-generated-dataset policy. No universal sports-game
framework, permanent pricing table or application write API was added.

Before final UI work, gather human playtests: do players understand safe offers,
budget pressure, arbitrary batting order and the distinction between historical
sample size and simulated availability? Compare resulting offensive strengths,
strategy incentives and forced-choice frequency, not just completion. Retain
known hit/PA/GDP/variance and standardized-pitching limitations in results copy.
Consider clear result attribution/history replay, then assess physical phone
latency before deciding whether draft matching needs a worker. Review fixed
opponent/template overlap and batting-order policy explicitly. Changing prices,
tiers, budget or eligibility needs another version and measured review.

M7C has not started. No deployment was performed.
