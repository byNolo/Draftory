import csv
import hashlib
import io

import pytest

from draftory_data import source
from draftory_data.source import DataError, digest, fetch, source_lock, verify_source
from draftory_data.tables import parse_cell, read_table


def small_lock(content=b"official synthetic bytes\n"):
    return {
        "source": "synthetic",
        "release": "test-v1",
        "license": "test-only",
        "attribution": "fabricated",
        "files": [
            {
                "path": "tiny.csv",
                "url": "https://example.invalid/",
                "size": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        ],
    }


def test_all_pinned_sources_are_official_and_complete():
    lock = source_lock()
    names = {entry["path"] for entry in lock["files"]}
    assert {
        "Batting.csv",
        "People.csv",
        "Teams.csv",
        "TeamsFranchises.csv",
        "Appearances.csv",
        "Fielding.csv",
        "FieldingOFsplit.csv",
        "readme2025.txt",
    } == names
    assert lock["license"] == "CC-BY-SA-3.0"
    for entry in lock["files"]:
        assert entry["url"].startswith("https://sabr.box.com/")
        assert len(entry["sha256"]) == 64
        assert entry["size"] > 0


def test_verification_detects_missing_same_size_tampered_and_truncated_files(tmp_path):
    lock = small_lock(b"test")
    with pytest.raises(DataError, match="Missing"):
        verify_source(tmp_path, lock)
    for content in (b"tEst", b"tes"):
        (tmp_path / "tiny.csv").write_bytes(content)
        with pytest.raises(DataError, match="mismatch"):
            verify_source(tmp_path, lock)
    (tmp_path / "tiny.csv").write_bytes(b"test")
    assert verify_source(tmp_path, lock)["release"] == "test-v1"


def test_download_verifies_before_publish_and_cached_files_require_no_network(
    tmp_path, monkeypatch
):
    content = b"test"
    monkeypatch.setattr(source, "source_lock", lambda: small_lock(content))
    calls = []

    def download(*args, **kwargs):
        calls.append(1)
        return io.BytesIO(content)

    monkeypatch.setattr(source, "urlopen", download)
    receipt = fetch(tmp_path)
    assert receipt["lockSha256"]
    assert digest(tmp_path / "tiny.csv") == hashlib.sha256(content).hexdigest()
    fetch(tmp_path)
    assert len(calls) == 1
    (tmp_path / "tiny.csv").write_bytes(b"bad!")
    with pytest.raises(DataError):
        fetch(tmp_path)
    assert len(calls) == 1


@pytest.mark.parametrize("content", [b"bad!", b"<html>not a csv</html>"])
def test_bad_download_does_not_publish_or_leave_partial_files(tmp_path, monkeypatch, content):
    monkeypatch.setattr(source, "source_lock", lambda: small_lock(b"test"))
    monkeypatch.setattr(source, "urlopen", lambda *a, **kw: io.BytesIO(content))
    with pytest.raises(DataError):
        fetch(tmp_path)
    assert not (tmp_path / "tiny.csv").exists()
    assert not (tmp_path / "tiny.csv.part").exists()


def test_league_na_and_ids_are_text_not_null_or_numbers():
    assert parse_cell("NA", "lgID") == "NA"
    assert parse_cell("001", "playerID") == "001"
    assert parse_cell("", "SF") is None
    assert parse_cell("0", "SF") == 0
    assert parse_cell("123", "AB") == 123
    with pytest.raises(DataError):
        parse_cell("1.5", "AB")


def test_exact_headers_bom_and_malformed_rows(tmp_path):
    columns = next(e["columns"] for e in source_lock()["files"] if e["path"] == "Batting.csv")
    path = tmp_path / "Batting.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(columns)
        writer.writerow(["synthetic01", "1871", "1", "T", "NA"] + ["0"] * (len(columns) - 5))
    row = list(read_table(tmp_path, path.name))[0][1]
    assert row["lgID"] == "NA"
    path.write_text("wrong,header\na,b\n", encoding="utf-8")
    with pytest.raises(DataError, match="headers"):
        list(read_table(tmp_path, path.name))
    path.write_text(",".join(columns) + "\nshort,row\n", encoding="utf-8")
    with pytest.raises(DataError, match="Malformed"):
        list(read_table(tmp_path, path.name))
