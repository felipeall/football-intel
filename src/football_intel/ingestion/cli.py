"""Command line: start ingestion workflows and report per-source success rates."""

import argparse
import asyncio
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta

from psycopg import AsyncConnection
from temporalio.client import Client

from football_intel.config import Settings
from football_intel.fetch_attempts import FetchAttemptStore, SuccessRate
from football_intel.ingestion.models import (
    BackfillInput,
    CompetitionSquadsInput,
    MatchIngestInput,
    SquadIngestInput,
    SquadIngestResult,
    UnderstatIngestInput,
)
from football_intel.ingestion.schedules import (
    POST_MATCH_SCHEDULE_ID,
    UNDERSTAT_SCHEDULE_ID,
    ensure_post_match_schedule,
    ensure_understat_schedule,
)
from football_intel.ingestion.workflows import (
    BackfillWorkflow,
    CompetitionSquadsWorkflow,
    MatchIngestWorkflow,
    SquadIngestWorkflow,
    UnderstatIngestWorkflow,
)
from football_intel.sources.sofascore.seasons import PREMIER_LEAGUE as SOFASCORE_PREMIER_LEAGUE
from football_intel.sources.transfermarkt.competitions import PREMIER_LEAGUE
from football_intel.sources.understat.league import PREMIER_LEAGUE as UNDERSTAT_PREMIER_LEAGUE


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


async def ingest_match(settings: Settings, event_id: int, refresh: bool) -> None:
    client = await _client(settings)
    result = await client.execute_workflow(
        MatchIngestWorkflow.run,
        MatchIngestInput(event_id=event_id, refresh=refresh),
        id=f"match-{event_id}",
        task_queue=settings.temporal_task_queue,
    )
    source = "cache hit, nothing fetched" if result.cache_hit else "fetched"
    print(
        f"Match {result.event_id} ({result.name}): {result.players} players, "
        f"{result.raw_responses} Raw Responses stored, {result.reused} reused ({source})"
    )


async def backfill(
    settings: Settings, year: str | None, refresh: bool, concurrency: int, per_player: bool
) -> None:
    client = await _client(settings)
    suffix = f"-{year.replace('/', '-')}" if year else ""
    result = await client.execute_workflow(
        BackfillWorkflow.run,
        BackfillInput(
            tournament_id=SOFASCORE_PREMIER_LEAGUE,
            year=year,
            refresh=refresh,
            max_concurrent_matches=concurrency,
            per_player=per_player,
        ),
        id=f"backfill-{SOFASCORE_PREMIER_LEAGUE}{suffix}",
        task_queue=settings.temporal_task_queue,
    )
    print("Full pass, with per-player data" if result.per_player else "Match-level pass")
    for season in result.seasons:
        print(
            f"Season {season.season.year}: {season.matches} finished Matches, "
            f"{season.already_complete} already complete, {season.ingested} ingested, "
            f"{len(season.failed_event_ids)} failed; "
            f"{season.raw_responses} Raw Responses stored, {season.reused} reused"
        )
        if season.failed_event_ids:
            print(f"  Failed Matches: {', '.join(map(str, season.failed_event_ids))}")
        if season.challenged:
            print(
                f"  Stopped: Sofascore's bot challenge; {len(season.not_attempted_event_ids)} "
                "Matches not attempted. Re-run once it has lifted."
            )


async def schedule_post_match(settings: Settings) -> None:
    outcome = await ensure_post_match_schedule(
        await _client(settings), settings.temporal_task_queue
    )
    print(f"Schedule {POST_MATCH_SCHEDULE_ID} {outcome}: daily at 06:00 UTC, paused")


async def understat_backfill(settings: Settings, year: int | None, refresh: bool) -> None:
    client = await _client(settings)
    suffix = f"-{year}" if year is not None else ""
    result = await client.execute_workflow(
        UnderstatIngestWorkflow.run,
        UnderstatIngestInput(league=UNDERSTAT_PREMIER_LEAGUE, year=year, refresh=refresh),
        id=f"understat-{UNDERSTAT_PREMIER_LEAGUE}{suffix}",
        task_queue=settings.temporal_task_queue,
    )
    for season in result.seasons:
        print(
            f"Understat {season.league} {season.year}: {season.matches} played Matches, "
            f"{season.already_complete} already stored, {season.ingested} ingested, "
            f"{len(season.failed_match_ids)} failed; {season.raw_responses} Raw Responses stored"
        )
        if season.failed_match_ids:
            print(f"  Failed Matches: {', '.join(map(str, season.failed_match_ids))}")


async def schedule_understat(settings: Settings) -> None:
    outcome = await ensure_understat_schedule(await _client(settings), settings.temporal_task_queue)
    print(f"Schedule {UNDERSTAT_SCHEDULE_ID} {outcome}: daily at 07:00 UTC, paused")


