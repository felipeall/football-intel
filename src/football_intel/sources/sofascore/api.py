"""Sofascore's web JSON API: base URL, client and the error every request can raise."""

import httpx

BASE_URL = "https://www.sofascore.com/api/v1"
TIMEOUT_SECONDS = 30.0


class UpstreamError(Exception):
    """Sofascore refused or failed a request (403, 429, 5xx…). Retryable."""

    def __init__(self, url: httpx.URL, status_code: int) -> None:
        super().__init__(f"Sofascore answered {status_code} for {url.path}")
        self.status_code = status_code


def client(transport: httpx.AsyncBaseTransport) -> httpx.AsyncClient:
    """A client for Sofascore's API; every request goes through `transport`."""
    return httpx.AsyncClient(transport=transport, base_url=BASE_URL, timeout=TIMEOUT_SECONDS)


def raise_for_failure(response: httpx.Response) -> None:
    """Raise `UpstreamError` for any error status except 404, which callers interpret."""
    if response.is_error and response.status_code != 404:
        raise UpstreamError(response.request.url, response.status_code)
