"""Football data platform: ingestion, transforms and a scouting agent.

This is the provider-neutral core package. Provider SDKs (`anthropic`,
`openai`, ...) are imported only inside `football_intel.agent.providers.<provider>`
(ADR 24); `import-linter` enforces it.
"""
