# football-intel — Glossary

Football intelligence platform: durable ingestion of live football data (Temporal) into a unified database, with an AI scouting agent on top. A transfer rumor tracker is in the backlog.

Decisions are recorded in [`docs/adr/`](docs/adr/).

## Glossary

- **Source** — An external data provider the platform ingests from: Transfermarkt (via `transfermarkt-api`), Sofascore, Understat. Each source is implemented behind a common source interface.
- **Raw Response** — The untouched payload returned by a source for one request, stored before any parsing so it can be reprocessed without re-scraping.
- **Fetch Attempt** — One upstream request a source interface handled, and how it ended: answered (with a status code), timed out, failed in transport, rejected by the open circuit breaker, or answered from a fresh stored Raw Response. Unlike Raw Responses, Fetch Attempts include requests that got no answer; per-source success rates are computed from them.
- **Freshness Window** — How long a stored Raw Response answers its request instead of the source, set per source. Failure responses never answer; a forced refresh skips the window.
- **Challenge** — A source refusing requests until a human solves a captcha, rather than refusing one request. Sofascore's is a 403 whose body says `"reason": "challenge"`. It lasts hours, so a challenged request is not retried and a backfill stops at the first one.
- **Captcha Token** — The short-lived JWT Sofascore issues once its Turnstile captcha is solved, bound to the solving IP and browser and valid for about an hour. The API only answers requests made with it from that browser ([ADR 30](docs/adr/0030-sofascore-browser-bridge.md)).
- **Browser Bridge** — A long-lived headless stealth browser that holds a Captcha Token, re-solves the captcha when needed, and sends a source's API requests as in-page `fetch()` calls. It is the Sofascore backend behind the common source interface ([ADR 30](docs/adr/0030-sofascore-browser-bridge.md)).
- **Source Record** — A source's own representation of an entity (player, team, match), keyed by that source's ID.
- **Player** — The canonical, cross-source identity of a footballer. One Player links to at most one Source Record per source.
- **Identity Resolution** — The process of linking Source Records to a Player: deterministic rules, then fuzzy scoring, then an LLM judge, then human review below a confidence threshold.
- **Identity Candidate** — A proposed link between a Source Record and a Player, with a confidence score and the method that produced it.
- **Match** — A single fixture, canonical across sources.
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
