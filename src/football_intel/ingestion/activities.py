"""Activities: all I/O of the ingestion workflows (HTTP, database) happens here."""

from collections.abc import Callable

import httpx
from psycopg import AsyncConnection
from temporalio import activity

from football_intel.ingestion.models import SquadIngestInput, SquadIngestResult
from football_intel.raw_responses import RawResponseStore
from football_intel.sources.transfermarkt.squads import fetch_squad
from football_intel.sources.transfermarkt.transports import RecordingTransport


class TransfermarktActivities:
    """Transfermarkt activities. `backend` builds the transport that reaches the network."""

    def __init__(
        self,
        database_url: str,
        backend: Callable[[], httpx.AsyncBaseTransport] = httpx.AsyncHTTPTransport,
    ) -> None:
        self._database_url = database_url
        self._backend = backend

    @activity.defn
    async def ingest_club_squad(self, input: SquadIngestInput) -> SquadIngestResult:
        """Fetch a squad and store every upstream response as a Raw Response."""
        async with await AsyncConnection.connect(self._database_url, autocommit=True) as conn:
            transport = RecordingTransport(self._backend(), RawResponseStore(conn))
            squad = await fetch_squad(transport, input.club_id, input.season_id)
        activity.logger.info(
            "Club %s season %s: %d players from %d Raw Responses",
            input.club_id,
            input.season_id,
            len(squad.players),
            transport.recorded,
        )
        return SquadIngestResult(
            club_id=input.club_id,
            season_id=input.season_id,
            players=len(squad.players),
            raw_responses=transport.recorded,
        )