SUCCESS_RATE_COLUMNS = (
    "source",
    "day",
    "attempts",
    "success",
    "not_found",
    "blocked",
    "other_4xx",
    "server_error",
    "timeout_transport",
    "circuit_open",
    "reused",
    "success_rate",
)


def format_success_rates(rates: Sequence[SuccessRate]) -> str:
    """A plain-text table, one row per source and day."""
    if not rates:
        return "No Fetch Attempts in this range."
    rows = [SUCCESS_RATE_COLUMNS] + [
        (
            rate.source,
            rate.day.isoformat(),
            *(
                str(count)
                for count in (
                    rate.attempts,
                    rate.success,
                    rate.not_found,
                    rate.blocked,
                    rate.other_client_error,
                    rate.server_error,
                    rate.timeout_or_transport_error,
                    rate.circuit_open,
                    rate.reused,
                )
            ),
            "-" if rate.success_rate is None else f"{rate.success_rate:.1%}",
        )
        for rate in rates
    ]
    widths = [max(len(row[i]) for row in rows) for i in range(len(SUCCESS_RATE_COLUMNS))]
    return "\n".join(
        "  ".join(
            cell.ljust(width) if i < 2 else cell.rjust(width)
            for i, (cell, width) in enumerate(zip(row, widths, strict=True))
        ).rstrip()
        for row in rows
    )


async def success_rates(settings: Settings, first_day: date, last_day: date) -> None:
    async with await AsyncConnection.connect(settings.database_url, autocommit=True) as conn:
        rates = await FetchAttemptStore(conn).success_rates(first_day, last_day)
    print(format_success_rates(rates))


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

    match = commands.add_parser(
        "ingest-match", help="store one finished Sofascore Match as Raw Responses"
    )
    match.add_argument("event_id", type=int, help="Sofascore event ID, e.g. 16363874")
    match.add_argument("--refresh", action="store_true", help=refresh_help)

    backfill_parser = commands.add_parser(
        "backfill",
        help="store every finished Premier League Match of the last three seasons from Sofascore",
    )
    backfill_parser.add_argument(
        "--season", help='only this season, as Sofascore writes it, e.g. "24/25"'
    )
    backfill_parser.add_argument("--refresh", action="store_true", help=refresh_help)
    backfill_parser.add_argument(
        "--match-level",
        action="store_true",
        help="first pass: event, lineups, shotmap and average positions only (4 requests a "
        "Match); without it, the full pass adds per-player heatmaps and rating breakdowns",
    )
    backfill_parser.add_argument(
        "--concurrency", type=int, default=3, help="Matches in flight at once (default 3)"
    )

    commands.add_parser(
        "schedule-post-match",
        help="create or update the daily Schedule that starts post-match workflows",
    )

    understat_parser = commands.add_parser(
        "understat-backfill",
        help="store every played Premier League Match of the last three seasons from Understat",
    )
    understat_parser.add_argument(
        "--season", type=int, help="only this season, by its start year, e.g. 2025 for 25/26"
    )
    understat_parser.add_argument("--refresh", action="store_true", help=refresh_help)

    commands.add_parser(
        "schedule-understat",
        help="create or update the daily Schedule that stores new Understat Matches",
    )

    today = datetime.now(UTC).date()
    rates = commands.add_parser(
        "success-rates", help="print each source's Fetch Attempts and success rate per day (UTC)"
    )
    rates.add_argument(
        "--from",
        dest="first_day",
        type=date.fromisoformat,
        default=today - timedelta(days=6),
        help="first day, YYYY-MM-DD (default six days ago)",
    )
    rates.add_argument(
        "--to",
        dest="last_day",
        type=date.fromisoformat,
        default=today,
        help="last day, included, YYYY-MM-DD (default today)",
    )

    args = parser.parse_args()
    settings = Settings()
    if args.command == "success-rates":
        asyncio.run(success_rates(settings, args.first_day, args.last_day))
    elif args.command == "schedule-post-match":
        asyncio.run(schedule_post_match(settings))
    elif args.command == "schedule-understat":
        asyncio.run(schedule_understat(settings))
    elif args.command == "understat-backfill":
        asyncio.run(understat_backfill(settings, args.season, args.refresh))
    elif args.command == "backfill":
        asyncio.run(
            backfill(settings, args.season, args.refresh, args.concurrency, not args.match_level)
        )
    elif args.command == "ingest-match":
        asyncio.run(ingest_match(settings, args.event_id, args.refresh))
    elif args.command == "ingest-squad":
        asyncio.run(ingest_squad(settings, args.club_id, args.season, args.refresh))
    else:
        asyncio.run(
            ingest_competition(
                settings, args.competition, args.season, args.refresh, args.concurrency
            )
        )


if __name__ == "__main__":
    main()
