# 20. MVP milestones

Status: Accepted — 2026-10-11

## Decision
Six weeks at ~8 hours/week:
1. Compose stack (Temporal, Postgres/pgvector, Langfuse); source interface; Transfermarkt source; Raw Response cache.
2. Sofascore source; post-match workflows; backfill Premier League, three seasons.
3. Understat source; dbt staging and marts; identity resolution workflow.
4. Style Profiles; typed agent tools; MCP server.
5. Eval suite in CI; durable Scouting Report job.
6. Thin Next.js UI; README; ADR index; demo video.

If behind schedule, the Next.js UI is cut first — the MCP server demo stands on its own.
