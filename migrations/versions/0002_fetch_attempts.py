"""Fetch Attempts and the per-source success-rate view.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-13
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE raw.fetch_attempts (
            id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            source       text        NOT NULL,
            method       text        NOT NULL,
            url          text        NOT NULL,  -- full request URL, credentials redacted
            outcome      text        NOT NULL CHECK (outcome IN (
                             'answered', 'timeout', 'transport_error', 'circuit_open', 'reused'
                         )),
            status_code  integer,               -- of the answer, fetched or reused
            attempted_at timestamptz NOT NULL,
            CHECK ((status_code IS NOT NULL) = (outcome IN ('answered', 'reused')))
        )
        """
    )
    op.execute(
        "CREATE INDEX fetch_attempts_source_time_idx ON raw.fetch_attempts (source, attempted_at)"
    )
    # Success rate: successes over the attempts that reached the source (answered, timed out
    # or failed in transport). Circuit-open rejections and reuses never reached it.
    op.execute(
        """
        CREATE VIEW raw.source_success_rates AS
        WITH counts AS (
            SELECT
                source,
                (attempted_at AT TIME ZONE 'UTC')::date AS day,
                count(*) AS attempts,
                count(*) FILTER (WHERE outcome = 'answered' AND status_code < 400) AS success,
                count(*) FILTER (WHERE outcome = 'answered' AND status_code = 404) AS not_found,
                count(*) FILTER (
                    WHERE outcome = 'answered' AND status_code IN (403, 429)
                ) AS blocked,
                count(*) FILTER (
                    WHERE outcome = 'answered' AND status_code BETWEEN 400 AND 499
                      AND status_code NOT IN (403, 404, 429)
                ) AS other_client_error,
                count(*) FILTER (
                    WHERE outcome = 'answered' AND status_code >= 500
                ) AS server_error,
                count(*) FILTER (
                    WHERE outcome IN ('timeout', 'transport_error')
                ) AS timeout_or_transport_error,
                count(*) FILTER (WHERE outcome = 'circuit_open') AS circuit_open,
                count(*) FILTER (WHERE outcome = 'reused') AS reused,
                count(*) FILTER (
                    WHERE outcome IN ('answered', 'timeout', 'transport_error')
                ) AS reached
            FROM raw.fetch_attempts
            GROUP BY 1, 2
        )
        SELECT
            source, day, attempts, success, not_found, blocked, other_client_error,
            server_error, timeout_or_transport_error, circuit_open, reused,
            round(success::numeric / NULLIF(reached, 0), 4) AS success_rate
        FROM counts
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW raw.source_success_rates")
    op.execute("DROP TABLE raw.fetch_attempts")
