"""Send one trace to Langfuse and read it back.

Usage: uv run --env-file .env scripts/langfuse_smoke.py

Uses LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY and LANGFUSE_BASE_URL from the
environment, the keys that headless initialisation creates on first start.
"""

import sys
import time
from datetime import UTC, datetime, timedelta

from langfuse import get_client


def main() -> int:
    started = datetime.now(UTC) - timedelta(minutes=1)
    langfuse = get_client()
    if not langfuse.auth_check():
        print("Langfuse rejected the API keys; check .env and the langfuse-web service.")
        return 1

    with langfuse.start_as_current_observation(
        as_type="span", name="langfuse-smoke", input={"check": "compose stack"}
    ) as span:
        span.update(output={"status": "ok"})
        trace_id = langfuse.get_current_trace_id()
    langfuse.flush()
    assert trace_id is not None

    # Ingestion is asynchronous: the worker writes the trace to ClickHouse.
    # Langfuse v4 reads go through the v2 Observations API.
    for _ in range(30):
        observations = langfuse.api.observations.get_many(
            trace_id=trace_id, from_start_time=started
        )
        if observations.data:
            print(f"Trace {trace_id} stored: {langfuse.get_trace_url(trace_id=trace_id)}")
            return 0
        time.sleep(1)

    print(f"Trace {trace_id} was sent but did not appear within 30 seconds.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
