"""Sofascore source: its web JSON API, through browser impersonation (ADR 3, ADR 14)."""

from datetime import timedelta

import httpx
from pydantic import Field

from football_intel.fetch_attempts import FetchAttemptStore
from football_intel.raw_responses import RawResponseStore
from football_intel.sources.interface import SourcePolicy, is_server_failure
from football_intel.sources.recording import RecordingTransport, ReplayTransport

SOURCE = "sofascore"


class SofascorePolicy(SourcePolicy):
    """Sofascore's defaults, from the #21 backfill. A sustained 1 request per second drew a
    403 bot challenge (`"reason": "challenge"`) within minutes, so: half that rate, and a
    15-minute circuit-breaker cool-down for other failures. A challenge itself is not retried
    (`ChallengeError`). Defaults on a subclass, so overriding one field from the environment
    keeps the others."""

    requests_per_second: float = Field(default=0.5, gt=0)
    breaker_cooldown_seconds: float = Field(default=900.0, gt=0)


# Temporal does not retry these: asking again cannot change the answer.
NON_RETRYABLE_ERRORS = (
    "MatchNotFound",
    "MatchNotFinished",
    "SeasonNotFound",
    "RawResponseMissingError",
    # The challenge lasts hours: retries would only spend attempts against it.
    "ChallengeError",
)


def recording_transport(
    backend: httpx.AsyncBaseTransport,
    store: RawResponseStore,
    attempts: FetchAttemptStore,
    freshness: timedelta | None = None,
) -> RecordingTransport:
    """A transport that stores every Sofascore response as a Raw Response and every request
    as a Fetch Attempt."""
    return RecordingTransport(backend, store, attempts, SOURCE, is_server_failure, freshness)


def replay_transport(store: RawResponseStore) -> ReplayTransport:
    """A transport that answers from stored Sofascore Raw Responses."""
    return ReplayTransport(store, SOURCE)
