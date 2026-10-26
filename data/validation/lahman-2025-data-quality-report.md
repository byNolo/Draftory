# Lahman 2025 measured data-quality report

Generated from checksum-verified official CSV files. No raw facts were corrected.

Source lock SHA-256: `8f4cfb56f0726ebe7c900f8d8748232a3c8b326b2fc0d44a387512442e58a22c`

## Tables, fields and missingness

Types are declared parser types, not statistical inference; all fields may be nullable.
Year counts, per-year nulls, leagues and source hashes are in `inspection.json`.

### Appearances.csv

128,512 rows; 1871–2025.

| Field     | Type    | Null rows |
| --------- | ------- | --------: |
| yearID    | integer |         0 |
| teamID    | string  |         0 |
| lgID      | string  |         0 |
| playerID  | string  |         0 |
| G_all     | integer |         0 |
| GS        | integer |    16,147 |
| G_batting | integer |     1,135 |
| G_defense | integer |    19,154 |
| G_p       | integer |         8 |
| G_c       | integer |         8 |
| G_1b      | integer |         8 |
| G_2b      | integer |         8 |
| G_3b      | integer |         8 |
| G_ss      | integer |         8 |
| G_lf      | integer |         8 |
| G_cf      | integer |         8 |
| G_rf      | integer |         8 |
| G_of      | integer |    11,457 |
| G_dh      | integer |     1,264 |
| G_ph      | integer |     8,969 |
| G_pr      | integer |     8,969 |

League coverage:

- `AA`: 1882–1891, 1,889 rows.
- `AL`: 1901–2025, 54,243 rows.
- `ANL`: 1929–1929, 154 rows.
- `EAS`: 1903–1928, 1,035 rows.
- `ECL`: 1923–1928, 917 rows.
- `EWL`: 1932–1932, 191 rows.
- `FL`: 1914–1915, 468 rows.
- `IND`: 1891–1936, 827 rows.
- `INT`: 1909–1909, 44 rows.
- `NA`: 1871–1875, 736 rows.
- `NAC`: 1907–1908, 105 rows.
- `NAL`: 1937–1948, 2,114 rows.
- `NL`: 1876–2025, 59,237 rows.
- `NN2`: 1933–1948, 2,731 rows.
- `NNL`: 1920–1931, 2,275 rows.
- `NSL`: 1932–1932, 237 rows.
- `PL`: 1890–1890, 148 rows.
- `UA`: 1884–1884, 334 rows.
- `WES`: 1902–1919, 827 rows.

### Batting.csv

128,598 rows; 1871–2025.

| Field    | Type    | Null rows |
| -------- | ------- | --------: |
| playerID | string  |         0 |
| yearID   | integer |         0 |
| stint    | integer |         0 |
| teamID   | string  |         0 |
| lgID     | string  |         0 |
| G        | integer |         0 |
| AB       | integer |         0 |
| R        | integer |         0 |
| H        | integer |         0 |
| 2B       | integer |         0 |
| 3B       | integer |         0 |
| HR       | integer |         0 |
| RBI      | integer |       756 |
| SB       | integer |     2,546 |
| CS       | integer |    32,495 |
| BB       | integer |         0 |
| SO       | integer |     8,859 |
| IBB      | integer |    46,527 |
| HBP      | integer |     2,816 |
| SH       | integer |     6,068 |
| SF       | integer |    46,664 |
| GIDP     | integer |    35,432 |

League coverage:

- `AA`: 1882–1891, 1,893 rows.
- `AL`: 1901–2025, 54,277 rows.
- `ANL`: 1929–1929, 154 rows.
- `EAS`: 1903–1928, 1,035 rows.
- `ECL`: 1923–1928, 917 rows.
- `EWL`: 1932–1932, 191 rows.
- `FL`: 1914–1915, 472 rows.
- `IND`: 1891–1936, 827 rows.
- `INT`: 1909–1909, 44 rows.
- `NA`: 1871–1875, 737 rows.
- `NAC`: 1907–1908, 105 rows.
- `NAL`: 1937–1948, 2,114 rows.
- `NL`: 1876–2025, 59,279 rows.
- `NN2`: 1933–1948, 2,731 rows.
- `NNL`: 1920–1931, 2,275 rows.
- `NSL`: 1932–1932, 237 rows.
- `PL`: 1890–1890, 149 rows.
- `UA`: 1884–1884, 334 rows.
- `WES`: 1902–1919, 827 rows.

### Fielding.csv

174,332 rows; 1871–2025.

