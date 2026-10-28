"""M8C.2 reproducible PA/pricing analysis; no simulation probability changes."""

import argparse
import json
import subprocess
import sys
from fractions import Fraction
from pathlib import Path
from statistics import mean

from .draft_catalog import MEASUREMENTS_SHA, measurement_digest
from .pricing import DEFAULT_BUDGET, POLICIES, POLICY_ID, prices, tier_boundaries, value_tier
from .source import DataError, canonical_bytes
from .valuation import (
    ROOT,
    distribution,
    load_fixture,
    load_publication,
    representative,
    research_input,
    sha,
    write,
)

VERSION = "mlb-pricing-pa-study-v1"


def reviewed(publication: Path, research_path: Path):
    research = json.loads(research_path.read_text(encoding="utf-8"))
    if measurement_digest(research) != MEASUREMENTS_SHA:
        raise DataError("Use the reviewed M7A observations")
    players, manifest = load_publication(publication, ROOT / "infra/d1/migrations")
    if (
        research["datasetId"] != manifest["datasetId"]
        or research["sqlSha256"] != manifest["sqlSha256"]
    ):
        raise DataError("Research/publication mismatch")
    records = {r["id"]: r for r in research["records"]}
    if set(records) != {p["id"] for p in players}:
        raise DataError("Research membership mismatch")
    for p in players:
        r = records[p["id"]]
        if r["profileId"] != p["profile"]["id"] or r["pa"] != p["pa"]:
            raise DataError("Research profile/sample mismatch")
    values = {
        pid: Fraction(sum(r["marginalReplicateTeamRuns"]), len(r["marginalReplicateTeamRuns"]))
        for pid, r in records.items()
    }
    return players, manifest, values


def measure_pa(players, fixture, reference, runner: Path, output: Path, reuse: bool):
    observations = {}
    runner_sha = sha(runner.read_bytes())
    for i, p in enumerate(players):
        rows = []
        for seed in ("0", "1"):
            input_data = research_input(fixture, p, reference, "marginal")
            input_data["seed"] = seed
            encoded = canonical_bytes(input_data)
            cache = output / "native" / f"{p['id'].replace(':', '-')}-{seed}.json"
            key = {
                "studyVersion": VERSION,
                "inputSha256": sha(encoded),
                "runnerSha256": runner_sha,
                "seed": seed,
            }
            if reuse and cache.exists():
                stored = json.loads(cache.read_text(encoding="utf-8"))
                if stored["key"] != key or stored["rowSha256"] != sha(
                    canonical_bytes(stored["row"])
                ):
                    raise DataError(
                        "PA measurement cache differs from inputs/runner or was modified"
                    )
                row = stored["row"]
            else:
                input_path = cache.with_suffix(".input.json")
                write(input_path, input_data)
                completed = subprocess.run(
                    [str(runner.resolve()), str(input_path.resolve())],
                    capture_output=True,
                    check=True,
                )
                result = json.loads(completed.stdout)
                if (
                    result["input"] != input_data
                    or result["engineVersion"] != "0.4.0"
                    or result["wins"] + result["losses"] != 162
                ):
                    raise DataError("Native PA measurement returned incompatible inputs/result")
                candidate = next(
                    b for b in result["team"]["batters"] if b["batterId"] == "research:batter-4"
                )
                row = {
                    "seed": seed,
                    "pa": candidate["stats"]["plateAppearances"],
                    "runsScored": result["runsScored"],
                }
                write(cache, {"key": key, "row": row, "rowSha256": sha(canonical_bytes(row))})
            if row["seed"] != seed or type(row["pa"]) is not int or row["pa"] <= 0:
                raise DataError("Invalid measured candidate PA")
            rows.append(row)
        observations[p["id"]] = rows
        if (i + 1) % 50 == 0:
            print(f"Measured candidate PA: {i + 1}/{len(players)}", flush=True)
    return observations


