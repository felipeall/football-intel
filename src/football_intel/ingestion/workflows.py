"""Workflows. Deterministic: no I/O here, only activity calls."""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from football_intel.ingestion.activities import TransfermarktActivities
    from football_intel.ingestion.models import SquadIngestInput, SquadIngestResult
    from football_intel.sources.transfermarkt import NON_RETRYABLE_ERRORS

# Polite backoff: 10s, 20s, 40s, 80s between the five attempts. A failed attempt is retried
# whole; Raw Responses it stored stay, as a record of what the source answered.
TRANSFERMARKT_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=10),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=5),
    maximum_attempts=5,
    non_retryable_error_types=list(NON_RETRYABLE_ERRORS),
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
