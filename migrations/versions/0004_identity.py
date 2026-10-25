"""Identity tables: Players and Identity Candidates (ADR 6, ADR 31).

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-25
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA identity")
    # A Player's ID is cited by the agent, so it never changes once given.
    op.execute(
        """
        CREATE TABLE identity.players (
            player_id  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    # Every proposed link from a Source Record to a Player. An accepted Candidate is the link.
    op.execute(
        """
        CREATE TABLE identity.identity_candidates (
            candidate_id     bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            source           text        NOT NULL,
            source_record_id text        NOT NULL,  -- the source's own ID for the player
            player_id        bigint      NOT NULL REFERENCES identity.players,
            method           text        NOT NULL,
            confidence       numeric(4, 3) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
            status           text        NOT NULL CHECK (status IN (
                                 'pending', 'accepted', 'rejected'
                             )),
            evidence         jsonb       NOT NULL DEFAULT '{}',
            created_at       timestamptz NOT NULL DEFAULT now(),
            decided_at       timestamptz,
            decided_by       text,  -- the rule, the LLM judge or a reviewer
            UNIQUE (source, source_record_id, player_id)
        )
        """
    )
    # A Source Record links to one Player, and a Player to one Source Record per source.
    op.execute(
        """
        CREATE UNIQUE INDEX identity_candidates_one_link_per_record
        ON identity.identity_candidates (source, source_record_id)
        WHERE status = 'accepted'
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX identity_candidates_one_link_per_player_source
        ON identity.identity_candidates (player_id, source)
        WHERE status = 'accepted'
        """
    )


def downgrade() -> None:
    op.execute("DROP SCHEMA identity CASCADE")
