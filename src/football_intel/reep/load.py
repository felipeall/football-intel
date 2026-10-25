"""Load a downloaded Reep release's player and team bridges into `reference` (ADR 32, 33)."""

import json
from pathlib import Path
from typing import Any

import duckdb
from psycopg import AsyncConnection
from psycopg.types.json import Jsonb

from football_intel.reep.release import Manifest

# The namespaces we use, per entity type and provider. Transfermarkt teams also have a
# `team` namespace in Reep; our Transfermarkt club IDs are `verein` IDs.
PLAYER_NAMESPACES = {"sofascore": "player", "transfermarkt": "spieler", "understat": "player"}
TEAM_NAMESPACES = {"sofascore": "team", "transfermarkt": "verein", "understat": "team"}

Bridge = tuple[str, str, str, str | None, str | None]  # reep_id, provider, external_id, rule, scope
TeamBridge = tuple[str, str, str]  # reep_id, provider, external_id


def player_bridges(directory: Path) -> list[Bridge]:
    """The bridges of every person Reep maps to a Sofascore player, for our three providers,
    with each Reep ID resolved through the release's redirects to its survivor."""
    return [
        (r, p, e, rule, scope)
        for r, p, e, rule, scope in _bridges(directory, "player", PLAYER_NAMESPACES)
    ]


def team_bridges(directory: Path) -> list[TeamBridge]:
    """The bridges of every team Reep maps to a Sofascore team (ADR 33), as for players."""
    return [(r, p, e) for r, p, e, _, _ in _bridges(directory, "team", TEAM_NAMESPACES)]


def _bridges(directory: Path, entity_type: str, namespaces: dict[str, str]) -> list[Bridge]:
    condition = " OR ".join(
        f"(provider = '{p}' AND namespace = '{n}')" for p, n in namespaces.items()
    )
    with duckdb.connect() as db:
        return [
            (
                str(r),
                str(p),
                str(e),
                None if rule is None else str(rule),
                None if scope is None else str(scope),
            )
            for r, p, e, rule, scope in db.execute(
                f"""
                WITH bridges AS (
                    SELECT DISTINCT COALESCE(redirects.to_id, bridges.reep_id) AS reep_id,
                        bridges.provider, bridges.external_id, bridges.rule_id, bridges.route_scope
                    FROM read_parquet(?) AS bridges
                    LEFT JOIN read_parquet(?) AS redirects ON redirects.from_id = bridges.reep_id
                    WHERE bridges.entity_type = ? AND ({condition})
                )
                SELECT reep_id, provider, external_id, rule_id, route_scope FROM bridges
                WHERE reep_id IN (SELECT reep_id FROM bridges WHERE provider = 'sofascore')
                ORDER BY reep_id, provider, external_id
                """,
                [
                    str(directory / "bridges.parquet"),
                    str(directory / "redirects.parquet"),
                    entity_type,
                ],
            ).fetchall()
        ]


async def load(
    conn: AsyncConnection[Any],
    manifest: Manifest,
    bridges: list[Bridge],
    teams: list[TeamBridge] | None = None,
) -> None:
    """Replace a release's rows with its player `bridges` and `teams`, in one transaction."""
    async with conn.transaction():
        await conn.execute(
            "DELETE FROM reference.reep_releases WHERE release = %s", (manifest.release,)
        )
        await conn.execute(
            "INSERT INTO reference.reep_releases (release, gate_passed, manifest)"
            " VALUES (%s, %s, %s)",
            (manifest.release, manifest.gate_passed, Jsonb(manifest.data)),
        )
        async with conn.cursor().copy(
            "COPY reference.reep_player_bridges"
            " (release, reep_id, provider, external_id, rule_id, route_scope) FROM STDIN"
        ) as copy:
            for bridge in bridges:
                await copy.write_row((manifest.release, *bridge))
        async with conn.cursor().copy(
            "COPY reference.reep_team_bridges (release, reep_id, provider, external_id) FROM STDIN"
        ) as copy:
            for team in teams or []:
                await copy.write_row((manifest.release, *team))
    # Fresh statistics, or the planner joins the bridges by nested loop: minutes, not seconds.
    await conn.execute("ANALYZE reference.reep_player_bridges")
    await conn.execute("ANALYZE reference.reep_team_bridges")


def manifest_from(directory: Path, release: str) -> Manifest:
    return Manifest(release, json.loads((directory / "manifest.json").read_text()))
