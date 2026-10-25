"""Identity Resolution workflow. Deterministic: the work is one activity."""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from football_intel.identity.activities import IdentityActivities, IdentityResolutionResult


@workflow.defn
class IdentityResolutionWorkflow:
    """Link the staged Source Records to Players (ADR 6). Part of the Transform Run (ADR 31),
    between building staging and building the marts that read the `identity` schema."""

    @workflow.run
    async def run(self) -> IdentityResolutionResult:
        return await workflow.execute_activity_method(
            IdentityActivities.resolve_identities,
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
