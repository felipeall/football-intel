# 28. Transfermarkt through the transfermarkt-api SDK, in-process

Status: Accepted — 2026-10-12. Refines ADR 3 (Transfermarkt via `transfermarkt-api`) and ADR 14 (access method).

## Context
`transfermarkt-api` was only an HTTP service. Calling it hides the upstream traffic: one squad request fans out to about 28 requests to Transfermarkt's JSON API (`tmapi.transfermarkt.technology`) — squad, reference data, batched players and clubs, one transfer history per player. The only response we could store was the service's assembled output, which breaks the Raw Response rule (store the untouched payload before parsing), and the source interface's rate limit and circuit breaker would wrap our own service instead of Transfermarkt.

Since 5.0.0, `transfermarkt-api` is also an async Python SDK. It accepts a caller-supplied `httpx.AsyncBaseTransport` through which every upstream request goes, can turn its caches off, raises typed exceptions, and re-assembles its output deterministically from replayed responses. Verified on 2026-10-12 against the live API: one club's squad produced 28 upstream responses through our transport, and replaying them offline gave identical output.

## Decision
- The Transfermarkt source uses the `transfermarkt-api` SDK in-process, pinned in `uv.lock`. No `transfermarkt-api` service runs in docker-compose.
- The source interface supplies the SDK's transport. That transport applies the rate limit, circuit breaker and proxy, and stores every upstream response — errors included — as a Raw Response before handing it to the SDK. The SDK runs with `cache=None`; caching of Raw Responses is ours.
- A Raw Response for Transfermarkt is one upstream JSON response, keyed by method and full URL, with its capture time in UTC.
- Re-parsing runs the SDK on a replay transport that answers from stored Raw Responses and never touches the network. A missing Raw Response is an error, not a fetch.
- Failure classification: `NotFound` is non-retryable; `UpstreamBlocked`, `UpstreamTimeout`, `UpstreamError` and the `httpx` timeout and transport errors raised by our own transport are retryable through Temporal. Our circuit-breaker error propagates through the SDK unchanged.
- The transport uses plain `httpx`, which the JSON API accepts. A `curl_cffi` impersonation transport (ADR 14) is added only if the API starts challenging requests.
- The SDK's assembled models are not Source Records. Parsing into Source Records is later work and reads the stored Raw Responses.

## Consequences
- One squad costs about 28 requests; a Premier League season of squads about 560. The per-source rate limit sets how long a full fan-out takes.
- A parser fix in the SDK reaches us as a version bump, then a replay over stored Raw Responses instead of a re-fetch.
- A replay is only complete if the SDK version makes the same requests; an SDK upgrade that adds upstream requests needs a fresh fetch for the missing ones.
