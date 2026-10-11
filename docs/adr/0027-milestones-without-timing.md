# 27. Milestones in sequence, without timing

Status: Accepted — 2026-10-12. Supersedes ADR 23. Amends ADR 1 (drops the hours-per-week budget).

## Decision
The roadmap is an ordered list of milestones with done-when criteria — no weeks, due dates or hour budgets. Milestone content is unchanged from ADR 23; its "week N" maps to "M*N*":

**PoC — local**
- **M1 — Foundation:** compose stack (Temporal, Postgres/pgvector, Langfuse); source interface; Transfermarkt source; Raw Response cache; CI.
- **M2 — Sofascore & match workflows:** Sofascore source; post-match workflows; Premier League backfill, three seasons.
- **M3 — Understat, dbt & identity:** Understat source; dbt staging and marts; identity resolution workflow.
- **M4 — Style profiles & agent:** Style Profiles; typed agent tools; `ClaudeRunner` + `ScriptedRunner`; MCP server.

**MVP — hosted**
- **M5 — Evals & reports:** eval suite in CI; durable Scouting Report job.
- **M6 — Web app:** Next.js UI; FastAPI agent API; GitHub login; per-user quota.
- **M7 — Hosted MVP:** deploy (Neon, Fly.io, Vercel, Langfuse Cloud); local workers sync to Neon.

Each milestone is a GitHub milestone without a due date. References to "week N" in earlier ADRs mean milestone M*N*.

## Consequences
Scope control comes from the done-when criteria and the cut order (the Scouting Report job before the hosted UI), not from a calendar.
