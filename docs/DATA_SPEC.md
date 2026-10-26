# Draftory — Historical Data and Player Profile Specification

**Version:** 0.1 (2026-10-25)  
**Status:** Contract proposal; confirm actual fields by inspecting the pinned source release before coding final tables.

## 1. Purpose

Define a durable data pipeline that transforms publicly available historical baseball statistics into compact, reproducible player profiles for the Draftory simulator. Data import and profile creation are **offline Python tasks**; live gameplay reads precomputed/compiled data from D1 via a Worker API.

This specification deliberately distinguishes **raw historical facts**, **aggregated statistical profiles**, **gameplay ratings/prices**, and **simulated outcomes**. They must not be stored as if they were interchangeable.

## 2. Sources and licensing

### Primary: SABR Lahman Baseball Database

- Official release: https://sabr.org/lahman-database/
- As checked October 2026, SABR offers the 2025 release covering statistics through 2025, downloadable in CSV and other formats.
- Relevant files typically include `People.csv`, `Batting.csv`, `Pitching.csv`, `Fielding.csv`, `Appearances.csv`, `Teams.csv`, `TeamsFranchises.csv`; actual released schema and coverage come from the included `readme2025.txt`.
- Retain source revision/retrieval URL/date, official license text and required attribution. Lahman is distributed under **CC BY-SA 3.0**; evaluate implications for derivative datasets and public redistribution before shipping.
- Treat reported seasons and Negro League records in their historical league context; **do not silently aggregate all leagues into modern MLB leaderboards**.

### Supplemental: Retrosheet

- https://www.retrosheet.org/
- Evaluate game logs and play-by-play/event records for base-runner advancement, double-play frequency, situational scoring and independent validation.
- Read current required notices and provenance rules. Never assume Retrosheet has the same field granularity or ID system as Lahman.

### Avoid as foundational dependencies

- Undocumented/restricted official league scraping endpoints, unless their allowed uses are confirmed.
- Runtime live API calls during the simulation hot path.
- Unlicensed player portraits/logos/branding as part of the dataset.

## 3. Canonical identity and source facts

### Required source entities

| Entity | Minimum fields | Notes |
| --- | --- | --- |
| Player | internal `player_id`, display name, external ID mappings | Do not use name as unique key; allow aliases and changes |
| Team/franchise | `team_id`, `franchise_id`, season, league, display name | Team IDs can be season-dependent; trades matter |
| Player-year-stint | player ID, year, team ID, stint, league | Keep records at source grain to avoid duplicate counting |
| Batting fact | PA components and totals as available | Preserve integer raw counts and null/missing distinctions |
| Appearance fact | field positions and appearances | Needed to determine draft eligibility |
| Historical context | league, season length, data coverage, available opponent/park baselines | Enables future era normalization |

A player traded during a season may have multiple `Batting.csv` rows: preserve stints; aggregate by player-year across stints only when making season-wide profiles. Team-specific profiles must filter stints to the selected team/franchise first.

### Raw batting fields to inspect

Core Lahman-like season batting data usually contains `G`, `AB`, `R`, `H`, `2B`, `3B`, `HR`, `RBI`, `SB`, `CS`, `BB`, `SO`, `IBB`, `HBP`, `SH`, `SF`, `GIDP` in addition to ID/year/stint/team/league fields. **Availability varies by era and missing values must not be silently converted to zero.** Derive singles from `H - 2B - 3B - HR` only where the component fields are reliable.

Plate appearances can be computed as `AB + BB + HBP + SH + SF` for rows with sufficiently complete inputs. If a component is missing/unknown, propagate an incomplete-PA quality flag, apply an explicit documented estimation policy, or exclude the record from applicable profiles.

## 4. Statistical player profile modes

The following are **scope/aggregation requests**, not separate player objects:

| Requested profile | Filtering and aggregation |
| --- | --- |
| `season` | One player's selected year, optionally one specific team stint/group |
| `career_mean` | Pool all valid opportunities across included seasons, then calculate rates from summed counts (PA-weighted) |
| `career_median` | Median of valid **season-level rates** per event type, after eligibility thresholding |
| `team_mean` | Pool all valid opportunities for one selected team/franchise, then calculate rates |
| `team_median` | Median of eligible team-season rates for that player/team |
| `year_range_mean` / `year_range_median` | Same rules after filtering to a specified inclusive range |

**Team ID vs franchise ID is an explicit option.** Historical club identity can change. Document whether a mode means one exact team-season identity or the franchise across name/location changes.

### Means, medians and sample size

- **Default average:** compute rates from pooled *event counts and opportunities*, not arithmetic averages of annual AVG/OPS values.
- **Median:** compute per-event median season rates after a minimum PA threshold. Independent medians will not necessarily sum to 1; normalize or project onto a valid probability simplex and flag the result as modeled.
- Use transparent shrinkage/smoothing toward contextual league averages for small samples; exact model and thresholds are still to be researched.
- Do not average or take a median of already-rounded AVG, OBP, SLG, OPS. Derive displays from component outcomes when possible.
- If a player has too few qualifying seasons, return a typed insufficient-data result rather than quietly making up a median.
- Apply deliberate policy for seasons with missing HBP, SF, SO etc.; missing is not 0.
- A year-specific season is a **historical source profile**; the simulator may still normalize it to a specified opponent era through a separate modeling transform.

## 5. Suggested logical schemas

Keep raw facts separate from generated profiles. These are **conceptual contracts**, not final SQL migrations.

