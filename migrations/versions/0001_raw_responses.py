"""Raw Responses: untouched source payloads in the raw schema.

Revision ID: 0001
Revises:
Create Date: 2026-10-12
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA raw")
    op.execute(
        """
        CREATE TABLE raw.raw_responses (
            id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            source      text        NOT NULL,
            method      text        NOT NULL,
            url         text        NOT NULL,  -- full request URL, credentials redacted
            status_code integer     NOT NULL,
            headers     jsonb       NOT NULL,  -- [[name, value], ...] as received
            body        bytea       NOT NULL,  -- decoded body, byte for byte
            body_json   jsonb,                 -- body parsed as JSON, when it is JSON
            captured_at timestamptz NOT NULL
        )
        """
    )
    op.execute(
        "CREATE INDEX raw_responses_request_idx"
        " ON raw.raw_responses (source, method, url, captured_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE raw.raw_responses")
    op.execute("DROP SCHEMA raw")
