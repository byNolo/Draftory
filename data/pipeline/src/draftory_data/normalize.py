"""Typed source facts and lossless-null aggregation; no eligibility or projection model."""

from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

from .source import DataError, canonical_bytes, digest, verify_source
from .tables import BAT_FIELDS, POSITION_FIELDS, Row, read_table, required

type Counts = dict[str, int | None]


@dataclass(frozen=True)
class Player:
    player_id: str
    source_id: str
    display_name: str
    facts: Row
    source_row: int


@dataclass(frozen=True)
class TeamSeason:
    year: int
    team_id: str
    league_id: str
    franchise_id: str
    facts: Row
    source_row: int


@dataclass(frozen=True)
class BattingStint:
    player_id: str
    year: int
    team_id: str
    league_id: str
    stint: int
    counts: Counts
    source_row: int
    quality_flags: tuple[str, ...]


@dataclass(frozen=True)
class Appearance:
    player_id: str
    year: int
    team_id: str
    league_id: str
    positions: Counts
    facts: Row
    source_row: int


@dataclass(frozen=True)
class Fielding:
    player_id: str
    year: int
    team_id: str
    league_id: str
    stint: int
    position: str
    facts: Row
    source_table: str
    source_row: int


@dataclass(frozen=True)
class SeasonBatting:
    player_id: str
    year: int
    team_ids: tuple[str, ...]
    league_ids: tuple[str, ...]
    counts: Counts
    source_rows: tuple[int, ...]
    quality_flags: tuple[str, ...]


def batting_flags(counts: Counts) -> tuple[str, ...]:
    flags = []
    if any(value is not None and value < 0 for value in counts.values()):
        flags.append("negative-count")
    if all(counts[key] is not None for key in ("H", "2B", "3B", "HR")):
        if counts["H"] < counts["2B"] + counts["3B"] + counts["HR"]:
            flags.append("extra-base-hits-exceed-hits")
    if counts["AB"] is not None and counts["H"] is not None:
        if counts["H"] > counts["AB"]:
            flags.append("hits-exceed-at-bats")
        if counts["SO"] is not None and counts["H"] + counts["SO"] > counts["AB"]:
            flags.append("hits-plus-strikeouts-exceed-at-bats")
    if counts["BB"] is not None and counts["IBB"] is not None:
        if counts["IBB"] > counts["BB"]:
            flags.append("intentional-walks-exceed-walks")
    return tuple(flags)


def sum_counts(counts: list[Counts]) -> Counts:
    """One missing component makes the aggregate unknown for that field."""
    return {
        key: None if any(row[key] is None for row in counts) else sum(row[key] for row in counts)
        for key in BAT_FIELDS
    }


def aggregate_seasons(stints: list[BattingStint]) -> list[SeasonBatting]:
    unique(stints, lambda x: (x.player_id, x.year, x.stint, x.team_id, x.league_id), "stint")
    groups = defaultdict(list)
    for stint in stints:
        groups[stint.player_id, stint.year].append(stint)
    result = []
    for (player_id, year), rows in sorted(groups.items()):
        counts = sum_counts([row.counts for row in rows])
        flags = sorted(
            {flag for row in rows for flag in row.quality_flags} | set(batting_flags(counts))
        )
        result.append(
            SeasonBatting(
                player_id,
                year,
                tuple(sorted({row.team_id for row in rows})),
                tuple(sorted({row.league_id for row in rows})),
                counts,
                tuple(sorted(row.source_row for row in rows)),
                tuple(flags),
            )
        )
    return result


def unique(items: list, key, label: str) -> None:
    seen = set()
    for item in items:
        value = key(item)
        if value in seen:
            raise DataError(f"Duplicate {label} key: {value}")
        seen.add(value)


