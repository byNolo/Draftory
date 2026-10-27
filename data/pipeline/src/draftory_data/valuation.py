"""M7A offline research over immutable publications and the unchanged native engine."""

import argparse
import csv
import hashlib
import json
import math
import sqlite3
import subprocess
import sys
from collections import defaultdict
from copy import deepcopy
from pathlib import Path
from statistics import correlation, mean, median, stdev

from .draft_research import (
    POLICIES,
    POSITIONS,
    CompletionCosts,
    eligibility,
    experiment,
    percentile_ranks,
    policy_counts,
    price_quotes,
)
from .normalize import sum_counts
from .profiles import display_stats, pa_count
from .publication import validate_prepared
from .simulation import identity
from .source import DataError, canonical_bytes
from .tables import POSITION_FIELDS

ROOT = Path(__file__).resolve().parents[4]
VERSION = "mlb-valuation-research-v1"
FIXTURE_SHA = "d02959d2673eeeec2951644cf327434babefeddeb1cb5b516d809d3aa8a562a4"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(value) + b"\n")


def load_publication(directory: Path, migrations: Path) -> tuple[list[dict], dict]:
    manifest = json.loads((directory / "manifest.json").read_text("utf-8"))
    sql = (directory / "import.sql").read_bytes()
    if manifest.get("schemaVersion") != "1.0.0" or sha(sql) != manifest.get("sqlSha256"):
        raise DataError("Publication SQL/manifest integrity mismatch")
    with sqlite3.connect(":memory:") as db:
        db.execute("PRAGMA foreign_keys=ON")
        for path in sorted(migrations.glob("[0-9]*.sql")):
            db.executescript(path.read_text("utf-8"))
        db.executescript(sql.decode("utf-8"))
        if db.execute("PRAGMA foreign_key_check").fetchall():
            raise DataError("Publication has invalid references")
        publications = db.execute("SELECT dataset_id FROM mlb_publications").fetchall()
        if publications != [(manifest["datasetId"],)]:
            raise DataError("Expected one complete published dataset")
        metadata = json.loads(db.execute("SELECT metadata_json FROM mlb_datasets").fetchone()[0])
        if metadata != manifest["metadata"] or metadata["year"] != 2024:
            raise DataError("Research requires the unchanged 2024 publication")
        players = []
        for pid, name, payload in db.execute(
            "SELECT m.player_id,p.display_name,v.payload_json FROM mlb_dataset_profiles m "
            "JOIN mlb_profiles v ON v.id=m.profile_id "
            "JOIN mlb_players p ON p.id=m.player_id AND p.source_id=m.source_id ORDER BY m.ordinal"
        ):
            profile = json.loads(payload)
            validate_prepared(profile)
            provenance = profile["provenance"]
            if (
                provenance["playerId"] != pid
                or provenance["sourceId"] != metadata["sourceId"]
                or provenance["contextId"] != metadata["context"]["id"]
                or provenance["policyId"] != metadata["policy"]["id"]
            ):
                raise DataError("Incompatible publication profile")
            stints = [
                json.loads(row[0])
                for row in db.execute(
                    "SELECT counts_json FROM mlb_batting_stints "
                    "WHERE player_id=? ORDER BY stint,team_id",
                    (pid,),
                )
            ]
            if not stints:
                raise DataError("Publication lacks original batting counts")
            counts = sum_counts(stints)
            pa = pa_count(counts)
            if pa is None or pa != profile["sampleOpportunities"]:
                raise DataError("Prepared sample does not match complete season opportunities")
            observations = defaultdict(list)
            for pos, games in db.execute(
                "SELECT position,games FROM mlb_position_appearances WHERE player_id=?", (pid,)
            ):
                if games is not None and (type(games) is not int or games < 0):
                    raise DataError("Invalid position appearance")
                observations[pos].append(games)
            appearances = {
                pos: sum(observations[pos])
                if observations[pos] and all(g is not None for g in observations[pos])
                else None
                for pos in POSITION_FIELDS
            }
            w = profile["weights"]
            players.append(
                {
                    "id": pid,
                    "name": name,
                    "profile": profile,
                    "pa": pa,
                    "appearances": appearances,
                    "stintCount": len(stints),
                    "raw": display_stats(counts),
                    # A model input's direct hit/BB/HBP mass, not a prediction of official OBP:
                    # unresolved contact can subsequently become ROE/FC/multiple outs.
                    "preparedDirectOnBaseMass": sum(
                        w[k]
                        for k in ("single", "double", "triple", "homeRun", "walk", "hitByPitch")
                    )
                    / 1_000_000,
                    "rawComparableDirectOnBaseMass": (counts["H"] + counts["BB"] + counts["HBP"])
                    / (pa - counts["SH"] - counts["SF"]),
                    "playerBlendWeight": pa / (pa + metadata["policy"]["prior_pa"]),
                }
            )
        pools = defaultdict(list)
        for pos, profile_id, games in db.execute(
            "SELECT position,profile_id,games FROM mlb_dataset_positions ORDER BY position,ordinal"
        ):
            pools[pos].append((profile_id, games))
        expected_id = identity(
            {
                "metadata": metadata,
                "profiles": [p["profile"]["id"] for p in players],
                "pools": dict(pools),
            },
            "dataset",
        )
        if expected_id != manifest["datasetId"]:
            raise DataError("Dataset membership/configuration digest mismatch")
    if len(players) != metadata["profileCount"] or len({p["id"] for p in players}) != len(players):
        raise DataError("Publication membership/count mismatch")
    return players, manifest


