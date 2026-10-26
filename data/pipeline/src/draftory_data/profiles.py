"""Descriptive batting rates, not a calibrated simulation/projection model."""

import hashlib
import math
from dataclasses import asdict, dataclass
from statistics import mean, median
from typing import Literal

from .normalize import Counts, Dataset, aggregate_seasons, sum_counts
from .source import DataError, canonical_bytes

SCHEMA_VERSION = "1.0.0"
MODEL_VERSION = "lahman-descriptive-pa/1.0.0"
OUTCOMES = (
    "single",
    "double",
    "triple",
    "homeRun",
    "walk",
    "hitByPitch",
    "strikeout",
    "otherAtBat",
    "sacrificeHit",
    "sacrificeFly",
)
REQUIRED_COUNTS = ("AB", "H", "2B", "3B", "HR", "BB", "HBP", "SO", "SH", "SF")


@dataclass(frozen=True)
class ProfileRequest:
    player_id: str
    method: Literal["aggregate", "season_rate_mean", "season_rate_median"]
    leagues: tuple[str, ...]
    start_year: int | None = None
    end_year: int | None = None
    team_id: str | None = None
    franchise_id: str | None = None
    min_season_pa: int = 1
    min_seasons: int = 1

    def __post_init__(self):
        if self.method not in ("aggregate", "season_rate_mean", "season_rate_median"):
            raise DataError("Unknown aggregation method")
        if not self.leagues or any(not league for league in self.leagues):
            raise DataError("Choose leagues explicitly; no implicit cross-league career pool")
        object.__setattr__(self, "leagues", tuple(sorted(set(self.leagues))))
        if self.team_id and self.franchise_id:
            raise DataError("Choose team_id or franchise_id, not both")
        if self.start_year is not None and self.end_year is not None:
            if self.start_year > self.end_year:
                raise DataError("start_year must not exceed end_year")
        if self.min_season_pa < 1 or self.min_seasons < 1:
            raise DataError("Minimum PA and season counts must be positive")


def pa_count(counts: Counts) -> int | None:
    values = [counts[k] for k in ("AB", "BB", "HBP", "SH", "SF")]
    return None if any(v is None for v in values) else sum(values)


def outcome_counts(counts: Counts) -> dict[str, int] | None:
    if any(counts[k] is None for k in REQUIRED_COUNTS):
        return None
    return dict(
        zip(
            OUTCOMES,
            (
                counts["H"] - counts["2B"] - counts["3B"] - counts["HR"],
                counts["2B"],
                counts["3B"],
                counts["HR"],
                counts["BB"],
                counts["HBP"],
                counts["SO"],
                counts["AB"] - counts["H"] - counts["SO"],
                counts["SH"],
                counts["SF"],
            ),
            strict=True,
        )
    )


def divide(numerator: int | None, denominator: int | None) -> float | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return numerator / denominator


def display_stats(counts: Counts) -> dict[str, float | None]:
    avg = divide(counts["H"], counts["AB"])
    tb = None
    if all(counts[k] is not None for k in ("H", "2B", "3B", "HR")):
        tb = counts["H"] + counts["2B"] + 2 * counts["3B"] + 3 * counts["HR"]
    slg = divide(tb, counts["AB"])
    obp = None
    if all(counts[k] is not None for k in ("H", "BB", "HBP", "AB", "SF")):
        obp = divide(
            counts["H"] + counts["BB"] + counts["HBP"],
            counts["AB"] + counts["BB"] + counts["HBP"] + counts["SF"],
        )
    return {
        "AVG": avg,
        "OBP": obp,
        "SLG": slg,
        "OPS": None if obp is None or slg is None else obp + slg,
    }


def normalize_vector(rates: dict[str, float]) -> tuple[dict[str, float], float]:
    if any(not math.isfinite(v) or v < 0 for v in rates.values()):
        raise DataError("Outcome rates must be finite and nonnegative")
    total = math.fsum(rates.values())
    if total <= 0:
        raise DataError("Outcome rates have no probability mass")
    return {key: value / total for key, value in rates.items()}, total


