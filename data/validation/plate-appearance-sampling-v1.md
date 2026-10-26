# M3 plate-appearance sampling validation v1

Measured locally on 2026-10-25. Engine 0.3.0, input 1.1.0,
`lahman-pa-adapter-v1`, `modern-neutral-v1`, `splitmix64-v1`, seed `2025`.
The [simulation guide](../../docs/SIMULATION_FOUNDATION.md#statistical-integration-m3)
defines all approximations, preparation commands and benchmark scope.

## Source and preparation

Official SABR Lahman 2025 snapshot, including February 2026 BOM revisions;
source lock SHA-256 `8f4cfb56f0726ebe7c900f8d8748232a3c8b326b2fc0d44a387512442e58a22c`.
[Attribution and CC BY-SA 3.0 terms](../../docs/DATA_ATTRIBUTION.md).
Judge 2025 has 679 computed PA, Soto 2025 has 714. The fixture repeats these
players in two artificial nine-slot orders; these are not historical rosters.

The 2025 AL/NL reference pools 673 complete positive-PA player-seasons,
182,838 computed PA, including each traded stint once.
797 player-seasons are excluded: {'zero-pa': 797}.
The full ignored preparation audit lists source rows and exact missing fields.
No missing values were replaced with zero.

The reference excludes 1.021123% observed sacrifice mass.
Judge excludes 1.030928%; Soto excludes
0.980392%.
Rates are explicitly conditioned on no sacrifice. The ordinary-out proxy maps
unresolved conditional contact mass (Judge 30.059524%, Soto 40.735502%) to one out
with holding runners. Those values are modeled proxies, not historical out counts.
With 200 prior PA, player blend weights are 0.772468714
and 0.781181619; maximum rounding errors are
5.36282571e-07 and 4.22097503e-07.
Original profiles/facts, mapping masses and adjusted distributions remain separate.

## Expected versus observed

Ten million standalone categorical draws per player (20 million total), with
seed reset to 2025 for each run. The runs share a random stream, so comparisons
between players are correlated; each marginal comparison still checks its own
prepared distribution. Expected values are prepared integer weights / 1,000,000,
not the raw historical profile. Observed columns include counts.

| Outcome       | Judge expected | Judge observed        | Soto expected | Soto observed         |
| ------------- | -------------- | --------------------- | ------------- | --------------------- |
| single        | 14.0887%       | 14.08205% (1,408,205) | 12.8810%      | 12.87671% (1,287,671) |
| double        | 4.4223%        | 4.41924% (441,924)    | 3.1463%       | 3.14617% (314,617)    |
| triple        | 0.3089%        | 0.31135% (31,135)     | 0.1864%       | 0.18662% (18,662)     |
| homeRun       | 6.8027%        | 6.79956% (679,956)    | 5.4343%       | 5.43430% (543,430)    |
| walk          | 16.1875%       | 16.18793% (1,618,793) | 15.8921%      | 15.88730% (1,588,730) |
| hitByPitch    | 1.0471%        | 1.05014% (105,014)    | 0.5646%       | 0.56507% (56,507)     |
| strikeout     | 23.5023%       | 23.49715% (2,349,715) | 20.0520%      | 20.04370% (2,004,370) |
| battedBallOut | 33.6405%       | 33.65258% (3,365,258) | 41.8433%      | 41.86013% (4,186,013) |

All 16 marginal deviations are within 1.40 binomial standard errors of
expectation. The unit convergence test separately uses one million draws, with a
six-standard-error plus ten-count tolerance per outcome. Fixed seeds and frozen
RNG/game goldens make tests reproducible; the rejection-boundary test forces a
raw zero draw to verify unbiased range reduction. Zero-weight tests never produce
an impossible event. These checks establish sampling consistency with the input,
**not historical scoring accuracy or independence quality of the PRNG**.

## Complete games and native performance

The real-profile fixture at seed 2025 ends home 13, away 3, after 90 PA.
The event trace replays to the same box scores/result; summary mode consumes the
same draws. One hundred tested seeds preserve PA/AB/hit/run/RBI/outs/LOB and team
counter invariants. A further 5,000 benchmark games (seeds 0..4999) all finish,
totaling 448,257 PA. Safety-limit aborts remain explicit errors, never winners.

Hardware: Snapdragon X Plus X1P42100 (Qualcomm Oryon), Windows ARM64,
`aarch64-pc-windows-msvc`, rustc 1.88.0, Cargo release defaults.
No CPU affinity, process isolation, repeated confidence intervals or allocator
instrumentation; timings are initial local observations, not a performance SLA.

| Measurement                         | Result                          |
| ----------------------------------- | ------------------------------- |
| 10,000,000 standalone Judge draws   | 0.1743932 s; 57,341,685 draws/s |
| First complete summary game (90 PA) | 0.1567 ms                       |
| 5,000 complete summary games        | 0.2150762 s; 23,248 games/s     |
| Mean repeated-game time             | 43.015 microseconds/game        |
| In-game throughput                  | 2,084,178 PA/s                  |
| Observed process peak working set   | 6,066,176 bytes (5.79 MiB)      |

Memory is a Windows process-wide peak sampled every 10 ms during the native
benchmark; it includes executable/runtime/input/output storage and may miss the
final sampling interval. It is not engine-only heap usage. Summary mode retains
no event history; detailed mode allocates a growing trace up to the configured
PA cap. Existing per-play state/runner allocations have not been optimized.

Reproduce from the repository root:

```sh
cargo build --locked --release --example measure --example simulate
cargo run --locked --release --example measure -- crates/baseball-sim/tests/fixtures/lahman-modern-game.json 10000000 5000
cargo run --locked --release --example simulate -- crates/baseball-sim/tests/fixtures/lahman-modern-game.json
```

The second distribution run reverses only the fixture's `profiles` array, so the
harness samples Soto first without changing lineup references. JSON parsing and
serialization are outside timed loops. Game timings include input cloning,
validation, setup and result allocation. Measurements are separate from tests.

## Verification and remaining work

- `cargo fmt --all -- --check`, Clippy with `-D warnings`: pass.
- `cargo test --locked --workspace`: 38 tests pass, including scripted mechanics.
- Native and `wasm32-unknown-unknown` builds: pass. WASM runtime execution parity
  is not tested; no browser bindings were added.
- `uv sync --locked`, Ruff lint/format, pytest with the pinned release: pass,
  115 tests including shared schemas, oversized-seed rejection and source reproduction. Without raw data,
  six source integration tests skip; the small Rust fixture still runs offline.
- Generated real input, full events result and companion audit pass shared JSON
  Schema validation. The real `prepare-game` CLI was executed end to end.
- Existing web/API TypeScript, ESLint, web build, Wrangler dry run, regenerated
  Worker types and local D1 `SELECT 1` checks pass. No cloud resources provisioned.
- Repository Prettier and `git diff --check`: pass.

Remaining statistical issues: error/choice and double-play frequencies, context
sacrifices and intentional walks, calibrated runner advancement, park/era effects,
pitcher effects, and empirically fitted smoothing. Conditioning/proxy rules bias
OBP, PA denominators, LOB, RBI and run production; star-only repeated lineups
cannot validate league scoring. Next M4 should establish independent held-out
season/scoring targets and review these policies before using a season loop for
historical calibration. No season implementation or commit is part of M3.
