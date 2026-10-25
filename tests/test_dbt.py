import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from psycopg import AsyncConnection
from psycopg.conninfo import conninfo_to_dict

from football_intel.fetch_attempts import FetchAttemptStore
from football_intel.raw_responses import RawResponseStore
from football_intel.sources import sofascore
from football_intel.sources.sofascore.matches import MatchNotFinished, fetch_match
from tests.sofascore_stub import NOT_STARTED_EVENT_ID, PLAYED, SofascoreStub

DBT_PROJECT = Path(__file__).parent.parent / "dbt"


def _dbt_build(database_url: str, tmp_path: Path) -> None:
    """`dbt build` against the test database, as a subprocess, as it runs from the CLI."""
    conninfo = conninfo_to_dict(database_url)
    env = os.environ | {
        "POSTGRES_HOST": str(conninfo["host"]),
        "POSTGRES_PORT": str(conninfo["port"]),
        "POSTGRES_DB": str(conninfo["dbname"]),
        "POSTGRES_USER": str(conninfo["user"]),
        "POSTGRES_PASSWORD": str(conninfo.get("password", "")),
    }
    dbt = Path(sys.executable).parent / "dbt"
    args = ["--project-dir", DBT_PROJECT, "--profiles-dir", DBT_PROJECT]
    paths = ["--target-path", tmp_path / "target", "--log-path", tmp_path / "logs"]
    result = subprocess.run(
        [dbt, "build", *args, *paths], env=env, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stdout[-4000:]


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
        (1001, "24/25", 1, 2, 2, 1),
        (1003, "24/25", 1, 2, 2, 1),
    ]
    cursor = await connection.execute(
        "SELECT DISTINCT player_id, team_id FROM staging.stg_sofascore__appearances"
        " ORDER BY player_id"
    )
    # The unused substitute has no minutes, so no Appearance.
    assert await cursor.fetchall() == [(p, p // 10) for p in PLAYED]
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
