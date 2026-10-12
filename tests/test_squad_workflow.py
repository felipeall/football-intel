import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from psycopg import AsyncConnection
from temporalio.client import WorkflowExecutionStatus
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from football_intel.ingestion.activities import TransfermarktActivities
from football_intel.ingestion.models import SquadIngestInput
from football_intel.ingestion.workflows import SquadIngestWorkflow
from tests.transfermarkt_stub import CLUB_ID, PLAYER_IDS, SEASON_ID, TransfermarktStub


@pytest.fixture(scope="session")
async def temporal() -> AsyncIterator[WorkflowEnvironment]:
    # The SDK's signature has a partially unknown parameter type.
    async with await WorkflowEnvironment.start_local() as env:  # pyright: ignore[reportUnknownMemberType]
        yield env


async def test_squad_workflow_stores_raw_responses_end_to_end(
    temporal: WorkflowEnvironment, database_url: str, connection: AsyncConnection[Any]
) -> None:
    stub = TransfermarktStub()
    activities = TransfermarktActivities(database_url, backend=stub.transport)
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
