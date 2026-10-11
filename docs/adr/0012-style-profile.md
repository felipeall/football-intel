# 12. Style Profile: per-90 stats plus spatial grid

Status: Accepted — 2026-10-11

## Decision
A Style Profile concatenates:
- per-90 statistics, standardized within position group;
- a spatial grid: Actions binned on a 12×8 pitch grid per action type (pass start, ball carry, defensive action), normalized.

Stored in pgvector; similarity by cosine distance.

## Rejected
- Learned embedding (autoencoder): deferred until the explainable version proves weak.
- LLM text embeddings of generated descriptions: slow, opaque, lose numeric signal.

## Consequences
Similarity is explainable feature by feature, so the agent can justify matches.
