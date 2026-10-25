"""The `identity` schema: Players and Identity Candidates (ADR 31)."""

from collections.abc import Iterable
from typing import Any

from psycopg import AsyncConnection
from psycopg.types.json import Jsonb

from football_intel.identity.rules import Method, Proposal

SOFASCORE = "sofascore"


class IdentityStore:
    """Writes Players and Identity Candidates. A Source Record is only ever proposed once:
    a re-run leaves earlier Candidates, accepted, pending or rejected, as they are."""

    def __init__(self, connection: AsyncConnection[Any]) -> None:
        self._connection = connection

    async def anchor_sofascore(
        self, sofascore_player_ids: Iterable[int]
    ) -> tuple[dict[int, int], int]:
        """The Player of every Sofascore player, created for those that have none yet.

        Returns the Player IDs by Sofascore player ID, and how many Players were created.
        """
        cursor = await self._connection.execute(
            """
            SELECT source_record_id::bigint, player_id FROM identity.identity_candidates
            WHERE source = %s AND status = 'accepted'
            """,
            (SOFASCORE,),
        )
        players: dict[int, int] = dict(await cursor.fetchall())
        created = 0
        for sofascore_id in sorted(set(sofascore_player_ids) - players.keys()):
            cursor = await self._connection.execute(
                "INSERT INTO identity.players DEFAULT VALUES RETURNING player_id"
            )
            row = await cursor.fetchone()
            assert row is not None
            players[sofascore_id] = row[0]
            await self._insert(
                SOFASCORE, sofascore_id, row[0], Method.SOFASCORE_ANCHOR, 1.0, "accepted", {}
            )
            created += 1
        return players, created

    async def propose(
        self, source: str, proposals: Iterable[Proposal], players: dict[int, int]
    ) -> int:
        """Store new Proposals as Candidates: accepted from `ACCEPT_FROM`, pending below.

        A Proposal for a Source Record that already has a Candidate is skipped, and one that
        would give a Player a second link from the same source waits for the judge instead.
        Returns how many Candidates were stored.
        """
        cursor = await self._connection.execute(
            "SELECT DISTINCT source_record_id FROM identity.identity_candidates WHERE source = %s",
            (source,),
        )
        proposed = {row[0] for row in await cursor.fetchall()}
        cursor = await self._connection.execute(
            """
            SELECT player_id FROM identity.identity_candidates
            WHERE source = %s AND status = 'accepted'
            """,
            (source,),
        )
        linked = {row[0] for row in await cursor.fetchall()}
        stored = 0
        for proposal in proposals:
            if str(proposal.source_record_id) in proposed:
                continue
            player_id = players[proposal.sofascore_player_id]
            accepted = proposal.accepted and player_id not in linked
            await self._insert(
                source,
                proposal.source_record_id,
                player_id,
                proposal.method,
                proposal.confidence,
                "accepted" if accepted else "pending",
                proposal.evidence,
            )
            if accepted:
                linked.add(player_id)
            stored += 1
        return stored

    async def counts(self) -> list[tuple[str, str, str, int]]:
        """Candidates by source, method and status."""
        cursor = await self._connection.execute(
            """
            SELECT source, method, status, count(*) FROM identity.identity_candidates
            GROUP BY 1, 2, 3 ORDER BY 1, 2, 3
            """
        )
        return [
            (source, method, status, count)
            for source, method, status, count in await cursor.fetchall()
        ]

    async def _insert(
        self,
        source: str,
        source_record_id: int,
        player_id: int,
        method: str,
        confidence: float,
        status: str,
        evidence: dict[str, Any],
    ) -> None:
        await self._connection.execute(
            """
            INSERT INTO identity.identity_candidates
                (source, source_record_id, player_id, method, confidence, status, evidence,
                 decided_at, decided_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s,
                    CASE WHEN %s = 'pending' THEN NULL ELSE now() END,
                    CASE WHEN %s = 'pending' THEN NULL ELSE %s END)
            """,
            (
                source,
                str(source_record_id),
                player_id,
                method,
                confidence,
                status,
                Jsonb(evidence),
                status,
                status,
                f"rule:{method}",
            ),
        )
