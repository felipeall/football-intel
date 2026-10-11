# 7. Agent architecture and model mix

Status: Superseded by ADR 24 — 2026-10-12

## Decision
- Interactive chat path: Anthropic SDK directly, without Temporal, for low latency and streaming.
- Long-running jobs (e.g. batch Scouting Reports): Pydantic AI with its Temporal integration, so model and tool calls are durable activities.
- Model mix, configurable: Claude Haiku 5.5 for identity resolution and extraction; Claude Sonnet 5.5 for the agent and reports. Track and publish cost per query.

## Consequences
Two agent runtimes, each where it fits. Temporal streaming immaturity does not affect chat UX.
