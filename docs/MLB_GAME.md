# First playable MLB game · M7C

The default `/` route is the game: introduction → nine protected draft rounds →
completed lineup → 162-game season → batting results. `/dev` retains the M6B
diagnostic harness, including full fixture runs and the M7B draft debugger. Its
fixture and CSS load in a separate dynamic chunk. A second HTML entry at
`dev/index.html` makes `/dev/` work on static hosts without a development fallback. No router or UI dependency was added.

## Run locally

Build WASM with `npm run build:wasm`. Follow the verified 2024 source export and
local D1 import in [the player API guide](PLAYER_DATA_API.md), then run
`npm run dev:api` and `npm run dev:web` in separate terminals. Open the Vite URL.
Rebuild WASM after adapter changes. The game needs the complete published
526-player dataset; the nine-player synthetic API test publication is insufficient.
The `/dev` bundled fixture continues to work without an imported database.

Open “Replay a draft seed” before starting to reproduce offers. Default rules
use 65 fictional credits, nine unique hitters, three protected offers where
possible, 10 observed games at each fielding position and universal DH. A choice
is offered only if an affordable matching for all remaining positions exists.
Three free rerolls per draft replace the current offers; each catalog fixes one price per player at every position.
M8C.2 uses the researched elite 1–30 curve, catalog schema 2.0.0 and policy
`m8c2-elite-1-30-smoothed-v1`. See [the draft contract](MLB_DRAFT.md) and
[pricing/PA measurements](../data/validation/pricing-pa-v1.md).

Cards explicitly label **historical PA**, the sample supporting the existing
smoothed profile. It does not cap simulated-season PA: every selected hitter
still plays the full season. No extra PA price discount, availability rule or
probability change is applied. The 65-credit budget is a provisional human
playtest choice; conservative drafts can still leave credits unused.

After completing the lineup, simulate, inspect the record and batting table,
then choose “Play another season” for a different seed or start a new draft.
“Season seed and model notes” allows exact seed replay. Seeds remain decimal
strings, including full u64 season seeds; browser-generated seeds use u32 entropy.
Cancelling terminates the worker and preserves the lineup. A failed run can be
retried with a fresh worker. Starting another draft clears the old result.

## Custom batting order (M8C.1)

After the ninth pick, the **Batting order** section shows all nine players with
numbered batting slots and their assigned fielding positions. Move a hitter with
the up/down buttons, drag the dedicated handle with mouse/touch, or focus the
handle and use Arrow Up/Down. **Reset batting order** restores the original
C,1B,2B,3B,SS,LF,CF,RF,DH order. These changes never alter picks, prices, fielding
assignments, draft history or the draft RNG/seed.

`draft/batting-order.ts` represents batting order as an immutable sequence of
player IDs, separate from position-keyed draft assignments. The existing
`draftedSeason` adapter accepts an optional order; it requires exactly the nine
unique drafted identities and validates before profile loading/WASM execution.
Only `userTeam.lineup` changes: player/profile mappings, profile-pool ordering,
opponent, contexts, models, rules and seed remain unchanged. The existing Web
Worker passes that complete JSON to the unchanged Rust season engine.

Results retain a snapshot of the order actually simulated, and the batting table
uses that sequence with statistics joined by stable batter ID. **Play another
season** changes the seed while preserving the order. **Edit batting order**
returns to the completed-lineup screen, retaining the current order and seed;
the displayed previous result is cleared. Cancellation/retry preserves the order.
Starting a new draft clears it; completing that draft initializes the default.
Reloading clears the ephemeral session. No database or persistent storage is used.
Local diagnostic exports include the current order and the result's order snapshot.

Controls have accessible player-specific names, 48px targets, native keyboard
focus and polite move/reset announcements. Editing is disabled during loading or
simulation. Touch scrolling remains available outside the drag handles; dropping
outside the list or cancelling a gesture leaves the order unchanged. Dragging
does not auto-scroll: use buttons/arrow keys or scroll between moves for distant
slots on short screens. Mobile emulation and browser touch input are covered;
physical-device and screen-reader usability still require human testing.
See [M8C.1 validation](../data/validation/batting-order-v1.md) for checks and limits.

## UI and boundaries

M8C.4 adds **Experimental error avoidance** to the completed-lineup screen.
It defaults off for legacy comparison. When enabled, a verified static supplement
binds the same eight fielding assignments to player-position error profiles;
customizing batting order never changes those assignments. Only supported
1B/2B/3B/SS error reaches change while the opponent bats. Catcher, outfield, DH,
pitching and all unmodeled defensive skills remain neutral. The display includes
defensive exposure and explicit neutral/insufficient mapping status. See
[defensive methodology, versions and reproduction](DEFENSIVE_SIMULATION.md).
Prices and the 65-credit budget are unchanged; no D1 migration is needed.

`apps/web/src/mlb/game/` contains:

- `MLBGame.tsx`: game flow, async loading/retry/cancellation, session caches and
  worker lifetime. Generation checks ignore obsolete work after cancellation or unmount.
- `DraftBoard.tsx`: historical offer cards and the nine-position roster.
- `BattingOrderEditor.tsx`: separate post-draft batting sequence and accessible moves.
- `SeasonResults.tsx`: record, batting totals, tied team leaders and denominator notes.
- `batting.ts`: explicitly separated historical and simulated display-rate calculations.

React uses the unchanged pure draft engine and existing published-data assembler.
There are no API/database/schema migrations or Rust baseball-core changes.
The API is contacted between rounds and before simulation, never during a game.
One `PlayerDataClient` and `PilotLoader` persist across drafts and seasons in the
page session; neither is stored in browser persistent storage. The WASM worker
is initialized on the first simulation and reused after successful runs.

