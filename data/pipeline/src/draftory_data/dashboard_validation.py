"""Offline M8C.5 payload/measurement collection; never fits or deploys anything."""

import argparse
import gzip
import json
import subprocess
import sys
from statistics import median

from .source import canonical_bytes
from .valuation import ROOT


def evaluate_larger_pool():
    from .opponents import select_players
    from .source import verify_source
    from .tables import read_table
    from .valuation import load_publication

    source = ROOT / "data/raw/lahman-2025"
    verify_source(source)
    players, _ = load_publication(ROOT / "data/processed/d1-2024", ROOT / "infra/d1/migrations")
    batting = [(i, r) for i, r in read_table(source, "Batting.csv") if r["yearID"] == 2024]
    teams = [
        r
        for _, r in read_table(source, "Teams.csv")
        if r["yearID"] == 2024 and r["teamID"] != "CHA"
    ]
    original = json.loads((ROOT / "data/publications/opponents-2024-v1.json").read_text("utf-8"))
    profiles, opponents = {}, []
    for t in sorted(teams, key=lambda t: t["teamID"]):
        tid = f"representative:2024:{t['teamID']}"
        lineup = []
        for player, pa in select_players(players, batting, t["teamID"]):
            p = player["profile"]
            profiles[p["id"]] = p
            lineup.append(
                {
                    "id": f"{tid}:{player['id']}",
                    "profileId": p["id"],
                    "playerId": player["id"],
                    "name": player["name"],
                    "teamPa": pa,
                }
            )
        opponents.append(
            {
                "id": tid,
                "sourceTeamId": t["teamID"],
                "name": t["name"],
                "abbreviation": t["teamIDBR"],
                "year": 2024,
                "lineup": lineup,
            }
        )
    preview = {**original, "opponents": opponents, "profiles": list(profiles.values())}
    encoded = canonical_bytes(preview)
    # Sizing only: deliberately do not publish a v1 artifact with 29 teams.
    result = {
        "kind": "sizing-only-not-a-publication",
        "excludedClub": "CHA",
        "teams": len(opponents),
        "uniqueProfiles": len(profiles),
        "previewBytes": len(encoded),
        "previewGzipBytes": len(gzip.compress(encoded, compresslevel=6)),
        "existingSchedulerGamesPerOpponent": {"sixGames": 23, "fourGames": 6},
        "decision": (
            "Retain nine balanced opponents; a larger pool needs a reviewed "
            "schedule policy/version."
        ),
    }
    (ROOT / "target/m8c5/larger-pool.json").write_bytes(canonical_bytes(result))
    return result


def spread(values):
    return {"median": median(values), "min": min(values), "max": max(values)}


def measure_native():
    work = ROOT / "target/m8c5"
    work.mkdir(parents=True, exist_ok=True)
    legacy = json.loads((ROOT / "data/fixtures/defense-season-2024-v1.json").read_text("utf-8"))
    defense = legacy["config"].pop("defense")
    legacy.update(
        schemaVersion="1.0.0", gameSchemaVersion="1.2.0", rulesVersion="contextual-nine-inning-v1"
    )
    new = json.loads((ROOT / "data/fixtures/dashboard-season-2024-v1.json").read_text("utf-8"))
    real = json.loads(json.dumps(new))
    real["config"]["defense"] = defense
    real.update(
        schemaVersion="1.1.0",
        gameSchemaVersion="1.3.0",
        rulesVersion="error-avoidance-nine-inning-v1",
    )
    suffix = ".exe" if sys.platform == "win32" else ""
    binary = ROOT / f"target/release/examples/measure_boundary{suffix}"
    season = ROOT / f"target/release/examples/season{suffix}"
    rows = []
    for mode, value, projection in (
        ("legacy-batting", legacy, "batting"),
        ("nine-neutral", new, "dashboard"),
        ("nine-defense", real, "dashboard"),
    ):
        path = work / f"native-{mode}.json"
        path.write_bytes(canonical_bytes(value))
        raw = json.loads(subprocess.check_output([str(binary), str(path), "21", projection]))
        payloads = {}
        for detail in ("summary", "events"):
            value["detail"] = detail
            path.write_bytes(canonical_bytes(value))
            result = json.loads(subprocess.check_output([str(season), str(path)]))
            encoded = canonical_bytes(result)
            payloads[detail] = {
                "bytes": len(encoded),
                "gzipBytes": len(gzip.compress(encoded, compresslevel=6)),
                "wins": result["wins"],
                "losses": result["losses"],
                "runsScored": result["runsScored"],
                "runsAllowed": result["runsAllowed"],
            }
        value["detail"] = "summary"
        path.write_bytes(canonical_bytes(value))
        rows.append(
            {
                "mode": mode,
                "inputBytes": len(canonical_bytes(value)),
                "compactBytes": raw["resultJsonBytes"],
                "full": payloads,
                "firstBoundaryMs": raw["boundaryMs"][0],
                "warmBoundaryMs": spread(raw["boundaryMs"][1:]),
                "warmSimulationMs": spread([s[1] for s in raw["stages"][1:]]),
                "samples": raw,
            }
        )
    (work / "native.json").write_bytes(canonical_bytes(rows) + b"\n")
    return rows


