# Historical data attribution

## Retrosheet calibration data

The information used here was obtained free of charge from and is copyrighted by
Retrosheet. Interested parties may contact Retrosheet at [www.retrosheet.org](https://www.retrosheet.org/).

M4 uses official Retrosheet 2022–2025 regular-season game logs and 2022–2023 parsed
plays. The pinned `retrosheet-m4.lock.json` records official URLs, observed hashes
and the training/development/final-holdout split. The official
[game-log source and data-use notice](https://www.retrosheet.org/gamelogs/index.html)
and [parsed-play documentation](https://www.retrosheet.org/downloads/plays.html)
are preserved with the ignored raw snapshot. Retrosheet permits data/product use
subject to its required notice; it does not use Lahman's CC BY-SA license.
Keep this notice with redistributed calibration tables and products using them.
Derived transition probabilities and fixed-lineup experiments are Draftory
transformations, not Retrosheet's predictions or historical game records.

## SABR Lahman

Draftory's Lahman adapter uses the official
[SABR Lahman Baseball Database](https://sabr.org/lahman-database/), 2025 release,
created by Sean Lahman and maintained by SABR, with annual updates by Bryan Walko.
The release includes Negro League data contributed by Seamheads. Full contributor,
copyright and use notices are in the pinned `readme2025.txt` downloaded alongside
the CSV files; the acquisition lock records its exact checksum and official URL.

The release readme identifies the database as copyright 1996–2025 by SABR following
Sean Lahman's donation and specifies
[Creative Commons Attribution-ShareAlike 3.0 Unported](https://creativecommons.org/licenses/by-sa/3.0/).
This statement concerns the upstream dataset; it does not select a software
license for Draftory. Keep source attribution, license notices, modifications
and provenance with any redistributed normalized or derived data, and review
the applicable terms before publishing artifacts. Local normalization does not
alter upstream data bytes; derived aggregates/profiles are labeled separately.

The official web page lists January 2, 2026 publication and February 18, 2026 BOM
revisions. The pinned readme header lists December 10, 2025. Draftory records this
disagreement and identifies its exact source snapshot through per-file hashes.
No unofficial mirror, player media, Retrosheet dataset or league API is included.
