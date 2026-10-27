# M7C · first playable MLB game

Measured locally on Windows, 2026-10-27. See [gameplay/development instructions](../../docs/MLB_GAME.md)
and [machine-readable balance measurements](mlb-game-v1.json). No production
deployment, cloud provisioning, commit or next-milestone work was performed.

## Implemented experience

The default page now offers introduction → protected nine-player draft → completed
lineup → 162-game results → repeat season/new draft. Cards show real historical
batting and fictional prices; the roster, remaining budget and draft progress are
visible. Results include the record, win percentage, runs, differential, every
player's batting totals, team totals and tied leaders. Loading, errors, retries,
cancellation, seed replay and local session export are supported.

The diagnostic harness moved to `/dev/`, with a real static HTML entry and lazy
fixture/CSS chunk. Tests caught and fixed two issues: a Vite fallback had hidden
the missing static route, and the diagnostic initialization row moved lower
controls by 41.6px in Firefox. The row now reserves its space; a gated-WASM test
demonstrated the movement before the fix and verifies stable control coordinates.

The draft algorithm, prices, catalog, historical publication, Rust baseball core,
RNG and existing full-result goldens are unchanged. The sole Rust addition is a
versioned compact batting projection copied from already computed season boxes.

## Reproducible example

Draft seed `20261027`, choosing the first offer at each round:

| Position | Player         | Credits |
| -------- | -------------- | ------: |
| C        | Will Smith     |      10 |
| SS       | Javier Baez    |       4 |
| CF       | Manuel Margot  |       7 |
| 1B       | Anthony Rizzo  |       6 |
| 2B       | Vaughn Grissom |       5 |
| 3B       | Josh Smith     |      10 |
| LF       | Miguel Andujar |       7 |
| RF       | Jonny DeLuca   |       6 |
| DH       | Brett Harris   |       7 |

Spent **62**, remaining **28**. Season seed `20261025`, engine `0.4.0`:
**81–81**, **50.0%** wins, **593** runs scored, **550** allowed, **+43** differential.
Team totals: **6,141 PA, 1,293 H, 155 HR, 585 RBI, 593 R**, AVG **.231**,
OBP **.301**, SLG **.365**. These are simulated counters/ratios, not predictions
or historical 2024 totals. All nine lines match the native result exactly.

Historical card example: Will Smith's actual 2024 full-season line is **.248 /
.327 / .433**, **20 HR, 544 PA**. The cards aggregate source stints once and use
the historical SF denominator. Simulation does not model sacrifices; its OBP
denominator is explicitly different. Zero denominators and unknown historical
counts display `—`; individual games played are not fabricated.

## Browser, mobile and accessibility validation

| Browser/tooling              | Game flow | Native/WASM parity and static delivery |
| ---------------------------- | --------- | -------------------------------------- |
| Chromium                     | Passed    | Passed                                 |
| Firefox                      | Passed    | Passed                                 |
| WebKit                       | Passed    | Passed                                 |
| Installed Microsoft Edge     | Passed    | Passed                                 |
| Pixel 7 / Chromium emulation | Passed    | Passed                                 |
| iPhone 13 / WebKit emulation | Passed    | Passed                                 |

The game tests also exercise a 390×844 viewport, keyboard Enter selection,
visible focus, heading focus after picks, 44px button targets, labeled errors,
API/player/profile failures, WASM failure, cancellation and fresh-worker retry.
Desktop/mobile screenshots were inspected. Cards stack without document-level
horizontal overflow. The batting table deliberately scrolls inside a labeled,
focusable region to retain all columns on phones.

No physical phone, actual Safari/iOS installation or assistive-technology user
session was tested. Emulation establishes functional layout/input behavior on
these desktop engines, not physical mobile performance or a complete accessibility audit.

## Transport and deployment

