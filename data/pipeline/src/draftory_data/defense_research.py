"""M8C.3 offline defensive-data audit. Never publishes simulation ratings."""

import argparse
import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from statistics import median

from . import retrosheet
from .source import DataError, canonical_bytes, digest, verify_source
from .tables import POSITION_FIELDS, Row, read_table
from .transitions import supported_transition
from .valuation import FIXTURE_SHA, ROOT, load_publication

VERSION = "defense-research-v1"
POSITIONS = ("C", "1B", "2B", "3B", "SS", "LF", "CF", "RF")
COUNTS = ("G", "GS", "InnOuts", "PO", "A", "E", "DP", "PB", "WP", "SB", "CS")
DATASET_ID = "dataset:1fba260824fe05abec3c5950cd184caa0d314b41f1253bc782f97b678bb28add"


def total(values):
    """An absent/unknown contribution is not a zero."""
    values = list(values)
    return sum(values) if values and all(v is not None for v in values) else None


def ratio(n, d):
    return n / d if n is not None and d is not None and d > 0 else None


@dataclass(frozen=True)
class FieldingLine:
    player: str
    year: int
    position: str
    counts: dict[str, int | None]
    teams: tuple[str, ...]
    rows: tuple[tuple[str, int], ...]

    @property
    def chances(self):
        return total(self.counts[k] for k in ("PO", "A", "E"))


def aggregate_fielding(tables: dict[str, list[tuple[int, Row]]]) -> list[FieldingLine]:
    """Choose one source per stint/position; split OF never adds to generic OF."""
    chosen = {}
    for table in ("Fielding.csv", "FieldingOFsplit.csv"):
        seen = set()
        for number, row in tables[table]:
            key = tuple(row[k] for k in ("playerID", "yearID", "stint", "teamID", "lgID", "POS"))
            if key in seen:
                raise DataError(f"Duplicate fielding key: {table}:{number}")
            seen.add(key)
            if table == "FieldingOFsplit.csv" and row["POS"] not in ("LF", "CF", "RF"):
                raise DataError("Unexpected split outfield position")
            for field in COUNTS:
                value = row[field]
                if value is not None and (type(value) is not int or value < 0):
                    raise DataError(f"Invalid fielding count: {table}:{number}:{field}")
            if key in chosen:
                # Specific-position main and split copies must agree on shared known facts.
                previous = chosen[key][2]
                if any(
                    previous[k] is not None and row[k] is not None and previous[k] != row[k]
                    for k in COUNTS
                ):
                    raise DataError("Conflicting specific-position fielding sources")
                continue
            chosen[key] = (table, number, row)
    grouped = defaultdict(list)
    for table, number, row in chosen.values():
        if row["lgID"] in ("AL", "NL") and row["POS"] in POSITIONS:
            grouped[row["playerID"], row["yearID"], row["POS"]].append((table, number, row))
    return [
        FieldingLine(
            player,
            year,
            position,
            {k: total(r[k] for _, _, r in rows) for k in COUNTS},
            tuple(sorted({r["teamID"] for _, _, r in rows})),
            tuple(sorted((t, n) for t, n, _ in rows)),
        )
        for (player, year, position), rows in sorted(grouped.items())
    ]


