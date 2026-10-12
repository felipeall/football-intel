"""`httpx` transports that store and replay a source's Raw Responses (ADR 4, ADR 28).

`RecordingTransport` stores each response as a Raw Response before the caller sees it, and
answers from a fresh stored one instead when it can; `ReplayTransport` answers from stored
Raw Responses and never touches the network. Both are source-neutral: each source passes its
name, and the recording transport its failure test.
"""

import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import httpx

from football_intel.raw_responses import RawResponse, RawResponseStore
from football_intel.sources.urls import redact_url

logger = logging.getLogger(__name__)

# The response extension that carries a Raw Response's capture time, unless a source's SDK
# reads it under its own key.
CAPTURED_AT = "raw_response_captured_at"
# Stored bodies are decoded; content-encoding/length would make httpx decode them twice.
# Cookies are session state, not data, and may carry credentials.
DROPPED_HEADERS = frozenset({"content-encoding", "content-length", "set-cookie"})


class RawResponseMissingError(Exception):
    """Replay found no Raw Response for a request; replay never falls back to a fetch."""


class RecordingTransport(httpx.AsyncBaseTransport):
    """Forward to `backend`, store the response as a Raw Response of `source`, then return it.

    With a `freshness` window, a stored Raw Response captured within it answers the request
    and `backend` is not called (ADR 4: parse again without scraping again). Stored responses
    that `is_failure` rejects never answer: the source is asked again.
    """

    def __init__(
        self,
        backend: httpx.AsyncBaseTransport,
        store: RawResponseStore,
        source: str,
        is_failure: Callable[[httpx.Response], bool],
        freshness: timedelta | None = None,
        captured_at_extension: str = CAPTURED_AT,
    ) -> None:
        self._backend = backend
        self._store = store
        self._source = source
        self._is_failure = is_failure
        self._freshness = freshness
        self._captured_at_extension = captured_at_extension
        self.recorded = 0
        self.reused = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        cached = await self._fresh(request)
        if cached is not None:
            self.reused += 1
            logger.info(
                "Reused Raw Response %s %s from %s", cached.method, cached.url, cached.captured_at
            )
            return _to_response(cached, self._captured_at_extension)
        response = await self._backend.handle_async_request(request)
        try:
            body = await response.aread()
        finally:
            await response.aclose()
        raw = RawResponse(
            source=self._source,
            method=request.method,
            url=redact_url(request.url),
            status_code=response.status_code,
            headers=tuple(
                (key, value)
                for key, value in response.headers.multi_items()
                if key.lower() not in DROPPED_HEADERS
            ),
            body=body,
            captured_at=datetime.now(UTC),
        )
        await self._store.save(raw)
        self.recorded += 1
        logger.info("Stored Raw Response %s %s -> %d", raw.method, raw.url, raw.status_code)
        return _to_response(raw, self._captured_at_extension)

    async def aclose(self) -> None:
        await self._backend.aclose()

    async def _fresh(self, request: httpx.Request) -> RawResponse | None:
        if not self._freshness:
            return None
        since = datetime.now(UTC) - self._freshness
        raw = await self._store.latest(self._source, request.method, redact_url(request.url), since)
        if raw is None or self._is_failure(_to_response(raw, self._captured_at_extension)):
            return None
        return raw


class ReplayTransport(httpx.AsyncBaseTransport):
    """Answer from the latest stored Raw Response of `source` for each request."""

    def __init__(
        self, store: RawResponseStore, source: str, captured_at_extension: str = CAPTURED_AT
    ) -> None:
        self._store = store
        self._source = source
        self._captured_at_extension = captured_at_extension

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        url = redact_url(request.url)
        raw = await self._store.latest(self._source, request.method, url)
        if raw is None:
            raise RawResponseMissingError(f"No Raw Response for {request.method} {url}")
        return _to_response(raw, self._captured_at_extension)


def _to_response(raw: RawResponse, captured_at_extension: str) -> httpx.Response:
    return httpx.Response(
        raw.status_code,
        headers=list(raw.headers),
        content=raw.body,
        extensions={captured_at_extension: raw.captured_at},
    )
