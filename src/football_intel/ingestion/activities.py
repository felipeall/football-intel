"""Activities: all I/O of the ingestion workflows (HTTP, database) happens here."""

from collections.abc import AsyncGenerator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from datetime import timedelta

import httpx
from psycopg import AsyncConnection
from temporalio import activity
from temporalio.exceptions import ApplicationError

from football_intel.fetch_attempts import FetchAttemptStore
from football_intel.ingestion.models import (
    CompetitionClubsInput,
    CompetitionClubsResult,
    MatchIngestInput,
    MatchIngestResult,
    SquadIngestInput,
    SquadIngestResult,
)
from football_intel.raw_responses import RawResponseStore
from football_intel.sources import sofascore, transfermarkt
from football_intel.sources.interface import CircuitOpenError, SourceInterface
from football_intel.sources.recording import RecordingTransport
from football_intel.sources.sofascore.matches import fetch_match
from football_intel.sources.transfermarkt.competitions import fetch_competition_clubs
from football_intel.sources.transfermarkt.squads import fetch_squad


class TransfermarktActivities:
    """Transfermarkt activities. `source` is the worker's one Transfermarkt source interface."""

    def __init__(self, database_url: str, source: SourceInterface) -> None:
        self._database_url = database_url
        self._source = source

    @activity.defn
    async def ingest_club_squad(self, input: SquadIngestInput) -> SquadIngestResult:
        """Fetch a squad and store every upstream response as a Raw Response."""
        async with self._recording(input.refresh) as transport:
            squad = await fetch_squad(transport, input.club_id, input.season_id)
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

    @activity.defn
    async def ingest_competition_clubs(
        self, input: CompetitionClubsInput
    ) -> CompetitionClubsResult:
        """Fetch a competition season's clubs; store every upstream response as a Raw Response."""
        async with self._recording(input.refresh) as transport:
            competition = await fetch_competition_clubs(
                transport, input.competition_id, input.season_id
            )
        club_ids = [club.id for club in competition.clubs]
        activity.logger.info(
            "Competition %s season %s: %d clubs; %d Raw Responses fetched, %d reused",
            input.competition_id,
            input.season_id,
            len(club_ids),
            transport.recorded,
            transport.reused,
        )
        return CompetitionClubsResult(
            competition_id=input.competition_id,
            season_id=input.season_id,
            club_ids=club_ids,
            raw_responses=transport.recorded,
            reused=transport.reused,
        )

    def _recording(self, refresh: bool) -> AbstractAsyncContextManager[RecordingTransport]:
        return _recording(
            self._database_url, self._source, transfermarkt.recording_transport, refresh
        )


class SofascoreActivities:
    """Sofascore activities. `source` is the worker's one Sofascore source interface."""

    def __init__(self, database_url: str, source: SourceInterface) -> None:
        self._database_url = database_url
        self._source = source

    @activity.defn
    async def ingest_match(self, input: MatchIngestInput) -> MatchIngestResult:
        """Fetch one finished Match and store every response as a Raw Response."""
        async with _recording(
            self._database_url, self._source, sofascore.recording_transport, input.refresh
        ) as transport:
            match = await fetch_match(transport, input.event_id)
        activity.logger.info(
            "Match %s (%s): %d players; %d Raw Responses fetched, %d reused",
            input.event_id,
            match.name,
            len(match.player_ids),
            transport.recorded,
            transport.reused,
        )
        return MatchIngestResult(
            event_id=input.event_id,
            name=match.name,
            players=len(match.player_ids),
            raw_responses=transport.recorded,
            reused=transport.reused,
        )


RecordingFactory = Callable[
    [httpx.AsyncBaseTransport, RawResponseStore, FetchAttemptStore, timedelta | None],
    RecordingTransport,
]


@asynccontextmanager
async def _recording(
    database_url: str, source: SourceInterface, recording: RecordingFactory, refresh: bool
) -> AsyncGenerator[RecordingTransport]:
    """A recording transport over the source interface, for one activity attempt."""
    async with await AsyncConnection.connect(database_url, autocommit=True) as conn:
        freshness = None if refresh else source.freshness
        try:
            yield recording(
                source.transport(), RawResponseStore(conn), FetchAttemptStore(conn), freshness
            )
        except CircuitOpenError as error:
            raise _retry_after_cooldown(error) from error


def _retry_after_cooldown(error: CircuitOpenError) -> ApplicationError:
    """Fail the attempt, and schedule the next one for when the circuit breaker lets requests by."""
    return ApplicationError(
        str(error),
        type=type(error).__name__,
        next_retry_delay=timedelta(seconds=error.retry_after),
    )
