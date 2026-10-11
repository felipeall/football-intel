# 24. Provider-neutral agent: Claude Tool Runner behind an AgentRunner port

Status: Accepted — 2026-10-12. Supersedes ADR 7.

## Context
ADR 7 planned two agent runtimes (Anthropic SDK for chat, Pydantic AI on Temporal for long jobs): two tool loops, two tool definitions, evals covering only one. Options weighed:

- **Pydantic AI** — multi-provider, native Temporal integration; risk of lagging 2026 Claude API changes (forced `tool_choice` rejected on Sonnet 5.5, preserved thinking requiring append-only history, task budgets, server-side fallbacks).
- **Claude Agent SDK** — the Claude Code harness as a library; its built-in file and shell tools do not serve a typed-tool agent, and per-session hosting is heavy.
- **LangGraph / LangChain** — graph state, checkpointing and human-in-the-loop overlap with Temporal; the agent is a single tool loop, not a graph; same wrapper lag risk.
- **Anthropic Tool Runner** — official SDK, newest features first, Claude only.

## Decision
One agent harness, with the provider behind ports.

**Ports** (provider-neutral interfaces, in the core package):
- `AgentRunner` — runs the tool loop for a conversation: streaming events, turn and token limits, tool execution, usage and cost reporting.
- `LLMClient` — a single structured call (identity resolution judge, eval judge).

**Implementations:**
- MVP: `ClaudeRunner` and `ClaudeClient`, built on the Anthropic SDK Tool Runner.
- Test double (week 4): `ScriptedRunner`, which replays scripted tool calls and answers. It runs the conformance suite alongside `ClaudeRunner`, proving the port does not depend on Claude-only behaviour, and lets agent tests run in CI without tokens.
- Backlog: `LiteLLMRunner` / `LiteLLMClient` on the LiteLLM SDK, covering OpenAI, Gemini, Bedrock, Mistral and open-source models (Ollama, vLLM). Triggers: a provider comparison in the README, a fallback during Claude outages, local development without tokens, or a target employer's stack. Pin the exact version with hashes (`uv.lock`) and upgrade deliberately: LiteLLM 1.82.7 and 1.82.8 shipped credential-stealing malware on PyPI on 2026-03-24.
- LiteLLM stays off the Claude path: translating to OpenAI format loses thinking blocks, fine-grained caching, server-side fallbacks and task budgets.
- Backlog: LiteLLM proxy as a gateway, only if several providers serve hosted traffic.

**Modularity rules:**
- Tools are plain domain functions with Pydantic input/output models, defined once. Each provider adapter converts them to its own tool format; the MCP server wraps the same functions.
- Provider SDKs (`anthropic`, `openai`, …) are imported only inside `agent/providers/<provider>/`. Enforced in CI with `import-linter`.
- Providers register by name. Configuration maps each **Model Role** (`chat`, `report`, `identity_judge`, `eval_judge`) to a provider and model ID, so switching a role is a configuration change, not a code change.
- Messages, tool calls, stream events and usage use the core's own types; adapters translate at the boundary. Provider-specific features (e.g. Claude thinking blocks) are carried as opaque adapter state, so history stays append-only.
- A shared conformance test suite runs against every registered runner; a new provider is done when it passes.
- Evals take the runner as a parameter, so the same suite compares providers.

**Execution:**
- Chat runs the runner directly, streaming, without Temporal.
- Long jobs: a Temporal workflow where each Scouting Report is one activity running the runner. A crash retries that report from the start.

**Model roles in the MVP:** `chat` and `report` on Claude Sonnet 5.5; `identity_judge` on Claude Haiku 5.5; `eval_judge` on Claude Sonnet 5.5.

## Consequences
- Claude features are available on day one; durability is per report, not per model call.
- Adding a provider is one package plus a configuration entry, verified by the conformance suite.
- Once a second runner exists, evals produce a provider comparison (quality, cost, latency per question).
