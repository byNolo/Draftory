"""Deterministic, selected MLB publication. No database/network access at runtime."""

import hashlib
import json
import sqlite3
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

from .normalize import Dataset, aggregate_seasons
from .profiles import ProfileRequest, generate_profile
from .simulation import PreparationPolicy, identity, league_context, prepare_profile
from .source import DataError, canonical_bytes, source_lock
from .tables import POSITION_FIELDS

EXPORT_VERSION = "mlb-d1-export-v1"
INPUT_SCHEMA = "1.2.0"
MODEL_VERSION = "lahman-contact-adapter-v1"


def contextual_profile(audit: dict) -> dict:
    """Exactly the existing M4 contact re-labeling, not a new statistical model."""
    prepared = deepcopy(audit["preparedProfile"])
    prepared["weights"]["otherContact"] = prepared["weights"]["battedBallOut"]
    prepared["weights"]["battedBallOut"] = 0
    prepared["modelVersion"] = MODEL_VERSION
    prepared["provenance"]["transformationVersion"] = MODEL_VERSION
    prepared["qualityFlags"] = [
        f for f in prepared["qualityFlags"] if f != "ordinary-out-contact-proxy"
    ] + ["unresolved-contact-requires-observed-transitions"]
    prepared["id"] = identity({k: v for k, v in prepared.items() if k != "id"}, "prepared")
    validate_prepared(prepared)
    return prepared


def validate_prepared(profile: dict) -> None:
    from .simulation import ENGINE_OUTCOMES, WEIGHT_SCALE

    weights = profile["weights"]
    if (
        set(weights) != {*ENGINE_OUTCOMES, "otherContact"}
        or any(type(v) is not int or not 0 <= v <= WEIGHT_SCALE for v in weights.values())
        or sum(weights.values()) != WEIGHT_SCALE
        or weights["battedBallOut"] != 0
        or profile["modelVersion"] != MODEL_VERSION
        or not 1 <= profile["sampleOpportunities"] <= 2**32 - 1
        or profile["id"] != identity({k: v for k, v in profile.items() if k != "id"}, "prepared")
    ):
        raise DataError("Invalid or incompatible prepared profile")


def quoted(value) -> str:
    if value is None:
        return "NULL"
    if type(value) is int:
        return str(value)
    if not isinstance(value, str) or "\x00" in value:
        raise DataError("Unsupported SQL literal")
    return "'" + value.replace("'", "''") + "'"


def insert(table: str, columns: tuple[str, ...], values: tuple) -> str:
    # Trusted identifiers only. On conflict, identical rows are true no-ops;
    # differing bytes fail NOT NULL rather than silently overwriting old inputs.
    equal = " AND ".join(f"{c} IS excluded.{c}" for c in columns)
    sql = (
        f"INSERT INTO {table} ({','.join(columns)}) VALUES "
        f"({','.join(quoted(v) for v in values)}) ON CONFLICT DO UPDATE "
        f"SET {columns[0]}=NULL WHERE NOT ({equal});\n"
    )
    if len(sql.encode("utf-8")) > 90_000:
        raise DataError("Export statement exceeds conservative D1 statement budget")
    return sql


