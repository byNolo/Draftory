# M8C.4 development evaluation plan

Written before the native outcome experiment. This is development validation,
not a new untouched historical holdout. No 2025 fit or retuning is allowed.

Use the separately versioned 2024 defensive fixture with nine actual published
batting profiles and the unchanged CHA opponent, neutral pitching, schedule and
seed derivation. For seeds 0–63 run five modes: legacy; new explicit neutral;
real assignments; controlled supported-position error ratios 0.5 and 1.5.
Controls are synthetic parameters, never published player ratings. All offensive
inputs stay identical. Log all rows, seeds and input hashes under ignored data.

Neutral must match every legacy game/event/counter exactly, except metadata that
identifies the new input/result mode. Report errors, ordinary contact outs, GDP,
PA, hits, runs for/against, wins/losses and base/out counts. Report paired mean
differences with 1.96*SE across the 64 season seeds; these describe Monte Carlo
noise for this fixture, not uncertainty about real defensive talent. Do not tune
effects if runs/wins are unresolved or noisy. Keep the existing GDP bias visible.

Measure preparation separately from sampling with a native example; time first
and repeated seasons without JSON/file I/O in that loop. Measure production
browser worker initialization, first and five repeated simulations, parsing,
serialization, processing and WebAssembly linear-memory high-water values.
Report medians and range/IQR. Caches may already be warm; no first-visit network,
JS-heap, physical-phone or production Cloudflare performance claim is supported.
Native and browser performance measurements should run without concurrent heavy
test/build work. Include exact full result parity in each available desktop and
mobile-emulation project and a complete draft-to-season test with reordered bats.

The 2024 development Retrosheet acquisition has its own pinned lock. Existing
Lahman/M4 locks and training/holdout roles remain unchanged. Error reliability
settings use 2022→2023 prediction; 2023→2024 is disclosed development sensitivity.
Retrosheet error attribution uses 2022/23 only. Unsupported mapping positions,
ambiguous reaches, advancing-only errors, compound plays and unsupported legal
alternatives remain unchanged.
