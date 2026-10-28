"""Reproducible 2024 representative opponents from the unchanged MLB publication."""

import argparse
import json
from collections import defaultdict
from pathlib import Path

from .defense_research import DATASET_ID
from .simulation import identity
from .source import DataError, canonical_bytes, digest, verify_source
from .tables import read_table
from .valuation import FIXTURE_SHA, ROOT, load_publication

TEAM_IDS = ("ARI", "BAL", "BOS", "CHA", "HOU", "LAN", "MIL", "NYA", "PHI")
SELECTION = "team-pa-ranked-nine-full-season-profiles-v1"


def select_players(players, batting, team_id):
    """Sum distinct stints once; rank membership PA, not prices or simulated wins."""
    totals = defaultdict(int)
    seen = set()
    for row_number, row in batting:
        if row["yearID"] != 2024 or row["teamID"] != team_id:
            continue
        key = (row["playerID"], row["stint"], team_id)
        if key in seen:
            raise DataError("Duplicate team batting stint")
        seen.add(key)
        counts = [row[k] for k in ("AB", "BB", "HBP", "SH", "SF")]
        if any(n is None or n < 0 for n in counts):
            raise DataError(f"Incomplete team PA at row {row_number}")
        totals["lahman:" + row["playerID"]] += sum(counts)
    available = {p["id"]: p for p in players}
    ranked = sorted(
        (pid for pid, pa in totals.items() if pa > 0 and pid in available),
        key=lambda pid: (-totals[pid], pid),
    )
    if len(ranked) < 9:
        raise DataError("Fewer than nine verified published team members")
    return [(available[pid], totals[pid]) for pid in ranked[:9]]


def prepare(source, publication, output):
    provenance = verify_source(source)
    players, manifest = load_publication(publication, ROOT / "infra/d1/migrations")
    if manifest["datasetId"] != DATASET_ID or manifest["metadata"]["source"] != provenance:
        raise DataError("Opponent source/publication mismatch")
    fixture = ROOT / "crates/baseball-sim/tests/fixtures/season-modern-2024.json"
    if digest(fixture) != FIXTURE_SHA:
        raise DataError("Changed legacy context fixture")
    context = json.loads(fixture.read_text("utf-8"))
    batting = [(i, r) for i, r in read_table(source, "Batting.csv") if r["yearID"] == 2024]
    teams = {r["teamID"]: r for _, r in read_table(source, "Teams.csv") if r["yearID"] == 2024}
    opponents, profiles = [], {}
    for tid in TEAM_IDS:
        selected = select_players(players, batting, tid)
        team = teams[tid]
        team_id = f"representative:2024:{tid}"
        lineup = []
        for player, pa in selected:
            p = player["profile"]
            profiles[p["id"]] = p
            lineup.append(
                {
                    "id": f"{team_id}:{player['id']}",
                    "profileId": p["id"],
                    "playerId": player["id"],
                    "name": player["name"],
                    "teamPa": pa,
                }
            )
        opponents.append(
            {
                "id": team_id,
                "sourceTeamId": tid,
                "name": team["name"],
                "abbreviation": team["teamIDBR"],
                "year": 2024,
                "lineup": lineup,
            }
        )
    metadata = manifest["metadata"]
    body = {
        "schemaVersion": "1.0.0",
        "selectionVersion": SELECTION,
        "year": 2024,
        "datasetId": DATASET_ID,
        "sourceId": metadata["sourceId"],
        "source": provenance,
        "sourceSqlSha256": manifest["sqlSha256"],
        "policyId": metadata["policy"]["id"],
        "contextId": metadata["context"]["id"],
        "transitionModelId": context["config"]["contextualModel"]["id"],
        "engineVersion": "0.4.0",
        "scheduleVersion": "round-robin-season-v1",
        "scheduleLabel": "Synthetic Draftory schedule",
        "opponentSetKind": "reconstructedFixedLineups",
        "opponents": opponents,
        "profiles": [profiles[k] for k in sorted(profiles)],
        "attribution": (
            "SABR Lahman 2025; Sean Lahman, Bryan Walko and contributors. "
            "CC BY-SA 3.0. See docs/DATA_ATTRIBUTION.md."
        ),
    }
    result = {"id": identity(body, "opponents"), **body}
    encoded = canonical_bytes(result) + b"\n"
    if output.exists() and output.read_bytes() != encoded:
        raise DataError("Refusing to replace an immutable opponent publication")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(encoded)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=ROOT / "data/raw/lahman-2025")
    parser.add_argument("--publication-dir", type=Path, default=ROOT / "data/processed/d1-2024")
    parser.add_argument(
        "--output", type=Path, default=ROOT / "data/publications/opponents-2024-v1.json"
    )
    args = parser.parse_args()
    result = prepare(args.source_dir, args.publication_dir, args.output)
    print(
        json.dumps(
            {
                "id": result["id"],
                "teams": len(result["opponents"]),
                "profiles": len(result["profiles"]),
            }
        )
    )


if __name__ == "__main__":
    main()
