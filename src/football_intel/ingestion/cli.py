"""Command line: start ingestion workflows."""

import argparse
import asyncio

from temporalio.client import Client

from football_intel.config import Settings
from football_intel.ingestion.models import (
    CompetitionSquadsInput,
    SquadIngestInput,
    SquadIngestResult,
)
from football_intel.ingestion.workflows import CompetitionSquadsWorkflow, SquadIngestWorkflow
from football_intel.sources.transfermarkt.competitions import PREMIER_LEAGUE


async def _client(settings: Settings) -> Client:
    return await Client.connect(settings.temporal_address, namespace=settings.temporal_namespace)


def _squad_line(result: SquadIngestResult) -> str:
    source = "cache hit, nothing fetched" if result.cache_hit else "fetched"
    return (
        f"Club {result.club_id} season {result.season_id}: {result.players} players, "
        f"{result.raw_responses} Raw Responses stored, {result.reused} reused ({source})"
    )


async def ingest_squad(settings: Settings, club_id: str, season_id: str, refresh: bool) -> None:
    client = await _client(settings)
    result = await client.execute_workflow(
        SquadIngestWorkflow.run,
        SquadIngestInput(club_id=club_id, season_id=season_id, refresh=refresh),
        id=f"squad-{club_id}-{season_id}",
        task_queue=settings.temporal_task_queue,
    )
    print(_squad_line(result))


async def ingest_competition(
    settings: Settings, competition_id: str, season_id: str, refresh: bool, concurrency: int
) -> None:
    client = await _client(settings)
    result = await client.execute_workflow(
        CompetitionSquadsWorkflow.run,
        CompetitionSquadsInput(
            competition_id=competition_id,
            season_id=season_id,
            refresh=refresh,
            max_concurrent_clubs=concurrency,
        ),
        id=f"competition-squads-{competition_id}-{season_id}",
        task_queue=settings.temporal_task_queue,
    )
    clubs = result.clubs
    print(
        f"Competition {competition_id} season {season_id}: {len(clubs.club_ids)} clubs, "
        f"{clubs.raw_responses} Raw Responses stored, {clubs.reused} reused"
    )
    for squad in result.squads:
        print(f"  {_squad_line(squad)}")
    if result.failed_club_ids:
        print(f"Failed clubs: {', '.join(result.failed_club_ids)}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="football-intel")
    commands = parser.add_subparsers(dest="command", required=True)
    refresh_help = "fetch from the source even if fresh data is stored"

    squad = commands.add_parser("ingest-squad", help="store one club's squad as Raw Responses")
    squad.add_argument("club_id", help="Transfermarkt club ID, e.g. 985 (Manchester United)")
    squad.add_argument("--season", required=True, help="season start year, e.g. 2025")
    squad.add_argument("--refresh", action="store_true", help=refresh_help)

    competition = commands.add_parser(
        "ingest-competition", help="store every club's squad in a competition as Raw Responses"
    )
    competition.add_argument("--season", required=True, help="season start year, e.g. 2025")
    competition.add_argument(
        "--competition",
        default=PREMIER_LEAGUE,
        help=f"Transfermarkt competition ID (default {PREMIER_LEAGUE}, the Premier League)",
    )
    competition.add_argument("--refresh", action="store_true", help=refresh_help)
    competition.add_argument(
        "--concurrency", type=int, default=3, help="squads in flight at once (default 3)"
    )

    args = parser.parse_args()
    settings = Settings()
    if args.command == "ingest-squad":
        asyncio.run(ingest_squad(settings, args.club_id, args.season, args.refresh))
    else:
        asyncio.run(
            ingest_competition(
                settings, args.competition, args.season, args.refresh, args.concurrency
            )
        )


if __name__ == "__main__":
    main()