```text
Player
  id, display_name, birth/death (if available), source_ids[]

PlayerStint
  player_id, year, team_id, league_id, stint, source_release

BattingFact
  player_stint_key, G, AB, H, 2B, 3B, HR, BB, HBP, SO,
  SF, SH, SB, CS, RBI, R, GIDP, ...,
  missing_fields[], provenance

AppearanceFact
  player_id, year, team_id, position, games, provenance

ProfileDefinition
  id, player_id, scope, aggregate, year/year_range?,
  team_id?, franchise_scope?, era_context?, config_version

CompiledBatterProfile
  definition_id, profile_version, source_release,
  probability_model_version, pa_sample_size,
  probabilities, runner_attributes?, fielding_attributes?,
  display_stats, warnings[], source_lineage
```

Use indexed source IDs internally; avoid serializing giant raw records into each profile. For player choices, include only the display numbers needed by the UI and the small set of simulation parameters required by Rust.

## 6. Initial PA outcome vector

**Provisional**, to validate against real data:

```json
{
  "schemaVersion": "0.1",
  "profileId": "example-profile-id",
  "playerId": "example-player-id",
  "opportunities": 600,
  "outcomes": {
    "single": 0.16,
    "double": 0.05,
    "triple": 0.01,
    "homeRun": 0.05,
    "walk": 0.09,
    "hitByPitch": 0.01,
    "strikeout": 0.22,
    "ballInPlayOut": 0.41
  },
  "qualityFlags": ["illustrative-not-real-data"]
}
```

These **illustrative numbers** sum to 1. Real event distinctions may require finer categories (sacrifice, reach on error, fielder's choice, double play), some of which cannot be derived fully from Lahman batting aggregates alone. Never claim the simple vector fully reproduces official plate appearances or official scoring.

## 7. Transformation pipeline

1. **Acquire:** download a pinned release from an approved source, save checksum/manifest and official documentation.
2. **Inspect:** report available files, columns, types, season coverage, missingness, duplicate/stint patterns and anomalies.
3. **Normalize:** validate IDs, parse nullable counts, retain raw grain and source provenance.
4. **Aggregate:** construct requested season/career/team profiles with explicit eligibility and weighting policies.
5. **Model:** convert raw rates to context-aware, mutually exclusive PA outcome distributions; apply smoothing and normalization.
6. **Validate:** probabilities finite/in `[0,1]`, sum to 1 within tolerance, source facts reconcile, derived AVG/OBP/SLG check out where covered.
7. **Version:** assign content hash and semantic profile/model version, write immutable outputs and a release manifest.
8. **Publish:** import normalized records and approved precomputed profiles into D1; do not overwrite old versions needed by saved runs without a retention policy.

## 8. Position eligibility

The first draft uses `C`, `1B`, `2B`, `3B`, `SS`, `LF`, `CF`, `RF`, `DH`.

- Position eligibility comes from appearance/fielding records, not batting numbers.
- Some older eras lack modern DH use; DH can accept hitters independent of their fielding position, subject to game-mode rules.
- Decide a games-at-position threshold after exploring coverage. Don't infer that everyone who played one inning at catcher is a normal catcher.
- Catchers/fielders may have multiple eligible positions; prevent duplicate player identities on the same roster unless a future mode explicitly allows them.
- Keep defensively meaningful attributes separate from batting profiles; standardized defense for MVP is explicitly a simplification.

## 9. Era and opponent context

An identical raw .300 AVG is not necessarily equally valuable across different run-scoring environments. Define a future optional **era-normalized model** that uses league context and preserves the requested historical source profile. Keep original statistics and adjusted simulation probabilities as **separate** fields/artifacts.

Cross-era normalization, park factors, schedule differences and historical rule differences are research questions, not v0.1 guarantees. A modern completed-season pilot avoids hiding those uncertainties.

## 10. Required validations and sample tests

- Unique internal player identity and stable source-ID mapping.
- Season aggregation deduplicates multi-team players; team aggregation excludes other stints.
- Pooled mean reproduces event counts/opportunity ratios exactly before modeling adjustments.
- Median differs predictably from pooled mean for a crafted uneven-sample fixture.
- Missing SO/HBP/SF is handled by explicit policy rather than converting to zero.
- Singles cannot be negative; event totals cannot exceed available opportunities without error/report.
- Outcome vector sums to 1 and has no NaN/negative probability.
- Different source releases or aggregation configs produce different versioned profile IDs.
- Player profiles for the same player cannot simultaneously occupy two roster slots if disallowed.
- UI display stats are distinguishable from modeled vs raw stats.

Produce a `data-quality-report.md` for each import: row counts, sample ID joins, coverage/missingness tables, decisions, excluded records and surprising cases.

## 11. Open modeling questions

1. PA denominator for incomplete historical records and era-specific stat coverage.
2. Opportunity/season thresholds for median and position eligibility.
3. Which outcomes are inferred from Lahman, and which require Retrosheet-derived priors.
4. How to combine batter probabilities with opponent pitching strength.
5. How to model stolen bases, double plays, errors, sacrifices and baserunner speed.
6. Whether profiles for historical players are supported in every game mode or only compatible-era contexts.
7. Which subsets to precompute vs generate dynamically, balancing D1 size, Worker CPU and demand.

## 12. First implementation task

Make a **read-only Python exploration script** that reads the pinned Lahman CSV release, validates schemas, prints fields and coverage for batting/appearances/people/teams, and writes a machine-readable import manifest and short quality report. Then implement one player-year aggregation and tests. **Do not create the final database schema or pricing system before this exploration.**

## 13. References

- SABR Lahman: https://sabr.org/lahman-database/
- Retrosheet: https://www.retrosheet.org/
- Companion docs: [PROJECT_PLAN.md](PROJECT_PLAN.md), [ARCHITECTURE.md](ARCHITECTURE.md), [SIMULATION_SPEC.md](SIMULATION_SPEC.md).
