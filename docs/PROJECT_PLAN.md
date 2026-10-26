# Draftory — Project Plan

**Status:** Planning baseline / implementation-ready foundation  
**Version:** 0.1 (2026-10-25)  
**Product:** Draftory — a browser-based collection of replayable sports drafting and simulation games

## 1. Vision

Draftory combines constrained roster-building decisions, randomized player offers, real historical statistics, and fast simulations. Players should be able to draft a team, simulate a season, understand *why* the team succeeded or failed, and want to try another combination. Start with a single-player MLB game; preserve room for other game modes, full-roster play, and additional sports.

The initial engineering priority is **trustworthy data and an accurate, fast simulation**, not polished game mechanics. Do not treat exploratory game ideas as locked requirements.

## 2. Decisions already made

| Area | Direction |
| --- | --- |
| Brand | Draftory (working product name) |
| First sport | MLB/baseball |
| Initial experience | Single-player, random-offer drafting; **no browse-any-player catalog** in the first game |
| MVP player selection | Nine batting slots: C, 1B, 2B, 3B, SS, LF, CF, RF, DH |
| Future mode | Full-roster game with rotations, bullpen, substitutions and fatigue |
| Initial pitching | Standardized league-average pitching/defensive environment for the user's team; opposing strength modeled consistently, not nine batters pitching |
| Simulation | Plate-appearance-level baseball events; 162-game season with individual game results |
| Player versions | Specific season; career or team-specific average/median; eventually user-selected year ranges |
| Historical data | Start with free SABR Lahman data; evaluate Retrosheet for event-level calibration |
| Data preparation | Python |
| Simulation core | Rust, compiled to browser WebAssembly; same core runnable natively |
| Frontend | React + TypeScript + Vite |
| Runtime hosting | Cloudflare static assets + Workers API + D1 database, subject to current limits |
| Execution | Browser Web Worker by default; no per-game server simulation for MVP |
| Monetization | None planned; review rights, data licensing and source choices before any commercial use |
| Competition | Defer ranked competition and verification server; retain deterministic input/seed/version contracts |

## 3. MVP scope — foundation first

### Included in the first technical prototype

- Import one completed MLB season from a pinned Lahman release.
- Normalize player identities, season/team stints, batting statistics, and position appearances.
- Generate versioned batter simulation profiles with explicit assumptions and quality flags.
- Simulate an at-bat/plate-appearance event stream with outs, base runners, inning progression, runs and batting order.
- Simulate full games and a 162-game season in Rust with seeded deterministic randomness.
- Accumulate team scores and supported batter box-score/season statistics.
- Measure realism against independent historical datasets and record deviations.
- Benchmark native Rust, desktop WASM and mid-range/older mobile WASM.
- Provide a minimal React development harness; a real game UI comes after data/simulation quality is credible.

### First playable game (after foundation)

- Random offers of eligible historical player profiles, draft state and lineup slots.
- Transparent player information and an eventually defined stat-derived pricing budget.
- Fast, readable season reveal, W–L record, runs scored/allowed, individual season batting lines and optional game inspection.
- User can try again; lightweight saved/local results initially, with accounts later if justified.

### Explicitly out of scope for initial implementation

- Final budget amount, reroll count, offer count, draft order, tier distributions or pricing formula.
- Player browsing as the main flow.
- Realistic 26-man roster management, bench substitutions, starting rotations, relievers and injuries.
- Pitch-by-pitch simulation, ball physics and rendered on-field player motion.
- Competitive verified leaderboards, anti-cheat infrastructure and verification server.
- Full historical era normalization on day one; design interfaces for it, test modern completed seasons first.
- Other sports, monetization, social features or complex user accounts.

## 4. Product principles

1. **Meaningful randomness:** randomized offers should create decisions; user choice and the resulting roster must matter.
2. **Fast feedback:** simulate a season quickly and let players inspect richer results selectively.
3. **Statistical honesty:** only show statistics derived from modeled events; do not claim a real MLB projection or exact historical prediction.
4. **Reproducibility:** same inputs, profile snapshot, rules version and seed must yield the same result.
5. **Extensibility without premature abstraction:** share platform contracts and drafting primitives, but keep MLB rules and simulator sport-specific.
6. **No expensive hidden infrastructure:** browser simulation, compact on-demand data downloads, caching and lightweight APIs.
7. **Explainable outcomes:** show why a lineup performs well or poorly in baseball terms; no LLM is required.
8. **Accessible play:** benchmark and support phones; keep the UI responsive via Web Workers.

## 5. Future gameplay directions (not commitments)

