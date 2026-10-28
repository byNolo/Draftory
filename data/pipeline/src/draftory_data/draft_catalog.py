"""Publish compact draft metadata from the reviewed M7A measurements, not a new model."""

import argparse
import json
import sys
from fractions import Fraction
from pathlib import Path

from .draft_research import POLICIES, POSITIONS, eligibility, price_quotes
from .pricing import DEFAULT_BUDGET, POLICY_ID, prices, tier_boundaries, value_tier
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


def publish(
    publication: Path, research_path: Path, pricing_policy: str = "m7a-linear-1-20-v1"
) -> dict:
    if pricing_policy not in ("m7a-linear-1-20-v1", POLICY_ID):
        raise DataError("Unsupported catalog pricing policy")
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
    if pricing_policy == POLICY_ID:
        exact_values = {pid: Fraction(value) for pid, value in values.items()}
        body = elite_body(body, exact_values)
    return {"id": identity(body, "draft-catalog"), **body}


def elite_body(legacy_body: dict, values: dict[str, Fraction]) -> dict:
    entries = legacy_body["players"]
    if set(values) != {p["id"] for p in entries}:
        raise DataError("Price values and catalog identities differ")
    quotes_v2 = prices(values, entries, "elite")
    boundaries = tier_boundaries(values)
    return {
        **legacy_body,
        "schemaVersion": "2.0.0",
        "pricingPolicy": POLICY_ID,
        "defaultBudget": DEFAULT_BUDGET,
        "players": [
            {
                **p,
                "price": quotes_v2[p["id"]],
                "valueTier": value_tier(values[p["id"]], boundaries),
            }
            for p in entries
        ],
        "attribution": (
            "SABR Lahman (CC BY-SA 3.0); M8C.2 provisional currency over reviewed "
            "M7A measurements. See docs/DATA_ATTRIBUTION.md."
        ),
    }


def write_catalog(path: Path, catalog: dict) -> None:
    encoded = canonical_bytes(catalog) + b"\n"
    if path.exists() and path.read_bytes() != encoded:
        raise DataError(
            "Immutable catalog already exists with different bytes; choose a new versioned path"
        )
    write(path, catalog)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publication-dir", type=Path, required=True)
    parser.add_argument("--research", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--pricing-policy", choices=("m7a-linear-1-20-v1", POLICY_ID), default="m7a-linear-1-20-v1"
    )
    args = parser.parse_args()
    try:
        catalog = publish(args.publication_dir, args.research, args.pricing_policy)
        write_catalog(args.output, catalog)
        print(f"Published {catalog['id']}: {len(catalog['players'])} players")
        return 0
    except (DataError, OSError, ValueError, KeyError) as error:
        print(f"draft catalog: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
