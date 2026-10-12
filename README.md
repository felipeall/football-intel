# football-intel

> Durable football data ingestion with Temporal, and an AI scouting agent on top.

**Status:** early development — local proof of concept, milestone M2 of 7. A hosted MVP behind GitHub login follows. See the [roadmap](#roadmap).

## What it does

- **Ingests live football data** from Transfermarkt (via [`transfermarkt-api`](https://github.com/felipeall/transfermarkt-api)), Sofascore and Understat, using Temporal workflows built for unreliable sources: per-source rate limits, retries with backoff, circuit breakers, and a cache of every raw response.
- **Unifies players across sources** with an identity resolution workflow: deterministic rules, fuzzy matching, an LLM judge for ambiguous cases, and human review via Temporal signals.
- **Builds style profiles** from per-90 statistics and the on-pitch location of each player's actions, stored in pgvector for similarity search.
- **Answers scouting questions** through a provider-neutral AI agent (Claude first) exposed as an MCP server: *"left-back under 23, under €15M, similar to Grimaldo"*.
- **Measures itself** with an eval suite in CI and LLM tracing in Langfuse.

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

## Tech stack

ADR numbers refer to [`docs/adr/`](docs/adr/).

| Layer | Technology | Runs on | Phase | ADR |
|---|---|---|---|---|
| Language & tooling | Python 3.13, `uv`, `ruff`, `pyright`, `pytest`, `import-linter`, `gitleaks` | local + CI | PoC | 15, 24 |
| Orchestration | Temporal: Schedules, post-match workflows, durable timers, signals | local | PoC | 5, 6 |
| Source: Transfermarkt | [`transfermarkt-api`](https://github.com/felipeall/transfermarkt-api) SDK, in-process | local | PoC | 2, 3, 28 |
| Source: Sofascore | `curl_cffi` browser impersonation, Playwright fallback | local (residential IP) | PoC | 3, 14 |
| Source: Understat | HTTP | local | PoC | 3 |
| Ingestion resilience | Per-source rate limits, retries with backoff, circuit breaker, raw response cache | local | PoC | 4 |
| Database | Postgres 17 + pgvector (raw JSONB → staging → marts) | local (Docker) | PoC | 11 |
| Transforms | dbt (Postgres adapter), run as a Temporal activity | local | PoC | 11 |
| Identity resolution | Rules → fuzzy matching → LLM judge (Claude Haiku 5.5) → human review via Temporal signal | local | PoC | 6 |
| Style profiles | Per-90 stats + 12×8 pitch grid, cosine similarity in pgvector | local | PoC | 12 |
| Agent harness | `AgentRunner` / `LLMClient` ports; `ClaudeRunner` (Anthropic SDK Tool Runner); `ScriptedRunner` test double | local + hosted | PoC | 24 |
| LLM | Anthropic API (backend configurable); Claude Sonnet 5.5 for chat, reports and eval judge; Claude Haiku 5.5 for identity resolution | API | PoC | 24, 25 |
| Agent tools | Typed tools + read-only SQL fallback on marts | local + hosted | PoC | 13 |
| MCP | MCP server over the same tools (Claude Desktop, Claude Code) | local | PoC | 8 |
| Observability | Langfuse — self-hosted locally, Langfuse Cloud for hosted traffic | local / cloud | PoC / MVP | 18, 22 |
| Evals | Deterministic checks + LLM judge in GitHub Actions, README badge | CI | MVP | 9 |
| Long-running jobs | Temporal workflow, one Scouting Report per activity | local | MVP | 24 |
| API | FastAPI | Fly.io | MVP | 22 |
| UI | Next.js chat with inline charts | Vercel | MVP | 8, 22 |
| Auth & limits | GitHub login (Auth.js), 10 queries per user per day, Anthropic console spend limit | hosted | MVP | 22 |
| Hosted database | Neon Postgres + pgvector (read-only for the app; local workers write) | cloud | MVP | 22 |
| CI/CD | GitHub Actions: lint, types, tests, import contracts, evals | GitHub | PoC → MVP | 15 |

## Roadmap

Seven milestones in order, no deadlines ([ADR 27](docs/adr/0027-milestones-without-timing.md)). Work items live in [GitHub milestones](https://github.com/felipeall/football-intel/milestones).

| Milestone | Phase | Delivery | Status |
|---|---|---|---|
| M1 | PoC | Compose stack, source interface, Transfermarkt, raw response cache, CI | ✅ |
| M2 | PoC | Sofascore, post-match workflows, three-season backfill | 🚧 |
| M3 | PoC | Understat, dbt, identity resolution | ⏳ |
| M4 | PoC | Style profiles, agent tools, `ClaudeRunner` + `ScriptedRunner`, MCP server — Claude Desktop answers locally | ⏳ |
| M5 | MVP | Evals in CI, durable scouting report job | ⏳ |
| M6 | MVP | Next.js UI, FastAPI, GitHub login, quota | ⏳ |
| M7 | MVP | Deploy (Neon, Fly.io, Vercel); local workers sync to Neon | ⏳ |

**Backlog:** `LiteLLMRunner` (OpenAI, Gemini, Bedrock, Ollama, vLLM) and provider comparison evals, LiteLLM gateway, transfer rumor tracker, Opta feeds, WhoScored events, learned style embeddings, more leagues.

## Run locally

Requires Docker with Compose.

```sh
cp .env.example .env       # then replace the placeholder values
docker compose up --wait   # Temporal, Postgres 17 + pgvector, Langfuse
```

- Temporal gRPC on `localhost:7233`, web UI at <http://localhost:8233>.
- Postgres on `localhost:5432`; data lives in the `postgres-data` volume and survives `docker compose down`. `docker compose down -v` deletes it.
- The Temporal dev server keeps its state in memory: workflow history is lost on restart.
- Langfuse UI at <http://localhost:3000>. The first start creates the `football-intel` organisation, project and API keys, and a user from the `LANGFUSE_INIT_USER_*` variables. Check tracing with `uv run --env-file .env scripts/langfuse_smoke.py`.
- A `migrate` service applies the database migrations ([ADR 29](docs/adr/0029-migrations-alembic.md)); the `worker` service then runs the ingestion workflows.

Store one club's squad for one season as Raw Responses (club `985` is Manchester United on Transfermarkt):

```sh
uv run football-intel ingest-squad 985 --season 2025
```

Store every Premier League club's squad for a season (`--competition` takes another Transfermarkt competition ID):

```sh
uv run football-intel ingest-competition --season 2025
```

That is about 560 upstream requests, so at the default rate limit of one request per second it takes roughly ten minutes. Clubs run as child workflows, three at a time (`--concurrency`); a club that fails is listed at the end without stopping the others. Within the freshness window (24 hours by default) a re-run reuses stored Raw Responses instead of fetching again; `--refresh` fetches anyway. Rate limit, circuit breaker, freshness and proxy are set per source in `.env` (see `.env.example`).

The runs show in the Temporal UI as `squad-985-2025` and `competition-squads-GB1-2025`. Every upstream response lands in `raw.raw_responses`, untouched, before anything parses it. Scraped data stays in the database or under `data/`, never in this repository (see the [data disclaimer](#data-disclaimer)).

Every upstream request also leaves one Fetch Attempt in `raw.fetch_attempts`, including timeouts, transport errors, circuit-breaker rejections and reuses of a fresh Raw Response. Print each source's outcomes and success rate per day (UTC) for the last seven days, or for a range with `--from` and `--to`:

```sh
uv run football-intel success-rates --from 2026-10-01 --to 2026-10-13
```

The success rate shows breakage: successful answers and 404s (the source answered; the thing does not exist) over the attempts that reached the source. Circuit-breaker rejections and reuses never reached it, so they are counted but left out of the rate. An answer counts as blocked when it is a 403 or 429, or when the source's own failure test rejects it, such as Transfermarkt's WAF challenge served with a 200. The same numbers are in the `raw.source_success_rates` view.

## Development

Requires [`uv`](https://docs.astral.sh/uv/).

```sh
uv sync                    # Python 3.13 and dev tools
uv run pytest              # tests; database tests need the compose Postgres
uv run ruff check && uv run ruff format --check
uv run pyright
uv run lint-imports        # provider SDKs only inside agent/providers/<provider>/ (ADR 24)
```

## Documentation

- [`GLOSSARY.md`](GLOSSARY.md) — domain glossary
- [`docs/adr/`](docs/adr/) — architecture decision records
- [`CONVENTIONS.md`](CONVENTIONS.md) — commits, branches, pull requests
- [`docs/agent-skills.md`](docs/agent-skills.md) — official agent skills enabled for coding agents

## Data disclaimer

This project collects data from third-party websites for personal, non-commercial research. No scraped data is stored in or distributed through this repository. If you run it, you are responsible for complying with each source's terms of service.

## Prior work

This project supersedes [`football-data-platform`](https://github.com/felipeall/football-data-platform) (v1).

## License

[MIT](LICENSE)
