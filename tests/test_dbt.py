import os
import subprocess
import sys
from contextlib import suppress
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from psycopg import AsyncConnection
from psycopg.conninfo import conninfo_to_dict

from football_intel.fetch_attempts import FetchAttemptStore
from football_intel.raw_responses import RawResponseStore
from football_intel.sources import sofascore, understat
from football_intel.sources.sofascore.matches import MatchNotFinished, fetch_match
from football_intel.sources.understat import league as understat_league
from tests.sofascore_stub import NOT_STARTED_EVENT_ID, SofascoreStub
from tests.understat_stub import ARSENAL, CHELSEA, LEAGUE, UnderstatStub

DBT_PROJECT = Path(__file__).parent.parent / "dbt"
REEP_RELEASE = "2026-01-02.1"
# A made-up Reep release mapping the stubs' clubs (ADR 33): Arsenal is Sofascore 42,
# Understat 83, Transfermarkt 11; Chelsea is 38, 80, 631.
REEP_TEAMS = {
    "rt_arsenal": {"sofascore": "42", "understat": "83", "transfermarkt": "11"},
    "rt_chelsea": {"sofascore": "38", "understat": "80", "transfermarkt": "631"},
}


@pytest.fixture(autouse=True)
async def reep_teams(connection: AsyncConnection[Any]) -> None:
    await connection.execute("TRUNCATE reference.reep_releases CASCADE")
    await connection.execute(
        "INSERT INTO reference.reep_releases (release, manifest) VALUES (%s, '{}')",
        (REEP_RELEASE,),
    )
    for reep_id, ids in REEP_TEAMS.items():
        for provider, external_id in ids.items():
            await connection.execute(
                "INSERT INTO reference.reep_team_bridges VALUES (%s, %s, %s, %s)",
                (REEP_RELEASE, reep_id, provider, external_id),
            )


def _dbt_build(database_url: str, tmp_path: Path, succeeds: bool = True) -> str:
    """`dbt build` against the test database, as a subprocess, as it runs from the CLI.
    Returns its output."""
    conninfo = conninfo_to_dict(database_url)
    env = os.environ | {
        "POSTGRES_HOST": str(conninfo["host"]),
        "POSTGRES_PORT": str(conninfo["port"]),
        "POSTGRES_DB": str(conninfo["dbname"]),
        "POSTGRES_USER": str(conninfo["user"]),
        "POSTGRES_PASSWORD": str(conninfo.get("password", "")),
        "REEP__RELEASE": REEP_RELEASE,
    }
    dbt = Path(sys.executable).parent / "dbt"
    args = ["--project-dir", DBT_PROJECT, "--profiles-dir", DBT_PROJECT]
    paths = ["--target-path", tmp_path / "target", "--log-path", tmp_path / "logs"]
    result = subprocess.run(
        [dbt, "build", *args, *paths], env=env, capture_output=True, text=True, check=False
    )
    assert (result.returncode == 0) == succeeds, result.stdout[-4000:]
    return result.stdout


async def _store_matches(connection: AsyncConnection[Any]) -> None:
    """Two finished Matches, one of them fetched twice, and a status check of a Match not
    started: what post-match workflows and re-runs leave in `raw.raw_responses`."""
    stub = SofascoreStub()
    recording = sofascore.recording_transport(
        stub.transport(), RawResponseStore(connection), FetchAttemptStore(connection)
    )
    for event_id in (1001, 1003, 1001):
        await fetch_match(recording, event_id, per_player=False)
    with pytest.raises(MatchNotFinished):
        await fetch_match(recording, NOT_STARTED_EVENT_ID, per_player=False)
    # A later challenge for a stored event must not hide its last successful answer.
    await connection.execute(
        "INSERT INTO raw.raw_responses (source, method, url, status_code, headers, body,"
        " body_json, captured_at)"
        " SELECT source, method, url, 403, '{}', '', '{\"error\": {\"reason\": \"challenge\"}}',"
        " captured_at + interval '1 hour' FROM raw.raw_responses WHERE url LIKE '%/event/1003'"
    )


async def test_dbt_builds_matches_appearances_and_season_minutes(
    connection: AsyncConnection[Any], database_url: str, tmp_path: Path
) -> None:
    await _store_matches(connection)

    _dbt_build(database_url, tmp_path)

    cursor = await connection.execute(
        "SELECT match_id, season_year, home_team_id, away_team_id, home_goals, away_goals"
        " FROM staging.stg_sofascore__matches ORDER BY match_id"
    )
    # A re-fetched Match counts once, and a Match not started is not a Match yet.
    assert await cursor.fetchall() == [
        (1001, "24/25", 42, 38, 2, 1),
        (1003, "24/25", 38, 42, 2, 1),
    ]
    cursor = await connection.execute(
        "SELECT player_id, team_id FROM staging.stg_sofascore__appearances"
        " WHERE match_id = 1001 ORDER BY player_id"
    )
    # The unused substitute has no minutes, so no Appearance. Home players take the home team.
    assert await cursor.fetchall() == [(11, 42), (12, 42), (21, 38), (22, 38)]
    cursor = await connection.execute(
        "SELECT player_id, season_year, appearances, minutes_played"
        " FROM marts.player_season_minutes ORDER BY player_id"
    )
    assert await cursor.fetchall() == [
        (11, "24/25", 2, 180),
        (12, "24/25", 2, 180),
        (21, "24/25", 2, 180),
        (22, "24/25", 2, 8),
    ]