| Field    | Type    | Null rows |
| -------- | ------- | --------: |
| playerID | string  |         0 |
| yearID   | integer |         0 |
| stint    | integer |         0 |
| teamID   | string  |         0 |
| lgID     | string  |         0 |
| POS      | string  |         0 |
| G        | integer |         0 |
| GS       | integer |    48,657 |
| InnOuts  | integer |    29,937 |
| PO       | integer |       616 |
| A        | integer |       616 |
| E        | integer |       630 |
| DP       | integer |       629 |
| PB       | integer |   158,054 |
| WP       | integer |   171,945 |
| SB       | integer |   162,044 |
| CS       | integer |   164,166 |
| ZR       | number  |   173,163 |

League coverage:

- `AA`: 1882–1891, 3,677 rows.
- `AL`: 1901–2025, 69,702 rows.
- `ANL`: 1929–1929, 271 rows.
- `EAS`: 1903–1928, 1,656 rows.
- `ECL`: 1923–1928, 1,528 rows.
- `EWL`: 1932–1932, 312 rows.
- `FL`: 1914–1915, 672 rows.
- `IND`: 1891–1936, 1,213 rows.
- `INT`: 1909–1909, 76 rows.
- `NA`: 1871–1875, 1,512 rows.
- `NAC`: 1907–1908, 176 rows.
- `NAL`: 1937–1948, 3,219 rows.
- `NL`: 1876–2025, 79,368 rows.
- `NN2`: 1933–1948, 4,310 rows.
- `NNL`: 1920–1931, 3,943 rows.
- `NSL`: 1932–1932, 374 rows.
- `PL`: 1890–1890, 293 rows.
- `UA`: 1884–1884, 676 rows.
- `WES`: 1902–1919, 1,354 rows.

### FieldingOFsplit.csv

45,147 rows; 1891–2025.

| Field    | Type    | Null rows |
| -------- | ------- | --------: |
| playerID | string  |         0 |
| yearID   | integer |         0 |
| stint    | integer |         0 |
| teamID   | string  |         0 |
| lgID     | string  |         0 |
| POS      | string  |         0 |
| G        | integer |         0 |
| GS       | integer |     1,157 |
| InnOuts  | integer |         0 |
| PO       | integer |       269 |
| A        | integer |       269 |
| E        | integer |       271 |
| DP       | integer |       273 |
| PB       | integer |    44,033 |
| WP       | integer |    45,147 |
| SB       | integer |    44,903 |
| CS       | integer |    45,146 |
| ZR       | number  |    45,147 |

League coverage:

- `AL`: 1954–2025, 18,517 rows.
- `ANL`: 1929–1929, 116 rows.
- `EAS`: 1903–1928, 706 rows.
- `ECL`: 1923–1928, 633 rows.
- `EWL`: 1932–1932, 136 rows.
- `IND`: 1891–1936, 487 rows.
- `INT`: 1909–1909, 39 rows.
- `NAC`: 1907–1908, 97 rows.
- `NAL`: 1937–1948, 1,279 rows.
- `NL`: 1954–2025, 18,868 rows.
- `NN2`: 1933–1948, 1,753 rows.
- `NNL`: 1920–1931, 1,793 rows.
- `NSL`: 1932–1932, 169 rows.
- `WES`: 1902–1919, 554 rows.

### People.csv

24,270 rows; not season-grained.

| Field        | Type    | Null rows |
| ------------ | ------- | --------: |
| ID           | integer |         0 |
| playerID     | string  |         0 |
| birthYear    | integer |       978 |
| birthMonth   | integer |     1,352 |
| birthDay     | integer |     1,521 |
| birthCity    | string  |     1,130 |
| birthCountry | string  |       939 |
| birthState   | string  |     1,361 |
| deathYear    | integer |    12,237 |
| deathMonth   | integer |    12,244 |
| deathDay     | integer |    12,341 |
| deathCountry | string  |    12,280 |
| deathState   | string  |    12,352 |
| deathCity    | string  |    12,300 |
| nameFirst    | string  |       413 |
| nameLast     | string  |         0 |
| nameGiven    | string  |         0 |
| weight       | integer |     2,182 |
| height       | integer |     2,008 |
| bats         | string  |     2,847 |
| throws       | string  |     2,140 |
| debut        | string  |     3,030 |
| bbrefID      | string  |     1,275 |
| finalGame    | string  |     4,932 |
| retroID      | string  |       897 |

League coverage:

No league/year columns.

### Teams.csv

3,614 rows; 1871–2025.

