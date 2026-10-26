"""Offline M4 preparation and repeated native-engine analysis, without runtime deps."""

import argparse
import json
import math
import subprocess
import sys
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from statistics import mean, stdev

from .normalize import Dataset
from .profiles import ProfileRequest, generate_profile
from .retrosheet import RETROSHEET_NOTICE, fetch, game_logs, verify
from .simulation import PreparationPolicy, identity, league_context, prepare_profile
from .source import DataError, canonical_bytes
from .transitions import fit_model

YEARS = (2022, 2023, 2024, 2025)
METRICS = ("runs", "hits", "walks", "strikeouts", "homeRuns", "pa")


def write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(value) + b"\n")


def summarize_targets(games: list[dict]) -> dict:
    teams = defaultdict(
        lambda: {"games": 0, "wins": 0, "losses": 0, "runsAllowed": 0, "totals": Counter()}
    )
    histogram = Counter()
    innings = [[0, 0] for _ in range(9)]
    for game in games:
        for side, team in enumerate(game["teams"]):
            line = teams[team["teamId"]]
            line["games"] += 1
            won = team["stats"]["runs"] > game["teams"][1 - side]["stats"]["runs"]
            line["wins"] += int(won)
            line["losses"] += int(not won)
            line["runsAllowed"] += game["teams"][1 - side]["stats"]["runs"]
            line["totals"].update(team["stats"])
            histogram[team["stats"]["runs"]] += 1
            for i, runs in enumerate(team["lineScore"][:9]):
                if runs is not None:
                    innings[i][0] += runs
                    innings[i][1] += 1
    metrics = {}
    # Game-level clusters retain home/away pairing in descriptive uncertainty.
    for metric in METRICS:
        samples = [sum(t["stats"][metric] for t in g["teams"]) / 2 for g in games]
        metrics[metric] = {
            "mean": mean(samples),
            "clusterSe": stdev(samples) / math.sqrt(len(samples)),
        }
    n = len(games) * 2
    runs = [t["stats"]["runs"] for g in games for t in g["teams"]]
    return {
        "games": len(games),
        "teamGames": n,
        "metrics": metrics,
        "scoreHistogram": dict(sorted(histogram.items())),
        "runSd": stdev(runs),
        "shutoutRate": histogram[0] / n,
        "highScoreRate": sum(v for k, v in histogram.items() if k >= 10) / n,
        "inningTotals": innings,
        "teams": dict(sorted(teams.items())),
        "homeBatsFirstGames": sum(g["homeBatsFirst"] for g in games),
        "extraInningGames": sum(max(len(t["lineScore"]) for t in g["teams"]) > 9 for g in games),
        "shortenedGames": sum(max(len(t["lineScore"]) for t in g["teams"]) < 9 for g in games),
    }


def select_lineup(data: Dataset, year: int, team, logs: list[dict], policy: PreparationPolicy):
    retro = team.facts["teamIDretro"]
    mapping = {}
    active_ids = {s.player_id for s in data.batting if s.year == year}
    for player in data.players:
        if player.player_id not in active_ids:
            continue
        rid = player.facts.get("retroID")
        if rid:
            if rid in mapping:
                raise DataError(f"Ambiguous Retrosheet player crosswalk: {rid}")
            mapping[rid] = player.player_id
    patterns = Counter(tuple(t["lineup"]) for g in logs for t in g["teams"] if t["teamId"] == retro)
    cache = {}

    def historical(pid):
        if pid not in cache:
            cache[pid] = json.loads(
                canonical_bytes(
                    generate_profile(
                        data,
                        ProfileRequest(
                            pid, "aggregate", ("AL", "NL"), year, year, team_id=team.team_id
                        ),
                    )
                )
            )
        return cache[pid]

    def eligible(pid):
        p = historical(pid)
        return (
            p["status"] == "ok" and not p["excludedSeasons"] and p["opportunities"] >= policy.min_pa
        )

    rejected = 0
    for pattern, count in sorted(patterns.items(), key=lambda pair: (-pair[1], pair[0])):
        players = [mapping.get(rid) for rid in pattern]
        if len(set(players)) == 9 and all(pid and eligible(pid) for pid in players):
            example = next(
                g
                for g in logs
                if any(t["teamId"] == retro and tuple(t["lineup"]) == pattern for t in g["teams"])
            )
            return [historical(pid) for pid in players], {
                "kind": "observed-starting-order",
                "occurrences": count,
                "exampleDate": example["date"],
                "sourceRow": example["sourceRow"],
                "rejectedPatterns": rejected,
                "retroPlayerIds": list(pattern),
            }
        rejected += 1
    # Deterministic fallback, labeled distinctly from an observed starting order.
    ids = sorted(
        {s.player_id for s in data.batting if s.team_id == team.team_id and s.year == year}
    )
    eligible_profiles = [historical(pid) for pid in ids if eligible(pid)]
    eligible_profiles.sort(key=lambda p: (-p["opportunities"], p["playerId"]))
    if len(eligible_profiles) < 9:
        raise DataError(f"Fewer than nine complete hitters: {year} {team.team_id}")
    return eligible_profiles[:9], {
        "kind": "reconstructed-pa-descending-order",
        "rejectedPatterns": rejected,
    }


