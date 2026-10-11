# 6. Player identity resolution

Status: Accepted — 2026-10-11

## Decision
Resolution pipeline, run as a Temporal workflow:
1. Deterministic rules (normalized name + birth date + nationality/club).
2. Fuzzy scoring for the remainder.
3. LLM judge (small model) for the ambiguous band, as a retryable activity.
4. Human review below a confidence threshold, delivered as a Temporal signal (approve/reject).

Every link is stored as an Identity Candidate with its confidence and method.

## Consequences
Showcases durable workflows, AI and human-in-the-loop in one feature. Understat has no birth date, so it relies more on steps 2–4.
