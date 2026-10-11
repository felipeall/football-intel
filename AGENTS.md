# AGENTS.md

Football data platform: Temporal ingestion from scraped sources into Postgres, dbt transforms, and a Claude scouting agent served over MCP.

## Read before working

- `CONTEXT.md` — the domain glossary. Name code, tables and tests with its terms (Player, Source Record, Raw Response, Appearance, Action, Style Profile…).
- `docs/adr/` — accepted decisions. Read the ADRs touching your area before changing it; a change that contradicts one needs a new ADR first.
- `CONVENTIONS.md` — commit, branch and pull request format. Follow it for every commit.
- `docs/agent-skills.md` — vendor skills enabled for this repo (Temporal, Pydantic, Langfuse, …). Load the matching skill before working with that technology; add new ones by its checklist.

## Rules the code does not show

- Store every source response as a Raw Response before parsing it, so parsers can be re-run without re-fetching.
- Every source goes through the common source interface, which owns rate limits, retries and the circuit breaker.
- Keep secrets in `.env` only. Strip credentials from URLs before logging or storing them.
- Scraped data lives under `data/` or in the database, both outside version control.
- Temporal workflows stay deterministic: all I/O (HTTP, database, LLM calls) runs in activities.
- The agent is provider-neutral (ADR 24): core code talks to the `AgentRunner` and `LLMClient` ports and imports provider SDKs only inside `agent/providers/<provider>/`.
- Pick models by Model Role through configuration; model IDs live in configuration only.
- A new provider is done when it passes the shared runner conformance suite.
- Chat runs the runner directly; Temporal is for ingestion and long-running jobs.
- A new domain term goes into `CONTEXT.md` in the same change.
