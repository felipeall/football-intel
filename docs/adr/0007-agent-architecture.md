# 7. Agent architecture and model mix

Status: Accepted — 2026-10-11

## Decision
- Interactive chat path: Anthropic SDK directly, without Temporal, for low latency and streaming.
- Long-running jobs (e.g. batch Scouting Reports): Pydantic AI with its Temporal integration, so model and tool calls are durable activities.
- Model mix, configurable: Claude Haiku 5.5 for identity resolution and extraction; Claude Sonnet 5.5 for the agent and reports. Track and publish cost per query.

## Consequences
Two agent runtimes, each where it fits. Temporal streaming immaturity does not affect chat UX.
