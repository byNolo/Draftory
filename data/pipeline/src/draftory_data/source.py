"""Pinned downloads from SABR's official Box folder; no mirrors or auto-upgrades."""

import hashlib
import json
import os
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path
from urllib.request import Request, urlopen


class DataError(ValueError):
    """Invalid, changed, incomplete or unsupported historical source data."""


def canonical_bytes(value: object) -> bytes:
    def json_numbers(item):
        if isinstance(item, float) and item.is_integer():
            return int(item)
        if isinstance(item, dict):
            return {key: json_numbers(value) for key, value in item.items()}
        if isinstance(item, (list, tuple)):
            return [json_numbers(value) for value in item]
        return item

    return json.dumps(
        json_numbers(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def source_lock() -> dict:
    text = files("draftory_data").joinpath("resources/lahman-2025.lock.json").read_text("utf-8")
    return json.loads(text)


def lock_digest(lock: dict) -> str:
    return hashlib.sha256(canonical_bytes(lock)).hexdigest()


def verify_file(path: Path, entry: dict) -> None:
    if not path.is_file():
        raise DataError(f"Missing source file: {path}; run fetch first")
    if path.stat().st_size != entry["size"] or digest(path) != entry["sha256"]:
        raise DataError(f"Source integrity mismatch: {path.name}; refusing changed bytes")


def verify_source(directory: Path, lock: dict | None = None) -> dict:
    lock = source_lock() if lock is None else lock
    for entry in lock["files"]:
        verify_file(directory / entry["path"], entry)
    return {"source": lock["source"], "release": lock["release"], "lockSha256": lock_digest(lock)}


def fetch(directory: Path) -> dict:
    """Download missing files atomically; reject changed cached files and HTML responses."""
    lock = source_lock()
    directory.mkdir(parents=True, exist_ok=True)
    for entry in lock["files"]:
        target = directory / entry["path"]
        if target.exists():
            verify_file(target, entry)
            continue
        temporary = target.with_suffix(target.suffix + ".part")
        try:
            request = Request(entry["url"], headers={"User-Agent": "Draftory-data/0.2"})
            with urlopen(request, timeout=60) as response, temporary.open("wb") as stream:
                size = 0
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > entry["size"]:
                        raise DataError(f"Unexpected download size for {target.name}")
                    stream.write(chunk)
            verify_file(temporary, entry)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
    receipt = {
        "schemaVersion": "1.0.0",
        **verify_source(directory, lock),
        "verifiedAt": datetime.now(UTC).isoformat(),
        "license": lock["license"],
        "attribution": lock["attribution"],
        "files": lock["files"],
    }
    (directory / "acquisition.json").write_bytes(canonical_bytes(receipt) + b"\n")
    return receipt
