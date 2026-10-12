"""Command line: start ingestion workflows."""

import argparse
import asyncio

from temporalio.client import Client

from football_intel.config import Settings
from football_intel.ingestion.models import SquadIngestInput
from football_intel.ingestion.workflows import SquadIngestWorkflow


async def ingest_squad(settings: Settings, club_id: str, season_id: str) -> None:
    client = await Client.connect(settings.temporal_address, namespace=settings.temporal_namespace)
    result = await client.execute_workflow(
        SquadIngestWorkflow.run,
        SquadIngestInput(club_id=club_id, season_id=season_id),
        id=f"squad-{club_id}-{season_id}",
        task_queue=settings.temporal_task_queue,
    )
    print(
        f"Club {result.club_id} season {result.season_id}: {result.players} players, "
        f"{result.raw_responses} Raw Responses stored"
    )


def main() -> None:
    parser = argparse.ArgumentParser(prog="football-intel")
    commands = parser.add_subparsers(dest="command", required=True)
    squad = commands.add_parser("ingest-squad", help="store one club's squad as Raw Responses")
    squad.add_argument("club_id", help="Transfermarkt club ID, e.g. 985 (Manchester United)")
    squad.add_argument("--season", required=True, help="season start year, e.g. 2025")
    args = parser.parse_args()
    asyncio.run(ingest_squad(Settings(), args.club_id, args.season))


if __name__ == "__main__":
    main()
