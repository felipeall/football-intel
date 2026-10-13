"""Temporal Schedules: the post-match refresh cadence (ADR 5)."""

from temporalio.client import (
    Client,
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleAlreadyRunningError,
    ScheduleCalendarSpec,
    ScheduleOverlapPolicy,
    SchedulePolicy,
    ScheduleRange,
    ScheduleSpec,
    ScheduleUpdate,
    ScheduleUpdateInput,
)

from football_intel.ingestion.models import FixturesInput
from football_intel.ingestion.workflows import FixturesWorkflow
from football_intel.sources.sofascore.seasons import PREMIER_LEAGUE

POST_MATCH_SCHEDULE_ID = "post-match-fixtures"
RUN_AT_HOUR_UTC = 6


def post_match_schedule(task_queue: str) -> Schedule:
    """Daily at 06:00 UTC, read the Premier League's fixtures and start their post-match
    workflows. A run still going at the next one's time makes that one skip."""
    return Schedule(
        action=ScheduleActionStartWorkflow(
            FixturesWorkflow.run,
            FixturesInput(tournament_id=PREMIER_LEAGUE),
            id=POST_MATCH_SCHEDULE_ID,
            task_queue=task_queue,
        ),
        spec=ScheduleSpec(calendars=[ScheduleCalendarSpec(hour=[ScheduleRange(RUN_AT_HOUR_UTC)])]),
        policy=SchedulePolicy(overlap=ScheduleOverlapPolicy.SKIP),
    )


async def ensure_post_match_schedule(client: Client, task_queue: str) -> str:
    """Create the post-match Schedule, or update it to the current definition.

    Returns "created" or "updated"; running it again changes nothing else.
    """
    schedule = post_match_schedule(task_queue)
    try:
        await client.create_schedule(POST_MATCH_SCHEDULE_ID, schedule)
        return "created"
    except ScheduleAlreadyRunningError:

        def update(_: ScheduleUpdateInput) -> ScheduleUpdate:
            return ScheduleUpdate(schedule=schedule)

        await client.get_schedule_handle(POST_MATCH_SCHEDULE_ID).update(update)
        return "updated"
