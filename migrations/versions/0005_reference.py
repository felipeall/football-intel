"""Reference data: Reep releases and their player bridges (ADR 32).

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-25
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA reference")
    op.execute(
        """
        CREATE TABLE reference.reep_releases (
            release     text        PRIMARY KEY,  -- the release stamp, e.g. 2026-10-25.1
            gate_passed boolean,                  -- the release's own quality gate
            manifest    jsonb       NOT NULL,     -- as published, checksums and diff included
            loaded_at   timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    # One row per bridge of a person Reep maps to a Sofascore player, its Sofascore bridge
    # included. Reep IDs are already resolved through the release's redirects.
    op.execute(
        """
        CREATE TABLE reference.reep_player_bridges (
            release     text NOT NULL REFERENCES reference.reep_releases ON DELETE CASCADE,
            reep_id     text NOT NULL,
            provider    text NOT NULL CHECK (
                            provider IN ('sofascore', 'transfermarkt', 'understat')
                        ),
            external_id text NOT NULL,
            rule_id     text,
            route_scope text,
            PRIMARY KEY (release, provider, external_id, reep_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX reep_player_bridges_person_idx"
        " ON reference.reep_player_bridges (release, reep_id)"
    )


def downgrade() -> None:
    op.execute("DROP SCHEMA reference CASCADE")