def distribution(values):
    v = sorted(x for x in values if x is not None)
    return (
        {
            "n": len(v),
            "min": v[0],
            "p25": v[(len(v) - 1) // 4],
            "median": median(v),
            "p75": v[3 * (len(v) - 1) // 4],
            "max": v[-1],
        }
        if v
        else {"n": 0}
    )


def field_coverage(rows):
    """All released leagues; ranges do not assert continuous or complete coverage."""
    result = {}
    for field in rows[0][1]:
        known = [(r["yearID"], r[field]) for _, r in rows if r[field] is not None]
        result[field] = {
            "known": len(known),
            "missing": len(rows) - len(known),
            "zero": sum(v == 0 for _, v in known),
            "firstKnownYear": min((y for y, _ in known), default=None),
            "lastKnownYear": max((y for y, _ in known), default=None),
        }
    return result


def era_coverage(rows):
    result = []
    for start, end in ((1871, 1899), (1900, 1953), (1954, 1989), (1990, 2021), (2022, 2025)):
        cohort = [(n, r) for n, r in rows if start <= r["yearID"] <= end]
        if cohort:
            result.append(
                {"start": start, "end": end, "rows": len(cohort), "fields": field_coverage(cohort)}
            )
    return result


def error_experiment(
    line: FieldingLine, baseline: Fraction, prior: int = 100, min_innings: int = 300
):
    """Error avoidance only, not range, talent, runs saved or a production rating."""
    if prior < 0 or min_innings < 0 or not 0 <= baseline <= 1:
        raise DataError("Invalid experimental error policy")
    tc, outs, errors = line.chances, line.counts["InnOuts"], line.counts["E"]
    if tc is None or tc <= 0 or outs is None or outs < min_innings * 3:
        return None
    rate = (Fraction(errors) + prior * baseline) / (tc + prior)
    return {
        "rawErrorRate": float(Fraction(errors, tc)),
        "shrunkErrorRate": float(rate),
        "avoidedErrorsPer1000Chances": float(1000 * (baseline - rate)),
        "dataWeight": tc / (tc + prior),
    }


def pool_audit(players, lines):
    season = [r for r in lines if r.year == 2024]
    lookup = {(r.player, r.position): r for r in season}
    ids = {p["id"].removeprefix("lahman:") for p in players}
    baselines = {}
    for pos in POSITIONS:
        complete = [
            r
            for r in season
            if r.position == pos
            and r.chances
            and r.counts["InnOuts"] is not None
            and r.counts["InnOuts"] >= 900
        ]
        baselines[pos] = Fraction(
            sum(r.counts["E"] for r in complete), sum(r.chances for r in complete)
        )
    coverage, examples = {}, []
    for pos in POSITIONS:
        observed = [lookup[pid, pos] for pid in ids if (pid, pos) in lookup]
        eligible = [p for p in players if (p["appearances"].get(pos) or 0) >= 10]
        eligible_lines = [
            lookup[p["id"].removeprefix("lahman:"), pos]
            for p in eligible
            if (p["id"].removeprefix("lahman:"), pos) in lookup
        ]
        coverage[pos] = {
            "recordedPlayers": len(observed),
            "eligiblePlayers": len(eligible),
            "eligibleMissingRecord": len(eligible) - len(eligible_lines),
            "eligibleMissingCore": sum(r.chances is None for r in eligible_lines),
            "eligibleMissingInnings": sum(r.counts["InnOuts"] is None for r in eligible_lines),
            "games": distribution(r.counts["G"] for r in eligible_lines),
            "innings": distribution(
                r.counts["InnOuts"] / 3 if r.counts["InnOuts"] is not None else None
                for r in eligible_lines
            ),
            "eligibleAtLeastInnings": {
                str(n): sum(
                    r.counts["InnOuts"] is not None and r.counts["InnOuts"] >= n * 3
                    for r in eligible_lines
                )
                for n in (50, 100, 300, 600)
            },
            "eligibleMultiTeam": sum(len(r.teams) > 1 for r in eligible_lines),
            "eligibleGamesMismatch": sum(
                lookup[p["id"].removeprefix("lahman:"), pos].counts["G"] != p["appearances"][pos]
                for p in eligible
                if (p["id"].removeprefix("lahman:"), pos) in lookup
            ),
            "baselineErrorRate": float(baselines[pos]),
        }
        for p in players:
            pid = p["id"].removeprefix("lahman:")
            line = lookup.get((pid, pos))
            if line is not None and (p["appearances"].get(pos) or 0) >= 10:
                examples.append(
                    {
                        "playerId": p["id"],
                        "name": p["name"],
                        "position": pos,
                        "counts": line.counts,
                        "chances": line.chances,
                        "teams": line.teams,
                        "rows": line.rows,
                        "experimental": error_experiment(line, baselines[pos]),
                        "rangeFactorPer9": ratio(
                            total(line.counts[k] for k in ("PO", "A")),
                            line.counts["InnOuts"] / 27 if line.counts["InnOuts"] else None,
                        ),
                        "caughtStealingRate": ratio(
                            line.counts["CS"], total(line.counts[k] for k in ("CS", "SB"))
                        )
                        if pos == "C"
                        else None,
                    }
                )
    field_counts = Counter(
        sum((p["appearances"].get(pos) or 0) >= 10 for pos in POSITIONS) for p in players
    )
    true_dh = [
        p["name"]
        for p in players
        if not any((p["appearances"].get(pos) or 0) > 0 for pos in POSITIONS)
    ]
    return {
        "positions": coverage,
        "eligibleFieldingPositionCounts": dict(sorted(field_counts.items())),
        "noRecordedFielding": sorted(true_dh),
        "playerPositionRecords": examples,
    }


def contact_event(row):
    if row["single"] == "1":
        return "single"
    if row["double"] == "1":
        return "double"
    if row["ab"] == "1" and all(row[k] == "0" for k in ("single", "double", "triple", "hr", "k")):
        return "otherContact"
    return None


def play_flags(row):
    outs = int(row["outs_pre"])
    mask = sum(1 << (i - 1) for i in range(1, 4) if row[f"br{i}_pre"])
    opportunity = outs < 2 and bool(mask & 1)
    if outs not in (0, 1, 2) or row["dpopp"] not in ("0", "1"):
        raise DataError("Invalid Retrosheet pre-play state/opportunity flag")
    return outs, mask, opportunity


def retrosheet_audit(directory: Path, model):
    """Inspect only existing 2022/23 training plays, never acquire holdout plays."""
    provenance = retrosheet.verify(directory)
    cells = {(c["event"], c["outs"], c["baseMask"]): c for c in model["cells"]}
    counts, cell_counts, reasons = Counter(), Counter(), Counter()
    first_fielders, hit_types = Counter(), Counter()
    expected_tickets = 0
    for year in retrosheet.source_lock()["trainingYears"]:
        for row in retrosheet.zip_rows(
            directory, f"{year}plays.zip", f"{year}plays.csv", headers=True
        ):
            if row["gametype"] != "regular" or row["pbp"] != "full" or int(row["inning"]) > 8:
                continue
            if row["pa"] != "1" or row["sh"] != "0" or row["sf"] != "0":
                continue
            outs, mask, opp = play_flags(row)
            event = contact_event(row)
            counts["pa"] += 1
            counts["stateOpportunity"] += opp
            counts["reportedDpopp"] += row["dpopp"] == "1"
            counts["dpoppStateMismatch"] += int(row["dpopp"]) != int(opp)
            counts["dpoppGroundMismatch"] += int(row["dpopp"]) != int(opp and row["ground"] == "1")
            counts["bip"] += row["bip"] == "1"
            counts["ground"] += row["ground"] == "1"
            counts["gdp"] += row["gdp"] == "1"
            counts["eligibleGround"] += opp and row["ground"] == "1"
            counts["eligibleOtherContact"] += opp and event == "otherContact"
            counts["otherContact"] += event == "otherContact"
            counts["eligibleOtherContactGround"] += (
                opp and event == "otherContact" and row["ground"] == "1"
            )
            if row["bip"] == "1":
                hit_types[row["hittype"] or "unknown"] += 1
                first_fielders[row["firstf"]] += 1
                counts["missingLocation"] += not row["loc"]
                counts["missingFielderId"] += any(not row[f"f{i}"] for i in range(2, 10))
            if event is not None:
                _, reason = supported_transition(row, event, outs, mask)
                reasons[reason] += 1
                cell_counts[event, outs, mask] += 1
                cell = cells[event, outs, mask]
                dp_weight = sum(
                    t["weight"]
                    for t in cell["choices"]
                    if t["destinations"][0] == 0
                    and t["destinations"][1] == 0
                    and event == "otherContact"
                    and opp
                )
                expected_tickets += dp_weight
    for key, n in cell_counts.items():
        if cells[key]["observations"] != n:
            raise DataError("Research denominator differs from frozen M4 fit")
    return {
        "source": provenance,
        "years": retrosheet.source_lock()["trainingYears"],
        "selection": "full regular PA, innings 1-8, no SH/SF; unchanged M4 selection",
        "counts": dict(counts),
        "hitTypes": dict(sorted(hit_types.items())),
        "firstFielders": dict(sorted(first_fielders.items())),
        "classificationCounts": dict(sorted(reasons.items())),
        "expectedGDPOnObservedStates": expected_tickets / 1_000_000,
        "cells": [
            {"event": e, "outs": o, "baseMask": b, "n": n}
            for (e, o, b), n in sorted(cell_counts.items())
        ],
    }


def native_diagnostic(runner: Path, output: Path):
    fixture = ROOT / "crates/baseball-sim/tests/fixtures/season-modern-2024.json"
    if digest(fixture) != FIXTURE_SHA:
        raise DataError("Changed M4 fixture")
    source = json.loads(fixture.read_text("utf-8"))
    source["detail"] = "events"
    path = output / "diagnostic.input.json"
    path.write_bytes(canonical_bytes(source) + b"\n")
    result = subprocess.run(
        [str(runner.resolve()), str(path.resolve())], capture_output=True, check=True, timeout=60
    )
    payload = json.loads(result.stdout)
    (output / "diagnostic.result.json").write_bytes(result.stdout)
    counts, fit_counts, states = Counter(), Counter(), Counter()
    for game in payload["games"]:
        outs, mask = 0, 0
        for play in game["eventLog"]:
            event = play["suppliedEvent"]["kind"]
            opp = outs < 2 and bool(mask & 1)
            for c in [counts, fit_counts] if play["inning"] <= 8 else [counts]:
                c["pa"] += 1
                c["stateOpportunity"] += opp
                c["otherContact"] += event == "otherContact"
                c["eligibleOtherContact"] += opp and event == "otherContact"
                c["gdp"] += event == "otherContact" and play["outsOnPlay"] == 2
            if event == "otherContact" and play["inning"] <= 8:
                states[outs, mask] += 1
            after = play["stateAfter"]
            outs = after["outs"]
            mask = sum(1 << i for i, r in enumerate(after["bases"]) if r is not None)
    return {
        "fixtureSha256": FIXTURE_SHA,
        "runnerSha256": digest(runner),
        "inputSha256": digest(path),
        "resultSha256": digest(output / "diagnostic.result.json"),
        "seed": source["seed"],
        "games": len(payload["games"]),
        "counts": dict(counts),
        "innings1to8Counts": dict(fit_counts),
        "otherContactStates": [
            {"outs": o, "baseMask": b, "n": n} for (o, b), n in sorted(states.items())
        ],
    }


def study(source: Path, retro: Path, publication: Path, output: Path, runner: Path | None):
    provenance = verify_source(source)
    players, manifest = load_publication(publication, ROOT / "infra/d1/migrations")
    if (
        manifest["datasetId"] != DATASET_ID
        or len(players) != 526
        or manifest["metadata"]["source"] != provenance
    ):
        raise DataError("M8C.3 requires the unchanged 526-player pilot")
    tables = {
        t: list(read_table(source, t))
        for t in ("Fielding.csv", "FieldingOFsplit.csv", "Appearances.csv", "Teams.csv")
    }
    people = {r["playerID"] for _, r in read_table(source, "People.csv")}
    teams = {(r["yearID"], r["teamID"], r["lgID"]) for _, r in tables["Teams.csv"]}
    for table in ("Fielding.csv", "FieldingOFsplit.csv", "Appearances.csv"):
        for _, r in tables[table]:
            if r["playerID"] not in people or (r["yearID"], r["teamID"], r["lgID"]) not in teams:
                raise DataError("Orphan defensive identity/team")
    for p in players:
        rows = [
            r
            for _, r in tables["Appearances.csv"]
            if r["yearID"] == 2024 and r["playerID"] == p["id"].removeprefix("lahman:")
        ]
        if p["id"].removeprefix("lahman:") not in people or not rows:
            raise DataError("Publication player missing official identity/appearance")
        if any(
            total(r[field] for r in rows) != p["appearances"][pos]
            for pos, field in POSITION_FIELDS.items()
        ):
            raise DataError("Publication position join differs from official appearances")
    lines = aggregate_fielding(tables)
    team_checks = []
    for _, team in tables["Teams.csv"]:
        if team["yearID"] != 2024 or team["lgID"] not in ("AL", "NL"):
            continue
        records = [
            r
            for _, r in tables["Fielding.csv"]
            if r["yearID"] == 2024 and r["teamID"] == team["teamID"] and r["lgID"] == team["lgID"]
        ]
        errors = total(r["E"] for r in records)
        putouts = total(r["PO"] for r in records)
        if errors != team["E"] or putouts != team["IPouts"]:
            raise DataError("2024 main-table team errors/putouts do not reconcile")
        team_checks.append(
            {
                "teamId": team["teamID"],
                "errors": errors,
                "putouts": putouts,
                "teamDP": team["DP"],
                "fielderDPParticipations": total(r["DP"] for r in records),
            }
        )
    fixture_path = ROOT / "crates/baseball-sim/tests/fixtures/season-modern-2024.json"
    if digest(fixture_path) != FIXTURE_SHA:
        raise DataError("Changed M4 fixture")
    fixture = json.loads(fixture_path.read_text("utf-8"))
    model = fixture["config"]["contextualModel"]
    output.mkdir(parents=True, exist_ok=True)
    body = {
        "schemaVersion": "1.0.0",
        "researchVersion": VERSION,
        "lahman": provenance,
        "datasetId": DATASET_ID,
        "sqlSha256": manifest["sqlSha256"],
        "transitionModelId": model["id"],
        "teamChecks2024": team_checks,
        "tables": {
            t: {
                "rows": len(rows),
                "fields": field_coverage(rows),
                "eras": era_coverage(rows),
                "leagues": sorted({r["lgID"] for _, r in rows}),
                "positions": dict(Counter(r.get("POS", "n/a") for _, r in rows)),
            }
            for t, rows in tables.items()
        },
        "pool": pool_audit(players, lines),
        "retrosheet": retrosheet_audit(retro, model),
    }
    if runner is not None:
        body["nativeDiagnostic"] = native_diagnostic(runner, output)
    body["researchId"] = "sha256:" + hashlib.sha256(canonical_bytes(body)).hexdigest()
    (output / "research.json").write_bytes(canonical_bytes(body) + b"\n")
    return body


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--retrosheet-dir", type=Path, required=True)
    parser.add_argument("--publication-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--runner", type=Path)
    parser.add_argument("--summary-output", type=Path)
    args = parser.parse_args()
    body = study(
        args.source_dir, args.retrosheet_dir, args.publication_dir, args.output_dir, args.runner
    )
    if args.summary_output:
        summary = deepcopy(body)
        summary["pool"].pop("playerPositionRecords")
        for table in summary["tables"].values():
            table.pop("eras")
        summary["fullResearchId"] = summary.pop("researchId")
        args.summary_output.parent.mkdir(parents=True, exist_ok=True)
        args.summary_output.write_bytes(canonical_bytes(summary) + b"\n")
    print(
        json.dumps(
            {"researchId": body["researchId"], "positions": body["pool"]["positions"]}, indent=2
        )
    )


if __name__ == "__main__":
    main()
