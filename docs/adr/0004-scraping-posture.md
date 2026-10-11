# 4. Scraping posture: resilient, polite, no redistribution

Status: Accepted — 2026-10-11

## Decision
- Scrapers are the core of ingestion, implemented behind a common source interface.
- Polite rate limits per source; Temporal retries with backoff; a circuit breaker per source.
- Every Raw Response is cached so parsing can be re-run without re-scraping.
- No scraped data is committed or redistributed. The README carries a disclaimer.
- A per-source success-rate view is part of the demo.

## Consequences
Framed as "ingestion built for hostile sources". Source breakage is expected and surfaced, not hidden.