def build_publication(dataset: Dataset, year: int, policy: PreparationPolicy) -> tuple[str, dict]:
    if type(year) is not int or not 2000 <= year <= 2025:
        raise DataError("Initial publication supports one modern season, 2000..2025")
    dataset.validate_keys()
    dataset.validate_relationships()
    subset = replace(
        dataset,
        batting=[s for s in dataset.batting if s.year == year and s.league_id in ("AL", "NL")],
    )
    context = league_context(subset, policy, year, year)
    grouped = aggregate_seasons(subset.batting)
    prepared = []
    excluded = []
    for season in grouped:
        request = ProfileRequest(season.player_id, "aggregate", ("AL", "NL"), year, year)
        historical = json.loads(canonical_bytes(generate_profile(subset, request)))
        # Insufficient/missing/small samples are reported, not repaired or exported.
        if (
            historical["status"] != "ok"
            or historical["excludedSeasons"]
            or historical["opportunities"] < policy.min_pa
        ):
            excluded.append(
                {"playerId": season.player_id, "reason": "incomplete-or-below-preparation-minimum"}
            )
            continue
        audit = prepare_profile(historical, subset, policy, context)
        prepared.append((historical, contextual_profile(audit)))
    if not prepared:
        raise DataError("No profiles qualify for the selected publication")
    prepared.sort(key=lambda pair: pair[0]["playerId"])
    player_ids = {h["playerId"] for h, _ in prepared}
    source_id = identity(dataset.provenance, "source")
    positions = [
        a
        for a in dataset.appearances
        if a.year == year and a.player_id in player_ids and a.league_id in ("AL", "NL")
    ]
    # Unknown appearances do not become zero or a fabricated positive filter match.
    position_totals = defaultdict(list)
    for a in positions:
        for pos, games in a.positions.items():
            if pos not in POSITION_FIELDS or (
                games is not None and (type(games) is not int or games < 0)
            ):
                raise DataError("Invalid position observation")
            position_totals[a.player_id, pos].append(games)
    pools = defaultdict(list)
    for historical, profile in prepared:
        for pos in POSITION_FIELDS:
            values = position_totals.get((historical["playerId"], pos), [])
            if values and all(v is not None for v in values) and sum(values) > 0:
                pools[pos].append((profile["id"], sum(values)))
    metadata = {
        "schemaVersion": "1.0.0",
        "exportVersion": EXPORT_VERSION,
        "sport": "mlb",
        "sourceId": source_id,
        "source": dataset.provenance,
        "year": year,
        "leagues": ["AL", "NL"],
        "profileType": "season",
        "aggregation": "aggregate",
        "inputSchemaVersion": INPUT_SCHEMA,
        "modelVersion": MODEL_VERSION,
        "policy": policy.document(),
        "context": context,
        "positionPolicy": "recorded-positive-complete-appearances-v1",
        "profileCount": len(prepared),
        "positionCounts": {p: len(pool) for p, pool in sorted(pools.items())},
    }
    # Bind membership/order/observed position pools too, not just configuration.
    dataset_id = identity(
        {"metadata": metadata, "profiles": [p["id"] for _, p in prepared], "pools": dict(pools)},
        "dataset",
    )
    statements = []
    counts = Counter()

    def add(table, columns, values):
        statements.append(insert(table, tuple(columns.split()), tuple(values)))
        counts[table] += 1

    def encoded(value):
        return canonical_bytes(value).decode("utf-8")

    lock = source_lock()
    attribution = {key: lock[key] for key in ("sourcePage", "license", "licenseUrl", "attribution")}
    add(
        "mlb_sources",
        "id provenance_json attribution_json",
        (source_id, encoded(dataset.provenance), encoded(attribution)),
    )
    for p in sorted(dataset.players, key=lambda p: p.player_id):
        if p.player_id in player_ids:
            facts = {
                k: p.facts.get(k) for k in ("bats", "throws", "birthYear", "retroID", "bbrefID")
            }
            add(
                "mlb_players",
                "source_id id lahman_id display_name metadata_json source_row",
                (source_id, p.player_id, p.source_id, p.display_name, encoded(facts), p.source_row),
            )
    stints = [s for s in subset.batting if s.player_id in player_ids]
    team_keys = {(s.year, s.team_id, s.league_id) for s in (*stints, *positions)}
    teams = [t for t in dataset.teams if (t.year, t.team_id, t.league_id) in team_keys]
    franchises = {t.franchise_id for t in teams}
    for f in sorted(dataset.franchises, key=lambda f: f["franchID"]):
        if f["franchID"] in franchises:
            add("mlb_franchises", "source_id id name", (source_id, f["franchID"], f["franchName"]))
    for t in sorted(teams, key=lambda t: (t.year, t.team_id, t.league_id)):
        add(
            "mlb_team_seasons",
            "source_id year team_id league_id franchise_id name source_row",
            (
                source_id,
                t.year,
                t.team_id,
                t.league_id,
                t.franchise_id,
                t.facts.get("name"),
                t.source_row,
            ),
        )
    for player in sorted(player_ids):
        add("mlb_player_seasons", "source_id player_id year", (source_id, player, year))
    for s in sorted(stints, key=lambda s: (s.player_id, s.stint, s.team_id, s.league_id)):
        add(
            "mlb_batting_stints",
            "source_id player_id year stint team_id league_id counts_json source_row",
            (
                source_id,
                s.player_id,
                year,
                s.stint,
                s.team_id,
                s.league_id,
                encoded(s.counts),
                s.source_row,
            ),
        )
    for a in sorted(positions, key=lambda a: (a.player_id, a.team_id, a.league_id)):
        for pos, games in sorted(a.positions.items()):
            add(
                "mlb_position_appearances",
                "source_id player_id year team_id league_id position games source_row",
                (source_id, a.player_id, year, a.team_id, a.league_id, pos, games, a.source_row),
            )
    for h, p in prepared:
        add(
            "mlb_profiles",
            "id source_id player_id model_version input_schema_version "
            "historical_profile_id aggregation definition_json payload_json",
            (
                p["id"],
                source_id,
                h["playerId"],
                MODEL_VERSION,
                INPUT_SCHEMA,
                h["profileId"],
                h["request"]["method"],
                encoded(h["request"]),
                encoded(p),
            ),
        )
    add(
        "mlb_datasets",
        "id source_id year metadata_json",
        (dataset_id, source_id, year, encoded(metadata)),
    )
    for ordinal, (h, p) in enumerate(prepared):
        add(
            "mlb_dataset_profiles",
            "dataset_id profile_id source_id player_id year ordinal",
            (dataset_id, p["id"], source_id, h["playerId"], year, ordinal),
        )
    for pos, pool in sorted(pools.items()):
        for ordinal, (profile_id, games) in enumerate(pool):
            add(
                "mlb_dataset_positions",
                "dataset_id position ordinal profile_id games",
                (dataset_id, pos, ordinal, profile_id, games),
            )
    add(
        "mlb_publications",
        "dataset_id player_count position_counts_json",
        (dataset_id, len(prepared), encoded(metadata["positionCounts"])),
    )
    sql = "-- Draftory deterministic MLB publication; apply migrations first.\n" + "".join(
        statements
    )
    return sql, {
        "schemaVersion": "1.0.0",
        "datasetId": dataset_id,
        "metadata": metadata,
        "rowCounts": dict(sorted(counts.items())),
        "excludedPlayers": excluded,
        "sqlBytes": len(sql.encode("utf-8")),
        "sqlSha256": hashlib.sha256(sql.encode("utf-8")).hexdigest(),
        "preparedPayloadBytes": sum(len(canonical_bytes(p)) for _, p in prepared),
    }