def compatible_opponents(user: dict, teams: list[dict], profiles: dict) -> tuple[list, list]:
    """Fixed orders from different dates cannot put one traded player on both sides."""
    user_ids = {profiles[b["profileId"]]["provenance"]["playerId"] for b in user["lineup"]}
    available, excluded = [], []
    for team in teams:
        if team["id"] == user["id"]:
            continue
        other_ids = {profiles[b["profileId"]]["provenance"]["playerId"] for b in team["lineup"]}
        shared = sorted(user_ids & other_ids)
        if shared:
            excluded.append({"teamId": team["id"], "sharedPlayerIds": shared})
        else:
            available.append(team)
    if not available:
        raise DataError("No opponents have disjoint player identities")
    return available, excluded


def prepare(lahman: Path, retro: Path, output: Path) -> dict:
    provenance = verify(retro)
    model, model_audit = fit_model(retro)  # Training set is fixed in the source lock.
    data = Dataset.load(lahman)
    policy = PreparationPolicy("ordinary-out-proxy-v1")
    targets = {}
    lineup_audits = []
    for year in YEARS:
        logs = game_logs(retro, year)
        targets[str(year)] = summarize_targets(logs)
        subset = replace(data, batting=[s for s in data.batting if s.year == year])
        context = league_context(subset, policy, year, year)
        historical_teams = sorted(
            (t for t in data.teams if t.year == year and t.league_id in ("AL", "NL")),
            key=lambda t: t.facts["teamIDretro"],
        )
        if len(historical_teams) != 30:
            raise DataError("Calibration requires all thirty AL/NL teams")
        teams = []
        team_kinds = {}
        profiles = {}
        for team in historical_teams:
            selected, selection = select_lineup(subset, year, team, logs, policy)
            tid = f"{year}.{team.facts['teamIDretro']}"
            lineup = []
            audits = []
            for p in selected:
                audit = prepare_profile(p, subset, policy, context)
                prepared = deepcopy(audit["preparedProfile"])
                prepared["weights"]["otherContact"] = prepared["weights"]["battedBallOut"]
                prepared["weights"]["battedBallOut"] = 0
                prepared["modelVersion"] = "lahman-contact-adapter-v1"
                prepared["provenance"]["transformationVersion"] = "lahman-contact-adapter-v1"
                prepared["qualityFlags"] = [
                    f for f in prepared["qualityFlags"] if f != "ordinary-out-contact-proxy"
                ]
                prepared["qualityFlags"].append("unresolved-contact-requires-observed-transitions")
                prepared["id"] = identity(
                    {k: v for k, v in prepared.items() if k != "id"}, "prepared"
                )
                profiles[prepared["id"]] = prepared
                lineup.append({"id": f"{tid}:{p['playerId']}", "profileId": prepared["id"]})
                audits.append({"basePreparation": audit, "preparedProfile": prepared})
            if len({p["playerId"] for p in selected}) != 9:
                raise DataError("Historical lineup contains a duplicate player")
            teams.append({"id": tid, "lineup": lineup})
            team_kinds[tid] = (
                "observedFixedLineups"
                if selection["kind"] == "observed-starting-order"
                else "reconstructedFixedLineups"
            )
            observed = targets[str(year)]["teams"][team.facts["teamIDretro"]]
            # Independent source comparison; never silently repair discrepancies.
            comparisons = {
                k: [team.facts[source], observed["totals"][k]]
                for k, source in (
                    ("runs", "R"),
                    ("hits", "H"),
                    ("walks", "BB"),
                    ("strikeouts", "SO"),
                    ("homeRuns", "HR"),
                )
                if team.facts[source] != observed["totals"][k]
            }
            comparisons.update(
                {
                    key: [team.facts[source], observed[field]]
                    for key, source, field in (
                        ("games", "G", "games"),
                        ("wins", "W", "wins"),
                        ("losses", "L", "losses"),
                        ("runsAllowed", "RA", "runsAllowed"),
                    )
                    if team.facts[source] != observed[field]
                }
            )
            lineup_audits.append(
                {
                    "teamId": tid,
                    "lahmanTeamId": team.team_id,
                    "season": year,
                    "selection": selection,
                    "profiles": audits,
                    "sourceComparisons": comparisons,
                }
            )
        inputs = []
        audit_lookup = {a["teamId"]: a for a in lineup_audits}
        for team in teams:
            opponents, exclusions = compatible_opponents(team, teams, profiles)
            audit_lookup[team["id"]]["excludedMatchups"] = exclusions
            value = {
                "schemaVersion": "1.0.0",
                "modelVersion": "round-robin-season-v1",
                "seedDerivationVersion": "splitmix64-index-v1",
                "seed": "20261025",
                "games": 162,
                "detail": "summary",
                "gameSchemaVersion": "1.2.0",
                "rulesVersion": "contextual-nine-inning-v1",
                "config": {
                    "advancementPolicy": "retrosheet-contextual-v1",
                    "maxInnings": 100,
                    "maxPlateAppearances": 10000,
                    "contextualModel": model,
                },
                "pitchingEnvironment": {"contextId": context["id"], "mode": "leagueAverage"},
                "sampling": {"rngVersion": "splitmix64-v1"},
                "userTeam": team,
                "userLineupKind": team_kinds[team["id"]],
                "opponentSetKind": (
                    "observedFixedLineups"
                    if all(team_kinds[t["id"]] == "observedFixedLineups" for t in opponents)
                    else "reconstructedFixedLineups"
                ),
                "opponents": opponents,
                "profiles": [profiles[k] for k in sorted(profiles)],
            }
            inputs.append(value)
        write(output / f"inputs-{year}.json", inputs)
        write(output / f"example-season-{year}.json", inputs[0])
        write(output / f"context-{year}.json", context)
    manifest = {
        "schemaVersion": "1.0.0",
        "lahman": data.provenance,
        "retrosheet": provenance,
        "retrosheetAttribution": RETROSHEET_NOTICE,
        "trainingYears": [2022, 2023],
        "holdoutYears": [2025],
        "developmentValidationYears": [2024],
        "policy": policy.document(),
        "transitionModelId": model["id"],
        "lineupCount": len(lineup_audits),
        "matchupPolicy": "exclude-shared-player-identities-v1",
    }
    write(output / "targets.json", targets)
    write(output / "lineups.json", lineup_audits)
    write(output / "transitions.json", model)
    write(output / "transitions-audit.json", model_audit)
    write(output / "manifest.json", manifest)
    return manifest


