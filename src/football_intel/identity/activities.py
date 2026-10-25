"""Identity Resolution activities: read staged Source Records, write the `identity` schema."""

from dataclasses import dataclass
from typing import Any, LiteralString

from psycopg import AsyncConnection
from temporalio import activity

from football_intel.identity.rules import (
    Appearance,
    SourcePlayer,
    transfermarkt_proposals,
    understat_proposals,
)
from football_intel.identity.store import IdentityStore


@dataclass(frozen=True)
class CandidateCount:
    source: str
    method: str
    status: str
    count: int


@dataclass(frozen=True)
class IdentityResolutionResult:
    players_created: int
    candidates_stored: int
    # Every Candidate in the schema after the run, not only this run's.
    candidates: list[CandidateCount]


class IdentityActivities:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    @activity.defn
    async def resolve_identities(self) -> IdentityResolutionResult:
        """Run the deterministic rules and fuzzy scoring over the staged Source Records, in
        one transaction. Needs dbt's staging models and the Club and Match marts built."""
        async with (
            await AsyncConnection.connect(self._database_url) as conn,
            conn.transaction(),
        ):
            sofascore = await _players(
                conn, "SELECT player_id, name, birth_date FROM staging.stg_sofascore__players"
            )
            transfermarkt = await _players(
                conn,
                "SELECT player_id, name, birth_date FROM staging.stg_transfermarkt__players",
            )
            understat_names = dict(
                await (
                    await conn.execute("SELECT player_id, name FROM staging.stg_understat__players")
                ).fetchall()
            )
            store = IdentityStore(conn)
            players, created = await store.anchor_sofascore(p.source_record_id for p in sofascore)
            stored = await store.propose(
                "transfermarkt", transfermarkt_proposals(transfermarkt, sofascore), players
            )
            stored += await store.propose(
                "understat",
                understat_proposals(
                    await _appearances(conn, "understat"),
                    await _appearances(conn, "sofascore"),
                    understat_names,
                    {p.source_record_id: p.name for p in sofascore},
                ),
                players,
            )
            counts = [CandidateCount(*row) for row in await store.counts()]
        activity.logger.info(
            "Identity Resolution: %d Players created, %d Candidates stored", created, stored
        )
        return IdentityResolutionResult(created, stored, counts)


async def _players(conn: AsyncConnection[Any], query: LiteralString) -> list[SourcePlayer]:
    cursor = await conn.execute(query)
    return [
        SourcePlayer(player_id, name, birth_date)
        for player_id, name, birth_date in await cursor.fetchall()
    ]


# A source's Appearances in canonical Matches both sources have, for canonical Clubs.
_APPEARANCES: dict[str, LiteralString] = {
    "sofascore": """
        SELECT matches.match_id, clubs.club_id, appearances.player_id, appearances.minutes_played
        FROM staging.stg_sofascore__appearances AS appearances
        JOIN marts.matches AS matches ON matches.sofascore_match_id = appearances.match_id
        JOIN marts.clubs AS clubs ON clubs.sofascore_team_id = appearances.team_id
        WHERE matches.understat_match_id IS NOT NULL
    """,
    "understat": """
        SELECT matches.match_id, clubs.club_id, appearances.player_id, appearances.minutes_played
        FROM staging.stg_understat__appearances AS appearances
        JOIN marts.matches AS matches ON matches.understat_match_id = appearances.match_id
        JOIN marts.clubs AS clubs ON clubs.understat_team_id = appearances.team_id
        WHERE matches.sofascore_match_id IS NOT NULL
    """,
}


async def _appearances(conn: AsyncConnection[Any], source: str) -> list[Appearance]:
    cursor = await conn.execute(_APPEARANCES[source])
    return [
        Appearance(match_id, club_id, player_id, minutes)
        for match_id, club_id, player_id, minutes in await cursor.fetchall()
    ]