async def test_dbt_builds_understat_matches_appearances_and_shots(
    connection: AsyncConnection[Any], database_url: str, tmp_path: Path
) -> None:
    recording = understat.recording_transport(
        UnderstatStub().transport(), RawResponseStore(connection), FetchAttemptStore(connection)
    )
    season = await understat_league.fetch_league_season(recording, LEAGUE, 2024)
    for match_id in season.finished_match_ids:
        with suppress(understat_league.MatchDataMissing):
            await understat_league.fetch_match(recording, match_id)

    _dbt_build(database_url, tmp_path)

    cursor = await connection.execute(
        "SELECT match_id, season, season_year, home_goals, away_goals, home_xg"
        " FROM staging.stg_understat__matches ORDER BY match_id"
    )
    # Match 3 is not played yet; Match 2 is played, though its data is missing.
    assert await cursor.fetchall() == [
        (1, 2024, "24/25", 2, 1, Decimal("1.5")),
        (2, 2024, "24/25", 2, 1, Decimal("1.5")),
    ]
    cursor = await connection.execute(
        "SELECT match_id, player_id, team_id, side, minutes_played"
        " FROM staging.stg_understat__appearances ORDER BY player_id"
    )
    assert await cursor.fetchall() == [
        (1, 801, ARSENAL, "home", 90),
        (1, 802, ARSENAL, "home", 75),
        (1, 803, CHELSEA, "away", 90),
        (1, 804, CHELSEA, "away", 15),
    ]
    cursor = await connection.execute(
        "SELECT match_id, player_id, side, x, y, xg FROM staging.stg_understat__shots"
    )
    assert await cursor.fetchall() == [
        (1, 801, "home", Decimal("0.9"), Decimal("0.5"), Decimal("0.25"))
    ]


async def test_dbt_links_matches_across_sources_by_season_and_clubs(
    connection: AsyncConnection[Any], database_url: str, tmp_path: Path
) -> None:
    await _store_matches(connection)
    recording = understat.recording_transport(
        UnderstatStub().transport(), RawResponseStore(connection), FetchAttemptStore(connection)
    )
    await understat_league.fetch_league_season(recording, LEAGUE, 2024)

    _dbt_build(database_url, tmp_path)

    cursor = await connection.execute(
        "SELECT match_id, season, home_club_id, away_club_id, sofascore_match_id,"
        " understat_match_id FROM marts.matches ORDER BY match_id"
    )
    # Sofascore names the season "24/25", Understat 2024; their team IDs differ. The Clubs
    # and the season link them, so each fixture is one Match with both IDs.
    assert await cursor.fetchall() == [
        ("2024:rt_arsenal:rt_chelsea", 2024, "rt_arsenal", "rt_chelsea", 1001, 1),
        ("2024:rt_chelsea:rt_arsenal", 2024, "rt_chelsea", "rt_arsenal", 1003, 2),
    ]


async def test_dbt_never_writes_to_the_schemas_alembic_owns(
    connection: AsyncConnection[Any], database_url: str, tmp_path: Path
) -> None:
    # A dbt relation in one of these schemas makes the next migration that creates or
    # changes that schema fail against a database dbt has already built (ADR 31).
    owned = """
        SELECT table_schema, table_name FROM information_schema.tables
        WHERE table_schema IN ('raw', 'identity', 'reference')
        ORDER BY 1, 2
    """
    before = await (await connection.execute(owned)).fetchall()

    _dbt_build(database_url, tmp_path)

    assert await (await connection.execute(owned)).fetchall() == before


async def test_a_club_reep_does_not_map_fails_the_build(
    connection: AsyncConnection[Any], database_url: str, tmp_path: Path
) -> None:
    await _store_matches(connection)
    await connection.execute("DELETE FROM reference.reep_team_bridges WHERE reep_id = 'rt_chelsea'")

    output = _dbt_build(database_url, tmp_path, succeeds=False)

    assert "not_null_matches_away_club_id" in output


async def test_clubs_come_from_the_pinned_reep_release(
    connection: AsyncConnection[Any], database_url: str, tmp_path: Path
) -> None:
    await _store_matches(connection)

    _dbt_build(database_url, tmp_path)

    cursor = await connection.execute(
        "SELECT club_id, name, sofascore_team_id, understat_team_id, transfermarkt_club_id"
        " FROM marts.clubs ORDER BY club_id"
    )
    # Sofascore's name for each (the stubs call every team "Home FC" or "Away FC").
    assert [row[0:1] + row[2:] for row in await cursor.fetchall()] == [
        ("rt_arsenal", 42, 83, 11),
        ("rt_chelsea", 38, 80, 631),
    ]
