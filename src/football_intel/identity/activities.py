"""Identity Resolution activities: read staged Source Records, write the `identity` schema."""

from dataclasses import dataclass
from typing import Any, LiteralString

from psycopg import AsyncConnection
from temporalio import activity
from temporalio.exceptions import ApplicationError

from football_intel.identity.rules import (
    Appearance,
    ReepBridge,
    SourcePlayer,
    reep_proposals,
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
    reep_release: str | None  # the Reep release that decided first; None when skipped
    players_created: int
    candidates_stored: int
    # Every Candidate in the schema after the run, not only this run's.
    candidates: list[CandidateCount]


class IdentityActivities:
    """`reep_release` is the pinned Reep release (ADR 32); None skips the Reep step."""

    def __init__(self, database_url: str, reep_release: str | None = None) -> None:
        self._database_url = database_url
        self._reep_release = reep_release

    @activity.defn
    async def resolve_identities(self) -> IdentityResolutionResult:
        """Link the staged Source Records to Players in one transaction: the pinned Reep
        release's mappings first, then the deterministic rules and fuzzy scoring for what
        Reep did not link (ADR 32). Needs dbt's staging models and the Club and Match marts."""
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
            cursor = await conn.execute(
                "SELECT player_id, name FROM staging.stg_understat__players"
            )
            understat_names: dict[int, str] = dict(await cursor.fetchall())
            store = IdentityStore(conn)
            players, created = await store.anchor_sofascore(p.source_record_id for p in sofascore)
            stored = 0
            if self._reep_release is not None:
                held = {
                    "transfermarkt": {p.source_record_id for p in transfermarkt},
                    "understat": set(understat_names),
                }
                for source, records in held.items():
                    bridges = await _reep_bridges(conn, self._reep_release, source)
                    stored += await store.propose(
                        source,
                        reep_proposals(self._reep_release, bridges, records, set(players)),
                        players,
                    )
            stored += await store.propose(
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
        return IdentityResolutionResult(self._reep_release, created, stored, counts)


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


async def _reep_bridges(conn: AsyncConnection[Any], release: str, source: str) -> list[ReepBridge]:
    """The release's bridges from `source` players to Sofascore players. Fails without
    retries if the release is not loaded: `football-intel load-reep` loads it."""
    cursor = await conn.execute(
        "SELECT 1 FROM reference.reep_releases WHERE release = %s", (release,)
    )
    if await cursor.fetchone() is None:
        raise ApplicationError(
            f"Reep release {release} is not loaded; run `football-intel load-reep`",
            type="ReepReleaseNotLoaded",
            non_retryable=True,
        )
    cursor = await conn.execute(
        """
        SELECT other.external_id::bigint, sofascore.external_id::bigint, other.rule_id,
            other.route_scope
        FROM reference.reep_player_bridges AS other
        JOIN reference.reep_player_bridges AS sofascore
            ON sofascore.release = other.release AND sofascore.reep_id = other.reep_id
            AND sofascore.provider = 'sofascore'
        WHERE other.release = %s AND other.provider = %s
            AND other.external_id ~ '^[0-9]+$' AND sofascore.external_id ~ '^[0-9]+$'
        """,
        (release, source),
    )
    return [ReepBridge(*row) for row in await cursor.fetchall()]
