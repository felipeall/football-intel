# 25. Claude backend: Anthropic API, configurable per deployment

Status: Accepted — 2026-10-12

## Context
Claude is reachable through the first-party Anthropic API, Claude Platform on AWS (Anthropic-operated, same-day feature parity, AWS billing), and Amazon Bedrock (partner-operated, separate pricing). Bedrock lacks features this project uses or plans to use: task budgets, server-side refusal fallbacks, Message Batches (batch Scouting Reports and the eval judge at 50% cost), the Models API and cache diagnostics. It also needs an AWS account, IAM and model-access setup, and AWS credentials on Fly.io.

## Decision
- Use the first-party Anthropic API.
- `ClaudeRunner` and `ClaudeClient` take the backend from configuration: `anthropic` (default), `claude_platform_aws`, `bedrock`. Each maps to the Anthropic SDK's dedicated client for that platform; the core is unaffected.
- Features unavailable on a backend are capability-flagged in the adapter and degrade gracefully (e.g. no task budget on Bedrock).

## Consequences
One API key and the Anthropic console spend limit (ADR 22) cover the MVP. Moving to AWS billing later is a configuration change, preferably to Claude Platform on AWS for feature parity.
