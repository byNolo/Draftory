# Verified historical sampling fixture

`season-modern-2024.json` contains observed, eligible nine-hitter 2024 New York
(NYA) and Chicago (CHA) batting orders selected from official Retrosheet game logs,
verified through Lahman `People.retroID` and team-season batting stints. Those
orders are held fixed against a synthetic paired home/away schedule. They do not
represent full rosters or actual 162-game lineups. Its contextual table is fitted
only from 2022–2023 regular-season plays, innings 1–8; 2024 is development
validation and 2025 is final holdout. Both sources' notices are in the linked
attribution document below. The optional source test reproduces the complete
transition table; the pipeline's lineup audit records exact game dates/source rows.

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
