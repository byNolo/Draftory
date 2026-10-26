# Lahman source review — foundation only

Reviewed 2026-10-25. No dataset downloaded or imported, no field coverage measured,
and no statistical model selected.

## Source inspected

The [official SABR page](https://sabr.org/lahman-database/) advertises the 2025
release covering 1871–2025, published January 2, 2026, with CSV byte-order-marker
updates on February 18, 2026. Its linked
[release readme](https://sabr.box.com/shared/static/qtgh1olzcaauz5x234wqx8huixizff8l.txt)
was read directly. The readme header says December 10, 2025: retain both dates as
source metadata rather than treating them as an unambiguous revision identifier.
The [CSV download](https://sabr.box.com/s/y1prhc795jk8zvmelfd3jq7tl389y6cd)
is the intended acquisition entry point; its archive bytes and actual headers
still need inspection during the import milestone. Readme field casing is not
proof of CSV header casing.

The readme identifies CC BY-SA 3.0 and credits SABR/Sean Lahman; retain the full
notice, attribution and upstream documentation with an eventual pinned archive.
It also documents Seamheads Negro League additions with distinct historical
contexts. Review redistribution terms before publishing derived data.

## Initial inputs and fields

These fields are documented in the official readme, not verified CSV headers.

| File                  | Initial fields                                                                                                                                                                               | Purpose / grain                                                                                                                                                 |
| --------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `People.csv`          | `playerID`, `nameFirst`, `nameLast`, `nameGiven`, `birthYear`, `birthMonth`, `birthDay`, `deathYear`, `deathMonth`, `deathDay`, `bats`, `throws`, `debut`, `finalGame`, `retroID`, `bbrefID` | Identity and cross-source mapping. The separate numeric `ID` is explicitly not used by other tables. Names and external IDs may be missing; names are not keys. |
| `Batting.csv`         | `playerID`, `yearID`, `stint`, `teamID`, `lgID`; `G`, `AB`, `R`, `H`, `2B`, `3B`, `HR`, `RBI`, `SB`, `CS`, `BB`, `SO`, `IBB`, `HBP`, `SH`, `SF`, `GIDP`                                      | Preserve source player/year/stint/team/league rows and nullable integer facts; aggregate only after validation.                                                 |
| `Appearances.csv`     | `yearID`, `teamID`, `lgID`, `playerID`, `G_all`, `GS`, `G_batting`, `G_defense`, `G_p`, `G_c`, `G_1b`, `G_2b`, `G_3b`, `G_ss`, `G_lf`, `G_cf`, `G_rf`, `G_of`, `G_dh`, `G_ph`, `G_pr`        | Primary position-appearance source at player/team/year grain; no stint column. Preserve individual OF positions.                                                |
| `Fielding.csv`        | `playerID`, `yearID`, `stint`, `teamID`, `lgID`, documented `Pos`, `G`, `GS`, `InnOuts`                                                                                                      | Cross-check position coverage at player/team/year/stint/position grain; retain other fielding facts in the raw source.                                          |
| `Teams.csv`           | `yearID`, `lgID`, `teamID`, `franchID`, `name`, `G`, `GHome`, `W`, `L`, `R`, `RA`, `AB`, `H`, `2B`, `3B`, `HR`, `BB`, `SO`, `HBP`, `SF`, `park`, `BPF`, `PPF`, `teamIDBR`, `teamIDretro`     | Team-season identity, franchise relation, season length and later aggregate comparisons. Park factors are facts to preserve, not a selected adjustment model.   |
| `TeamsFranchises.csv` | `franchID`, `franchName`, `active`, `NAassoc`                                                                                                                                                | Franchise identity across relocations/name changes.                                                                                                             |

There is no separate seasons table required initially: derive a season/league
inventory from `Teams.yearID/lgID`, cross-check against batting/appearances, and
retain each team's actual `G`. Do not impose 162 historical games on every season.
`Pitching.csv` can be evaluated later for league-context checks (`BFP`, `IPOuts`,
`H`, `HR`, `BB`, `SO`, `HBP`, `R`, `SH`, `SF` plus identity fields); individual
pitcher profiles are not needed for the nine-hitter foundation.

## Import hazards and unresolved questions

- Pin archive and extracted-file SHA-256 values, resolved download URL, retrieval
  time and documentation/license bytes. The manifest contract is ready, but no
  real manifest exists yet. Determine encoding/BOM behavior from the actual files;
  names include diacritics. Never silently strip or merge identities.
- Check candidate uniqueness keys before enforcing them. Join identities on
  `playerID`, team seasons on year/team/league where appropriate, and franchises
  through `Teams.franchID`. Aggregate batting stints to the appearance grain
  before joining; joining appearance counts to every stint can multiply counts.
- The readme notes `G_batting` and `G_old` were removed from **Batting** in this
  release; `G_batting` remains documented in **Appearances**. Do not reuse an old
  Batting schema blindly.
- Missing counts are unknown, not zero. PA can use `AB + BB + HBP + SH + SF` only
  with complete components; singles use `H - 2B - 3B - HR` with reliable inputs.
  `IBB` is part of `BB`, not an extra PA outcome. PA denominator, smoothing,
  missingness exclusions and event taxonomy remain decisions for later review.
- Position counts overlap within games; summing `G_lf/G_cf/G_rf` need not equal
  distinct `G_of`. DH eligibility and minimum position appearances remain open.
  Check `FieldingOFsplit.csv` if granular historical OF coverage is needed;
  the readme says legacy `FieldingOF` was intended only through 1955.
- Preserve leagues explicitly. The readme describes the 1939 Toledo Crawfords as
  two team IDs (`TC`, `TC2`) under franchise `PC`. Negro League player totals may
  include games against all teams while team records can represent league-only
  results; some game-level facts lack player-level coverage. Reconciliation must
  respect these contexts rather than forcing equality.
- Choose the pilot completed season and leagues explicitly after coverage
  inspection. No season or league pool is selected here. Lahman aggregates do
  not resolve situational baserunning, double plays, or pitcher/batter interaction;
  Retrosheet calibration remains a separate research task.

## Recommended import milestone sequence

1. Acquire and pin the official CSV archive, readme and notices; emit a real
   schema-valid manifest and inspect exact filenames/headers/encoding.
2. Build a read-only exploration command reporting row counts, season/league
   coverage, nulls, duplicates, candidate keys, orphan IDs and representative joins.
3. Review pilot-season scope and missingness policy; test one player-year sum
   across stints and one team-filtered sum without appearance multiplication.
4. Produce the required quality report and normalized sample before reviewing
   permanent D1 migrations. Defer profile models and all game mechanics.
