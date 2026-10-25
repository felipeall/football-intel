"""Reep team bridges, for canonical Clubs (ADR 33).

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-25
"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # One row per bridge of a team Reep maps to a Sofascore team, its Sofascore bridge
    # included. Transfermarkt's are its `verein` IDs. Reep IDs are resolved through redirects.
    op.execute(
        """
        CREATE TABLE reference.reep_team_bridges (
            release     text NOT NULL REFERENCES reference.reep_releases ON DELETE CASCADE,
            reep_id     text NOT NULL,
            provider    text NOT NULL CHECK (
                            provider IN ('sofascore', 'transfermarkt', 'understat')
                        ),
            external_id text NOT NULL,
            PRIMARY KEY (release, provider, external_id, reep_id)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE reference.reep_team_bridges")
