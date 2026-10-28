# MLB draft developer playtest (M7B)

M7C: the playable game is now at `/`; the diagnostic harness described below
is at `/dev`. See [the game guide](MLB_GAME.md) for current gameplay and result
projection behavior.

The draft rules are versioned experiments, using the unchanged reviewed M7A
measurements. See the [playtest report](../data/validation/draft-engine-v1.md)
and [valuation limitations](../data/validation/valuation-eligibility-v1.md).

## Local use and boundaries

Follow the [M6A local export/import](PLAYER_DATA_API.md#reproducible-export-and-local-import),
then run `npm run dev:api` and `npm run dev:web`. The new **MLB draft · developer
playtest** sits below the preserved simulation harnesses. Start a seeded draft,
select one offer per position, inspect roster/history JSON, then simulate the
completed roster with a separate season seed. Drafting works with static assets;
simulation needs the compatible API publication. Data failures are visible and
retryable. There is no account, persistence or undo. The alpha game supports three free rerolls per draft.

`apps/web/src/mlb/draft/engine.ts` owns MLB game rules independently of React,
network, clocks and Rust. React only presents states and dispatches choices.
`catalog.ts` verifies static metadata; `season.ts` adapts completed rosters to
the existing assembler. Matching caches change speed, not observable results.
The developer draft is ephemeral client state, an explained adjustment to the
planning baseline's future Worker-owned sessions. No session API/storage is needed
for this casual prototype; client results are not competitive verification.

## Rules and state

`mlb-protected-draft-v1` with the current M8C.2 catalog defaults to 65 credits,
three offers, ten observed games
at each specific fielding position, universal DH and the existing 50-PA publication
floor. Positions are C,1B,2B,3B,SS,LF,CF,RF,DH; draft order is
C,SS,CF,1B,2B,3B,LF,RF,DH. Each player has one researched elite price (1–30),
regardless of position. No scarcity premium is used. Selected identities must be
unique. [M8C.2 measurements](../data/validation/pricing-pa-v1.md) justify this
provisional choice; prices do not change prepared ability or historical availability.

The algorithm/rules and RNG identifiers remain unchanged: state still records
schema 1.0.0, explicit config and catalog ID. Catalog **2.0.0** adds a reviewed
`defaultBudget` and broad `valueTier`, with policy `m8c2-elite-1-30-smoothed-v1`.
Legacy catalog 1.0.0, 1–20 prices, 90-credit defaults and replay goldens are retained.
A new-catalog engine rejects old-catalog state; replay must use its original
catalog/config. `DEFAULTS` is the legacy fallback; the current catalog supplies
65 unless an explicit developer config overrides it.

`DraftConfig` exposes budget (0–180), offer count (1–10), any permutation of nine
positions, minimum games, minimum PA >=50, and universal/observed DH. The form
exposes budget and seeds. Configurable eligibility uses the catalog's nullable
specific-position games and PA; its `positions` labels describe defaults.
Unknown is not zero; generic OF never grants LF/CF/RF. Lowering the published PA
floor requires a different publication, not a runtime setting.

`start(seed)` validates initial feasibility and returns `drafting` with offers.
`select(state, offeredId)` deducts price, fills the current position and returns
the next round; the ninth selection returns `complete`, empty offers and full
history. Invalid choices, infeasible initial states and absent legal continuations
throw `DraftError`. Catalog, config and returned states are frozen. Imported
histories use `replay(seed, pickIds)`, which reconstructs valid offers; arbitrary
JSON is not accepted as a saved state. Simulation requires exact replay equality.
Start/replay resets the entered seed/config; repeating picks repeats the roster.
New-random uses browser crypto outside the engine.

## Three free rerolls

The playable game allows **three rerolls total per draft**, shared across all
nine positions. Each replaces the entire visible offer with distinct safe players
not in that immediately previous offer. Picks, position and credits stay unchanged.
Rerolled players may appear again on a later reroll or round; selected players
never reappear. A new draft resets the allowance. If too few alternatives exist to
replace every current card, reroll is disabled without consuming an allowance.

The pure engine exposes `canReroll(state)` and `reroll(state)`. The first reroll
opts into state schema **1.1.0**, rules `mlb-protected-draft-rerolls-v1`, with
`rerollRounds`: up to three ordered zero-based round indexes (duplicates represent
multiple rerolls at the same position). Exported sessions include this history.
`replay(seed, pickIds, rerollRounds)` reconstructs all draws, including rerolls
before an unfinished round. Season assembly verifies this complete replay before
loading simulation profiles. No-reroll drafts retain the exact legacy schema,
versions, RNG sequence and goldens. This is an additive draft feature, with no
simulation model, price, catalog, database or API changes.

## Completion guarantee and offer distribution

Rectangular Hungarian matching computes the cheapest distinct-player assignment
for remaining positions. Missing eligibility edges are forbidden. Flexible
identities mean independent slot minima are insufficient. Only the cheapest `n`
available candidates per slot are needed for `n` slots: at most `n-1` can occupy
other slots, leaving an equally cheap or cheaper exchange. With nine slots and
at most nine exclusions, only the first 18/slot can affect the normalized cache
key. The cache is bounded at 8,192 states.

A candidate is safe iff its price plus the cheapest assignment for the suffix
fits the remaining budget, excluding previously selected identities and itself.
**Only safe players are offered.** Sample uniformly without replacement from the
entire safe pool; return three distinct choices when available, fewer otherwise.
Every displayed button is selectable. No invented choice, unavailable card,
rejection/retry loop or fallback insertion is needed: an initially feasible
matching supplies at least one safe candidate, and every permitted pick preserves
that invariant. The zero-slot suffix costs zero. This inductively guarantees
completion for every permitted sequence, not only a greedy agent. Unchosen offers
may recur; selected identities cannot.

Randomness is conditional on eligibility, affordability and future completion.
It is not uniform over the original catalog or completed rosters. Tight budgets
can force single choices. Completion is not evidence of balance or fun.

## RNG, replay and seeds

`mulberry32-rejection-v1` accepts canonical unsigned 32-bit decimal draft seeds,
including zero. Each word adds `0x6d2b79f5` modulo 2^32, then uses the explicit
`Math.imul`/xor/unsigned-shift mixer in `drawIndex`. For bound `b`, reject words

> = `2^32 - (2^32 mod b)` and take `word mod b`. Partial Fisher–Yates samples the
> safe pool sorted by ASCII player ID. Matching ties also use ASCII IDs, never
> locale-dependent collation. Golden word/rejection/offer tests freeze the stream.
> This is not a secure lottery or the baseball engine's RNG.

Replay requires catalog ID, rules/RNG versions, complete config, seed and ordered
picks. Those plus prior offers/prices and remaining budget appear in state JSON
schema 1.0.0. Season seeds remain independent canonical u64 decimal strings.
Changing the season seed does not change draft offers.

## Catalog publication and network

The explicitly requested static `data/publications/mlb-draft-2024-v2.json` is a
small exception to the general restriction on committing generated datasets.
It contains 526 identities/names/profile IDs, fixed prices, default eligibility,
nullable observed games and historical PA, with source/dataset/policy IDs and
attribution. It contains no simulation probability profiles. The language-neutral
[catalog schema](../contracts/mlb-draft-catalog-v2.schema.json), digest and counts
are tested. Producer bytes stay compact; Prettier ignores this publication.
Vite emits a lazy-loaded hashed JSON asset covered by immutable-asset headers.
The browser checks its pinned content ID and versions; a new publication requires
a reviewed pin/build. No D1 schema changes or new API endpoints are introduced.

```sh
uv run --project data/pipeline python -m draftory_data.draft_catalog --publication-dir data/processed/d1-2024 --research data/processed/m7a/research.json --pricing-policy m8c2-elite-1-30-smoothed-v1 --output data/publications/mlb-draft-2024-v2.json
```

The producer verifies the publication and a pinned portable digest of M7A model
versions, source/fixture IDs, positions, PA, seeds and eight integer marginal-run
observations/player. Host executable hashes and floating error bars are excluded
from that portable digest. Current prices use `round_half_up(1 + 29*z²)` on means
of the reviewed observations, with the same pool min/max and exact rational
arithmetic. The original linear producer/catalog remains available; catalog files
cannot be replaced with different bytes. There are no manual overrides, extra PA
discounts or new valuation models. Changed measurements require review. Lahman attribution
and CC BY-SA 3.0 notice accompany the artifact; see [data notices](DATA_ATTRIBUTION.md).

Drafting requests only static app/catalog assets. Simulation loads a compatible
dataset envelope, the existing pilot artifact, and one batch of **nine selected
profile IDs**. It does not load all-player metadata or all full profiles. Session
caches reuse unchanged data. Verification requires HTTPS or localhost Web Crypto;
this is not a guaranteed offline/PWA experience.

The fictional user lineup is labeled `userLineupKind: synthetic` under the
existing Rust contract, while selected identities remain unique. A selected
hitter may also occur in the immutable CHA opponent template; the UI discloses
this. No source IDs, opponent profiles, rules or calibration are changed. The
original historical-pilot path retains its overlap guard. Default batting order
is C,1B,2B,3B,SS,LF,CF,RF,DH, independent of draft order. M8C.1 lets the playable
game customize that sequence separately from draft state; the developer harness
continues to use the default. See [custom batting order](MLB_GAME.md#custom-batting-order-m8c1).

## Validation

```sh
npm run test:data-client
npm run build
npm run test:integration
npm run test:browser
uv run --project data/pipeline pytest data/pipeline/tests
```

The existing unit runner includes 1,200 seeded draft playtests, exhaustive small
choice trees and selected-profile/native integration using verified M4 profiles
with a clearly synthetic test catalog. Browser integration adds UI, mobile-layout,
replay and failure/retry tests. CI has only the nine-player M4 test publication;
the real 526-player draft-to-D1 tests explicitly skip there. Exercise them locally:

```powershell
$env:M6B_IMPORT_SQL = 'data/processed/d1-2024/import.sql'
npm run test:integration
Remove-Item Env:M6B_IMPORT_SQL
```

Real-source import gets up to five minutes startup time; fixture CI retains its
two-minute cap. No dataset download is part of CI. Metrics/screenshots stay in
ignored `target/m7b/`. Synchronous draft computation is measured separately from
Playwright click-to-render latency. Desktop mobile layouts do not establish
physical Android/iOS performance. Season computation remains in its Web Worker.
