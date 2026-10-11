# 9. Evaluation strategy

Status: Accepted — 2026-10-11

## Decision
- Deterministic checks for retrieval and filtering (returned player IDs must match the expected set).
- LLM-as-judge only for Scouting Report quality, used sparingly.
- Run in CI on every pull request; publish the score as a README badge.
