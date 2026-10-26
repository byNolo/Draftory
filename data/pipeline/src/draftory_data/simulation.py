"""Explicit, lossy research adapter. Never alters descriptive historical profiles."""

import hashlib
import math
from dataclasses import asdict, dataclass
from fractions import Fraction
from typing import Literal

from .normalize import Dataset, aggregate_seasons
from .profiles import (
    OUTCOMES,
    REQUIRED_COUNTS,
    ProfileRequest,
    generate_profile,
    outcome_counts,
    pa_count,
)
from .source import DataError, canonical_bytes

TRANSFORMATION_VERSION = "lahman-pa-adapter-v1"
POLICY_VERSION = "modern-neutral-v1"
WEIGHT_SCALE = 1_000_000
ENGINE_OUTCOMES = (*OUTCOMES[:7], "battedBallOut")


def identity(value: dict, prefix: str) -> str:
    return prefix + ":" + hashlib.sha256(canonical_bytes(value)).hexdigest()


@dataclass(frozen=True)
class PreparationPolicy:
    # Rejection is deliberate: the lossy contact policy requires explicit opt-in.
    contact_policy: Literal["reject", "ordinary-out-proxy-v1"] = "reject"
    min_pa: int = 50
    prior_pa: int = 200
    min_year: int = 2000
    max_year: int = 2025

    def __post_init__(self):
        if self.contact_policy not in ("reject", "ordinary-out-proxy-v1"):
            raise DataError("Unsupported contact approximation")
        for name in ("min_pa", "prior_pa", "min_year", "max_year"):
            if type(getattr(self, name)) is not int:
                raise DataError(f"Policy {name} must be an integer")
        if self.min_pa < 1 or self.prior_pa < 0:
            raise DataError("Minimum PA must be positive and prior PA nonnegative")
        if not 1954 <= self.min_year <= self.max_year <= 2025:
            raise DataError("Supported recorded-season window is 1954..2025")

    def document(self):
        value = {"version": POLICY_VERSION, **asdict(self)}
        return {"id": identity(value, "policy"), **value}


def fractions(rates: dict) -> dict[str, Fraction]:
    if not isinstance(rates, dict) or set(rates) != set(OUTCOMES):
        raise DataError("Require all ten historical outcome categories")
    if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in rates.values()):
        raise DataError("Outcome probabilities must be finite, nonnegative numbers")
    if not math.isclose(math.fsum(rates.values()), 1, abs_tol=1e-12, rel_tol=0):
        raise DataError("Historical probability mass must sum to one")
    values = {k: Fraction(str(v)) for k, v in rates.items()}
    total = sum(values.values())
    return {k: v / total for k, v in values.items()}


def map_outcomes(rates: dict, policy: PreparationPolicy) -> tuple[dict, dict]:
    values = fractions(rates)
    if values["otherAtBat"] and policy.contact_policy == "reject":
        raise DataError(
            "Unresolved otherAtBat: explicitly select ordinary-out-proxy-v1 to approximate"
        )
    excluded = values["sacrificeHit"] + values["sacrificeFly"]
    retained = 1 - excluded
    if retained <= 0:
        raise DataError("No representable non-sacrifice probability mass")
    result = {key: values[key] / retained for key in OUTCOMES[:7]}
    result["battedBallOut"] = values["otherAtBat"] / retained
    audit = {
        "historicalSacrificeHitMass": float(values["sacrificeHit"]),
        "historicalSacrificeFlyMass": float(values["sacrificeFly"]),
        "excludedSacrificeMass": float(excluded),
        "retainedMass": float(retained),
        "conditionalContactProxyMass": float(result["battedBallOut"]),
    }
    return result, audit


