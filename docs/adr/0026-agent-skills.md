# 26. Official agent skills, project-scoped and enabled just in time

Status: Accepted — 2026-10-12

## Context
Several vendors in the stack publish official agent skills (Temporal, Langfuse, dbt, Neon, Vercel, Pydantic, Microsoft Playwright; Anthropic bundles `claude-api` and publishes `mcp-builder`). Every enabled skill's description stays in the agent's context in every conversation, and skills can grant tool permissions or ship hooks and MCP servers.

## Decision
- **Project scope.** Plugin marketplaces and enabled plugins are declared in the committed `.claude/settings.json`, so every clone — including cloud agents — gets the same skills. Skills without a plugin marketplace are vendored under `.claude/skills/` at a reviewed commit, with their license.
- **Just in time.** Each skill is enabled at the start of the roadmap week that needs it. Week 1: Temporal, Pydantic, Langfuse.
- **Official sources only**, reviewed before enabling (`SKILL.md`, references, hooks, MCP configs, scripts). The inventory and reviewed commits live in [`docs/agent-skills.md`](../agent-skills.md).

## Consequences
The agent's context stays focused on the current week's work. Plugin marketplaces track the vendor's latest version; vendored skills are updated deliberately.
