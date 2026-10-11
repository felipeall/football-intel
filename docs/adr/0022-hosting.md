# 22. PoC runs locally; MVP is hosted behind GitHub login

Status: Accepted — 2026-10-12. Supersedes ADR 10. Amends ADR 18.

## Context
A clickable link is a stronger portfolio artifact than a recorded video. Constraints: Sofascore answers from a residential IP but datacenter IP ranges are reportedly blocked; serving scraped data publicly is redistribution (ADR 4); open LLM endpoints invite cost abuse.

## Decision
- **No demo video.**
- **PoC** (weeks 1–4) runs locally with `docker compose up`.
- **MVP** (weeks 5–7) is hosted, using a hybrid model:
  - Temporal, workers and scrapers stay on the developer's machine and write to a managed Postgres.
  - Hosted: Neon Postgres with pgvector; FastAPI agent API on Fly.io; Next.js UI on Vercel.
  - The hosted app has read-only access to the marts schema and serves derived outputs (agent answers, similarity, charts).
- **Access:** GitHub login via Auth.js; quota of 10 queries per user per day.
- **Cost guard:** monthly spend limit in the Anthropic console.
- **Observability:** Langfuse Cloud (free tier) for hosted traffic; self-hosted Langfuse stays for local development.

## Consequences
Hosted data refreshes only while the developer's machine runs ingestion. Moving ingestion to a server (with proxies) would need a new ADR.