## Historical versus simulated statistics

Cards show **2024 historical batting**, obtained from the existing player-detail
endpoint for only the current offers. They show name, eligible positions,
fictional price, AVG/OBP/SLG, HR and PA; secondary details identify source teams
and the budget after choosing that player. Each source-grain batting stint is
summed once, independently of position appearance rows. Duplicate stint keys,
wrong player/year/profile, invalid counts and catalog PA disagreements fail visibly.
Missing counts remain unknown, displayed as `—`.

Historical AVG is H/AB, OBP is (H+BB+HBP)/(AB+BB+HBP+SF), SLG is total bases/AB,
and PA is AB+BB+HBP+SH+SF. IBB is already included in BB. These numbers are not
derived from smoothed simulation weights.

Results show **actual simulated counters**: PA, H, HR, RBI, R and derived
AVG/OBP/SLG. Simulated OBP omits SF because sacrifices are not implemented;
all zero denominators display `—`. Team rates use team counters, never averages
of player ratios. Individual games played are not tracked and are not invented.
Tied leaders all appear. Roster positions and fictional prices remain visible.

## Result projection

The additive `simulate_season_batting_json` adapter export and Worker output
`batting` return the established season summary plus a versioned `batting`
object: team ID, team counters and nine batter IDs/counter lines. This is specified
in [the compact projection schema](../contracts/season-batting-summary.schema.json).
Counters are copied from Rust's computed season box, not recomputed in JavaScript.
The Worker parses this small JSON and sends the structured summary and batting
object once to React; it does not also send the JSON string, input or event log.
The original compact summary and full result remain available and unchanged.
No RNG consumption, model, baseball rules or golden output was changed.

## Local playtesting and tests

In development, or with `/?playtest=1`, “Local playtest tools” exports a JSON
download with versioned draft history, seeds, compact results and local transfer
timings. It sends nothing to a server and collects no user analytics. This is a
diagnostic export, not a save/import or competitive verification format.

```sh
npm run test:data-client
# Quick display-stat and balance diagnostics, without the longer existing draft suite:
npx playwright test --config apps/web/playwright.unit.config.ts game.spec.ts
npm run build
npm run test:integration
npm run test:browser
```

The unit suite writes `target/m7c/playtests.json` for 60 drafts across first,
cheapest and most-expensive-offered strategies, measuring completion, remaining
credits, chosen prices and safe offer counts. It verifies deterministic replay.
`target/m7c/seasons.json` measures 12 season seeds for one fixed verified lineup;
this separates seed variation from roster strength. Neither establishes human enjoyment.

Browser tests cover full gameplay, card correctness, budget, lineup, native/WASM
batting equality, repeat seeds, fresh seasons, new-draft reset, export, keyboard
focus, mobile layout, touch-target size, API/WASM failures, cancellation and retry.
Ordinary CI intercepts player/profile responses with a small verified source
excerpt in `data/fixtures/mlb-game-2024-v1.json`; it still uses real production
WASM. M8C.2 retains that historical excerpt unchanged, replaying its same offered
identities under the new catalog's prices/config. The legacy unit replay and
81–81 simulation golden remain intact. To exercise genuine local D1 without those intercepts:

```powershell
$env:M6B_IMPORT_SQL = 'data/processed/d1-2024/import.sql'
npm run test:integration
Remove-Item Env:M6B_IMPORT_SQL
```

The source excerpt includes the 26 players offered on the fixed first-choice
path for draft seed `20261027`, nine prepared profiles and the compact dataset
descriptor. It was extracted from the catalog-pinned M6A SQL after checking its
SHA-256, using SQLite with the existing migration. Unneeded context audits and
position detail are omitted. It is test data, never bundled into gameplay. Its
facts retain the Lahman CC BY-SA 3.0 attribution linked in the catalog and footer.

## Usability and alpha limits

Native buttons, labeled inputs, polite status announcements and alert errors are
keyboard accessible. Focus moves to each new draft heading and the results record.
Interactive controls have visible keyboard focus and 44px minimum height.
Offer cards stack on narrow screens. The document does not scroll horizontally;
the full batting table has a separately labeled keyboard-scrollable region.
Automated mobile viewports and device emulation do not establish physical phone
performance or substitute for a screen-reader/human usability pass.

Local-phone use requires a trusted HTTPS origin or localhost forwarding: profile
digest verification needs Web Crypto. See [browser validation](BROWSER_VALIDATION.md)
and [data browser setup](PLAYER_DATA_BROWSER.md); plain LAN HTTP is insufficient.

This is experimental baseball with provisional prices, fixed lineups, neutral
pitching/defense, a fixed CHA template and synthetic schedule. The same historical
identity may occur in that opponent. Known excess hits/double plays and compressed
variance remain; this milestone does not recalibrate them. See the
[M7C validation report](../data/validation/mlb-game-v1.md) for measurements and
recommended human playtests. See [alpha deployment](ALPHA_DEPLOYMENT.md) for the
hosting arrangement; M8C.1 itself makes no cloud or database changes.

## Offer rerolls

Use **Reroll players** while drafting to replace the current offer. Each draft has
three free rerolls shared across all positions; the button shows how many remain.
Picks and credits stay unchanged. Rerolling requires enough different affordable
players to replace every displayed card. Starting a new draft restores all three.
See [draft rules and replay](MLB_DRAFT.md#three-free-rerolls).
