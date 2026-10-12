import logging
from typing import Any

import httpx
import pytest
from psycopg import AsyncConnection

from football_intel.raw_responses import RawResponseStore
from football_intel.sources.transfermarkt.squads import fetch_squad
from football_intel.sources.transfermarkt.transports import (
    RawResponseMissingError,
    RecordingTransport,
    ReplayTransport,
)
from tests.transfermarkt_stub import CLUB_ID, PLAYER_IDS, SEASON_ID, TransfermarktStub


async def test_recording_stores_one_raw_response_per_upstream_request(
    connection: AsyncConnection[Any],
) -> None:
    stub = TransfermarktStub()
    transport = RecordingTransport(stub.transport(), RawResponseStore(connection))

    squad = await fetch_squad(transport, CLUB_ID, SEASON_ID)

    assert [player.id for player in squad.players] == list(PLAYER_IDS)
    cursor = await connection.execute(
        "SELECT url, status_code, body FROM raw.raw_responses ORDER BY id"
    )
    rows = await cursor.fetchall()
    assert len(rows) == len(stub.requests) == transport.recorded
    assert sorted(url for url, _, _ in rows) == sorted(str(r.url) for r in stub.requests)
    # Error responses are Raw Responses too: player 103 has no transfer history.
    assert any(status == 404 for _, status, _ in rows)
    # Bodies are stored as received.
    bodies = {url: bytes(body) for url, _, body in rows}
    expected = TransfermarktStub()
    for request in list(stub.requests):
        assert bodies[str(request.url)] == expected.handle(request).content


async def test_replay_reassembles_the_same_squad_without_network(
    connection: AsyncConnection[Any],
) -> None:
    store = RawResponseStore(connection)
    live = await fetch_squad(
        RecordingTransport(TransfermarktStub().transport(), store), CLUB_ID, SEASON_ID
    )

    # ReplayTransport has no backend at all: it can only answer from the store.
    replayed = await fetch_squad(ReplayTransport(store), CLUB_ID, SEASON_ID)

    assert replayed == live


async def test_replay_of_an_unrecorded_request_is_an_error(
    connection: AsyncConnection[Any],
) -> None:
    with pytest.raises(RawResponseMissingError):
        await fetch_squad(ReplayTransport(RawResponseStore(connection)), CLUB_ID, SEASON_ID)


async def test_stored_and_logged_urls_contain_no_credentials(
    connection: AsyncConnection[Any], caplog: pytest.LogCaptureFixture
) -> None:
    backend = httpx.MockTransport(lambda request: httpx.Response(200, json={"ok": True}))
    transport = RecordingTransport(backend, RawResponseStore(connection))
    request = httpx.Request("GET", "https://user:s3cret@example.com/club/1?token=t0ken&season=2025")

    with caplog.at_level(logging.DEBUG):
        await transport.handle_async_request(request)

    cursor = await connection.execute("SELECT url FROM raw.raw_responses")
    (stored_url,) = await cursor.fetchone() or ("",)
    assert stored_url == "https://example.com/club/1?token=REDACTED&season=2025"
    for secret in ("user", "s3cret", "t0ken"):
        assert secret not in stored_url
        assert secret not in caplog.text