def load_fixture(path: Path, metadata: dict) -> dict:
    content = path.read_bytes()
    if sha(content) != FIXTURE_SHA:
        raise DataError("Use the pinned, unchanged M4 fixture")
    fixture = json.loads(content)
    if fixture["pitchingEnvironment"]["contextId"] != metadata["context"]["id"]:
        raise DataError("Incompatible league context")
    for profile in fixture["profiles"]:
        validate_prepared(profile)
        if (
            profile["provenance"]["sourceId"] != metadata["sourceId"]
            or profile["provenance"]["policyId"] != metadata["policy"]["id"]
        ):
            raise DataError("Fixture/publication preparation mismatch")
    return fixture


def representative(players: list[dict], fixture: dict) -> dict:
    keys = tuple(players[0]["profile"]["weights"])
    total = sum(p["pa"] for p in players)
    average = {k: sum(p["pa"] * p["profile"]["weights"][k] for p in players) / total for k in keys}
    opponents = {
        p["provenance"]["playerId"]
        for p in fixture["profiles"]
        if p["id"] in {b["profileId"] for t in fixture["opponents"] for b in t["lineup"]}
    }
    # Select an actual prepared hitter nearest the PA-weighted probability vector;
    # do not synthesize a new profile or call this a true league-average player.
    return min(
        (p for p in players if p["id"] not in opponents),
        key=lambda p: (sum(abs(p["profile"]["weights"][k] - average[k]) for k in keys), p["id"]),
    )


def research_input(fixture: dict, player: dict, reference: dict, method: str) -> dict:
    if method not in ("reference", "homogeneous", "marginal"):
        raise DataError("Unknown valuation experiment")
    value = deepcopy(fixture)
    value["userTeam"] = {
        "id": "research:" + player["id"],
        "lineup": [
            {
                "id": f"research:batter-{slot}",
                "profileId": (
                    player["profile"]["id"]
                    if method == "homogeneous" or method == "marginal" and slot == 4
                    else reference["profile"]["id"]
                ),
            }
            for slot in range(9)
        ],
    }
    value["userLineupKind"] = "synthetic"
    # Repeated parameter templates are explicitly synthetic, never legal draft rosters.
    required = {
        b["profileId"] for t in [value["userTeam"], *value["opponents"]] for b in t["lineup"]
    }
    profiles = {p["id"]: p for p in [*fixture["profiles"], player["profile"], reference["profile"]]}
    value["profiles"] = [profiles[key] for key in sorted(required)]
    return value