def collect():
    work = ROOT / "target/m8c5"
    browsers = {}
    for path in sorted(work.glob("parity-*.json")):
        modes = json.loads(path.read_text("utf-8"))
        browsers[path.stem.removeprefix("parity-")] = [
            {
                "mode": m["mode"],
                "inputBytes": m["inputBytes"],
                "initializationMs": m["initialization"]["initializationMs"],
                "firstSimulationMs": m["runs"][0]["timings"]["simulationMs"],
                "warmSimulationMs": spread([r["timings"]["simulationMs"] for r in m["runs"][1:]]),
                "warmRoundTripMs": spread([r["roundTripMs"] for r in m["runs"][1:]]),
                "warmResultProcessingMs": spread(
                    [r["timings"]["resultProcessingMs"] for r in m["runs"][1:]]
                ),
                "compactJsonBytes": m["runs"][0]["timings"]["resultJsonBytes"],
                "workerMessageBytes": spread([r["workerMessageBytes"] for r in m["runs"]]),
                "wasmLinearMemoryMaxBytes": max(
                    r["timings"]["wasmMemoryAfterBytes"] for r in m["runs"]
                ),
            }
            for m in modes
        ]
    games = {}
    for path in sorted(work.glob("game-*.json")):
        g = json.loads(path.read_text("utf-8"))
        selective = [
            t
            for t in g["transfers"]
            if "/api/" in t["url"] or "/assets/opponents-2024-" in t["url"]
        ]
        games[path.stem.removeprefix("game-")] = {
            "inputBytes": g["inputBytes"],
            "transferScope": g.get("transferScope", "API-and-opponent-asset-only"),
            "requestCount": len(g["transfers"]),
            "selectiveDataRequests": len(selective),
            "selectiveDataDecodedBytes": sum(t["bytes"] for t in selective),
            "decodedResponseBytes": sum(t["bytes"] for t in g["transfers"]),
            "opponentRequests": sum("/assets/opponents-2024-" in t["url"] for t in g["transfers"]),
            "firstUi": {
                k: g.get("firstUi", {}).get(k) for k in ("assemblyMs", "roundTripMs", "endToEndMs")
            },
            "repeatedUi": {
                k: g.get("repeatedUi", {}).get(k)
                for k in ("assemblyMs", "roundTripMs", "endToEndMs")
            },
        }
    assets = []
    for path in sorted((ROOT / "apps/web/dist/assets").glob("*")):
        data = path.read_bytes()
        assets.append(
            {
                "name": path.name,
                "bytes": len(data),
                "gzipBytes": len(gzip.compress(data, compresslevel=6)),
            }
        )
    result = {
        "schemaVersion": "1.0.0",
        "gzipLevel": 6,
        "timingScope": (
            "Local production assets; fresh worker then five repeats. "
            "No first-WAN-visit or physical-phone claim."
        ),
        "native": json.loads((work / "native.json").read_text("utf-8")),
        "browsers": browsers,
        "gameFlows": games,
        "assets": assets,
        "largerPoolEvaluation": json.loads((work / "larger-pool.json").read_text("utf-8"))
        if (work / "larger-pool.json").exists()
        else None,
    }
    output = ROOT / "data/validation/season-dashboard-v1.json"
    output.write_bytes(canonical_bytes(result) + b"\n")
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--measure-native", action="store_true")
    parser.add_argument("--evaluate-pool", action="store_true")
    args = parser.parse_args()
    if args.measure_native:
        measure_native()
    if args.evaluate_pool:
        evaluate_larger_pool()
    print(collect())


if __name__ == "__main__":
    main()
