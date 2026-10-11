# 23. Milestones: local PoC, hosted MVP

Status: Accepted — 2026-10-12. Supersedes ADR 20.

## Decision
Seven weeks at ~8 hours/week.

**PoC — local**
1. Compose stack (Temporal, Postgres/pgvector, Langfuse); source interface; Transfermarkt source; Raw Response cache; CI.
2. Sofascore source; post-match workflows; backfill Premier League, three seasons.
3. Understat source; dbt staging and marts; identity resolution workflow.
4. Style Profiles; typed agent tools; MCP server. PoC done: Claude Desktop answers Scouting Queries against local data.

**MVP — hosted**
5. Eval suite in CI; durable Scouting Report job.
6. Next.js UI; FastAPI agent API; GitHub login; per-user quota.
7. Deploy (Neon, Fly.io, Vercel, Langfuse Cloud); local workers sync to Neon; README with architecture diagram.

If behind schedule, cut the Scouting Report job before the hosted UI — the link is the portfolio artifact.