| Field          | Type    | Null rows |
| -------------- | ------- | --------: |
| yearID         | integer |         0 |
| lgID           | string  |         0 |
| teamID         | string  |         0 |
| franchID       | string  |         0 |
| divID          | string  |     2,026 |
| Rank           | integer |         0 |
| G              | integer |         0 |
| Ghome          | integer |       628 |
| W              | integer |         0 |
| L              | integer |         0 |
| DivWin         | string  |     2,054 |
| WCWin          | string  |     2,690 |
| LgWin          | string  |       488 |
| WSWin          | string  |       855 |
| R              | integer |         1 |
| AB             | integer |         1 |
| H              | integer |         1 |
| 2B             | integer |         1 |
| 3B             | integer |         1 |
| HR             | integer |         1 |
| BB             | integer |         1 |
| SO             | integer |        80 |
| SB             | integer |       141 |
| CS             | integer |     1,116 |
| HBP            | integer |     1,159 |
| SF             | integer |     1,990 |
| RA             | integer |         1 |
| ER             | integer |         1 |
| ERA            | number  |         1 |
| CG             | integer |         1 |
| SHO            | integer |         1 |
| SV             | integer |         1 |
| IPouts         | integer |         1 |
| HA             | integer |         1 |
| HRA            | integer |        14 |
| BBA            | integer |         1 |
| SOA            | integer |         1 |
| E              | integer |        14 |
| DP             | integer |       394 |
| FP             | number  |        14 |
| name           | string  |         0 |
| park           | string  |        56 |
| attendance     | integer |       788 |
| BPF            | integer |       509 |
| PPF            | integer |       509 |
| teamIDBR       | string  |         0 |
| teamIDlahman45 | string  |       509 |
| teamIDretro    | string  |        61 |

League coverage:

- `AA`: 1882–1891, 85 rows.
- `AL`: 1901–2025, 1,355 rows.
- `ANL`: 1929–1929, 6 rows.
- `EAS`: 1903–1928, 57 rows.
- `ECL`: 1923–1928, 42 rows.
- `EWL`: 1932–1932, 8 rows.
- `FL`: 1914–1915, 16 rows.
- `IND`: 1891–1936, 46 rows.
- `INT`: 1909–1909, 3 rows.
- `NA`: 1871–1875, 50 rows.
- `NAC`: 1907–1908, 7 rows.
- `NAL`: 1937–1948, 77 rows.
- `NL`: 1876–2025, 1,579 rows.
- `NN2`: 1933–1948, 106 rows.
- `NNL`: 1920–1931, 94 rows.
- `NSL`: 1932–1932, 11 rows.
- `PL`: 1890–1890, 8 rows.
- `UA`: 1884–1884, 12 rows.
- `WES`: 1902–1919, 52 rows.

### TeamsFranchises.csv

203 rows; not season-grained.

| Field      | Type   | Null rows |
| ---------- | ------ | --------: |
| franchID   | string |         0 |
| franchName | string |         0 |
| active     | string |         0 |
| NAassoc    | string |       191 |

League coverage:

No league/year columns.

## Keys, joins and anomalies

Duplicate candidate keys are rejected; none found.

Multi-team player-seasons: 9,725.
Batting team-seasons without appearances: 8.
Appearance team-seasons without batting: 0.

```json
{
  "appearances": { "orphanPlayers": 0, "orphanTeamSeasons": 0 },
  "batting": { "orphanPlayers": 0, "orphanTeamSeasons": 0 },
  "fielding": { "orphanPlayers": 0, "orphanTeamSeasons": 0 },
  "teams": { "orphanFranchises": 0 }
}
```

Flagged batting rows (retained in normalized facts, excluded from profiles):

- lahman:cantwto01 (1909), Batting row 17507: hits-plus-strikeouts-exceed-at-bats.
- lahman:tayloci99 (1912), Batting row 113677: extra-base-hits-exceed-hits.

Team/player count discrepancies across AB/H/HR/BB/R: 579. These are diagnostics, not corrections.
Historical team totals can have different game coverage from player totals.

## Interpretation

- `NA` is the National Association league code, not a missing-value marker.
- Sum batting stints before appearance joins. Team profiles filter stints first.
- Positions overlap within games; G_of and G_defense are not position sums.
- FieldingOFsplit remains a separate source, never added to Fielding totals.
- Missing required counts excludes the complete player-season from rates.
- PA is AB + BB + HBP + SH + SF, omitting unrecorded interference and other rare awards.
- AB - H - SO includes errors and fielder choices; it is not an out probability.
- Sacrifice rates are descriptive and require contextual rules before simulation use.
- No inferred values, era/park adjustments, smoothing or final eligibility thresholds.
- SABR/Sean Lahman and Seamheads; retain pinned readme notices (CC BY-SA 3.0).
