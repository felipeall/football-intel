"""Load a downloaded Reep release's player bridges into `reference` (ADR 32)."""

import json
from pathlib import Path
from typing import Any

import duckdb
from psycopg import AsyncConnection
from psycopg.types.json import Jsonb

from football_intel.reep.release import Manifest

# The player namespaces we use, per provider.
NAMESPACES = {"sofascore": "player", "transfermarkt": "spieler", "understat": "player"}

Bridge = tuple[str, str, str, str | None, str | None]  # reep_id, provider, external_id, rule, scope


def player_bridges(directory: Path) -> list[Bridge]:
    """The bridges of every person Reep maps to a Sofascore player, for our three providers,
    with each Reep ID resolved through the release's redirects to its survivor."""
    namespaces = " OR ".join(
        f"(provider = '{p}' AND namespace = '{n}')" for p, n in NAMESPACES.items()
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
                    WHERE bridges.entity_type = 'player' AND ({namespaces})
                )
                SELECT reep_id, provider, external_id, rule_id, route_scope FROM bridges
                WHERE reep_id IN (SELECT reep_id FROM bridges WHERE provider = 'sofascore')
                ORDER BY reep_id, provider, external_id
                """,
                [str(directory / "bridges.parquet"), str(directory / "redirects.parquet")],
            ).fetchall()
        ]


async def load(conn: AsyncConnection[Any], manifest: Manifest, bridges: list[Bridge]) -> None:
    """Replace a release's rows with `bridges`, in one transaction."""
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
    # Fresh statistics, or the planner joins the bridges by nested loop: minutes, not seconds.
    await conn.execute("ANALYZE reference.reep_player_bridges")


def manifest_from(directory: Path, release: str) -> Manifest:
    return Manifest(release, json.loads((directory / "manifest.json").read_text()))
