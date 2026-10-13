"""Sofascore source: its web JSON API, through browser impersonation (ADR 3, ADR 14)."""

from datetime import timedelta

import httpx

from football_intel.fetch_attempts import FetchAttemptStore
from football_intel.raw_responses import RawResponseStore
from football_intel.sources.interface import is_server_failure
from football_intel.sources.recording import RecordingTransport, ReplayTransport

SOURCE = "sofascore"

# Temporal does not retry these: asking again cannot change the answer.
NON_RETRYABLE_ERRORS = (
    "MatchNotFound",
    "MatchNotFinished",
    "SeasonNotFound",
    "RawResponseMissingError",
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