def generate_profile(dataset: Dataset, request: ProfileRequest) -> dict:
    player_id = request.player_id
    if not player_id.startswith("lahman:"):
        player_id = f"lahman:{player_id}"
    player = next((p for p in dataset.players if p.player_id == player_id), None)
    if player is None:
        raise DataError(f"Unknown player: {request.player_id}")
    known_leagues = {row.league_id for row in dataset.teams}
    if not set(request.leagues) <= known_leagues:
        raise DataError(f"Unknown league filter: {set(request.leagues) - known_leagues}")
    if request.team_id and request.team_id not in {t.team_id for t in dataset.teams}:
        raise DataError(f"Unknown team: {request.team_id}")
    if request.franchise_id and request.franchise_id not in {
        r["franchID"] for r in dataset.franchises
    }:
        raise DataError(f"Unknown franchise: {request.franchise_id}")
    teams = {(t.year, t.team_id, t.league_id): t.franchise_id for t in dataset.teams}
    selected = [
        row
        for row in dataset.batting
        if row.player_id == player_id
        and row.league_id in request.leagues
        and (request.start_year is None or row.year >= request.start_year)
        and (request.end_year is None or row.year <= request.end_year)
        and (request.team_id is None or row.team_id == request.team_id)
        and (
            request.franchise_id is None
            or teams.get((row.year, row.team_id, row.league_id)) == request.franchise_id
        )
    ]
    seasons = aggregate_seasons(selected)
    eligible = []
    excluded = []
    for season in seasons:
        missing = [k for k in REQUIRED_COUNTS if season.counts[k] is None]
        pa = pa_count(season.counts)
        reasons = list(season.quality_flags)
        if missing:
            reasons.append("missing-required-counts:" + ",".join(missing))
        if pa is not None and pa < request.min_season_pa:
            reasons.append("below-requested-minimum-pa")
        if reasons:
            excluded.append(
                {"year": season.year, "reasons": reasons, "sourceRows": season.source_rows}
            )
        else:
            eligible.append(season)
    result = {
        "schemaVersion": SCHEMA_VERSION,
        "producerVersion": "draftory-data/0.2.0",
        "modelVersion": MODEL_VERSION,
        "source": dataset.provenance,
        "playerId": player_id,
        "displayName": player.display_name,
        "request": {**asdict(request), "player_id": player_id},
        "status": "ok" if len(eligible) >= request.min_seasons else "insufficient_data",
        "historicalTotals": sum_counts([s.counts for s in seasons]) if seasons else None,
        "includedTotals": sum_counts([s.counts for s in eligible]) if eligible else None,
        "excludedSeasons": excluded,
        "seasonSamples": [],
        "opportunities": 0,
        "rawOutcomeRates": None,
        "probabilities": None,
        "normalizationFactor": None,
        "pooledDisplayStats": None,
        "qualityFlags": [
            "preliminary-uncalibrated",
            "no-small-sample-smoothing",
            "other-at-bat-is-not-equivalent-to-an-out",
            "sacrifices-require-contextual-model",
            "pa-omits-unrecorded-interference",
        ],
    }
    for season in eligible:
        pa = pa_count(season.counts)
        events = outcome_counts(season.counts)
        if events is None or pa is None or pa <= 0 or sum(events.values()) != pa:
            raise DataError("Invalid complete-season outcome accounting")
        result["seasonSamples"].append(
            {
                "year": season.year,
                "pa": pa,
                "teamIds": season.team_ids,
                "leagueIds": season.league_ids,
                "sourceRows": season.source_rows,
                "rates": {key: value / pa for key, value in events.items()},
            }
        )
    result["opportunities"] = sum(s["pa"] for s in result["seasonSamples"])
    if excluded:
        result["qualityFlags"].append("selected-seasons-excluded-see-reasons")
    if len(eligible) == 1:
        result["qualityFlags"].append("single-season-only")
    if result["status"] == "ok":
        counts = result["includedTotals"]
        if request.method == "aggregate":
            events = outcome_counts(counts)
            raw = {key: value / result["opportunities"] for key, value in events.items()}
        else:
            reducer = mean if request.method == "season_rate_mean" else median
            raw = {
                key: reducer(s["rates"][key] for s in result["seasonSamples"]) for key in OUTCOMES
            }
        if math.fsum(raw.values()) == 0:
            result["status"] = "insufficient_data"
            result["qualityFlags"].append("component-medians-have-zero-mass")
        else:
            probabilities, factor = normalize_vector(raw)
            result.update(
                rawOutcomeRates=raw,
                probabilities=probabilities,
                normalizationFactor=factor,
                pooledDisplayStats=display_stats(counts),
            )
            if request.method == "season_rate_median":
                result["qualityFlags"].append("component-medians-renormalized")
    result["profileId"] = "sha256:" + hashlib.sha256(canonical_bytes(result)).hexdigest()
    return result
