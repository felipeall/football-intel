"""Ingestion worker: runs the workflows and activities on the ingestion task queue."""

import asyncio
import logging

from temporalio.client import Client
from temporalio.worker import Worker

from football_intel.config import Settings
from football_intel.ingestion.activities import TransfermarktActivities
from football_intel.ingestion.workflows import SquadIngestWorkflow
from football_intel.sources.interface import SourceInterface
from football_intel.sources.transfermarkt import SOURCE, is_upstream_failure


async def run_worker(settings: Settings) -> None:
    client = await Client.connect(settings.temporal_address, namespace=settings.temporal_namespace)
    transfermarkt = SourceInterface(SOURCE, settings.transfermarkt, is_failure=is_upstream_failure)
    activities = TransfermarktActivities(settings.database_url, transfermarkt)
    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[SquadIngestWorkflow],
        activities=[activities.ingest_club_squad],
    )
    await worker.run()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    # httpx logs full request URLs; ours are logged redacted by the recording transport.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    asyncio.run(run_worker(Settings()))


if __name__ == "__main__":
    main()