The fixed example has a **64,668-byte** UTF-8 simulation input. Its existing full
summary-detail season result is **916,934 bytes** when minified; the new Rust
batting JSON is **3,315 bytes**, a **99.64% reduction**. The Worker sends only
the structured summary, batting object and timing envelope, without another JSON
string or any input/event echo. The full diagnostic/replay path remains available.
Summary and event modes give exactly equal batting counters for the same seed.

On the real D1 example path, historical cards fetch **26 distinct player details**
(**41,628 decoded response bytes**) across nine rounds. Simulation fetches only
**nine profiles**, **8,844 response bytes**, plus the compact dataset descriptor.
All API responses total **51,938 bytes**; the separately cached shared pilot is
**55,591 bytes**. Repeating a season adds no profile/data requests. These local
decoded sizes are not compressed WAN transfer measurements.

Production assets, decimal KB (raw / gzip):

| Asset                                                         |     KB | Gzip KB |
| ------------------------------------------------------------- | -----: | ------: |
| Main frontend JavaScript, including React                     | 258.29 |   81.67 |
| Lazy diagnostic JavaScript, absent from initial game requests | 129.96 |   12.45 |
| Worker JavaScript                                             |   5.85 |    2.25 |
| WASM                                                          | 401.65 |  134.53 |
| Main CSS                                                      |   8.53 |    2.54 |
| Existing draft catalog                                        | 135.55 |   37.52 |
| Existing shared pilot                                         |  55.59 |    6.74 |

Hashed assets retain immutable caching; both HTML routes revalidate. Local
Cloudflare Static Assets tests verify MIME, CSP, strict missing-asset 404s,
new deployment recovery and an already running worker surviving asset replacement.
No runtime development paths, cross-origin isolation or SharedArrayBuffer were added.
The game still needs same-origin API routing and its pinned publication at hosting
time. This is local deployment validation, not a hosted Cloudflare acceptance test.

Local execution observations, milliseconds (three seasons per browser):

| Engine / emulation | Worker WASM initialization | First WASM call | Two repeated WASM calls |
| ------------------ | -------------------------: | --------------: | ----------------------- |
| chromium           |                       18.5 |           131.0 | 47.1 / 47.9             |
| firefox            |                       20.0 |           304.0 | 207.0 / 210.0           |
| webkit             |                       43.0 |           155.0 | 62.0 / 53.0             |
| edge               |                        6.9 |            30.0 | 21.5 / 18.6             |
| mobile-chromium    |                        9.9 |           144.9 | 48.7 / 44.1             |
| mobile-webkit      |                       23.0 |           156.0 | 64.0 / 51.0             |

These are first-worker versus warm execution observations on the same Windows
machine, with browser/OS caches already exercised by earlier tests. They are not
first-visit network benchmarks. The repeated pair includes one exact seed replay
and one fresh season seed; the small sample is diagnostic, not a performance SLA.
All three calls in each browser reported **1,703,936 bytes** of allocated WASM
linear memory afterward. This measures capacity at those points, not transient
peak memory, JavaScript heap or whole-process consumption.

## Balance diagnostics and simulator limits

Sixty deterministic drafts use seeds 0–19 for three strategies. “Expensive” means
the most expensive **offered** player; it does not assume access to any catalog player.
Each group contains 180 picks. Price ties can count as both cheapest and expensive.

| Strategy             | Completed | Credits left min / median / max | Mean pick price | Displayed safe offers           |
| -------------------- | --------: | ------------------------------- | --------------: | ------------------------------- |
| First offer          |     20/20 | 4 / 15 / 37                     |            8.08 | 3 on all 180 rounds             |
| Cheapest offer       |     20/20 | 27 / 33.5 / 45                  |            6.19 | 3 on all 180 rounds             |
| Most expensive offer |     20/20 | 0 / 3.5 / 11                    |            9.63 | 3 on 179 rounds; 1 on one round |

