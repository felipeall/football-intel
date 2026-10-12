# AGENTS.md

Football data platform: Temporal ingestion from scraped sources into Postgres, dbt transforms, and a Claude scouting agent served over MCP.

## Read before working

- `GLOSSARY.md` — the domain glossary. Name code, tables and tests with its terms (Player, Source Record, Raw Response, Appearance, Action, Style Profile…).
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
- A new domain term goes into `GLOSSARY.md` in the same change.
- Langfuse runs v4 in events-only mode: read traces through the v2 Observations API (`/api/public/v2/observations`); the legacy `/api/public/traces` endpoints answer with an error.

## Pull requests

`CONVENTIONS.md` sets the branch and commit format; these are the GitHub mechanics around it.

- Open one pull request at a time, branched from `main`, and start dependent work once it has merged.
- When a pull request must build on an unmerged one, retarget it to `main` (`gh pr edit <n> --base main`) before merging its base. Squash-merging with `--delete-branch` closes every pull request still based on the deleted branch, and GitHub refuses to reopen one whose branch was force-pushed since.
- Read CI from the run on the pull request's current head commit (`gh run list --branch <branch>`); a rebase or force-push starts a new run.
- Write `Closes #N` only in pull request bodies: in a commit pushed straight to `main` it closes the issue on push, before its remaining criteria are met. After `gh issue reopen`, confirm the state with `gh issue view`.
- The repository is private on a free plan: branch protection and rulesets answer 403, so `main` has no required checks yet (#1).

## Progress

Work is tracked in GitHub Issues, one GitHub milestone per roadmap milestone (M1–M7).

- At session start: read the open issues of the current milestone (`gh issue list --milestone "<title>"`) and the latest comment on the issue you pick up.
- At session end: comment on that issue with what was done, what is next, and any blockers.
- Pull requests close their issues (`Closes #N`). When a milestone closes, update its row in the README roadmap.

## Agent skills

### Issue tracker

GitHub Issues on `felipeall/football-intel`, via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