def integer_weights(rates: dict[str, Fraction]) -> dict[str, int]:
    """Hamilton/largest remainder; ties follow ENGINE_OUTCOMES, never dict order."""
    if set(rates) != set(ENGINE_OUTCOMES) or any(v < 0 for v in rates.values()):
        raise DataError("Invalid prepared outcome vector")
    total = sum(rates.values())
    if total <= 0:
        raise DataError("Prepared vector has zero mass")
    scaled = [rates[k] * WEIGHT_SCALE / total for k in ENGINE_OUTCOMES]
    weights = [x.numerator // x.denominator for x in scaled]
    order = sorted(range(8), key=lambda i: (-(scaled[i] - weights[i]), i))
    for i in order[: WEIGHT_SCALE - sum(weights)]:
        weights[i] += 1
    return dict(zip(ENGINE_OUTCOMES, weights, strict=True))


def league_context(
    dataset: Dataset, policy: PreparationPolicy, start_year: int, end_year: int
) -> dict:
    if not policy.min_year <= start_year <= end_year <= policy.max_year:
        raise DataError("League context years must be inside the policy window")
    selected = [
        s
        for s in dataset.batting
        if start_year <= s.year <= end_year and s.league_id in ("AL", "NL")
    ]
    counts = dict.fromkeys(OUTCOMES, 0)
    excluded = []
    included = 0
    # Group before checking facts, so a bad traded stint cannot leak a partial season.
    for season in aggregate_seasons(selected):
        events = outcome_counts(season.counts)
        pa = pa_count(season.counts)
        reasons = list(season.quality_flags)
        missing = [key for key in REQUIRED_COUNTS if season.counts[key] is None]
        if missing:
            reasons.append("missing-required-counts:" + ",".join(missing))
        if pa == 0:
            reasons.append("zero-pa")
        if reasons:
            excluded.append(
                {
                    "playerId": season.player_id,
                    "year": season.year,
                    "sourceRows": season.source_rows,
                    "reasons": reasons,
                }
            )
            continue
        if min(events.values()) < 0 or sum(events.values()) != pa:
            raise DataError("Inconsistent league outcome totals")
        included += 1
        for key in OUTCOMES:
            counts[key] += events[key]
    pa = sum(counts.values())
    if pa == 0:
        raise DataError("League context has no complete positive-PA seasons")
    rates = {k: v / pa for k, v in counts.items()}
    mapped, audit = map_outcomes(rates, policy)
    value = {
        "version": "league-average-v1",
        "source": dataset.provenance,
        "startYear": start_year,
        "endYear": end_year,
        "leagues": ["AL", "NL"],
        "policyId": policy.document()["id"],
        "opportunities": pa,
        "includedPlayerSeasons": included,
        "excludedPlayerSeasons": excluded,
        "historicalOutcomeCounts": counts,
        "historicalProbabilities": rates,
        "mappedProbabilities": {k: float(v) for k, v in mapped.items()},
        "mapping": audit,
    }
    return {"id": identity(value, "context"), **value}


def verify_historical_profile(profile: dict, dataset: Dataset) -> None:
    """Reproduce the existing producer, validating structure, facts, rates and hash.

    Avoid a second implementation of the descriptive profile or a runtime schema
    library. The verified source release is required at this offline boundary.
    """
    try:
        request = profile["request"]
        if not isinstance(request, dict):
            raise DataError("Profile request must be an object")
        for key in ("min_season_pa", "min_seasons"):
            if type(request[key]) is not int:
                raise DataError(f"Profile {key} must be an integer")
        for key in ("start_year", "end_year"):
            if request[key] is not None and type(request[key]) is not int:
                raise DataError(f"Profile {key} must be an integer or null")
        if not isinstance(request["leagues"], list) or any(
            not isinstance(x, str) for x in request["leagues"]
        ):
            raise DataError("Profile leagues must be an array of strings")
        regenerated = generate_profile(dataset, ProfileRequest(**request))
        if canonical_bytes(profile) != canonical_bytes(regenerated):
            raise DataError(
                "Historical profile does not match the versioned producer and verified source"
            )
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise DataError(f"Invalid historical profile: {error}") from error


def prepare_profile(
    profile: dict, dataset: Dataset, policy: PreparationPolicy, context: dict
) -> dict:
    verify_historical_profile(profile, dataset)
    if profile["status"] != "ok" or profile["excludedSeasons"]:
        raise DataError("Profile is insufficient or excludes seasons; select a complete year range")
    samples = profile["seasonSamples"]
    if not samples or any(
        not policy.min_year <= s["year"] <= policy.max_year
        or not set(s["leagueIds"]) <= {"AL", "NL"}
        for s in samples
    ):
        raise DataError("Profile seasons must be AL/NL inside the recorded-season policy window")
    # Equal-season summaries do not gain confidence from a different, large season.
    n = (
        profile["opportunities"]
        if profile["request"]["method"] == "aggregate"
        else min(s["pa"] for s in samples)
    )
    if n < policy.min_pa:
        raise DataError(f"Effective sample {n} PA is below minimum {policy.min_pa}")
    if context["policyId"] != policy.document()["id"] or context["source"] != dataset.provenance:
        raise DataError("League context must use the same source and preparation policy")
    # Re-derive its ID to reject accidental tampering, including altered baseline rates.
    if context["id"] != identity({k: v for k, v in context.items() if k != "id"}, "context"):
        raise DataError("League context digest mismatch")
    mapped, audit = map_outcomes(profile["probabilities"], policy)
    baseline, _ = map_outcomes(context["historicalProbabilities"], policy)
    alpha = Fraction(n, n + policy.prior_pa)
    smoothed = {k: alpha * mapped[k] + (1 - alpha) * baseline[k] for k in ENGINE_OUTCOMES}
    weights = integer_weights(smoothed)
    provenance = {
        "playerId": profile["playerId"],
        "sourceProfileId": profile["profileId"],
        "sourceId": identity(dataset.provenance, "source"),
        "transformationVersion": TRANSFORMATION_VERSION,
        "policyId": policy.document()["id"],
        "contextId": context["id"],
    }
    prepared = {
        "modelVersion": TRANSFORMATION_VERSION,
        "sampleOpportunities": profile["opportunities"],
        "weights": weights,
        "qualityFlags": [
            "uncalibrated",
            "conditional-on-no-sacrifice",
            "ordinary-out-contact-proxy"
            if policy.contact_policy == "ordinary-out-proxy-v1"
            else "unresolved-contact-rejected",
            "ibb-included-in-nonintentional-walk",
            "no-era-or-park-adjustment",
            "league-baseline-smoothing" if policy.prior_pa else "no-small-sample-smoothing",
        ],
        "provenance": provenance,
    }
    prepared = {"id": identity(prepared, "prepared"), **prepared}
    return {
        "preparedProfile": prepared,
        "historicalProfile": profile,
        "effectiveSamplePa": n,
        "playerBlendWeight": float(alpha),
        "mapping": audit,
        "mappedProbabilities": {k: float(v) for k, v in mapped.items()},
        "smoothedProbabilities": {k: float(v) for k, v in smoothed.items()},
        "maxRoundingError": max(
            abs(weights[k] / WEIGHT_SCALE - float(smoothed[k])) for k in ENGINE_OUTCOMES
        ),
    }


def prepare_game(
    dataset: Dataset,
    away: list[dict],
    home: list[dict],
    policy: PreparationPolicy,
    context: dict,
    seed: str,
    detail: str = "summary",
) -> tuple[dict, dict]:
    if len(away) != 9 or len(home) != 9:
        raise DataError("Supply exactly nine ordered profiles per team")
    if (
        not isinstance(seed, str)
        or len(seed) > 20
        or not seed.isascii()
        or not seed.isdecimal()
        or str(int(seed)) != seed
        or int(seed) > 2**64 - 1
    ):
        raise DataError("Seed must be a canonical decimal u64 string")
    if detail not in ("summary", "events"):
        raise DataError("Detail must be summary or events")
    audits = {}
    teams = {}
    for side, profiles in (("away", away), ("home", home)):
        lineup = []
        for i, historical in enumerate(profiles):
            # Verify every supplied object, including repeated profile IDs.
            verify_historical_profile(historical, dataset)
            key = historical["profileId"]
            if key not in audits:
                audits[key] = prepare_profile(historical, dataset, policy, context)
            lineup.append(
                {"id": f"{side}-batter-{i + 1}", "profileId": audits[key]["preparedProfile"]["id"]}
            )
        teams[side] = {"id": side, "lineup": lineup}
    value = {
        "schemaVersion": "1.1.0",
        "rulesVersion": "foundation-nine-inning-v1",
        "seed": seed,
        "config": {
            "advancementPolicy": "conservative-outs-v1",
            "maxInnings": 100,
            "maxPlateAppearances": 10000,
        },
        "detail": detail,
        "pitchingEnvironment": {"contextId": context["id"], "mode": "leagueAverage"},
        "sampling": {"rngVersion": "splitmix64-v1"},
        "teams": teams,
        "profiles": [a["preparedProfile"] for a in audits.values()],
    }
    report = {
        "schemaVersion": "1.0.0",
        "transformationVersion": TRANSFORMATION_VERSION,
        "inputId": identity(value, "game"),
        "policy": policy.document(),
        "context": context,
        "profiles": list(audits.values()),
    }
    return value, report
