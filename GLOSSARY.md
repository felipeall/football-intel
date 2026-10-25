# football-intel — Glossary

Football intelligence platform: durable ingestion of live football data (Temporal) into a unified database, with an AI scouting agent on top. A transfer rumor tracker is in the backlog.

Decisions are recorded in [`docs/adr/`](docs/adr/).

## Glossary

- **Source** — An external data provider the platform ingests from: Transfermarkt (via `transfermarkt-api`), Sofascore, Understat. Each source is implemented behind a common source interface.
- **Raw Response** — The untouched payload returned by a source for one request, stored before any parsing so it can be reprocessed without re-scraping.
- **Fetch Attempt** — One upstream request a source interface handled, and how it ended: answered (with a status code), timed out, failed in transport, rejected by the open circuit breaker, or answered from a fresh stored Raw Response. Unlike Raw Responses, Fetch Attempts include requests that got no answer; per-source success rates are computed from them.
- **Freshness Window** — How long a stored Raw Response answers its request instead of the source, set per source. Failure responses never answer; a forced refresh skips the window.
- **Challenge** — A source refusing requests until a human solves a captcha, rather than refusing one request. Sofascore's is a 403 whose body says `"reason": "challenge"`, or `"jwt:…"` when the Captcha Token it was sent is rejected. The Token Provider answers it with a new Captcha Token. Only when none can be obtained does the request fail as `ChallengeError`, which is not retried, and a backfill stops there.
- **Captcha Token** — The short-lived JWT Sofascore issues in exchange for a solved Turnstile captcha. It is bound to the IP and to the client that exchanged it, and is valid for about an hour. Sofascore's API only answers requests that carry it ([ADR 30](docs/adr/0030-sofascore-captcha-token.md)).
- **Token Provider** — The part of the Sofascore source that obtains Captcha Tokens. About once an hour, an anti-detect browser (camoufox) produces a Turnstile response, and `curl_cffi` exchanges it for the token its own requests carry ([ADR 30](docs/adr/0030-sofascore-captcha-token.md)).
- **Source Record** — A source's own representation of an entity (player, club, match), keyed by that source's ID.
- **Player** — The canonical, cross-source identity of a footballer. One Player links to at most one Source Record per source. Every Sofascore player is a Player; other sources link to them. A Player's ID never changes.
- **Identity Resolution** — The process of linking Source Records to a Player: the Reep Release's mappings first, then deterministic rules, fuzzy scoring, an LLM judge, and human review below a confidence threshold.
- **Identity Candidate** — A proposed link between a Source Record and a Player, with a confidence score, the method that produced it (the Reep Release, a rule, fuzzy scoring, the LLM judge or a reviewer) and a status: pending, accepted or rejected. An accepted Candidate is the link. Pending ones form the ambiguous band the LLM judge and human review decide.
- **Reep Release** — A pinned, checksum-verified release of the Reep football identity register (CC0). It maps provider IDs to one another. Identity Resolution takes its mappings first, and its own rules decide only where Reep has none ([ADR 32](docs/adr/0032-reep-first-mapping-layer.md)).
- **Transform Run** — One pass that builds dbt staging, runs Identity Resolution's automatic steps, then builds the marts. Only one runs at a time; it runs daily and on demand ([ADR 31](docs/adr/0031-identity-schema-and-transform-runs.md)).
- **Club** — A football club, canonical across sources. Each source has its own ID for it; a hand-maintained seed maps them.
- **Season** — One league season, named by its start year (2025 is 2025/26, written "25/26" by Sofascore). Understat and Transfermarkt use the start year too.
- **Match** — A single fixture, canonical across sources. Within a league Season, its home and away Club identify it.
- **Appearance** — One Player's participation in one Match, with minutes and per-match statistics.
- **Action** — A located on-ball event attributed to a player in a match (pass with start/end, dribble, ball carry, defensive action), from Sofascore's rating breakdown. No timestamps or sequence.
- **Shot** — A located shot with xG (and xGOT on Sofascore). Shots arrive from two independent sources: Sofascore and Understat.
- **Style Profile** — A per-player vector built from per-90 statistics and the spatial distribution of Actions over a season window, used for similarity search.
- **Scouting Query** — A natural-language request to the agent ("left-back under 23, under €15M, similar to X").
- **Scouting Report** — A generated, cited write-up about one player, produced by a long-running durable job.
- **Rumor** *(backlog)* — A structured claim extracted from news: player, from club, to club, fee, journalist, date. Resolved against actual transfers when the window closes.
- **Provider** — An LLM vendor or serving stack (Anthropic; later OpenAI-compatible endpoints such as OpenAI, Ollama, vLLM), implemented as an adapter behind the agent ports.
- **Runner** — A Provider's implementation of the `AgentRunner` port: the tool loop that answers a Scouting Query.
- **Model Role** — A named job an LLM does (`chat`, `report`, `identity_judge`, `eval_judge`). Configuration maps each role to a Provider and model ID.
