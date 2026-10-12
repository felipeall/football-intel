"""Fetch Attempts keep the source's failure verdict; 404s count as healthy answers.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-13
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

# Shared by both views: only the classification of answers and the rate differ.
COUNTS = """
    count(*) FILTER (WHERE outcome IN ('timeout', 'transport_error'))
        AS timeout_or_transport_error,
    count(*) FILTER (WHERE outcome = 'circuit_open') AS circuit_open,
    count(*) FILTER (WHERE outcome = 'reused') AS reused,
    count(*) FILTER (WHERE outcome IN ('answered', 'timeout', 'transport_error')) AS reached
"""


def upgrade() -> None:
    # The source's failure test, applied when the answer arrived. Null when nothing answered.
    op.execute("ALTER TABLE raw.fetch_attempts ADD COLUMN failed boolean")
    # Earlier rows: the status-code rule every source's failure test includes. Reuses are never
    # failures, since stored failures never answer.
    op.execute(
        """
        UPDATE raw.fetch_attempts
        SET failed = outcome = 'answered' AND (status_code IN (403, 429) OR status_code >= 500)
        WHERE status_code IS NOT NULL
        """
    )
    op.execute(
        "ALTER TABLE raw.fetch_attempts"
        " ADD CHECK ((failed IS NOT NULL) = (status_code IS NOT NULL))"
    )
    op.execute("DROP VIEW raw.source_success_rates")
    # Blocked: a 403/429, or any other non-5xx answer the source's failure test rejected
    # (a WAF challenge served with a 200, say). The rate counts successes and 404s — the source
    # answered, the thing does not exist — over the attempts that reached the source.
    op.execute(
        f"""
        CREATE VIEW raw.source_success_rates AS
        WITH counts AS (
            SELECT
                source,
                (attempted_at AT TIME ZONE 'UTC')::date AS day,
                count(*) AS attempts,
                count(*) FILTER (
                    WHERE outcome = 'answered' AND NOT failed AND status_code < 400
                ) AS success,
                count(*) FILTER (
                    WHERE outcome = 'answered' AND NOT failed AND status_code = 404
                ) AS not_found,
                count(*) FILTER (
                    WHERE outcome = 'answered' AND status_code < 500
                      AND (failed OR status_code IN (403, 429))
                ) AS blocked,
                count(*) FILTER (
                    WHERE outcome = 'answered' AND NOT failed
                      AND status_code BETWEEN 400 AND 499
                      AND status_code NOT IN (403, 404, 429)
                ) AS other_client_error,
                count(*) FILTER (
                    WHERE outcome = 'answered' AND status_code >= 500
                ) AS server_error,
                {COUNTS}
            FROM raw.fetch_attempts
            GROUP BY 1, 2
        )
        SELECT
            source, day, attempts, success, not_found, blocked, other_client_error,
            server_error, timeout_or_transport_error, circuit_open, reused,
            round((success + not_found)::numeric / NULLIF(reached, 0), 4) AS success_rate
        FROM counts
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW raw.source_success_rates")
    op.execute(
        f"""
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
                {COUNTS}
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
    op.execute("ALTER TABLE raw.fetch_attempts DROP COLUMN failed")
