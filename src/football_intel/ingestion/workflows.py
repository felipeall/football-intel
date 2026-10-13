"""Workflows. Deterministic: no I/O here, only activity calls."""

import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ChildWorkflowError

with workflow.unsafe.imports_passed_through():
    from football_intel.ingestion.activities import SofascoreActivities, TransfermarktActivities
    from football_intel.ingestion.models import (
        BackfillInput,
        BackfillResult,
        CompetitionClubsInput,
        CompetitionSquadsInput,
        CompetitionSquadsResult,
        CompleteMatchesInput,
        MatchIngestInput,
        MatchIngestResult,
        SeasonBackfillInput,
        SeasonBackfillResult,
        SeasonMatchesInput,
        SeasonsInput,
        SquadIngestInput,
        SquadIngestResult,
    )
    from football_intel.sources import sofascore, transfermarkt

# Polite backoff: 10s, 20s, 40s, 80s between the five attempts. A failed attempt is retried
# whole; Raw Responses it stored stay, as a record of what the source answered.
TRANSFERMARKT_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=10),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=5),
    maximum_attempts=5,
    non_retryable_error_types=list(transfermarkt.NON_RETRYABLE_ERRORS),
)
# The same backoff for Sofascore. A retried Match reuses the Raw Responses its failed attempts
# stored within the Freshness Window, so it only fetches what is still missing.
SOFASCORE_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=10),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=5),
    maximum_attempts=5,
    non_retryable_error_types=list(sofascore.NON_RETRYABLE_ERRORS),
)


@workflow.defn
class SquadIngestWorkflow:
    """Store one club's squad for one season as Raw Responses."""

    @workflow.run
    async def run(self, input: SquadIngestInput) -> SquadIngestResult:
        return await workflow.execute_activity_method(
            TransfermarktActivities.ingest_club_squad,
            input,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=TRANSFERMARKT_RETRY_POLICY,
        )


@workflow.defn
class CompetitionSquadsWorkflow:
    """Store every club's squad in one competition season as Raw Responses.

    One child `SquadIngestWorkflow` per club. A club that fails does not stop the others; the
    result lists it.
    """

    @workflow.run
    async def run(self, input: CompetitionSquadsInput) -> CompetitionSquadsResult:
        clubs = await workflow.execute_activity_method(
            TransfermarktActivities.ingest_competition_clubs,
            CompetitionClubsInput(input.competition_id, input.season_id, input.refresh),
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=TRANSFERMARKT_RETRY_POLICY,
        )
        slots = asyncio.Semaphore(input.max_concurrent_clubs)

        async def squad(club_id: str) -> SquadIngestResult | None:
            async with slots:
                try:
                    return await workflow.execute_child_workflow(
                        SquadIngestWorkflow.run,
                        SquadIngestInput(club_id, input.season_id, input.refresh),
                        id=f"{workflow.info().workflow_id}-squad-{club_id}",
                    )
                except ChildWorkflowError:
                    workflow.logger.warning("Squad of club %s failed", club_id)
                    return None

        results = await asyncio.gather(*(squad(club_id) for club_id in clubs.club_ids))
        return CompetitionSquadsResult(
            competition_id=input.competition_id,
            season_id=input.season_id,
            clubs=clubs,
            squads=[result for result in results if result is not None],
            failed_club_ids=[
                club_id
                for club_id, result in zip(clubs.club_ids, results, strict=True)
                if result is None
            ],
        )


@workflow.defn
class MatchIngestWorkflow:
    """Store one finished Sofascore Match as Raw Responses."""

    @workflow.run
    async def run(self, input: MatchIngestInput) -> MatchIngestResult:
        # About 70 requests: a little over a minute at one per second, several when Matches
        # in flight share the rate limit. Heartbeats on every request catch a dead worker.
        return await workflow.execute_activity_method(
            SofascoreActivities.ingest_match,
            input,
            start_to_close_timeout=timedelta(minutes=30),
            heartbeat_timeout=timedelta(minutes=1),
            retry_policy=SOFASCORE_RETRY_POLICY,
        )


@workflow.defn
class SeasonBackfillWorkflow:
    """Store every finished Match of one season as Raw Responses.

    Matches already stored completely are skipped without a request. One child
    `MatchIngestWorkflow` per remaining Match; a Match that fails does not stop the others,
    and the result lists it.
    """

    @workflow.run
    async def run(self, input: SeasonBackfillInput) -> SeasonBackfillResult:
        listing = await workflow.execute_activity_method(
            SofascoreActivities.season_matches,
            SeasonMatchesInput(input.tournament_id, input.season.id, input.refresh),
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=SOFASCORE_RETRY_POLICY,
        )
        complete: set[int] = set()
        if not input.refresh:
            complete = set(
                await workflow.execute_activity_method(
                    SofascoreActivities.complete_matches,
                    CompleteMatchesInput(listing.event_ids),
                    start_to_close_timeout=timedelta(minutes=30),
                    heartbeat_timeout=timedelta(minutes=1),
                    retry_policy=SOFASCORE_RETRY_POLICY,
                )
            )
        pending = [event_id for event_id in listing.event_ids if event_id not in complete]
        slots = asyncio.Semaphore(input.max_concurrent_matches)

        async def match(event_id: int) -> MatchIngestResult | None:
            async with slots:
                try:
                    return await workflow.execute_child_workflow(
                        MatchIngestWorkflow.run,
                        MatchIngestInput(event_id, input.refresh),
                        id=f"{workflow.info().workflow_id}-match-{event_id}",
                    )
                except ChildWorkflowError:
                    workflow.logger.warning("Match %s failed", event_id)
                    return None

        results = await asyncio.gather(*(match(event_id) for event_id in pending))
        ingested = [result for result in results if result is not None]
        return SeasonBackfillResult(
            season=input.season,
            matches=len(listing.event_ids),
            already_complete=len(complete),
            ingested=len(ingested),
            failed_event_ids=[
                event_id
                for event_id, result in zip(pending, results, strict=True)
                if result is None
            ],
            raw_responses=listing.raw_responses + sum(r.raw_responses for r in ingested),
            reused=listing.reused + sum(r.reused for r in ingested),
        )


@workflow.defn
class BackfillWorkflow:
    """Store a tournament's latest seasons (ADR 5: the current one and the two before it), or
    one chosen season, as Raw Responses. One child `SeasonBackfillWorkflow` per season, one
    season after another."""

    @workflow.run
    async def run(self, input: BackfillInput) -> BackfillResult:
        seasons = await workflow.execute_activity_method(
            SofascoreActivities.tournament_seasons,
            SeasonsInput(input.tournament_id, input.count, input.year, input.refresh),
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=SOFASCORE_RETRY_POLICY,
        )
        results: list[SeasonBackfillResult] = []
        for season in seasons:
            results.append(
                await workflow.execute_child_workflow(
                    SeasonBackfillWorkflow.run,
                    SeasonBackfillInput(
                        input.tournament_id,
                        season,
                        input.refresh,
                        input.max_concurrent_matches,
                    ),
                    id=f"{workflow.info().workflow_id}-season-{season.id}",
                )
            )
        return BackfillResult(tournament_id=input.tournament_id, seasons=results)
