"""Transfermarkt source, through the `transfermarkt-api` SDK in-process (ADR 28)."""

import httpx

SOURCE = "transfermarkt"

# Temporal does not retry these (ADR 28): asking again cannot change the answer.
NON_RETRYABLE_ERRORS = ("NotFound", "EndpointUnavailable", "RawResponseMissingError")


def is_upstream_failure(response: httpx.Response) -> bool:
    """Responses that count against the circuit breaker: the ones the SDK raises
    `UpstreamBlocked` or `UpstreamError` for, except a 404 (`NotFound`)."""
    if response.headers.get("x-amzn-waf-action"):
        return True
    if response.status_code == 202 and not response.content:
        return True
    return response.status_code in (403, 429) or response.status_code >= 500
