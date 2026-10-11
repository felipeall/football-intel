# 18. LLM observability: self-hosted Langfuse

Status: Accepted — 2026-10-11

## Decision
Run Langfuse as a docker-compose service. Trace every agent run (tool calls, tokens, latency, cost per query) and store eval scores alongside traces.