def native_rows(inputs: list[dict], runner: Path, repeats: int, path: Path, reuse: bool):
    encoded = canonical_bytes(inputs)
    key = identity(
        {
            "inputSha256": sha(encoded),
            "runnerSha256": sha(runner.read_bytes()),
            "repetitions": repeats,
            "researchVersion": VERSION,
        },
        "experiment",
    )
    if reuse and path.exists():
        cached = json.loads(path.read_text("utf-8"))
        if cached["id"] != key:
            raise DataError("Cached experiment differs from requested inputs/engine")
        rows = cached["rows"]
        if cached.get("rowsSha256") != sha(canonical_bytes(rows)):
            raise DataError("Cached native observations failed checksum verification")
    else:
        input_path = path.with_suffix(".input.json")
        write(input_path, inputs)
        completed = subprocess.run(
            [str(runner.resolve()), str(input_path.resolve()), str(repeats), "contextual"],
            capture_output=True,
            text=True,
            check=True,
        )
        rows = [json.loads(line) for line in completed.stdout.splitlines() if line]
        # Timings are diagnostic only and never part of deterministic valuation artifacts.
        for row in rows:
            row.pop("seasonSeconds", None)
    expected = {(item["userTeam"]["id"], repeat) for item in inputs for repeat in range(repeats)}
    if len(rows) != len(expected) or {(r["teamId"], r["repeat"]) for r in rows} != expected:
        raise DataError("Missing or duplicate native observations")
    for row in rows:
        if (
            row["engineVersion"] != "0.4.0"
            or row["seasonModelVersion"] != "round-robin-season-v1"
            or row["rngVersion"] != "splitmix64-v1"
            or row["games"] != 162
            or row["wins"] + row["losses"] != 162
            or row["totals"]["runs"] != row["runsScored"]
        ):
            raise DataError("Unsupported/incomplete native result")
    if not (reuse and path.exists()):
        write(path, {"id": key, "rows": rows, "rowsSha256": sha(canonical_bytes(rows))})
    return {(r["teamId"], r["repeat"]): r for r in rows}


def estimate(samples: list[float]) -> dict:
    if len(samples) < 2 or any(not math.isfinite(v) for v in samples):
        raise DataError("At least two finite native repetitions required")
    return {
        "mean": mean(samples),
        "monteCarloSe": stdev(samples) / math.sqrt(len(samples)),
        "min": min(samples),
        "max": max(samples),
        "repetitions": len(samples),
    }


def value_players(players, fixture, reference, runner, output, repeats, reuse):
    records = []
    for start in range(0, len(players), 30):
        batch = players[start : start + 30]
        measured = {
            method: native_rows(
                [research_input(fixture, p, reference, method) for p in batch],
                runner,
                repeats,
                output / "native" / f"{start:03d}-{method}.json",
                reuse,
            )
            for method in ("reference", "homogeneous", "marginal")
        }
        for player in batch:
            tid = "research:" + player["id"]
            deltas, homogeneous, baseline, seeds = [], [], [], []
            for repeat in range(repeats):
                a, b, c = (
                    measured[m][tid, repeat] for m in ("reference", "homogeneous", "marginal")
                )
                if not a["seed"] == b["seed"] == c["seed"]:
                    raise DataError("Native comparisons must have paired seeds")
                seeds.append(a["seed"])
                baseline.append(a["runsScored"])
                homogeneous.append(b["runsScored"] / 162)
                deltas.append(c["runsScored"] - a["runsScored"])
            records.append(
                {
                    **{k: v for k, v in player.items() if k != "profile"},
                    "profileId": player["profile"]["id"],
                    "seeds": seeds,
                    "marginalReplicateTeamRuns": deltas,
                    "homogeneousRunsPerGame": estimate(homogeneous),
                    "marginalTeamRunsPer162": estimate(deltas),
                    "referenceTeamRunsPer162": estimate(baseline),
                }
            )
        print(
            f"Native valuation: {min(start + 30, len(players))}/{len(players)} profiles", flush=True
        )
    return records