The first-offer strategy chose a cheapest offer 73 times and a most-expensive
offer 82 times. The cheapest strategy did so 180/8 times; the expensive strategy
10/180. Full price histograms are in the companion JSON. All drafts replay exactly.
Offer counts measure the displayed safe choices, not the full feasible candidate pool.

Twelve season seeds (0–11) for the **same fixed example lineup** yielded 72–97 wins,
median 82.5, population SD 6.89. This measures seed variation, not relative roster
strength or the effect of price. The deterministic example also repeats exactly.

The budget is loose for conservative choices; expensive picking can end in a
forced last choice. Large unused budgets, position-dependent variety and whether
the decision-making feels rewarding need human playtests. These diagnostics do
not establish enjoyment or justify new prices. No price/model changes were made.

Known accuracy limits remain: fixed batting orders and opponent template, neutral
pitching/defense, no substitutions or sacrifices, contact approximations, excess
hits/double plays and compressed scoring variance. The opponent may reuse a
historical identity from the fictional user lineup. See the existing M4/M7A
calibration and valuation reports before interpreting roster strength.

## Checks

| Command                                                                  | Result                                                               |
| ------------------------------------------------------------------------ | -------------------------------------------------------------------- |
| `npm run build:wasm`                                                     | Release WASM and pinned wasm-bindgen bindings built                  |
| `cargo build --locked --workspace --target wasm32-unknown-unknown`       | Passed                                                               |
| `cargo build --release --example season`                                 | Passed                                                               |
| `cargo fmt --all --check`                                                | Passed                                                               |
| `cargo clippy --workspace --all-targets -- -D warnings`                  | Passed                                                               |
| `cargo test --workspace`                                                 | 52 passed                                                            |
| `npm run build`, `npm run typecheck`                                     | Passed                                                               |
| `npm run lint`, `npm run format:check`, `git diff --check`               | Passed                                                               |
| `npm run types:api` plus generated-type diff                             | Passed, no type drift                                                |
| `npm run test:data-client`                                               | 26 passed, including 1,200 existing seeded draft playtests           |
| `npm run test:browser`                                                   | 62 passed                                                            |
| `npm run test:edge`                                                      | 13 passed                                                            |
| Ordinary `npm run test:integration`                                      | 25 passed, 3 real-publication-only tests skipped                     |
| Ordinary `npm run test:integration:edge`                                 | 7 passed, 1 real-publication-only test skipped                       |
| Full-publication integration, both commands                              | 28 passed across desktop/mobile projects; 8 passed in Edge; no skips |
| `npm run test:api`                                                       | 8 passed                                                             |
| `npm run check:api` and local `d1:check`                                 | Dry run and local query passed                                       |
| `uv run ruff check .`, `uv run ruff format --check .` in `data/pipeline` | Passed                                                               |
| `uv run pytest` in `data/pipeline`                                       | 145 passed, 8 optional raw-source/native-calibration tests skipped   |

Ordinary CI uses verified historical response excerpts for the new game and the
existing M4 fixture publication for old API integration tests. The full-publication
run sets `M6B_IMPORT_SQL=data/processed/d1-2024/import.sql`, exercises the real
526-player local D1 publication and does not intercept normal game data responses.
Intentional failure injection remains enabled in recovery tests. Source/fixture
SHA checks and prepared-profile content checks remain active.

## Next steps toward a private alpha

1. Run human playtests on desktop and real phones, including keyboard and a screen
   reader. Examine mobile scrolling, historical-stat clarity, offer variety,
   unused credits and whether reruns feel meaningful.
2. Compare more independently drafted lineups and seeds offline before drawing
   conclusions about price/roster strength. Address existing calibration biases
   as separately scoped statistical work, not an unreviewed UI adjustment.
3. Separately approve a private hosting/access plan: same-origin Worker API,
   pinned D1 publication, trusted HTTPS, immutable asset retention/revalidation and
   a hosted smoke test. No authentication or deployment was implemented here.