- Daily/common-seed challenges and personal records.
- Blind auction / randomized roster-building variants; position-based challenges.
- Franchise-specific and era-specific drafting; team mean/median and year-range player profiles.
- Full MLB roster management, opposing pitching matchups, advanced defense and park effects.
- Shared result cards, playoffs, leagues, friends and eventual verified competition.
- Other sports with independent rating/simulation implementations.

## 6. Implementation milestones and exit criteria

| Milestone | Deliverable | Done when |
| --- | --- | --- |
| M0 — Repo and contracts | Rust crate, Python pipeline, TS app shell, shared documented schemas | Local tests/lint/build run; docs and version conventions committed |
| M1 — Lahman exploration/import | Reproducible import and normalized sample dataset | Raw release pinned; ID/stint handling validated; counts and missing fields reported |
| M2 — Batter profiles | Season/team/career rate generator with quality metadata | Probabilities valid; aggregation tests demonstrate weighted mean vs season median; no fabricated raw values |
| M3 — Rust game engine | PA → bases/outs/runs → innings → games | Baseball rule unit tests pass and fixed-seed outputs repeat |
| M4 — Season and validation | 162 games, player totals, benchmark/calibration scripts | Run distribution and batting rates compared to historical references with documented acceptance thresholds |
| M5 — Browser proof of concept | WASM Web Worker + barebones React harness | A nine-batter lineup simulates a season smoothly on tested desktop and phone |
| M6 — Cloudflare/data API | Versioned compact profile API and selective loading | Only profiles/opponent context needed for the chosen game are sent; caching and D1 read usage measured |
| M7 — First game | Random-offer draft and presentation | Usable repeatable single-player loop; game rules chosen using playtests |

**Execution order:** M0 → M1 → M2 and M3 (M3 can use fixtures) → M4 → M5 → M6 → M7. Avoid jumping to the polished draft UI before the simulator is credible.

## 7. Success measures (targets pending benchmarks)

- **Correctness:** deterministic tests pass, baseball edge cases covered, no invalid base/out state.
- **Realism:** aggregate PA outcomes and run scoring resemble the chosen historical comparison set; measured, not assumed.
- **Speed:** provisional engineering goal of roughly **< 1 second** for 162 games on a typical desktop after WASM initialization; establish a separate mobile target with actual device measurements. This is a goal, **not a performance claim**.
- **Cost:** intended to operate under applicable Cloudflare free allowances at small scale; measure API calls, D1 row reads and storage before launch.
- **Gameplay:** users understand price/stat tradeoffs and can complete another run without confusing delays.

## 8. Risks and responses

| Risk | Mitigation |
| --- | --- |
| Lahman has insufficient event-level detail | Keep unknown mechanics explicit; use Retrosheet for baserunning/out calibration and validation |
| Cross-era profiles produce unrealistic stats | Start modern; make era/league context explicit; add normalization as a versioned transform |
| One-pitcher/lineup-only model feels unrealistic | Standardized staff for MVP; model opponent run environment explicitly and label simplifications |
| Bad baserunning distorts runs | Test runner transitions against historical events, with conservation/invariant tests |
| WASM performance on phones | Benchmark early; design configurable simulation fidelity and low-allocation engine |
| Browser result manipulation | Casual single-player only; future competitive mode can replay deterministic runs on a verification server |
| Data terms change or use becomes commercial | Retain data provenance, attribution, replaceable adapters and re-evaluate licensing |
| Scope creep | Keep open questions here; only lock decisions after M1–M4 evidence |

## 9. Open decisions

- Which seasons and leagues constitute each game's eligible player pool?
- Minimum opportunity thresholds and small-sample smoothing for means/medians?
- Era and ballpark normalization policy?
- What constitute valid position eligibility (appearances threshold, fallback positions, DH)?
- How opponent teams, neutral parks, designated hitter rules and extra-inning rules are configured?
- Detailed PA taxonomy and probabilistic baserunner advancements?
- Final price curve, rarity, budget, draft offers and rerolls?
- Which results to record vs reconstruct from a seed?
- Guest result retention and future auth requirements?

## 10. Immediate Codex task

**Build M0, then M1 as separate reviewed changes.** For M1, download the official pinned Lahman CSV release, inspect its supplied schema/readme, and produce a concise field/coverage report before creating permanent D1 tables. Do not implement speculative price logic, frontend game modes, or full-roster features.

## 11. Sources and companion documents

- Official Lahman database: https://sabr.org/lahman-database/
- Retrosheet: https://www.retrosheet.org/
- Cloudflare Workers: https://developers.cloudflare.com/workers/
- Cloudflare D1: https://developers.cloudflare.com/d1/
- See [ARCHITECTURE.md](ARCHITECTURE.md), [DATA_SPEC.md](DATA_SPEC.md), [SIMULATION_SPEC.md](SIMULATION_SPEC.md).
