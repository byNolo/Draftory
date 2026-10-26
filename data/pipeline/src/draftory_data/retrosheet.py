"""Narrow official, checksum-pinned M4 game-log/parsed-play acquisition."""

import csv
import io
import json
import re
import zipfile
from importlib.resources import files
from pathlib import Path
from urllib.request import urlopen

from .source import DataError, canonical_bytes, digest, lock_digest

RETROSHEET_NOTICE = (
    "The information used here was obtained free of charge from and is copyrighted by Retrosheet. "
    "Interested parties may contact Retrosheet at www.retrosheet.org."
)


def source_lock():
    return json.loads(
        files("draftory_data").joinpath("resources/retrosheet-m4.lock.json").read_text("utf-8")
    )


def verify(directory: Path) -> dict:
    lock = source_lock()
    for entry in lock["files"]:
        path = directory / entry["name"]
        if (
            not path.is_file()
            or path.stat().st_size != entry["sizeBytes"]
            or digest(path) != entry["sha256"]
        ):
            raise DataError(f"Retrosheet integrity mismatch or missing file: {path}")
    return {"source": lock["source"], "lockSha256": lock_digest(lock)}


def fetch(directory: Path) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    for entry in source_lock()["files"]:
        path = directory / entry["name"]
        if path.exists():
            if path.stat().st_size != entry["sizeBytes"] or digest(path) != entry["sha256"]:
                raise DataError(f"Changed cached Retrosheet file: {path}")
            continue
        temp = path.with_suffix(path.suffix + ".part")
        try:
            with urlopen(entry["url"], timeout=90) as response, temp.open("wb") as out:
                remaining = entry["sizeBytes"] + 1
                while remaining:
                    chunk = response.read(min(remaining, 1024 * 1024))
                    if not chunk:
                        break
                    out.write(chunk)
                    remaining -= len(chunk)
            if temp.stat().st_size != entry["sizeBytes"] or digest(temp) != entry["sha256"]:
                raise DataError(f"Retrosheet download changed: {entry['url']}")
            temp.replace(path)
        finally:
            temp.unlink(missing_ok=True)
    provenance = verify(directory)
    (directory / "acquisition.json").write_bytes(canonical_bytes(provenance) + b"\n")
    return provenance


def zip_rows(directory: Path, archive: str, member: str, *, headers: bool):
    with zipfile.ZipFile(directory / archive) as source:
        if source.namelist() != [member]:
            raise DataError(f"Unexpected Retrosheet archive members: {archive}")
        with source.open(member) as stream:
            text = io.TextIOWrapper(stream, encoding="utf-8-sig", newline="")
            reader = csv.DictReader(text) if headers else csv.reader(text)
            yield from reader


def line_score(value: str) -> list[int | None]:
    parts = re.findall(r"\(\d+\)|\d|x", value.lower())
    if "".join(parts) != value.lower():
        raise DataError(f"Unsupported line score: {value}")
    return [None if p == "x" else int(p.strip("()")) for p in parts]


STAT_FIELDS = (
    "ab",
    "hits",
    "double",
    "triple",
    "homeRuns",
    "rbi",
    "sh",
    "sf",
    "hbp",
    "walks",
    "ibb",
    "strikeouts",
    "sb",
    "cs",
    "gdp",
    "interference",
    "lob",
)


def game_logs(directory: Path, year: int) -> list[dict]:
    if year not in (2022, 2023, 2024, 2025):
        raise DataError("M4 source supports 2022 through 2025 only")
    games = []
    seen = set()
    for number, row in enumerate(
        zip_rows(directory, f"gl{year}.zip", f"gl{year}.txt", headers=False), 1
    ):
        if (
            len(row) != 161
            or not row[0].startswith(str(year))
            or row[4] not in ("AL", "NL")
            or row[7] not in ("AL", "NL")
        ):
            raise DataError(f"Unexpected Retrosheet game-log record {year}:{number}")
        key = (row[0], row[1], row[3], row[6])
        if key in seen:
            raise DataError("Duplicate Retrosheet game")
        seen.add(key)
        if row[14] or int(row[9]) == int(row[10]):
            raise DataError("Unsupported forfeit or tied calibration game")
        sides = []
        for side in (0, 1):
            offset = 21 if side == 0 else 49
            values = row[offset : offset + 17]
            if any(v == "" for v in values):
                raise DataError(f"Missing game-log batting counts {year}:{number}")
            stats = dict(zip(STAT_FIELDS, map(int, values), strict=True))
            if min(stats.values()) < 0:
                raise DataError("Negative game-log count")
            stats["runs"] = int(row[9 + side])
            stats["pa"] = sum(stats[k] for k in ("ab", "walks", "hbp", "sh", "sf", "interference"))
            lines = line_score(row[19 + side])
            if sum(v or 0 for v in lines) != stats["runs"]:
                raise DataError("Game-log line score does not reconcile")
            start = 105 if side == 0 else 132
            lineup = row[start : start + 27 : 3]
            if len(set(lineup)) != 9 or any(not p for p in lineup):
                raise DataError("Missing or duplicate historical starter")
            sides.append(
                {
                    "teamId": row[3 if side == 0 else 6],
                    "stats": stats,
                    "lineScore": lines,
                    "lineup": lineup,
                }
            )
        games.append(
            {
                "date": row[0],
                "number": row[1],
                "sourceRow": number,
                "outs": int(row[11]),
                "homeBatsFirst": "HTBF" in row[159],
                "teams": sides,
            }
        )
    return games
