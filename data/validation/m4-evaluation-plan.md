# M4 evaluation plan

The M4 model uses 2022 and 2023 Retrosheet regular-season plays, innings 1–8,
to fit conditional transitions. Source counts determine the weights; there is no
run-scoring multiplier or optimization against final game scores. The minimum
cell count is 50; profile smoothing remains the M3 200-PA prior and 50-PA floor.

2024 is **development validation**, not an untouched holdout: its first diagnostic
run was observed while investigating the missing error/choice taxonomy. The final
holdout is **2025**. Its game logs and Lahman player profiles will be used only
after the transition taxonomy/estimator and these diagnostics are fixed. No 2025
plays are imported or used for fitting. Same-year player-season profiles make this
a retrospective conditional mechanics test, not an out-of-sample player forecast.

Compare the final contextual model and the preserved M3 proxy baseline across
all 30 clubs per year, with 20 independently seeded 162-game seasons per club.
Keep source team mappings and observed batting orders fixed across models.
Report per-repetition league means, their Monte Carlo standard deviation and
95% mean half-width; actual-data uncertainty uses paired-game clusters.
Do not pool the 20 simulated repetitions as 20 independent historical seasons.

Freeze diagnostic acceptance bands from training-year game logs: for each mean,
use the larger of the absolute 2022–2023 difference and the 95% uncertainty of
that difference. For score distributions, use total variation between the two
training-year empirical histograms. Also display shutout/high-score percentages,
inning means, strength terciles, individual-team W–L/run differentials and season
variability. These are provisional, data-derived prototype bands, not a claim of
historical equivalence; disclose every failed band and systematic bias.

The 2024/2025 targets must not change transition probabilities, minimum sample
thresholds or smoothing strength. Any later revision informed by the final
holdout requires a new model version and a new evaluation dataset.

## Integrity amendment

After the first evaluation, the final identity review found that traded players
could appear in two observed club orders from different dates. The fixed-lineup
schedule now excludes matchups sharing a player identity, and the Rust season
validator rejects those matchups even when batter instance/profile IDs differ.
All comparisons are rerun with the same corrected opponent sets for both models.
This is an identity-integrity correction, not an outcome-driven parameter change:
the estimator, source split, smoothing, thresholds and diagnostic bands are fixed.
Disclose that the corrected 2025 evaluation is a rerun after this amendment;
it is not pristine preregistered confirmation. Event fitting still uses no 2025 data.
