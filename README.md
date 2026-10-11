# football-intel

> Durable football data ingestion with Temporal, and an AI scouting agent on top.

**Status:** early development (MVP week 1 of 6). See the [roadmap](docs/adr/0020-mvp-milestones.md).

## What it does

- **Ingests live football data** from Transfermarkt (via [`transfermarkt-api`](https://github.com/felipeall/transfermarkt-api)), Sofascore and Understat, using Temporal workflows built for unreliable sources: per-source rate limits, retries with backoff, circuit breakers, and a cache of every raw response.
- **Unifies players across sources** with an identity resolution workflow: deterministic rules, fuzzy matching, an LLM judge for ambiguous cases, and human review via Temporal signals.
- **Builds style profiles** from per-90 statistics and the on-pitch location of each player's actions, stored in pgvector for similarity search.
- **Answers scouting questions** through an AI agent (Claude) exposed as an MCP server: *"left-back under 23, under €15M, similar to Grimaldo"*.
- **Measures itself** with an eval suite in CI and LLM tracing in Langfuse.

Planned for phase 2: a transfer rumor tracker that grades journalists' reliability against real transfers.

## Architecture (planned)

```
Sources ─▶ Temporal workflows ─▶ Postgres (raw JSONB) ─▶ dbt (staging ▶ marts) ─▶ pgvector
                                                                                   │
                                     MCP server / Next.js chat ◀── Claude agent ◀──┘
```

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
