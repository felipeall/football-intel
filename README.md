# football-intel

> Durable football data ingestion with Temporal, and an AI scouting agent on top.

**Status:** early development — local proof of concept, week 1 of 7. A hosted MVP behind GitHub login follows. See the [roadmap](docs/adr/0023-milestones-v2.md).

## What it does

- **Ingests live football data** from Transfermarkt (via [`transfermarkt-api`](https://github.com/felipeall/transfermarkt-api)), Sofascore and Understat, using Temporal workflows built for unreliable sources: per-source rate limits, retries with backoff, circuit breakers, and a cache of every raw response.
- **Unifies players across sources** with an identity resolution workflow: deterministic rules, fuzzy matching, an LLM judge for ambiguous cases, and human review via Temporal signals.
- **Builds style profiles** from per-90 statistics and the on-pitch location of each player's actions, stored in pgvector for similarity search.
- **Answers scouting questions** through an AI agent (Claude) exposed as an MCP server: *"left-back under 23, under €15M, similar to Grimaldo"*.
- **Measures itself** with an eval suite in CI and LLM tracing in Langfuse.

Planned for phase 2: a transfer rumor tracker that grades journalists' reliability against real transfers.

## Architecture (planned)

```
 Developer machine                                  Hosted (MVP)
┌──────────────────────────────────────┐     ┌──────────────────────────────────────┐
│ Sources ─▶ Temporal workflows        │     │ Neon Postgres (marts, pgvector)      │
│              │                       │     │   ▲ read-only                        │
│              ▼                       │     │   │                                  │
│ Postgres (raw JSONB) ─▶ dbt ─────────┼────▶│ FastAPI + Claude agent (Fly.io)      │
│                                      │     │   ▲                                  │
│ MCP server (local PoC)               │     │ Next.js chat, GitHub login (Vercel)  │
└──────────────────────────────────────┘     └──────────────────────────────────────┘
```

Ingestion stays on a residential connection, where the sources answer; the hosted app serves derived outputs only ([ADR 22](docs/adr/0022-hosting.md)).

## Documentation

- [`CONTEXT.md`](CONTEXT.md) — domain glossary
- [`docs/adr/`](docs/adr/) — architecture decision records
- [`CONVENTIONS.md`](CONVENTIONS.md) — commits, branches, pull requests

## Data disclaimer

This project collects data from third-party websites for personal, non-commercial research. No scraped data is stored in or distributed through this repository. If you run it, you are responsible for complying with each source's terms of service.

## Prior work

This project supersedes [`football-data-platform`](https://github.com/felipeall/football-data-platform) (v1).

## License

[MIT](LICENSE)
