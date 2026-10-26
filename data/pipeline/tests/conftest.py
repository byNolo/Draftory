"""Small fabricated seasons with deliberately uneven opportunity counts."""

from pathlib import Path

import pytest

from draftory_data.normalize import BattingStint, Dataset, Player, TeamSeason, batting_flags
from draftory_data.tables import BAT_FIELDS


def stint(year=2000, team="A", stint_id=1, row=2, **counts):
    values = dict.fromkeys(BAT_FIELDS, 0)
    values.update(counts)
    return BattingStint(
        "lahman:synthetic01", year, team, "AL", stint_id, values, row, batting_flags(values)
    )


def synthetic_dataset():
    return Dataset(
        {"source": "synthetic-test-only", "release": "fixture-v1", "lockSha256": "0" * 64},
        [Player("lahman:synthetic01", "synthetic01", "Synthetic Batter", {}, 2)],
        [
            TeamSeason(y, t, "AL", "F", {}, i + 2)
            for i, (y, t) in enumerate([(2000, "A"), (2001, "A"), (2002, "B")])
        ],
        [{"franchID": "F", "franchName": "Synthetic Franchise", "active": "Y", "NAassoc": None}],
        [
            stint(2000, AB=100, H=40, **{"2B": 10, "HR": 10, "SO": 20}),
            stint(2001, row=3, AB=10, H=4, BB=10, SO=2),
            stint(2002, team="B", row=4, AB=20, SO=20),
        ],
        [],
        [],
    )


@pytest.fixture
def dataset():
    return synthetic_dataset()


def pytest_addoption(parser):
    parser.addoption(
        "--lahman-source", help="Run offline integration tests against a verified release"
    )


@pytest.fixture(scope="session")
def official_dataset(request):
    path = request.config.getoption("--lahman-source")
    if not path:
        pytest.skip("Provide --lahman-source to run release integration tests")
    return Dataset.load(Path(path))
