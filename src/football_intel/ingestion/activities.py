"""Activities: all I/O of the ingestion workflows (HTTP, database) happens here."""

from datetime import timedelta

from psycopg import AsyncConnection
from temporalio import activity
from temporalio.exceptions import ApplicationError

from football_intel.ingestion.models import SquadIngestInput, SquadIngestResult
from football_intel.raw_responses import RawResponseStore
from football_intel.sources.interface import CircuitOpenError, SourceInterface
from football_intel.sources.transfermarkt.squads import fetch_squad
from football_intel.sources.transfermarkt.transports import RecordingTransport


class TransfermarktActivities:
    """Transfermarkt activities. `source` is the worker's one Transfermarkt source interface."""

    def __init__(self, database_url: str, source: SourceInterface) -> None:
        self._database_url = database_url
        self._source = source

    @activity.defn
    async def ingest_club_squad(self, input: SquadIngestInput) -> SquadIngestResult:
        """Fetch a squad and store every upstream response as a Raw Response."""
        async with await AsyncConnection.connect(self._database_url, autocommit=True) as conn:
            freshness = None if input.refresh else self._source.freshness
            transport = RecordingTransport(
                self._source.transport(), RawResponseStore(conn), freshness
            )
            try:
                squad = await fetch_squad(transport, input.club_id, input.season_id)
            except CircuitOpenError as error:
                raise _retry_after_cooldown(error) from error
        activity.logger.info(
            "Club %s season %s: %d players; %d Raw Responses fetched, %d reused",
            input.club_id,
            input.season_id,
            len(squad.players),
            transport.recorded,
            transport.reused,
        )
        return SquadIngestResult(
            club_id=input.club_id,
            season_id=input.season_id,
            players=len(squad.players),
            raw_responses=transport.recorded,
            reused=transport.reused,
        )


def _retry_after_cooldown(error: CircuitOpenError) -> ApplicationError:
    """Fail the attempt, and schedule the next one for when the circuit breaker lets requests by."""
    return ApplicationError(
        str(error),
        type=type(error).__name__,
        next_retry_delay=timedelta(seconds=error.retry_after),
    )
