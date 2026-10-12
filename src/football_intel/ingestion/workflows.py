"""Workflows. Deterministic: no I/O here, only activity calls."""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from football_intel.ingestion.activities import TransfermarktActivities
    from football_intel.ingestion.models import SquadIngestInput, SquadIngestResult


@workflow.defn
class SquadIngestWorkflow:
    """Store one club's squad for one season as Raw Responses."""

    @workflow.run
    async def run(self, input: SquadIngestInput) -> SquadIngestResult:
        return await workflow.execute_activity_method(
            TransfermarktActivities.ingest_club_squad,
            input,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