@dataclass
class Dataset:
    provenance: dict
    players: list[Player]
    teams: list[TeamSeason]
    franchises: list[Row]
    batting: list[BattingStint]
    appearances: list[Appearance]
    fielding: list[Fielding]

    @classmethod
    def load(cls, directory: Path) -> "Dataset":
        provenance = verify_source(directory)
        players = []
        for number, row in read_table(directory, "People.csv"):
            sid = required(row, "playerID", str)
            name = " ".join(str(row[k]) for k in ("nameFirst", "nameLast") if row[k])
            players.append(Player(f"lahman:{sid}", sid, name or sid, row, number))
        teams = [
            TeamSeason(
                required(r, "yearID", int),
                required(r, "teamID", str),
                required(r, "lgID", str),
                required(r, "franchID", str),
                r,
                n,
            )
            for n, r in read_table(directory, "Teams.csv")
        ]
        batting = []
        for number, row in read_table(directory, "Batting.csv"):
            counts = {key: row[key] for key in BAT_FIELDS}
            batting.append(
                BattingStint(
                    f"lahman:{required(row, 'playerID', str)}",
                    required(row, "yearID", int),
                    required(row, "teamID", str),
                    required(row, "lgID", str),
                    required(row, "stint", int),
                    counts,
                    number,
                    batting_flags(counts),
                )
            )
        appearances = [
            Appearance(
                f"lahman:{required(r, 'playerID', str)}",
                required(r, "yearID", int),
                required(r, "teamID", str),
                required(r, "lgID", str),
                {pos: r[col] for pos, col in POSITION_FIELDS.items()},
                r,
                n,
            )
            for n, r in read_table(directory, "Appearances.csv")
        ]
        fielding = [
            Fielding(
                f"lahman:{required(r, 'playerID', str)}",
                required(r, "yearID", int),
                required(r, "teamID", str),
                required(r, "lgID", str),
                required(r, "stint", int),
                required(r, "POS", str),
                r,
                name,
                n,
            )
            for name in ("Fielding.csv", "FieldingOFsplit.csv")
            for n, r in read_table(directory, name)
        ]
        franchises = [r for _, r in read_table(directory, "TeamsFranchises.csv")]
        result = cls(provenance, players, teams, franchises, batting, appearances, fielding)
        result.validate_keys()
        result.validate_relationships()
        return result

    def validate_keys(self) -> None:
        unique(self.players, lambda x: x.player_id, "player")
        unique(self.teams, lambda x: (x.year, x.team_id, x.league_id), "team-season")
        unique(self.franchises, lambda x: x["franchID"], "franchise")
        unique(
            self.batting, lambda x: (x.player_id, x.year, x.stint, x.team_id, x.league_id), "stint"
        )
        unique(
            self.appearances, lambda x: (x.player_id, x.year, x.team_id, x.league_id), "appearance"
        )
        unique(
            self.fielding,
            lambda x: (
                x.source_table,
                x.player_id,
                x.year,
                x.stint,
                x.team_id,
                x.league_id,
                x.position,
            ),
            "fielding",
        )

    def validate_relationships(self) -> None:
        players = {p.player_id for p in self.players}
        teams = {(t.year, t.team_id, t.league_id) for t in self.teams}
        franchises = {r["franchID"] for r in self.franchises}
        if any(t.franchise_id not in franchises for t in self.teams):
            raise DataError("Team references an unknown franchise")
        for rows in (self.batting, self.appearances, self.fielding):
            for row in rows:
                if row.player_id not in players:
                    raise DataError(f"Unknown player reference: {row.player_id}")
                if (row.year, row.team_id, row.league_id) not in teams:
                    raise DataError(f"Unknown team-season reference: {row.year}/{row.team_id}")

    def write(self, destination: Path) -> dict:
        """Write stable JSONL facts; a manifest records exact output hashes."""
        self.validate_keys()
        self.validate_relationships()
        destination.mkdir(parents=True, exist_ok=True)
        team_groups = defaultdict(list)
        for row in self.batting:
            team_groups[row.player_id, row.year, row.team_id, row.league_id].append(row)
        team_seasons = []
        for (_, _, team_id, league_id), rows in sorted(team_groups.items()):
            record = asdict(aggregate_seasons(rows)[0])
            record.update(team_id=team_id, league_id=league_id)
            team_seasons.append(record)
        entities = {
            "players": [asdict(x) for x in self.players],
            "teams": [asdict(x) for x in self.teams],
            "franchises": self.franchises,
            "batting-stints": [asdict(x) for x in self.batting],
            "player-seasons": [asdict(x) for x in aggregate_seasons(self.batting)],
            "player-team-seasons": team_seasons,
            "position-appearances": [asdict(x) for x in self.appearances],
            "fielding": [asdict(x) for x in self.fielding],
        }
        manifest = {"schemaVersion": "1.0.0", "source": self.provenance, "files": []}
        for name, records in entities.items():
            path = destination / f"{name}.jsonl"
            with path.open("wb") as stream:
                for record in records:
                    stream.write(canonical_bytes(record) + b"\n")
            manifest["files"].append(
                {"path": path.name, "rows": len(records), "sha256": digest(path)}
            )
        (destination / "manifest.json").write_bytes(canonical_bytes(manifest) + b"\n")
        return manifest