def correlation(xs, ys):
    mx, my = mean(xs), mean(ys)
    den = math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
    return None if den == 0 else sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / den


def total_variation(first, second):
    a = {int(k): v for k, v in first.items()}
    b = {int(k): v for k, v in second.items()}
    return (
        sum(
            abs(a.get(k, 0) / sum(a.values()) - b.get(k, 0) / sum(b.values()))
            for k in a.keys() | b.keys()
        )
        / 2
    )


def analyze(rows: list[dict], target: dict) -> dict:
    rows = sorted(rows, key=lambda row: (row["repeat"], row["teamId"]))
    repeats = defaultdict(list)
    for row in rows:
        repeats[row["repeat"]].append(row)
    mapping = {
        "runs": "runs",
        "hits": "hits",
        "walks": "walks",
        "strikeouts": "strikeouts",
        "homeRuns": "homeRuns",
        "pa": "plateAppearances",
    }
    metrics = {}
    for metric, field in mapping.items():
        samples = [
            sum(row["totals"][field] for row in batch) / sum(row["games"] for row in batch)
            for batch in repeats.values()
        ]
        avg = mean(samples)
        sd = stdev(samples) if len(samples) > 1 else 0
        metrics[metric] = {
            "observed": target["metrics"][metric]["mean"],
            "simulated": avg,
            "bias": avg - target["metrics"][metric]["mean"],
            "repeatSd": sd,
            "mc95HalfWidth": 1.96 * sd / math.sqrt(len(samples)),
        }
    histogram = Counter()
    innings = [[0, 0] for _ in range(9)]
    grouped = defaultdict(list)
    for row in rows:
        histogram.update({int(k): v for k, v in row["scoreHistogram"].items()})
        grouped[row["teamId"]].append(row)
        for i, values in enumerate(row["inningTotals"]):
            innings[i][0] += values[0]
            innings[i][1] += values[1]
    n = histogram.total()
    avg_runs = sum(k * v for k, v in histogram.items()) / n
    run_sd = math.sqrt(sum(v * (k - avg_runs) ** 2 for k, v in histogram.items()) / (n - 1))
    team_results = []
    ordered = sorted(
        target["teams"],
        key=lambda t: (target["teams"][t]["totals"]["runs"] / target["teams"][t]["games"], t),
    )
    for team, runs in sorted(grouped.items()):
        tid = team.split(".", 1)[1]
        actual = target["teams"][tid]
        wins = [r["wins"] for r in runs]
        diff = [(r["runsScored"] - r["runsAllowed"]) / r["games"] for r in runs]
        team_results.append(
            {
                "teamId": team,
                "strength": ("weak", "average", "strong")[ordered.index(tid) // 10],
                "observedWins": actual["wins"],
                "observedLosses": actual["losses"],
                "observedRunDifferential": actual["totals"]["runs"] - actual["runsAllowed"],
                "observedRpg": actual["totals"]["runs"] / actual["games"],
                "simulatedRpg": mean(r["runsScored"] / r["games"] for r in runs),
                "meanWins": mean(wins),
                "sdWins": stdev(wins) if len(wins) > 1 else 0,
                "meanRunDifferentialPerGame": mean(diff),
            }
        )
    win_rates = [r["wins"] / r["games"] for r in rows]
    differentials = [(r["runsScored"] - r["runsAllowed"]) / r["games"] for r in rows]
    groups = {
        label: {
            "observedRpg": mean(t["observedRpg"] for t in team_results if t["strength"] == label),
            "simulatedRpg": mean(t["simulatedRpg"] for t in team_results if t["strength"] == label),
        }
        for label in ("weak", "average", "strong")
    }
    return {
        "metrics": metrics,
        "teamGames": n,
        "repetitions": len(repeats),
        "scoreHistogram": dict(sorted(histogram.items())),
        "runSd": run_sd,
        "shutoutRate": histogram[0] / n,
        "highScoreRate": sum(v for k, v in histogram.items() if k >= 10) / n,
        "inningTotals": innings,
        "teams": team_results,
        "strengthGroups": groups,
        "runDifferentialWinRateCorrelation": correlation(differentials, win_rates),
        "meanSeasonSeconds": mean(r["seasonSeconds"] for r in rows),
        "contextDiagnostics": {
            "observedGdpPerGame": (
                sum(t["totals"]["gdp"] for t in target["teams"].values())
                / sum(t["games"] for t in target["teams"].values())
                if all("gdp" in t["totals"] for t in target["teams"].values())
                else None
            ),
            "simulatedGdpPerGame": sum(r["totals"].get("groundedIntoDoublePlays", 0) for r in rows)
            / n,
            "simulatedRoePerGame": sum(r["totals"].get("reachedOnError", 0) for r in rows) / n,
            "simulatedChoicePerGame": sum(r["totals"].get("fieldersChoices", 0) for r in rows) / n,
            "simulatedExtraInningRate": (
                sum(r["extraInningGames"] for r in rows) / n
                if all("extraInningGames" in r for r in rows)
                else None
            ),
        },
    }


def run(inputs: Path, runner: Path, repetitions: int, output: Path) -> dict:
    if not 2 <= repetitions <= 1000:
        raise DataError("Calibration requires 2..1000 repeated seasons")
    targets = json.loads((inputs / "targets.json").read_text("utf-8"))
    results = {}
    engine_versions = set()
    for year in YEARS:
        results[str(year)] = {}
        for mode in ("baseline", "contextual"):
            process = subprocess.run(
                [
                    str(runner.resolve()),
                    str((inputs / f"inputs-{year}.json").resolve()),
                    str(repetitions),
                    mode,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if process.returncode:
                raise DataError(f"Rust calibration failed ({year} {mode}): {process.stderr}")
            rows = [json.loads(line) for line in process.stdout.splitlines()]
            if len(rows) != 30 * repetitions:
                raise DataError("Rust batch omitted a team or repetition")
            expected = {
                (repeat, f"{year}.{team}")
                for repeat in range(repetitions)
                for team in targets[str(year)]["teams"]
            }
            keys = [(row["repeat"], row["teamId"]) for row in rows]
            if len(set(keys)) != len(keys) or set(keys) != expected:
                raise DataError("Rust batch duplicated or substituted a team/repetition")
            engine_versions.update(row.get("engineVersion") for row in rows)
            if None in engine_versions or len(engine_versions) != 1:
                raise DataError("Missing or mixed native engine versions; rebuild the runner")
            write(output / f"rows-{year}-{mode}.json", rows)
            results[str(year)][mode] = analyze(rows, targets[str(year)])
            rpg = results[str(year)][mode]["metrics"]["runs"]["simulated"]
            print(f"{year} {mode}: RPG={rpg:.4f}", file=sys.stderr)
    bands = {}
    for metric in METRICS:
        a, b = (targets[str(y)]["metrics"][metric] for y in (2022, 2023))
        bands[metric] = max(
            abs(a["mean"] - b["mean"]), 1.96 * math.sqrt(a["clusterSe"] ** 2 + b["clusterSe"] ** 2)
        )
    tv_band = total_variation(targets["2022"]["scoreHistogram"], targets["2023"]["scoreHistogram"])
    for year in YEARS:
        for mode in ("baseline", "contextual"):
            result = results[str(year)][mode]
            tv = total_variation(result["scoreHistogram"], targets[str(year)]["scoreHistogram"])
            result["diagnostics"] = {
                "meanBands": bands,
                "meanPass": {m: abs(result["metrics"][m]["bias"]) <= bands[m] for m in METRICS},
                "scoreTotalVariation": tv,
                "scoreTvBand": tv_band,
                "scoreTvPass": tv <= tv_band,
            }
    report = {
        "schemaVersion": "1.0.0",
        "engineVersion": next(iter(engine_versions)),
        "manifest": json.loads((inputs / "manifest.json").read_text()),
        "repetitions": repetitions,
        "results": results,
    }
    write(output / "calibration.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m draftory_data.calibration")
    commands = parser.add_subparsers(dest="command", required=True)
    acquire = commands.add_parser("fetch")
    acquire.add_argument("--retrosheet-dir", type=Path, required=True)
    prep = commands.add_parser("prepare")
    prep.add_argument("--source-dir", type=Path, required=True)
    prep.add_argument("--retrosheet-dir", type=Path, required=True)
    prep.add_argument("--output-dir", type=Path, required=True)
    batch = commands.add_parser("run")
    batch.add_argument("--input-dir", type=Path, required=True)
    batch.add_argument("--runner", type=Path, required=True)
    batch.add_argument("--repetitions", type=int, default=20)
    batch.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "fetch":
            result = fetch(args.retrosheet_dir)
        elif args.command == "prepare":
            result = prepare(args.source_dir, args.retrosheet_dir, args.output_dir)
        else:
            result = run(args.input_dir, args.runner, args.repetitions, args.output_dir)
        print(
            canonical_bytes(
                {
                    "command": args.command,
                    "status": "ok",
                    "artifactId": identity(result, "artifact"),
                }
            ).decode()
        )
        return 0
    except (DataError, OSError, ValueError) as error:
        print(f"draftory calibration: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