def export_publication(
    dataset: Dataset, year: int, policy: PreparationPolicy, output: Path, migrations: Path
) -> dict:
    sql, summary = build_publication(dataset, year, policy)
    # Real SQLite constraints validate all artifacts before any output is published.
    with sqlite3.connect(":memory:") as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        for migration in sorted(migrations.glob("[0-9]*.sql")):
            connection.executescript(migration.read_text("utf-8"))
        if not connection.execute(
            "SELECT count(*) FROM sqlite_master WHERE name='mlb_profiles'"
        ).fetchone()[0]:
            raise DataError("Player data migrations are required")
        connection.executescript(sql)
        if connection.execute("PRAGMA foreign_key_check").fetchall():
            raise DataError("Publication contains orphan references")
        before = connection.total_changes
        connection.executescript(sql)
        if connection.total_changes != before:
            raise DataError("Publication import is not idempotent")
        summary["sqlitePageBytes"] = (
            connection.execute("PRAGMA page_count").fetchone()[0]
            * connection.execute("PRAGMA page_size").fetchone()[0]
        )
    output.mkdir(parents=True, exist_ok=True)
    (output / "import.sql").write_bytes(sql.encode("utf-8"))
    (output / "manifest.json").write_bytes(canonical_bytes(summary) + b"\n")
    return summary
