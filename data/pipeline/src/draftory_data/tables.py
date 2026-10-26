"""Strict parsing using exact pinned headers, nullable counts and explicit column types."""

import csv
import math
from collections.abc import Iterator
from pathlib import Path

from .source import DataError, source_lock

BAT_FIELDS = (
    "G",
    "AB",
    "R",
    "H",
    "2B",
    "3B",
    "HR",
    "RBI",
    "SB",
    "CS",
    "BB",
    "SO",
    "IBB",
    "HBP",
    "SH",
    "SF",
    "GIDP",
)
POSITION_FIELDS = {
    "P": "G_p",
    "C": "G_c",
    "1B": "G_1b",
    "2B": "G_2b",
    "3B": "G_3b",
    "SS": "G_ss",
    "LF": "G_lf",
    "CF": "G_cf",
    "RF": "G_rf",
    "OF": "G_of",
    "DH": "G_dh",
}
TEXT_FIELDS = {
    "playerID",
    "teamID",
    "lgID",
    "franchID",
    "franchName",
    "active",
    "NAassoc",
    "POS",
    "birthCity",
    "birthCountry",
    "birthState",
    "deathCountry",
    "deathState",
    "deathCity",
    "nameFirst",
    "nameLast",
    "nameGiven",
    "bats",
    "throws",
    "debut",
    "bbrefID",
    "finalGame",
    "retroID",
    "divID",
    "DivWin",
    "WCWin",
    "LgWin",
    "WSWin",
    "name",
    "park",
    "teamIDBR",
    "teamIDlahman45",
    "teamIDretro",
}
FLOAT_FIELDS = {"ERA", "FP", "ZR"}
NULLS = {"", "NULL", "\\N"}
type Cell = str | int | float | None
type Row = dict[str, Cell]


def column_type(column: str) -> str:
    if column in TEXT_FIELDS:
        return "string"
    return "number" if column in FLOAT_FIELDS else "integer"


def parse_cell(value: str, column: str) -> Cell:
    if value in NULLS:
        return None
    kind = column_type(column)
    if kind == "string":
        return value
    try:
        parsed = float(value) if kind == "number" else int(value)
        if isinstance(parsed, float) and not math.isfinite(parsed):
            raise ValueError("Non-finite number")
        return parsed
    except ValueError as error:
        raise DataError(f"Invalid {kind} in {column}: {value!r}") from error


def read_table(directory: Path, name: str) -> Iterator[tuple[int, Row]]:
    entry = next(item for item in source_lock()["files"] if item["path"] == name)
    with (directory / name).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != entry["columns"]:
            raise DataError(f"Unexpected CSV headers in {name}: {reader.fieldnames}")
        for number, row in enumerate(reader, 2):
            if None in row or None in row.values():
                raise DataError(f"Malformed CSV row: {name}:{number}")
            try:
                yield number, {column: parse_cell(value, column) for column, value in row.items()}
            except DataError as error:
                raise DataError(f"{name}:{number}: {error}") from error


def required(row: Row, key: str, kind: type):
    value = row[key]
    if not isinstance(value, kind) or value == "":
        raise DataError(f"Required {key} must be {kind.__name__}: {value!r}")
    return value
