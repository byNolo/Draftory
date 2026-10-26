"""Measured schema, coverage, missingness and join diagnostics for the pinned release."""

from collections import Counter, defaultdict
from pathlib import Path

from .normalize import Dataset
from .source import canonical_bytes, source_lock
from .tables import column_type, read_table


def inspect_source(directory: Path, dataset: Dataset) -> dict:
    tables = {}
    for entry in source_lock()["files"]:
        name = entry["path"]
        if not name.endswith(".csv"):
            continue
        columns = {key: {"type": column_type(key), "nulls": 0} for key in entry["columns"]}
        years = Counter()
        leagues = defaultdict(list)
        missing_by_year = defaultdict(Counter)
        total = 0
        for _, row in read_table(directory, name):
            total += 1
            for key, value in row.items():
                if value is None:
                    columns[key]["nulls"] += 1
                    if "yearID" in row:
                        missing_by_year[row["yearID"]][key] += 1
            if "yearID" in row:
                years[row["yearID"]] += 1
                leagues[row["lgID"]].append(row["yearID"])
        tables[name] = {
            "rows": total,
            "sha256": entry["sha256"],
            "columns": columns,
            "yearCounts": dict(sorted(years.items())),
            "leagueCoverage": {
                league: {"firstYear": min(values), "lastYear": max(values), "rows": len(values)}
                for league, values in sorted(leagues.items())
            },
            "nullCountsByYear": dict(sorted(missing_by_year.items())),
        }
    players = {p.player_id for p in dataset.players}
    teams = {(t.year, t.team_id, t.league_id) for t in dataset.teams}
    franchises = {r["franchID"] for r in dataset.franchises}
    joins = {}
    for name, rows in (
        ("batting", dataset.batting),
        ("appearances", dataset.appearances),
        ("fielding", dataset.fielding),
    ):
        joins[name] = {
            "orphanPlayers": sum(r.player_id not in players for r in rows),
            "orphanTeamSeasons": sum((r.year, r.team_id, r.league_id) not in teams for r in rows),
        }
    joins["teams"] = {
        "orphanFranchises": sum(t.franchise_id not in franchises for t in dataset.teams)
    }
    groups = defaultdict(list)
    for row in dataset.batting:
        groups[row.player_id, row.year].append(row)
    multi = [
        (player, year, rows)
        for (player, year), rows in groups.items()
        if len({r.team_id for r in rows}) > 1
    ]
    bat_keys = {(r.player_id, r.year, r.team_id, r.league_id) for r in dataset.batting}
    app_keys = {(r.player_id, r.year, r.team_id, r.league_id) for r in dataset.appearances}
    team_groups = defaultdict(list)
    for row in dataset.batting:
        team_groups[row.year, row.team_id, row.league_id].append(row)
    discrepancies = []
    for team in dataset.teams:
        rows = team_groups[team.year, team.team_id, team.league_id]
        for key in ("AB", "H", "HR", "BB", "R"):
            if (
                rows
                and team.facts[key] is not None
                and all(r.counts[key] is not None for r in rows)
            ):
                summed = sum(r.counts[key] for r in rows)
                if summed != team.facts[key]:
                    discrepancies.append(
                        {
                            "year": team.year,
                            "team": team.team_id,
                            "league": team.league_id,
                            "field": key,
                            "playerSum": summed,
                            "teamValue": team.facts[key],
                        }
                    )
    return {
        "schemaVersion": "1.0.0",
        "source": dataset.provenance,
        "tables": tables,
        "joins": joins,
        "duplicateKeyPolicy": "Duplicate candidate keys are rejected; none found",
        "multiTeamPlayerSeasons": len(multi),
        "battingWithoutAppearance": len(bat_keys - app_keys),
        "appearancesWithoutBatting": len(app_keys - bat_keys),
        "battingAnomalies": [
            {
                "playerId": r.player_id,
                "year": r.year,
                "row": r.source_row,
                "counts": r.counts,
                "flags": r.quality_flags,
            }
            for r in dataset.batting
            if r.quality_flags
        ],
        "teamPlayerTotalDiscrepancies": len(discrepancies),
        "teamPlayerTotalDiscrepancyExamples": discrepancies[:15],
    }


def write_inspection(report: dict, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "inspection.json").write_bytes(canonical_bytes(report) + b"\n")
    lines = [
        "# Lahman 2025 measured data-quality report",
        "",
        "Generated from checksum-verified official CSV files. No raw facts were corrected.",
        "",
        f"Source lock SHA-256: `{report['source']['lockSha256']}`",
        "",
        "## Tables, fields and missingness",
        "",
        "Types are declared parser types, not statistical inference; all fields may be nullable.",
        "Year counts, per-year nulls, leagues and source hashes are in `inspection.json`.",
        "",
    ]
    for name, table in report["tables"].items():
        years = table["yearCounts"]
        coverage = f"{min(years)}–{max(years)}" if years else "not season-grained"
        lines += [
            f"### {name}",
            "",
            f"{table['rows']:,} rows; {coverage}.",
            "",
            "| Field | Type | Null rows |",
            "| --- | --- | ---: |",
        ]
        lines += [
            f"| {key} | {value['type']} | {value['nulls']:,} |"
            for key, value in table["columns"].items()
        ]
        lines += ["", "League coverage:", ""]
        lines += [
            f"- `{league}`: {v['firstYear']}–{v['lastYear']}, {v['rows']:,} rows."
            for league, v in table["leagueCoverage"].items()
        ]
        if not table["leagueCoverage"]:
            lines += ["No league/year columns."]
        lines += [""]
    lines += [
        "## Keys, joins and anomalies",
        "",
        report["duplicateKeyPolicy"] + ".",
        "",
        f"Multi-team player-seasons: {report['multiTeamPlayerSeasons']:,}.",
        f"Batting team-seasons without appearances: {report['battingWithoutAppearance']}.",
        f"Appearance team-seasons without batting: {report['appearancesWithoutBatting']}.",
        "",
        "```json",
        canonical_bytes(report["joins"]).decode(),
        "```",
        "",
        "Flagged batting rows (retained in normalized facts, excluded from profiles):",
        "",
    ]
    for row in report["battingAnomalies"]:
        lines += [
            f"- {row['playerId']} ({row['year']}), Batting row {row['row']}: "
            + ", ".join(row["flags"])
            + "."
        ]
    lines += [
        "",
        f"Team/player count discrepancies across AB/H/HR/BB/R: "
        f"{report['teamPlayerTotalDiscrepancies']:,}. These are diagnostics, not corrections.",
        "Historical team totals can have different game coverage from player totals.",
        "",
        "## Interpretation",
        "",
        "- `NA` is the National Association league code, not a missing-value marker.",
        "- Sum batting stints before appearance joins. Team profiles filter stints first.",
        "- Positions overlap within games; G_of and G_defense are not position sums.",
        "- FieldingOFsplit remains a separate source, never added to Fielding totals.",
        "- Missing required counts excludes the complete player-season from rates.",
        "- PA is AB + BB + HBP + SH + SF, omitting unrecorded interference and other rare awards.",
        "- AB - H - SO includes errors and fielder choices; it is not an out probability.",
        "- Sacrifice rates are descriptive and require contextual rules before simulation use.",
        "- No inferred values, era/park adjustments, smoothing or final eligibility thresholds.",
        "- SABR/Sean Lahman and Seamheads; retain pinned readme notices (CC BY-SA 3.0).",
        "",
    ]
    (destination / "data-quality-report.md").write_text("\n".join(lines), encoding="utf-8")