def summarize(players, values, observations, manifest, runner):
    boundaries = tier_boundaries(values)
    quotes = {policy: prices(values, players, policy) for policy in POLICIES}
    records = []
    for p in players:
        samples = observations[p["id"]]
        records.append(
            {
                "id": p["id"],
                "name": p["name"],
                "profileId": p["profile"]["id"],
                "historicalPa": p["pa"],
                "value": float(values[p["id"]]),
                "tier": value_tier(values[p["id"]], boundaries),
                "playerBlendWeight": p["playerBlendWeight"],
                "rawComparableDirectOnBaseMass": p["rawComparableDirectOnBaseMass"],
                "preparedDirectOnBaseMass": p["preparedDirectOnBaseMass"],
                "simulatedPa": samples,
                "meanSimulatedPa": mean(r["pa"] for r in samples),
                "prices": {policy: quotes[policy][p["id"]] for policy in POLICIES},
            }
        )
    bands = []
    for low, high in ((50, 99), (100, 199), (200, 399), (400, 599), (600, 10000)):
        group = [r for r in records if low <= r["historicalPa"] <= high]
        bands.append(
            {
                "band": f"{low}-{high}" if low < 600 else "600+",
                "count": len(group),
                **{
                    field: distribution([r[field] for r in group])
                    for field in ("historicalPa", "value", "playerBlendWeight", "meanSimulatedPa")
                },
                "exposureRatio": distribution(
                    [r["meanSimulatedPa"] / r["historicalPa"] for r in group]
                ),
                "prices": {
                    policy: distribution([r["prices"][policy] for r in group])
                    for policy in POLICIES
                },
                "outliers": sorted(group, key=lambda r: (-r["value"], r["id"]))[:3],
            }
        )
    tiers = [
        {
            "tier": tier,
            "count": sum(r["tier"] == tier for r in records),
            "prices": {
                policy: distribution([r["prices"][policy] for r in records if r["tier"] == tier])
                for policy in POLICIES
            },
        }
        for tier in ("low", "middle", "aboveAverage", "elite")
    ]
    return {
        "schemaVersion": "1.0.0",
        "studyVersion": VERSION,
        "datasetId": manifest["datasetId"],
        "sourceSqlSha256": manifest["sqlSha256"],
        "measurementSha256": MEASUREMENTS_SHA,
        "runnerSha256": sha(runner.read_bytes()),
        "engineVersion": "0.4.0",
        "fixtureSha256": sha(
            (ROOT / "crates/baseball-sim/tests/fixtures/season-modern-2024.json").read_bytes()
        ),
        "method": (
            "Candidate in batting slot five; other eight reference templates; fixed CHA opponent; "
            "two seeds 0 and 1. Conditional usage experiment, "
            "not historical availability or forecasting."
        ),
        "tierBoundaries": {k: float(v) for k, v in boundaries.items()},
        "tiers": tiers,
        "bands": bands,
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publication-dir", type=Path, required=True)
    parser.add_argument("--research", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--runner",
        type=Path,
        default=ROOT
        / "target/release/examples"
        / ("season.exe" if sys.platform == "win32" else "season"),
    )
    parser.add_argument("--reuse-native", action="store_true")
    parser.add_argument("--draft-study", type=Path)
    parser.add_argument("--summary-output", type=Path)
    args = parser.parse_args()
    try:
        if bool(args.draft_study) != bool(args.summary_output):
            raise DataError("Supply both --draft-study and --summary-output")
        players, manifest, values = reviewed(args.publication_dir, args.research)
        fixture = load_fixture(
            ROOT / "crates/baseball-sim/tests/fixtures/season-modern-2024.json",
            manifest["metadata"],
        )
        reference = representative(players, fixture)
        observations = measure_pa(
            players, fixture, reference, args.runner, args.output_dir, args.reuse_native
        )
        result = summarize(players, values, observations, manifest, args.runner)
        write(args.output_dir / "pa-pricing.json", result)
        if args.draft_study:
            drafts = json.loads(args.draft_study.read_text(encoding="utf-8"))
            catalog = json.loads(
                (ROOT / "data/publications/mlb-draft-2024-v2.json").read_text(encoding="utf-8")
            )
            write(args.summary_output, compact_summary(result, drafts, catalog))
        print(f"Wrote {args.output_dir / 'pa-pricing.json'}")
        return 0
    except (DataError, OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f"pricing study: {error}", file=sys.stderr)
        return 2


PRICING_ENGINE_SHA = "38c8a68ba2c1bc9876b69107ddf44e25ad22781d5c1d8b4bdb792cf5792f082a"


def pricing_engine_source() -> bytes:
    source = (ROOT / "data/research/pricing-draft-engine-v1.ts").read_bytes()
    if sha(source) != PRICING_ENGINE_SHA:
        raise DataError("Historical pricing engine integrity mismatch")
    return source


def compact_summary(pa: dict, drafts: dict, catalog: dict) -> dict:
    if (
        drafts["datasetId"] != pa["datasetId"]
        or drafts["measurementSha256"] != pa["measurementSha256"]
        or drafts["paStudySha256"] != sha(canonical_bytes(pa))
        or drafts["engineSourceSha256"] != sha(pricing_engine_source())
        or catalog["datasetId"] != pa["datasetId"]
        or catalog["defaultBudget"] != DEFAULT_BUDGET
        or catalog["pricingPolicy"] != POLICY_ID
        or catalog["sourceSqlSha256"] != pa["sourceSqlSha256"]
        or catalog["researchMeasurementSha256"] != MEASUREMENTS_SHA
    ):
        raise DataError("Summary inputs differ from the measured pricing/game versions")
    measured = {r["id"]: r for r in pa["records"]}
    if set(measured) != {p["id"] for p in catalog["players"]} or any(
        p["profileId"] != measured[p["id"]]["profileId"]
        or p["pa"] != measured[p["id"]]["historicalPa"]
        or p["price"] != measured[p["id"]]["prices"]["elite"]
        or p["valueTier"] != measured[p["id"]]["tier"]
        for p in catalog["players"]
    ):
        raise DataError("Published currency/profile identities differ from measured policies")
    expected = {
        (p, b, a)
        for p in POLICIES
        for b in (65, 70, 75, 90)
        for a in ("first", "cheapest", "price-max", "value-tier")
    }
    cases = drafts["cases"]
    if (
        {(r["policy"], r["budget"], r["agent"]) for r in cases} != expected
        or len(cases) != len(expected)
        or any(r["completed"] != r["trials"] or r["trials"] < 100 for r in cases)
        or drafts["totalDrafts"] != sum(r["completed"] for r in cases)
    ):
        raise DataError("All pricing/budget/agent cases require at least 100 completed trials")
    columns = [
        "policy",
        "budget",
        "agent",
        "trials",
        "minimumCost",
        "meanCost",
        "medianCost",
        "medianRemaining",
        "meanOffers",
        "oneChoiceRoundPct",
        "meanElitePicks",
        "draftsWithElitePct",
        "meanLowPaPicks",
        "meanValueIndex",
        "distinctRosters",
        "distinctPlayers",
        "medianInitialMs",
        "p95InitialMs",
        "medianSelectionMs",
        "p95SelectionMs",
        "medianTotalMs",
        "p95TotalMs",
        "selectedLow",
        "selectedMiddle",
        "selectedAboveAverage",
        "selectedElite",
        "meanRemaining",
        "valueIndexP25",
        "valueIndexMedian",
        "valueIndexP75",
    ]
    rows = [
        [
            c["policy"],
            c["budget"],
            c["agent"],
            c["trials"],
            c["minimumCost"],
            round(c["cost"]["mean"], 3),
            c["cost"]["median"],
            c["remaining"]["median"],
            round(c["meanSelectableOffers"], 4),
            round(100 * c["oneChoiceRoundRate"], 3),
            c["elitePlayersPerDraft"]["mean"],
            round(100 * c["draftsWithEliteRate"], 4),
            c["lowPaPlayersPerDraft"]["mean"],
            round(c["meanMarginalValueIndex"]["mean"], 4),
            c["distinctRosters"],
            c["distinctPickedPlayers"],
            *[
                round(c["timings"][field][metric], 4)
                for field in ("initializationAndFirstOfferMs", "selectionMs", "totalComputeMs")
                for metric in ("median", "p95")
            ],
            *[c["selectedTierCounts"][tier] for tier in ("low", "middle", "aboveAverage", "elite")],
            round(c["remaining"]["mean"], 4),
            *[round(c["meanMarginalValueIndex"][metric], 4) for metric in ("p25", "median", "p75")],
        ]
        for c in cases
    ]
    example_ids = {
        "lahman:judgeaa01",
        "lahman:ohtansh01",
        "lahman:sotoju01",
        "lahman:troutmi01",
        "lahman:hindsre01",
        "lahman:arandjo01",
    }
    return {
        "schemaVersion": "1.0.0",
        "studyVersion": VERSION,
        "datasetId": pa["datasetId"],
        "sourceSqlSha256": pa["sourceSqlSha256"],
        "measurementSha256": pa["measurementSha256"],
        "runnerSha256": pa["runnerSha256"],
        "fixtureSha256": pa["fixtureSha256"],
        "engineVersion": pa["engineVersion"],
        "paStudySha256": sha(canonical_bytes(pa)),
        "draftStudySha256": sha(canonical_bytes(drafts)),
        "draftEngineSourceSha256": drafts["engineSourceSha256"],
        "nativePaSeasons": 2 * len(pa["records"]),
        "nativePaGames": 2 * 162 * len(pa["records"]),
        "paMethod": pa["method"],
        "paBands": pa["bands"],
        "valueTiers": pa["tiers"],
        "tierBoundaries": pa["tierBoundaries"],
        "priceHistograms": {
            policy: {
                str(n): sum(r["prices"][policy] == n for r in pa["records"]) for n in range(1, 31)
            }
            for policy in POLICIES
        },
        "changedPricesVersusElite": {
            policy: sum(r["prices"][policy] != r["prices"]["elite"] for r in pa["records"])
            for policy in POLICIES
        },
        "totalDrafts": drafts["totalDrafts"],
        "checkedSafeOffers": sum(c["checkedSafeOffers"] for c in cases),
        "draftExperiments": {"columns": columns, "rows": rows},
        "choicesByRound": [
            {
                "policy": c["policy"],
                "budget": c["budget"],
                "agent": c["agent"],
                "countsOneTwoThree": [[r["one"], r["two"], r["three"]] for r in c["choices"]],
            }
            for c in cases
        ],
        "examples": [r for r in pa["records"] if r["id"] in example_ids],
        "selected": {
            "catalogId": catalog["id"],
            "pricingPolicy": POLICY_ID,
            "defaultBudget": DEFAULT_BUDGET,
            "additionalPaAdjustment": "none; retain existing simulation smoothing",
        },
        "limitations": [
            (
                "Two seeds/player in one lineup/opponent context. Usage measurements, "
                "not historical availability or talent confidence intervals."
            ),
            (
                "M7A values have Monte Carlo error. Elite tier uses the 95th-percentile "
                "threshold with ties, not a precise talent ranking."
            ),
            (
                "Fresh matching cache/draft, warmed Node JS/JIT. Timings exclude agent/safety "
                "assertions; not phone/network measurements."
            ),
            (
                "Value index is a mean of marginal estimates, not additive predicted roster runs. "
                "Common seed paths diverge across policies; enjoyment is untested."
            ),
            "Currency changes do not fix availability, calibration, parks, pitching or defense.",
        ],
    }


if __name__ == "__main__":
    raise SystemExit(main())
