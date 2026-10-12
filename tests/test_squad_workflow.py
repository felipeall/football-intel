import uuid
from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx
import pytest
from psycopg import AsyncConnection
from temporalio.client import WorkflowExecutionStatus, WorkflowFailureError
from temporalio.exceptions import ActivityError, ApplicationError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from football_intel.ingestion.activities import TransfermarktActivities
from football_intel.ingestion.models import SquadIngestInput
from football_intel.ingestion.workflows import TRANSFERMARKT_RETRY_POLICY, SquadIngestWorkflow
from football_intel.sources.interface import SourceInterface, SourcePolicy
from football_intel.sources.transfermarkt import SOURCE, is_upstream_failure
from tests.transfermarkt_stub import CLUB_ID, PLAYER_IDS, SEASON_ID, TransfermarktStub


def _source(backend: Callable[[], httpx.AsyncBaseTransport]) -> SourceInterface:
    policy = SourcePolicy(requests_per_second=1000, breaker_failures=100)
    return SourceInterface(SOURCE, policy, is_failure=is_upstream_failure, backend=backend)


@pytest.fixture(scope="session")
async def temporal() -> AsyncIterator[WorkflowEnvironment]:
    # The SDK's signature has a partially unknown parameter type.
    async with await WorkflowEnvironment.start_local() as env:  # pyright: ignore[reportUnknownMemberType]
        yield env


async def test_squad_workflow_stores_raw_responses_end_to_end(
    temporal: WorkflowEnvironment, database_url: str, connection: AsyncConnection[Any]
) -> None:
    stub = TransfermarktStub()
    activities = TransfermarktActivities(database_url, _source(stub.transport))
    task_queue = f"test-{uuid.uuid4()}"

    async with Worker(
        temporal.client,
        task_queue=task_queue,
        workflows=[SquadIngestWorkflow],
        activities=[activities.ingest_club_squad],
    ):
        handle = await temporal.client.start_workflow(
            SquadIngestWorkflow.run,
            SquadIngestInput(club_id=CLUB_ID, season_id=SEASON_ID),
            id=f"squad-{uuid.uuid4()}",
            task_queue=task_queue,
        )
        result = await handle.result()

    assert (await handle.describe()).status == WorkflowExecutionStatus.COMPLETED
    assert result.players == len(PLAYER_IDS)
    assert result.raw_responses == len(stub.requests)
    cursor = await connection.execute(
        "SELECT count(*) FROM raw.raw_responses WHERE source = 'transfermarkt'"
    )
    assert await cursor.fetchone() == (len(stub.requests),)


class FlakySquad(TransfermarktStub):
    """Fails the squad request `failures` times with `fail`, then answers like the stub."""

    def __init__(self, failures: int, fail: Callable[[httpx.Request], httpx.Response]) -> None:
        super().__init__()
        self.failures = failures
        self.fail = fail
        self.squad_requests = 0

    def handle(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == f"/club/{CLUB_ID}/squad":
            self.squad_requests += 1
            if self.squad_requests <= self.failures:
                self.requests.append(request)
                return self.fail(request)
        return super().handle(request)


def _blocked(request: httpx.Request) -> httpx.Response:
    return httpx.Response(403)


def _not_found(request: httpx.Request) -> httpx.Response:
    return httpx.Response(404)


def _timeout(request: httpx.Request) -> httpx.Response:
    raise httpx.ReadTimeout("timed out", request=request)


@pytest.fixture(scope="session")
async def time_skipping() -> AsyncIterator[WorkflowEnvironment]:
    # Skips the retry policy's backoff instead of waiting it out.
    async with await WorkflowEnvironment.start_time_skipping() as env:  # pyright: ignore[reportUnknownMemberType]
        yield env


async def _run(env: WorkflowEnvironment, database_url: str, stub: TransfermarktStub) -> Any:
    activities = TransfermarktActivities(database_url, _source(stub.transport))
    task_queue = f"test-{uuid.uuid4()}"
    async with Worker(
        env.client,
        task_queue=task_queue,
        workflows=[SquadIngestWorkflow],
        activities=[activities.ingest_club_squad],
    ):
        return await env.client.execute_workflow(
            SquadIngestWorkflow.run,
            SquadIngestInput(club_id=CLUB_ID, season_id=SEASON_ID),
            id=f"squad-{uuid.uuid4()}",
            task_queue=task_queue,
        )


@pytest.mark.parametrize(
    "fail",
    [
        pytest.param(_blocked, id="UpstreamBlocked"),
        pytest.param(_timeout, id="httpx-timeout"),
    ],
)
async def test_transient_failures_are_retried_with_backoff(
    time_skipping: WorkflowEnvironment,
    database_url: str,
    connection: AsyncConnection[Any],
    fail: Callable[[httpx.Request], httpx.Response],
) -> None:
    stub = FlakySquad(failures=2, fail=fail)

    result = await _run(time_skipping, database_url, stub)

    assert result.players == len(PLAYER_IDS)
    assert stub.squad_requests == 3
    assert TRANSFERMARKT_RETRY_POLICY.backoff_coefficient > 1


async def test_not_found_is_not_retried(
    time_skipping: WorkflowEnvironment, database_url: str, connection: AsyncConnection[Any]
) -> None:
    stub = FlakySquad(failures=5, fail=_not_found)

    with pytest.raises(WorkflowFailureError) as failure:
        await _run(time_skipping, database_url, stub)

    activity_error = failure.value.cause
    assert isinstance(activity_error, ActivityError)
    assert isinstance(activity_error.cause, ApplicationError)
    assert activity_error.cause.type == "NotFound"
    assert stub.squad_requests == 1