def distribution(values: list[float]) -> dict:
    ordered = sorted(values)
    if not ordered:
        return {"n": 0}
    return {
        "n": len(ordered),
        "min": ordered[0],
        "p25": ordered[(len(ordered) - 1) // 4],
        "median": median(ordered),
        "p75": ordered[3 * (len(ordered) - 1) // 4],
        "max": ordered[-1],
        "mean": mean(ordered),
    }


def rank_correlation(first: dict[str, float], second: dict[str, float]) -> float | None:
    ids = sorted(first)
    if set(first) != set(second):
        raise DataError("Rank comparisons need identical player membership")
    if len(ids) < 2 or len(set(first.values())) < 2 or len(set(second.values())) < 2:
        return None
    return correlation([first[p] for p in ids], [second[p] for p in ids])


def analyze(records: list[dict], trials: int) -> dict:
    values = {r["id"]: r["marginalTeamRunsPer162"]["mean"] for r in records}
    policies, experiments = [], []
    for policy in POLICIES:
        pools = {
            pos: [r["id"] for r in records if pos in eligibility(r, policy)] for pos in POSITIONS
        }
        policy_report = policy_counts(records, policy)
        policy_report["valueByPosition"] = {
            pos: distribution([values[p] for p in ids]) for pos, ids in pools.items()
        }
        policy_report["prices"] = {}
        for curve in ("linear", "elite", "scarcity"):
            quotes = price_quotes(values, pools, curve)
            minimum = CompletionCosts(pools, quotes).minimum(POSITIONS)
            policy_report["prices"][curve] = {
                "byPosition": {
                    pos: distribution([quotes[p, pos] for p in ids]) for pos, ids in pools.items()
                },
                "minimumDistinctLineupCost": minimum[0] if minimum else None,
                "cheapestLineup": minimum[1] if minimum else None,
            }
            if policy.name not in ("games-10-dh-all", "games-20-dh-all"):
                continue
            for budget in (60, 90, 120):
                for offers, selection in (
                    ("global", "greedy"),
                    ("position", "greedy"),
                    ("position", "reserve"),
                    ("tier", "reserve"),
                    ("tier", "protected"),
                ):
                    result = experiment(
                        values,
                        pools,
                        quotes,
                        budget=budget,
                        offers=offers,
                        selection=selection,
                        trials=trials,
                        seed=20261027,
                    )
                    experiments.append({"policy": policy.name, "curve": curve, **result})
        policies.append(policy_report)
    # Small order sensitivity, separately seeded configurations rather than a
    # paired causal estimate. DH-first stresses shared multi-position identities.
    sensitivity = []
    policy = POLICIES[3]
    pools = {pos: [p["id"] for p in records if pos in eligibility(p, policy)] for pos in POSITIONS}
    for order in (
        tuple(sorted(POSITIONS, key=lambda pos: (len(pools[pos]), pos))),
        ("DH", *POSITIONS[:-1]),
    ):
        for offers in ("position", "tier"):
            sensitivity.append(
                experiment(
                    values,
                    pools,
                    price_quotes(values, pools, "linear"),
                    budget=90,
                    offers=offers,
                    selection="reserve",
                    trials=trials,
                    seed=20261027,
                    order=order,
                )
            )
    policy = POLICIES[3]
    pools = {pos: [p["id"] for p in records if pos in eligibility(p, policy)] for pos in POSITIONS}
    quotes = {
        curve: price_quotes(values, pools, curve) for curve in ("linear", "elite", "scarcity")
    }
    for r in records:
        r["eligiblePositions"] = list(eligibility(r, policy))
        r["examplePrices"] = {
            curve: {pos: quote[r["id"], pos] for pos in r["eligiblePositions"]}
            for curve, quote in quotes.items()
        }
    rank_a = percentile_ranks({r["id"]: r["homogeneousRunsPerGame"]["mean"] for r in records})
    rank_b = percentile_ranks(values)
    discordant = sorted(records, key=lambda r: (-abs(rank_a[r["id"]] - rank_b[r["id"]]), r["id"]))[
        :10
    ]
    halves = []
    for side in (0, 1):
        values_half = {}
        for row in records:
            samples = row["marginalReplicateTeamRuns"]
            half = len(samples) // 2
            values_half[row["id"]] = mean(samples[:half] if side == 0 else samples[half:])
        halves.append(percentile_ranks(values_half))
    return {
        "policies": policies,
        "draftExperiments": experiments,
        "orderSensitivity": sensitivity,
        "marginalDistribution": distribution(list(values.values())),
        "homogeneousDistribution": distribution(
            [r["homogeneousRunsPerGame"]["mean"] for r in records]
        ),
        "methodRankCorrelation": rank_correlation(rank_a, rank_b),
        "splitHalfRankCorrelation": rank_correlation(*halves),
        "rankDiscordance": [
            {"id": r["id"], "name": r["name"], "rankGap": rank_a[r["id"]] - rank_b[r["id"]]}
            for r in discordant
        ],
    }


def compact_summary(result: dict) -> dict:
    """Small review artifact; full rankings, seeds and observations stay generated."""
    rows = sorted(result["records"], key=lambda r: (-r["marginalTeamRunsPer162"]["mean"], r["id"]))
    examples = {
        "lahman:judgeaa01",
        "lahman:ohtansh01",
        "lahman:sotoju01",
        "lahman:wittbo02",
        "lahman:bettsmo01",
        "lahman:ramirjo01",
        "lahman:contrwi02",
        "lahman:rutscad01",
        "lahman:raleica01",
        "lahman:troutmi01",
        "lahman:acunaro01",
        result["reference"]["id"],
    }
    ids = examples | {r["id"] for r in rows[:10] + rows[-5:]}
    columns = (
        "policy",
        "curve",
        "budget",
        "offers",
        "selection",
        "simulatedTrials",
        "minimumLineupCost",
        "completed",
        "completionRate",
        "completionWilson95",
        "protectedInsertions",
        "multipleSafeChoiceRate",
        "meanSafeOfferCount",
        "meanSafeValueSpread",
    )
    return {
        **{
            k: result[k]
            for k in (
                "schemaVersion",
                "researchVersion",
                "datasetId",
                "sqlSha256",
                "fixtureSha256",
                "runnerSha256",
                "engineVersion",
                "transitionModelId",
                "reference",
                "repetitions",
                "batchSize",
                "nativeGames",
                "unknownPositionCells",
                "marginalDistribution",
                "homogeneousDistribution",
                "methodRankCorrelation",
                "splitHalfRankCorrelation",
                "rankDiscordance",
                "orderSensitivity",
            )
        },
        "sourceId": result["metadata"]["sourceId"],
        "policyId": result["metadata"]["policy"]["id"],
        "contextId": result["metadata"]["context"]["id"],
        "eligibility": [
            {k: v for k, v in p.items() if k not in ("prices", "valueByPosition")}
            for p in result["policies"]
        ],
        "tenGameValueByPosition": result["policies"][3]["valueByPosition"],
        "tenGamePrices": result["policies"][3]["prices"],
        "examplesAndOutliers": [
            {k: v for k, v in r.items() if k not in ("seeds", "marginalReplicateTeamRuns")}
            for r in rows
            if r["id"] in ids
        ],
        "draftExperiments": {
            "trialsPerConfiguration": result["draftExperiments"][0]["trials"],
            "seed": 20261027,
            "rngVersion": "python-random-mt19937-sha256-config-v1",
            "offerSize": 3,
            "order": list(POSITIONS),
            "columns": list(columns),
            "rows": [[row[k] for k in columns] for row in result["draftExperiments"]],
        },
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publication-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--migrations-dir", type=Path, default=ROOT / "infra/d1/migrations")
    parser.add_argument(
        "--fixture",
        type=Path,
        default=ROOT / "crates/baseball-sim/tests/fixtures/season-modern-2024.json",
    )
    parser.add_argument(
        "--runner",
        type=Path,
        default=ROOT
        / "target/release/examples"
        / ("calibrate.exe" if sys.platform == "win32" else "calibrate"),
    )
    parser.add_argument("--repetitions", type=int, default=8)
    parser.add_argument("--draft-trials", type=int, default=500)
    parser.add_argument("--reuse-native", action="store_true")
    args = parser.parse_args(argv)
    try:
        if not 2 <= args.repetitions <= 1000 or args.draft_trials < 1:
            raise DataError("Require 2..1000 native repetitions and positive draft trials")
        players, manifest = load_publication(args.publication_dir, args.migrations_dir)
        fixture = load_fixture(args.fixture, manifest["metadata"])
        reference = representative(players, fixture)
        records = value_players(
            players,
            fixture,
            reference,
            args.runner,
            args.output_dir,
            args.repetitions,
            args.reuse_native,
        )
        result = analyze(records, args.draft_trials)
        result.update(
            {
                "schemaVersion": "1.0.0",
                "researchVersion": VERSION,
                "datasetId": manifest["datasetId"],
                "sqlSha256": manifest["sqlSha256"],
                "metadata": manifest["metadata"],
                "fixtureSha256": FIXTURE_SHA,
                "runnerSha256": sha(args.runner.read_bytes()),
                "engineVersion": "0.4.0",
                "transitionModelId": fixture["config"]["contextualModel"]["id"],
                "reference": {
                    "id": reference["id"],
                    "name": reference["name"],
                    "profileId": reference["profile"]["id"],
                },
                "repetitions": args.repetitions,
                "batchSize": 30,
                "nativeGames": len(players) * args.repetitions * 3 * 162,
                "unknownPositionCells": sum(
                    v is None for p in players for v in p["appearances"].values()
                ),
                "records": records,
            }
        )
        write(args.output_dir / "research.json", result)
        write(args.output_dir / "summary.json", compact_summary(result))
        fields = (
            "id",
            "name",
            "profileId",
            "pa",
            "playerBlendWeight",
            "rawOps",
            "directOnBaseMass",
            "marginalRuns",
            "marginalSe",
            "homogeneousRpg",
            "positions",
        )
        with (args.output_dir / "rankings.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for r in sorted(records, key=lambda r: (-r["marginalTeamRunsPer162"]["mean"], r["id"])):
                writer.writerow(
                    dict(
                        zip(
                            fields,
                            (
                                r["id"],
                                r["name"],
                                r["profileId"],
                                r["pa"],
                                r["playerBlendWeight"],
                                r["raw"]["OPS"],
                                r["preparedDirectOnBaseMass"],
                                r["marginalTeamRunsPer162"]["mean"],
                                r["marginalTeamRunsPer162"]["monteCarloSe"],
                                r["homogeneousRunsPerGame"]["mean"],
                                "|".join(r["eligiblePositions"]),
                            ),
                            strict=True,
                        )
                    )
                )
        print(
            f"Research complete: {len(records)} profiles; "
            f"{result['nativeGames']} native games; {args.output_dir}"
        )
        return 0
    except (
        DataError,
        OSError,
        ValueError,
        KeyError,
        sqlite3.Error,
        subprocess.CalledProcessError,
    ) as error:
        print(f"valuation research: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
