# Verified historical sampling fixture

`lahman-modern-game.json` is a small regression fixture derived from the official
SABR Lahman 2025 release pinned by the pipeline lock. It contains prepared 2025
Aaron Judge and Juan Soto distributions, repeated in synthetic batting orders.
It is not an authentic team roster or an assertion of historical game accuracy.

Source attribution and CC BY-SA 3.0 terms: [data attribution](../../../../docs/DATA_ATTRIBUTION.md).
The modified distributions use `lahman-pa-adapter-v1`; provenance records source,
profile, policy and context IDs. The optional Python integration test reproduces
this exact fixture from verified source bytes. Large raw/generated datasets and
the full preparation audit remain ignored. Usage and approximation policy are in
the [simulation guide](../../../../docs/SIMULATION_FOUNDATION.md#statistical-integration-m3).
