# M8C.1 · Custom batting order

Checked 2026-10-28. Scope: post-draft lineup editing and the existing browser
season-input path. No pricing, plate-appearance availability, defensive model,
Rust mechanics, RNG, historical data, opponents, contracts or cloud resources
were changed. Existing uncommitted M8A preparation work is preserved.

## Implementation

- `draft/batting-order.ts` defines an immutable ordered list of player IDs and
  validates an exact permutation of the completed nine-player roster. Fielding
  positions and draft history stay in the existing immutable draft state.
- `BattingOrderEditor.tsx` supplies numbered slots, names/assigned positions,
  up/down buttons, pointer capture for mouse/touch drag, keyboard arrow handling,
  polite announcements and reset. No dependency was added. Controls are 48px;
  the regression assertion retains its 44px minimum across engines.
- `draftedSeason` validates order before network loading, resolves profiles by
  player ID, and changes only `userTeam.lineup`. Profile-pool serialization stays
  in the default order. The existing Web Worker passes the input to unchanged
  native/WASM Rust code. The developer draft harness retains its default order.
- Results snapshot the simulated order and join counters by stable batter ID.
  They display that sequence even if the order for a subsequent run is changed.
  Editing returns to the lineup screen and clears the previous displayed result;
  replay/new season/cancellation retain the selection. A new draft resets it.
  No persistent storage or database dependency was introduced.

See [the game guide](../../docs/MLB_GAME.md#custom-batting-order-m8c1) for interaction
and state details. Local playtest exports now contain current and result orders.

## Verification

Unit checks cover default order, up/down/distant moves, missing/duplicate/foreign
players, incomplete drafts, unchanged fielding/history, early rejection before
fetching, stable profile references and input serialization. The same custom
order/seed repeats exactly in native Rust; a reversed fixture order produces a
different simulated team result. This demonstrates integration, not that one
order is universally better. Existing default-order goldens remain unchanged.

Browser checks exercise drag, keyboard focus/moves, reset, result row identity,
full native/WASM batting equality, repeat/new seeds, edit navigation and new-draft
reset. Pixel emulation uses actual Chromium touch events through Playwright/CDP
for dragging; iPhone emulation uses touchscreen taps for reset and mouse pointer
drag coverage in WebKit. Both check narrow layouts and control sizes. Existing
failure/cancellation tests require the editor to be disabled during execution.

| Check                                                | Result                                                               |
| ---------------------------------------------------- | -------------------------------------------------------------------- |
| TypeScript, ESLint, Prettier, Git whitespace         | Passed                                                               |
| Production Vite build                                | Passed                                                               |
| Client/draft/game unit suite                         | 29 passed                                                            |
| Browser/API integration                              | 35 passed, 3 optional full-publication cases skipped in fixture mode |
| Edge browser/API integration                         | 9 passed, 1 optional full-publication case skipped in fixture mode   |
| Rust fmt, Clippy, workspace tests, WASM-target build | Passed; 52 tests                                                     |
| Python Ruff lint/format and pytest                   | Passed; 145 tests, 8 optional source integrations skipped            |

The existing `test:browser` suite passed all 62 cases and `test:edge` passed all
13 cases, including full native/WASM equality, golden seeds, error recovery,
developer diagnostics and local redeployment behavior.

`npm run test:alpha`, with `M6B_IMPORT_SQL` pointing to
`data/processed/d1-2024/import.sql`, passed all 32 cases using the real verified
526-player publication with local D1 and
production Static Assets on one origin. Chromium, Firefox, WebKit and both mobile
projects passed; no responses are substituted except deliberate error injections.
The final Firefox custom-order case also passed three consecutive repetitions.

`npm run test:api` passed 8 tests; `npm run test:alpha:tools` passed 6 tests.
`npm run check:alpha` and `npm run check:api` bundled successfully in dry-run
mode; the existing D1 `SELECT 1` check passed with `--local`. No cloud deployment,
import or configuration change was executed for this milestone.

GitHub Actions has not run these uncommitted changes. Generated screenshots and
logs remain under ignored `target/` paths.

## Limits and next milestone

Dragging does not auto-scroll; use buttons/arrow keys or scroll between moves for
distant slots. No physical Android/iPhone or screen-reader testing is claimed.
Session state clears on page reload. Editing ends the previous results view;
this milestone does not save or compare multiple seasons.

M8C.2 should first quantify how full-season opportunities for low-PA historical
hitters interact with provisional prices, reserve evaluation cases, and review a
versioned availability/pricing policy. Do not infer balance or optimize prices
from this small order-integration fixture. M8C.2 has not started.

No commit or deployment was performed for M8C.1.
