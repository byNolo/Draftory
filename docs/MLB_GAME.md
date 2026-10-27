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
remain 90 fictional credits, nine unique hitters, three protected offers where
possible, 10 observed games at each fielding position and universal DH. A choice
is offered only if an affordable matching for all remaining positions exists.
There are no rerolls or price changes. See [the draft contract](MLB_DRAFT.md).

After completing the lineup, simulate, inspect the record and batting table,
then choose “Play another season” for a different seed or start a new draft.
“Season seed and model notes” allows exact seed replay. Seeds remain decimal
strings, including full u64 season seeds; browser-generated seeds use u32 entropy.
Cancelling terminates the worker and preserves the lineup. A failed run can be
retried with a fresh worker. Starting another draft clears the old result.

## UI and boundaries

`apps/web/src/mlb/game/` contains:

- `MLBGame.tsx`: game flow, async loading/retry/cancellation, session caches and
  worker lifetime. Generation checks ignore obsolete work after cancellation or unmount.
- `DraftBoard.tsx`: historical offer cards and the nine-position roster.
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
WASM. To exercise genuine local D1 without those intercepts:

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
recommended human playtests before a privately hosted alpha. No hosting, access
control or Cloudflare production resources have been provisioned.
