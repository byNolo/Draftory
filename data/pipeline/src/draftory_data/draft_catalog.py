"""Publish compact draft metadata from the reviewed M7A measurements, not a new model."""

import argparse
import json
import sys
from pathlib import Path

from .draft_research import POLICIES, POSITIONS, eligibility, price_quotes
from .simulation import identity
from .source import DataError, canonical_bytes
from .valuation import ROOT, load_publication, sha, write

MEASUREMENTS_SHA = "d450086adca34294ca61c6de5f3e06dca25b875545c5c8ea55c36993540431a6"


def measurement_digest(research: dict) -> str:
    # Exclude host binary hashes, floating SEs and presentation fields. These
    # integer observations/versions must reproduce on native/WASM hosts.
    measured = {
        k: research[k]
        for k in (
            "researchVersion",
            "datasetId",
            "sqlSha256",
            "fixtureSha256",
            "engineVersion",
            "transitionModelId",
            "repetitions",
            "batchSize",
        )
    }
    measured["records"] = [
        {
            k: p[k]
            for k in (
                "id",
                "profileId",
                "pa",
                "appearances",
                "seeds",
                "marginalReplicateTeamRuns",
            )
        }
        for p in sorted(research["records"], key=lambda p: p["id"])
    ]
    return sha(canonical_bytes(measured))


def publish(publication: Path, research_path: Path) -> dict:
    content = research_path.read_bytes()
    research = json.loads(content)
    if measurement_digest(research) != MEASUREMENTS_SHA:
        raise DataError("Use the reviewed M7A research snapshot; new measurements require review")
    players, manifest = load_publication(publication, ROOT / "infra/d1/migrations")
    if (
        research["datasetId"] != manifest["datasetId"]
        or research["sqlSha256"] != manifest["sqlSha256"]
    ):
        raise DataError("Research/publication mismatch")
    rows = {r["id"]: r for r in research["records"]}
    if len(rows) != len(players) or set(rows) != {p["id"] for p in players}:
        raise DataError("Research membership mismatch")
    values = {
        pid: sum(r["marginalReplicateTeamRuns"]) / len(r["marginalReplicateTeamRuns"])
        for pid, r in rows.items()
    }
    quotes = price_quotes(values, {"DH": list(values)}, "linear")
    entries = []
    for p in sorted(players, key=lambda p: p["id"]):
        r = rows[p["id"]]
        if r["profileId"] != p["profile"]["id"] or r["pa"] != p["pa"]:
            raise DataError("Research profile/sample mismatch")
        entries.append(
            {
                "id": p["id"],
                "name": p["name"],
                "profileId": p["profile"]["id"],
                "positions": list(eligibility(p, POLICIES[3])),
                "games": {pos: p["appearances"].get(pos) for pos in POSITIONS},
                "pa": p["pa"],
                "price": quotes[p["id"], "DH"],
            }
        )
    metadata = manifest["metadata"]
    body = {
        "schemaVersion": "1.0.0",
        "datasetId": manifest["datasetId"],
        "year": 2024,
        "sourceId": metadata["sourceId"],
        "profilePolicyId": metadata["policy"]["id"],
        "contextId": metadata["context"]["id"],
        "researchMeasurementSha256": MEASUREMENTS_SHA,
        "pricingPolicy": "m7a-linear-1-20-v1",
        "eligibilityPolicy": "observed-10-universal-dh-v1",
        "sourceSqlSha256": manifest["sqlSha256"],
        "players": entries,
        "attribution": (
            "SABR Lahman (CC BY-SA 3.0); M7A experimental model-derived prices. "
            "See docs/DATA_ATTRIBUTION.md."
        ),
    }
    return {"id": identity(body, "draft-catalog"), **body}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publication-dir", type=Path, required=True)
    parser.add_argument("--research", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        catalog = publish(args.publication_dir, args.research)
        write(args.output, catalog)
        print(f"Published {catalog['id']}: {len(catalog['players'])} players")
        return 0
    except (DataError, OSError, ValueError, KeyError) as error:
        print(f"draft catalog: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
